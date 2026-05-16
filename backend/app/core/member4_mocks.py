# app/core/member4_mocks.py
import re

class PALRouter:
    """Mock implementation for Member 4's PALRouter."""
    def __init__(self, llm_client=None):
        self.client = llm_client

    async def classify(self, query: str) -> str:
        # Simple heuristic to classify calculation vs narrative
        math_keywords = ["calculate", "add", "subtract", "multiply", "divide", "+", "-", "*", "/", "sum", "average", "total"]
        if any(kw in query.lower() for kw in math_keywords):
            return "calculation"
        return "narrative"

class CodeGenerator:
    """Mock implementation for Member 4's CodeGenerator."""
    def __init__(self, llm_client=None):
        self.client = llm_client

    async def generate(self, query: str, context: list) -> str:
        # Mock code generation
        return "def calculate():\n    return 42\nresult = calculate()"

class SymbolicExecutor:
    """Mock implementation for Member 4's SymbolicExecutor."""
    def run(self, code: str):
        class ExecutionResult:
            def __init__(self, success, output, error):
                self.success = success
                self.output = output
                self.error = error
        
        # Mock execution success
        return ExecutionResult(success=True, output="42", error=None)


class CitationQueryEngine:
    """Mock implementation for Member 4's CitationQueryEngine."""
    class CitedResponse:
        def __init__(self, text, citation_ids):
            self.text = text
            self.citation_ids = citation_ids

    def add_citations(self, response_text: str, source_chunks: list) -> CitedResponse:
        # Just mock a citation appendage
        if source_chunks:
            citation_id = source_chunks[0].get("chunk_id", "source_1")
            text = f"{response_text} [Source 1, p1]"
            return self.CitedResponse(text=text, citation_ids=[citation_id])
        return self.CitedResponse(text=response_text, citation_ids=[])

class BoundingBoxMapper:
    """Mock implementation for Member 4's BoundingBoxMapper."""
    def map(self, citation_ids: list, source_chunks: list) -> list:
        # Return mock visual citations
        return [{"chunk_id": cid, "page": 1, "bounding_box": {"x": 10, "y": 10, "w": 100, "h": 50}} for cid in citation_ids]


class GLEANVerifier:
    """Mock implementation for Member 4's GLEANVerifier."""
    def __init__(self, llm_client=None):
        self.client = llm_client

    class VerifyResult:
        def __init__(self, passed, violations, corrected_response):
            self.passed = passed
            self.violations = violations
            self.corrected_response = corrected_response

    async def verify(self, response: str, retrieved_chunks: list, project_guidelines: str):
        # Mock verification pass
        return self.VerifyResult(passed=True, violations=[], corrected_response=None)
