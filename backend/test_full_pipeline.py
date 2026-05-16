import asyncio
from app.models.database import SessionLocal, engine
from app.models.orm import File, Project
from sqlalchemy import select
from app.ingestion.pipeline import IngestionPipeline
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    try:
        async with SessionLocal() as db:
            result = await db.execute(select(File).order_by(File.created_at.desc()).limit(1))
            file_obj = result.scalars().first()
            if not file_obj:
                print('No files found')
                return
            print(f'Testing pipeline on file {file_obj.id}')
            file_id = str(file_obj.id)
            
            pipeline = IngestionPipeline(db)
            res = await pipeline.run(file_id)
            print('Pipeline finished successfully. Result:', res)
    except Exception as e:
        print('PIPELINE ERROR:', e)
    finally:
        await engine.dispose()

asyncio.run(main())
