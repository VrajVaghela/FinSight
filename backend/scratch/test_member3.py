import asyncio
import uuid
from app.core.memory_manager import QueryRewriter, SessionScopeManager

class DummyLLM:
    class Chat:
        class Completions:
            async def create(self, **kwargs):
                class MockMessage:
                    content = '{"query": "revenue last year compared to this year", "cross_document": true}'
                class MockChoice:
                    message = MockMessage()
                class MockResponse:
                    choices = [MockChoice()]
                return MockResponse()
        completions = Completions()
    chat = Chat()

async def test():
    print("Testing QueryRewriter...")
    rewriter = QueryRewriter(llm_client=DummyLLM())
    result = await rewriter.rewrite([{"role": "user", "content": "hello"}], "what is the revenue last year compared to this year?")
    print(f"Rewrite result: {result}")
    
    print("\nTesting SessionScopeManager (without Redis)...")
    manager = SessionScopeManager(redis=None)
    scope = await manager.get_scope("conv_1")
    print(f"Initial scope: {scope}")
    await manager.update_scope("conv_1", ["sec_1"])
    scope2 = await manager.get_scope("conv_1")
    print(f"Scope after update (no redis): {scope2}")

if __name__ == "__main__":
    asyncio.run(test())
