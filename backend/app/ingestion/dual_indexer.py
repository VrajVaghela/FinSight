"""
FinSight AI — DualIndexer
Writes chunks to BOTH:
  1. Qdrant (dense vector search) — using Gemini text-embedding-004
  2. BM25 (sparse keyword search) — using rank_bm25, persisted per project_id

Also handles:
  - Qdrant collection creation with payload indexes
  - Re-ingestion (delete old points for a file_id before re-indexing)
  - BM25 index rebuild when files change
"""
import os
import json
import pickle
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict


class DualIndexer:
    """
    Simultaneously writes chunks to Qdrant (dense vectors) and BM25 (sparse index).
    
    Qdrant Collection: document_chunks
      - Vector: 3072 dimensions (Gemini gemini-embedding-001), Cosine distance
      - Payload: All FinalChunk fields
      - Payload Indexes: project_id (keyword), file_id (keyword), is_table (bool)
    
    BM25 Index: /data/bm25_indexes/{project_id}.pkl
      - Serialized dict with BM25Okapi index, chunk_ids list, raw_texts list
    """

    COLLECTION_NAME = "document_chunks"
    VECTOR_DIM = 384  # all-MiniLM-L6-v2 output dimension
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Local model, no API needed

    def __init__(self):
        self._qdrant_client = None
        self._embed_model = None
        self._bm25_dir = os.getenv("BM25_INDEX_DIR", "./data/bm25_indexes")
        os.makedirs(self._bm25_dir, exist_ok=True)

    def _get_qdrant(self):
        """Lazy-load Qdrant client."""
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient
            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", "6333"))
            self._qdrant_client = QdrantClient(
                host=host,
                port=port,
                check_compatibility=False,
            )
            print(f"[DualIndexer] Connected to Qdrant at {host}:{port}")
        return self._qdrant_client

    _global_embed_model = None

    def _get_embed_model(self):
        """Lazy-load local sentence-transformers model. No API key needed."""
        if DualIndexer._global_embed_model is None:
            import os
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            from sentence_transformers import SentenceTransformer
            print(f"[DualIndexer] Loading local embedding model: {self.EMBEDDING_MODEL}...")
            DualIndexer._global_embed_model = SentenceTransformer(self.EMBEDDING_MODEL)
            print(f"[DualIndexer] Local embeddings ready (dim={self.VECTOR_DIM})")
        return DualIndexer._global_embed_model

    def _collection_vector_size(self, collection_info) -> Optional[int]:
        """Return the configured vector size for unnamed or first named vectors."""
        config = getattr(collection_info, "config", None)
        params = getattr(config, "params", None)
        vectors = getattr(params, "vectors", None)

        if isinstance(vectors, dict):
            size = vectors.get("size")
            if size is not None:
                return int(size)
            for vector in vectors.values():
                size = getattr(vector, "size", None)
                if size is None and isinstance(vector, dict):
                    size = vector.get("size")
                if size is not None:
                    return int(size)
            return None

        size = getattr(vectors, "size", None)
        return int(size) if size is not None else None

    def ensure_collection(self):
        """
        Create the Qdrant collection if it doesn't exist.
        Set up payload indexes for project_id, file_id, is_table.
        """
        from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

        client = self._get_qdrant()
        collections = [c.name for c in client.get_collections().collections]

        if self.COLLECTION_NAME not in collections:
            client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_DIM,
                    distance=Distance.COSINE,
                ),
            )
            print(f"[DualIndexer] Created Qdrant collection: {self.COLLECTION_NAME}")

            # Create payload indexes for fast filtered search
            client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="project_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="file_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="is_table",
                field_schema=PayloadSchemaType.BOOL,
            )
            client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="chunk_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print("[DualIndexer] Payload indexes created (project_id, file_id, is_table, chunk_id)")
        else:
            info = client.get_collection(collection_name=self.COLLECTION_NAME)
            existing_size = self._collection_vector_size(info)
            if existing_size and existing_size != self.VECTOR_DIM:
                raise RuntimeError(
                    f"Qdrant collection '{self.COLLECTION_NAME}' has vector size "
                    f"{existing_size}, but {self.EMBEDDING_MODEL} is configured for "
                    f"{self.VECTOR_DIM}. Re-ingest into a new collection name or "
                    "recreate the collection explicitly."
                )
            print(f"[DualIndexer] Collection '{self.COLLECTION_NAME}' already exists")

    def delete_file_points(self, file_id: str):
        """
        Delete all existing Qdrant points for a given file_id.
        Used during re-ingestion to avoid duplicates.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._get_qdrant()
        client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="file_id", match=MatchValue(value=file_id))]
            ),
        )
        print(f"[DualIndexer] Deleted old points for file_id={file_id[:8]}...")

    def index_chunks(self, chunks: list) -> int:
        """
        Index a list of FinalChunks into both Qdrant and BM25.
        
        Args:
            chunks: List of FinalChunk objects (fully enriched)
            
        Returns:
            Number of chunks successfully indexed.
        """
        if not chunks:
            return 0

        # 1. Generate embeddings for all chunks using Gemini
        embeddings = self._generate_embeddings(chunks)

        # 2. Upsert into Qdrant
        self._upsert_qdrant(chunks, embeddings)

        # 3. Build/update BM25 index for this project
        project_id = chunks[0].project_id
        self._update_bm25(project_id)

        print(f"[DualIndexer] Indexed {len(chunks)} chunks into Qdrant + BM25")
        return len(chunks)

    def _generate_embeddings(self, chunks: list) -> list:
        """
        Generate embeddings using local sentence-transformers model.
        No API calls, no rate limits, runs entirely on CPU.
        """
        model = self._get_embed_model()
        texts = [c.enriched_text for c in chunks]
        print(f"[DualIndexer] Embedding {len(texts)} chunks locally...")
        embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
        print(f"[DualIndexer] Embedding complete ({len(embeddings)} vectors, dim={len(embeddings[0])})")
        return [emb.tolist() for emb in embeddings]

    def _upsert_qdrant(self, chunks: list, embeddings: list):
        """Upsert chunk vectors + payloads into Qdrant."""
        from qdrant_client.models import PointStruct

        client = self._get_qdrant()
        points = []

        import hashlib
        import uuid

        for chunk, embedding in zip(chunks, embeddings):
            # Qdrant strictly requires UUID or uint64 for Point ID.
            # We hash project_id + chunk_id to make it deterministic and globally unique.
            m = hashlib.md5(f"{chunk.project_id}_{chunk.chunk_id}".encode("utf-8"))
            qdrant_id = str(uuid.UUID(m.hexdigest()))

            payload = {
                "chunk_id": chunk.chunk_id,
                "project_id": chunk.project_id,
                "file_id": chunk.file_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "section_header": chunk.section_header,
                "raw_text": chunk.raw_text,
                "context_summary": chunk.context_summary,
                "enriched_text": chunk.enriched_text,
                "bounding_box": chunk.bounding_box,
                "token_count": chunk.token_count,
                "is_table": chunk.is_table,
                "table_html": chunk.table_html,
                "table_kv": json.dumps(chunk.table_kv) if chunk.table_kv else None,
                "is_image": getattr(chunk, "is_image", False),
                "image_path": getattr(chunk, "image_path", None),
                "image_description": getattr(chunk, "image_description", None),
            }
            points.append(PointStruct(
                id=qdrant_id,
                vector=embedding,
                payload=payload,
            ))

        # Batch upsert (max 100 per request for Qdrant)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=batch,
            )
        print(f"[DualIndexer] Upserted {len(points)} points to Qdrant")

    def _update_bm25(self, project_id: str):
        """
        Rebuild the BM25 index for a project by reading all chunks for that
        project from Qdrant. This ensures the BM25 index stays in sync.
        
        Storage: /data/bm25_indexes/{project_id}.pkl
        Contents: {index: BM25Okapi, chunk_ids: [...], raw_texts: [...]}
        """
        from rank_bm25 import BM25Okapi
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._get_qdrant()

        # Scroll all chunks for this project from Qdrant
        all_chunk_ids = []
        all_raw_texts = []

        offset = None
        while True:
            results, offset = client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
                ),
                limit=500,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in results:
                all_chunk_ids.append(point.id)
                all_raw_texts.append(point.payload.get("raw_text", ""))
            if offset is None:
                break

        if not all_raw_texts:
            print(f"[DualIndexer] No chunks found for project {project_id[:8]}..., skipping BM25")
            return

        # Tokenize and build BM25 index
        tokenized = [text.lower().split() for text in all_raw_texts]
        bm25_index = BM25Okapi(tokenized)

        # Persist to disk
        index_path = os.path.join(self._bm25_dir, f"{project_id}.pkl")
        with open(index_path, "wb") as f:
            pickle.dump({
                "index": bm25_index,
                "chunk_ids": all_chunk_ids,
                "raw_texts": all_raw_texts,
            }, f)

        print(f"[DualIndexer] BM25 index built for project {project_id[:8]}... "
              f"({len(all_raw_texts)} docs, saved to {index_path})")
