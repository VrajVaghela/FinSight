import asyncio
import json
import random
import os
from typing import Any
from pathlib import Path

from app.config import get_settings
from app.core.llm_client import get_llm_client, create_chat_completion
from app.retrieval.vector_searcher import get_client, COLLECTION_NAME, create_collection_if_not_exists

async def generate_eval_dataset(num_samples: int = 50, project_id: str | None = None):
    """
    Generates a synthetic evaluation dataset by fetching random chunks from Qdrant
    and using an LLM to generate relevant questions for each chunk.
    """
    # Ensure collection exists
    create_collection_if_not_exists()
    
    client = get_client()
    llm_client = get_llm_client()
    settings = get_settings()

    print(f"[*] Starting synthetic dataset generation (target: {num_samples} samples)...")

    # 1. Fetch random chunks from Qdrant
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    must = []
    if project_id:
        must.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))
    
    query_filter = Filter(must=must) if must else None
    
    # We scroll to get a pool of candidates
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=query_filter,
        limit=num_samples * 5, # Fetch a larger pool to pick from
        with_payload=True,
        with_vectors=False
    )
    
    if not points:
        print("[!] No chunks found in the collection. Make sure you have ingested some documents first.")
        return

    random.shuffle(points)
    candidates = points[:num_samples]
    
    dataset = []
    
    for i, point in enumerate(candidates):
        # Prefer enriched_text if available, fallback to raw_text
        content = point.payload.get("enriched_text") or point.payload.get("raw_text")
        if not content or len(content) < 150:
            print(f"[-] Skipping point {point.id}: Content too short or missing.")
            continue
            
        chunk_id = point.id
        file_id = point.payload.get("file_id")
        proj_id = point.payload.get("project_id")
        
        print(f"[{i+1}/{len(candidates)}] Generating question for chunk {chunk_id[:8]}...")
        
        prompt = f"""
        You are an expert financial analyst. I will provide a text snippet from a financial document.
        Your task is to generate a HIGH-QUALITY, specific, and concise question that is answered DIRECTLY and UNAMBIGUOUSLY by this snippet.
        
        Rules:
        1. The question must be answerable using ONLY the information in the snippet.
        2. Avoid generic questions like "What does this section talk about?".
        3. Use professional financial terminology.
        4. Do NOT mention "the snippet" or "the text" in your question.
        
        Text Snippet:
        ---
        {content}
        ---
        
        Return ONLY the question text. Do not include any preamble, quotes, or conversational filler.
        """
        
        try:
            # Using the configured model (fallback to llama-3.3-70b-versatile if not set)
            model = getattr(settings, "groq_model_name", "llama-3.3-70b-versatile")
            
            response = await create_chat_completion(
                client=llm_client,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            question = response.choices[0].message.content.strip().strip('"')
            
            dataset.append({
                "question": question,
                "expected_chunk_id": chunk_id,
                "file_id": file_id,
                "project_id": proj_id,
                "content_preview": content[:200] + "..."
            })
        except Exception as e:
            print(f"[!] Error generating question for chunk {chunk_id[:8]}: {e}")
            
    # 2. Save to file
    data_dir = Path("backend/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "eval_dataset.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        
    print(f"\n[+] SUCCESS: Generated {len(dataset)} samples.")
    print(f"[+] Dataset saved to: {output_path}")

if __name__ == "__main__":
    # For running standalone
    import sys
    
    # Simple CLI arg for num samples
    n = 20
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
        
    asyncio.run(generate_eval_dataset(num_samples=n))
