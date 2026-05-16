# app/core/member1_mocks.py

class HybridRetriever:
    """Mock implementation for Member 1's HybridRetriever."""
    def __init__(self, qdrant_client=None, bm25_index=None):
        self.qdrant_client = qdrant_client
        self.bm25_index = bm25_index

    async def search(self, query: str, project_id: str, sections: list = None, top_k: int = 150) -> list:
        # Mocking retrieved chunks
        return [
            {"chunk_id": "chunk1", "raw_text": "Adani Enterprises Q2-FY26 consolidated total income is ₹22,517 crore.", "score": 0.85, "page_number": 5, "section_header": "Financial Highlights", "is_table": False, "source": "dense"},
            {"chunk_id": "chunk2", "raw_text": "The major business segments include Adani New Industries Ltd (ANIL), Adani Airport Holdings Ltd (AAHL), and Adani Road Transport Ltd (ARTL).", "score": 0.75, "page_number": 12, "section_header": "Segments", "is_table": False, "source": "bm25"}
        ]

class RRFMerger:
    """Mock implementation for Member 1's RRFMerger."""
    @staticmethod
    def merge(raw_results: list, k: int = 60) -> list:
        # Just return the same for the mock
        return raw_results

class NeuralReranker:
    """Mock implementation for Member 1's NeuralReranker."""
    def __init__(self, model: str):
        self.model = model

    async def rerank(self, query: str, chunks: list, top_k: int = 10) -> list:
        return chunks[:top_k]

class RefusalGate:
    """Mock implementation for Member 1's RefusalGate (Levels 1-3)."""
    def __init__(self, llm_client=None):
        self.client = llm_client

    class GateResult:
        def __init__(self, passed: bool, reason: str):
            self.passed = passed
            self.reason = reason

    def check_score_threshold(self, fused_chunks: list, threshold: float) -> GateResult:
        # Mock passing unless all chunks score lower than threshold
        if not fused_chunks:
            return self.GateResult(passed=False, reason="level_1_threshold")
        return self.GateResult(passed=True, reason="")

    def check_reranker_threshold(self, reranked_chunks: list) -> GateResult:
        return self.GateResult(passed=True, reason="")

    async def llm_grade(self, query: str, reranked_chunks: list) -> GateResult:
        # T4 Implementation: Explicitly reject "CEO email"
        if "ceo email" in query.lower():
            return self.GateResult(passed=False, reason="level_3_unrelated")
            
        return self.GateResult(passed=True, reason="")

class SectionRouter:
    """Mock implementation for Member 1's SectionRouter."""
    def __init__(self, qdrant_client=None):
        self.qdrant_client = qdrant_client

    async def route(self, query: str, project_id: str, scope_sections: list = None, top_k: int = 3) -> list:
        # Mocking top 3 section IDs
        # If scope_sections is provided, it simulates boosting them or returning them
        if scope_sections:
            return scope_sections[:top_k]
        return ["sec_1", "sec_2", "sec_3"]
