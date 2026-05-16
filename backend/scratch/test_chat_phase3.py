# scratch/test_chat_phase3.py
import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

# Import from our application
from app.services.chat_service import ChatService
from app.models.orm import Conversation

class DummyDB:
    def add(self, obj): pass
    def add_all(self, objs): pass
    async def commit(self): pass
    async def refresh(self, obj): obj.id = uuid4()
    async def execute(self, stmt):
        class MockResult:
            def scalars(self):
                class MockScalars:
                    def all(self): return []
                return MockScalars()
        return MockResult()
    async def get(self, model, ident): return None

class DummyLLM:
    class Chat:
        class Completions:
            async def create(self, **kwargs):
                class MockChunk:
                    class Choice:
                        class Delta:
                            content = "Here is the calculation result: 42."
                        delta = Delta()
                    choices = [Choice()]
                
                async def async_generator():
                    yield MockChunk()
                
                if kwargs.get('stream'):
                    return async_generator()
                else:
                    class MockMessage:
                        content = "standalone query"
                    class MockResponse:
                        class Choice:
                            message = MockMessage()
                        choices = [Choice()]
                    return MockResponse()
        completions = Completions()
    chat = Chat()

async def test():
    db = DummyDB()
    llm = DummyLLM()
    service = ChatService(db=db, openai_client=llm, redis_client=None)

    print("Testing Phase 3 PAL Execution and Citations with Math Keyword...")
    
    # We pass 'calculate' to trigger the PAL execution
    async for event in service.process_chat(
        project_id=uuid4(),
        message="Calculate the total revenue",
        user_id="test_user"
    ):
        print(f"EVENT YIELDED:\n{event}")

if __name__ == "__main__":
    asyncio.run(test())
