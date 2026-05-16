import asyncio
from app.ingestion.pipeline import async_ingest_pdf
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    try:
        # We need a file_id and project_id in the DB.
        # Let's just create a dummy one or look at the last uploaded file
        from app.models.database import SessionLocal, engine
        from app.models.orm import File, Project
        from sqlalchemy import select
        
        async with SessionLocal() as db:
            result = await db.execute(select(File).order_by(File.created_at.desc()).limit(1))
            file_obj = result.scalars().first()
            if not file_obj:
                print('No files found')
                return
            print(f'Testing pipeline on file {file_obj.id}')
            await async_ingest_pdf(file_obj.id)
            print('Pipeline finished.')
    except Exception as e:
        print('PIPELINE ERROR:', e)

asyncio.run(main())
