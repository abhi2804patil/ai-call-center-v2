import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.script import Script
from app.models.script_audio import ScriptAudio
from app.models.user import User
from app.schemas.script import ScriptAudioResponse
from app.services.audio_generator import AudioGenerator
from app.services.sarvam_client import SarvamClient
from app.workers.audio_worker import generate_script_audio
from pydantic import BaseModel

router = APIRouter()


class GenerateSingleRequest(BaseModel):
    node_key: str
    language_code: str


class PreviewRequest(BaseModel):
    text: str
    language_code: str
    voice_id: str = "meera"


@router.post("/generate/{script_id}")
async def trigger_audio_generation(
    script_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    script.audio_status = "generating"
    await db.flush()

    generate_script_audio.delay(str(script_id))

    return {"message": "Audio generation started", "script_id": str(script_id), "status": "generating"}


@router.post("/generate-single/{script_id}", response_model=ScriptAudioResponse)
async def regenerate_single_audio(
    script_id: uuid.UUID,
    body: GenerateSingleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    sarvam = SarvamClient()
    generator = AudioGenerator(sarvam=sarvam)
    try:
        audio_record = await generator.generate_single_audio(
            db, script_id, body.node_key, body.language_code
        )
        return ScriptAudioResponse.model_validate(audio_record)
    finally:
        await sarvam.close()


@router.post("/preview")
async def preview_audio(
    body: PreviewRequest,
    user: User = Depends(get_current_user),
):
    sarvam = SarvamClient()
    generator = AudioGenerator(sarvam=sarvam)
    try:
        audio_bytes = await generator.preview_audio(body.text, body.language_code, body.voice_id)
        return Response(content=audio_bytes, media_type="audio/wav")
    finally:
        await sarvam.close()


@router.get("/{script_id}", response_model=list[ScriptAudioResponse])
async def list_audio_files(
    script_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    audio_result = await db.execute(
        select(ScriptAudio).where(ScriptAudio.script_id == script_id).order_by(ScriptAudio.node_key)
    )
    audio_files = audio_result.scalars().all()
    return [ScriptAudioResponse.model_validate(f) for f in audio_files]


@router.get("/{script_id}/{node_key}/{language_code}", response_model=ScriptAudioResponse)
async def get_audio_file(
    script_id: uuid.UUID,
    node_key: str,
    language_code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    audio_result = await db.execute(
        select(ScriptAudio).where(
            ScriptAudio.script_id == script_id,
            ScriptAudio.node_key == node_key,
            ScriptAudio.language_code == language_code,
        )
    )
    audio = audio_result.scalar_one_or_none()
    if not audio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")
    return ScriptAudioResponse.model_validate(audio)


@router.delete("/{script_id}")
async def delete_audio_files(
    script_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    audio_result = await db.execute(
        select(ScriptAudio).where(ScriptAudio.script_id == script_id)
    )
    audio_files = audio_result.scalars().all()
    for af in audio_files:
        await db.delete(af)

    script.audio_status = "pending"
    await db.flush()

    return {"message": f"Deleted {len(audio_files)} audio files", "script_id": str(script_id)}
