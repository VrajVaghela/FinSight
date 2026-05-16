import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

# Import from our application
from app.services.chat_service import ChatService

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
            def scalar_one_or_none(self): return None
        return MockResult()
    async def get(self, model, ident): return None

class DummyLLM:
    class Chat:
        class Completions:
            async def create(self, **kwargs):
                class MockChunk:
                    class Choice:
                        class Delta:
                            content = "Should not reach here."
                        delta = Delta()
                    choices = [Choice()]
                    usage = None
                
                async def async_generator():
                    yield MockChunk()
                
                if kwargs.get('stream'):
                    return async_generator()
                else:
                    class MockMessage:
                        content = "standalone query ceo email"
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

    print("Testing T4 (CEO Email)...")
    
    # We pass 'ceo email' to trigger the Refusal Gate Level 3
    async for event in service.process_chat(
        project_id=uuid4(),
        message="What is the ceo email?",
        user_id="test_user"
    ):
        print(f"EVENT YIELDED:\n{event}")

if __name__ == "__main__":
    asyncio.run(test())
