import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os

async def test_db():
    db_url = "postgresql+asyncpg://finsight:finsight_dev@localhost:5432/finsight"
    print(f"Connecting to {db_url}...")
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            print("Successfully connected to the database!")
    except Exception as e:
        print(f"Failed to connect: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())
