import asyncio
import os
import uuid
import json
from pathlib import Path

# Add the project root to sys.path
import sys
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from app.retrieval.vector_searcher import create_collection_if_not_exists, get_client, COLLECTION_NAME
from app.retrieval.eval_dataset_generator import generate_eval_dataset

async def bootstrap():
    print("\n[*] Bootstrapping Evaluation Environment...")
    
    # 1. Ensure collection exists
    create_collection_if_not_exists()
    
    client = get_client()
    count_res = client.count(COLLECTION_NAME)
    count = getattr(count_res, "count", 0)
    
    # 2. If collection is empty or has very few chunks, populate it with document.md
    if count < 5:
        print(f"[!] Only {count} chunks found. Populating with document.md for evaluation...")
        
        doc_md = Path("document.md")
        if not doc_md.exists():
            print("[!] document.md not found. Cannot bootstrap data.")
            return

        text = doc_md.read_text(encoding="utf-8")
        # Split by sections
        sections = [s.strip() for s in text.split("## ") if len(s.strip()) > 100]
        
        from app.ingestion.dual_indexer import DualIndexer
        from app.ingestion.metadata_extractor import FinalChunk
        
        indexer = DualIndexer()
        indexer.ensure_collection()
        
        chunks = []
        project_id = "eval_demo_project"
        
        print(f"[*] Creating {len(sections)} chunks from document.md...")
        for i, section in enumerate(sections):
            header = section.split("\n")[0].strip("# ").strip()
            chunks.append(FinalChunk(
                chunk_id=f"eval_chunk_{i}",
                project_id=project_id,
                file_id="document_md",
                chunk_index=i,
                page_number=1,
                section_header=header,
                raw_text=section,
                enriched_text=section,
                token_count=len(section.split()),
                bounding_box=None,
                is_table=False,
                table_html=None,
                table_kv=None,
                context_summary=f"Section about {header}"
            ))
        
        indexer.index_chunks(chunks)
        print(f"[+] Ingested {len(chunks)} chunks into '{COLLECTION_NAME}'.")
    else:
        print(f"[+] Found {count} chunks in Qdrant. Ready for generation.")

    # 3. Trigger dataset generation
    print("\n[*] Starting synthetic dataset generation...")
    # We pass the project_id to ensure we only generate questions for what we just ingested
    await generate_eval_dataset(num_samples=10, project_id="eval_demo_project" if count < 5 else None)
    
    print("\n" + "="*50)
    print("READY TO EVALUATE!")
    print("Run the following to see your RAG metrics:")
    print("backend\\.venv\\Scripts\\python.exe backend\\app\retrieval\\retrieval_benchmarker.py")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(bootstrap())
