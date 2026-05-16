import asyncio
import json
import time
import os
from pathlib import Path
from typing import Any

# Add the project root to sys.path for absolute imports
import sys
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from app.config import get_settings
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.vector_searcher import VectorSearcher

async def run_benchmark(top_k: int = 5):
    """
    Runs a retrieval benchmark using the generated eval_dataset.json.
    Calculates Hit Rate, MRR, and Precision@K for the Dense (Vector) retrieval layer.
    """
    dataset_path = Path("backend/data/eval_dataset.json")
    if not dataset_path.exists():
        print("[!] Evaluation dataset not found. Run eval_dataset_generator.py first.")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if not dataset:
        print("[!] Dataset is empty.")
        return

    print(f"[*] Starting benchmark on {len(dataset)} samples (Top-K: {top_k})...")

    # Load embedder (matching the model used in indexing)
    from sentence_transformers import SentenceTransformer
    print("[*] Loading embedding model (all-MiniLM-L6-v2)...")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    retriever = HybridRetriever()

    stats = {
        "hits": 0,
        "reciprocal_ranks": [],
        "latencies": [],
        "total_precision": 0.0
    }

    for i, item in enumerate(dataset):
        query = item["question"]
        expected_id = item["expected_chunk_id"]
        project_id = item.get("project_id", "default")

        start_time = time.perf_counter()
        
        # 1. Generate query vector
        query_vector = embedder.encode(query).tolist()
        
        # 2. Run retrieval (Directly testing HybridRetriever components)
        # We focus on dense_search results for this specific retrieval evaluation
        _, dense_hits = await retriever.retrieve(
            query=query,
            query_vector=query_vector,
            project_id=project_id,
            top_k=top_k
        )
        
        retrieved_ids = [str(hit.id) for hit in dense_hits]
        
        latency = (time.perf_counter() - start_time) * 1000
        stats["latencies"].append(latency)

        # 3. Calculate Hit Rate & MRR
        if expected_id in retrieved_ids:
            stats["hits"] += 1
            rank = retrieved_ids.index(expected_id) + 1
            stats["reciprocal_ranks"].append(1.0 / rank)
            print(f"[{i+1}/{len(dataset)}] [PASS] Hit at rank {rank} | Q: {query[:60]}...")
        else:
            stats["reciprocal_ranks"].append(0.0)
            print(f"[{i+1}/{len(dataset)}] [FAIL] Miss          | Q: {query[:60]}...")

        # 4. Precision (In synthetic datasets, usually only 1 is ground-truth 'relevant')
        precision = 1.0 / top_k if expected_id in retrieved_ids else 0.0
        stats["total_precision"] += precision

    # Final Metrics calculation
    num_samples = len(dataset)
    hit_rate = stats["hits"] / num_samples
    mrr = sum(stats["reciprocal_ranks"]) / num_samples
    avg_precision = stats["total_precision"] / num_samples
    avg_latency = sum(stats["latencies"]) / num_samples

    report = f"""# Retrieval Layer Evaluation Report
**Date:** {time.strftime("%Y-%m-%d %H:%M:%S")}
**Total Samples:** {num_samples}
**Top-K Evaluated:** {top_k}

## Core Retrieval Metrics
| Metric | Value | Description |
| :--- | :--- | :--- |
| **Hit Rate / Recall@{top_k}** | **{hit_rate:.2%}** | % of queries where the ground-truth chunk was retrieved. |
| **MRR (Mean Reciprocal Rank)** | **{mrr:.4f}** | Measures ranking quality (closer to 1 is better). |
| **Precision@{top_k}** | **{avg_precision:.4f}** | % of retrieved chunks that are relevant (synthetic estimate). |
| **Avg Latency** | **{avg_latency:.2f} ms** | Time taken for embedding + VDB search. |

## Interpretation
- **Recall**: A Hit Rate of {hit_rate:.1%} indicates how well your embedding model and chunking strategy capture semantic intent.
- **MRR**: An MRR of {mrr:.2f} means the correct answer is found at rank **{1/mrr if mrr > 0 else 'N/A':.1f}** on average.
- **Action Items**: If Hit Rate is low, consider increasing chunk overlap or switching to a larger embedding model.
"""
    
    print("\n" + "="*40)
    print(report)
    print("="*40)
    
    report_path = Path("backend/data/retrieval_report.md")
    report_path.write_text(report)
    print(f"[+] Detailed report saved to: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
