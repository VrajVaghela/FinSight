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
    VECTOR_DIM = int(os.getenv("QDRANT_VECTOR_SIZE", "3072"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

    def __init__(self):
        self._qdrant_client = None
        self._gemini_client = None
        self._bm25_dir = os.getenv("BM25_INDEX_DIR", "./data/bm25_indexes")
        os.makedirs(self._bm25_dir, exist_ok=True)

    def _get_qdrant(self):
        """Lazy-load Qdrant client."""
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient
            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", "6333"))
            self._qdrant_client = QdrantClient(host=host, port=port)
            print(f"[DualIndexer] Connected to Qdrant at {host}:{port}")
        return self._qdrant_client

    def _get_gemini_client(self):
        """Lazy-load the Google GenAI client for embeddings."""
        if self._gemini_client is None:
            from google import genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in environment")
            self._gemini_client = genai.Client(api_key=api_key)
            print(f"[DualIndexer] Gemini embeddings ready: {self.EMBEDDING_MODEL}")
        return self._gemini_client

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
            print("[DualIndexer] Payload indexes created (project_id, file_id, is_table)")
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
        Generate embeddings for all chunks using Gemini embeddings.
        Uses enriched_text (context_summary + raw_text) for richer semantic vectors.
        
        Batches requests in groups of 100 to stay within API limits.
        """
        from google.genai import types

        client = self._get_gemini_client()
        texts = [c.enriched_text for c in chunks]
        all_embeddings = []

        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            print(f"[DualIndexer] Embedding batch {i // batch_size + 1} "
                  f"({len(batch)} chunks)...")
            result = client.models.embed_content(
                model=self.EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.VECTOR_DIM,
                ),
            )
            all_embeddings.extend(
                list(getattr(embedding, "values", embedding))
                for embedding in result.embeddings
            )

        return all_embeddings

    def _upsert_qdrant(self, chunks: list, embeddings: list):
        """Upsert chunk vectors + payloads into Qdrant."""
        from qdrant_client.models import PointStruct

        client = self._get_qdrant()
        points = []

        for chunk, embedding in zip(chunks, embeddings):
            payload = {
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
                id=chunk.chunk_id,
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
