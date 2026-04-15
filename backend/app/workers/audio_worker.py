import asyncio
import json
import logging
import uuid

import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.script import Script
from app.services.audio_generator import AudioGenerator
from app.services.sarvam_client import SarvamClient
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


async def _generate_audio(script_id_str: str):
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = redis.Redis.from_url(settings.REDIS_URL)

    sarvam = None
    async with session_factory() as db:
        try:
            sarvam = SarvamClient()
            generator = AudioGenerator(sarvam=sarvam)
            script_id = uuid.UUID(script_id_str)

            result = await generator.generate_all_audio(db, script_id)
            await db.commit()

            script_result = await db.execute(select(Script).where(Script.id == script_id))
            script = script_result.scalar_one_or_none()
            company_id = str(script.company_id) if script else ""

            redis_client.publish(
                f"calls:{company_id}",
                json.dumps({
                    "type": "audio_generation_complete",
                    "script_id": script_id_str,
                    "result": result,
                }),
            )

            logger.info(f"Audio generation task completed for script {script_id_str}")
            return result

        except Exception as e:
            logger.error(f"Audio generation failed for script {script_id_str}: {e}")
            script_id = uuid.UUID(script_id_str)
            script_result = await db.execute(select(Script).where(Script.id == script_id))
            script = script_result.scalar_one_or_none()
            if script:
                script.audio_status = "failed"
                await db.commit()
            raise

        finally:
            if sarvam:
                await sarvam.close()
            await engine.dispose()
            redis_client.close()


@celery_app.task(name="app.workers.audio_worker.generate_script_audio", bind=True, max_retries=2)
def generate_script_audio(self, script_id: str):
    try:
        return asyncio.run(_generate_audio(script_id))
    except Exception as exc:
        logger.error(f"Audio generation task error: {exc}")
        self.retry(exc=exc, countdown=30)
