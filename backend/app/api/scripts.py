import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.script import Script
from app.models.script_audio import ScriptAudio
from app.models.user import User
from app.schemas.script import (
    ScriptAudioResponse,
    ScriptCreate,
    ScriptListResponse,
    ScriptResponse,
    ScriptUpdate,
)
from app.services.gemini_client import GeminiIntentClassifier
from app.services.script_engine import ScriptEngine
from pydantic import BaseModel

router = APIRouter()
engine = ScriptEngine()


async def _script_to_response(db: AsyncSession, script: Script) -> ScriptResponse:
    count_result = await db.execute(
        select(func.count(ScriptAudio.id)).where(ScriptAudio.script_id == script.id)
    )
    audio_count = count_result.scalar() or 0
    resp = ScriptResponse.model_validate(script)
    resp.audio_file_count = audio_count
    return resp


@router.get("", response_model=ScriptListResponse)
async def list_scripts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Script).where(
        Script.company_id == user.company_id,
        Script.is_active == True,
    )
    if search:
        query = query.where(Script.name.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Script.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    scripts = result.scalars().all()

    script_responses = []
    for s in scripts:
        script_responses.append(await _script_to_response(db, s))

    return ScriptListResponse(scripts=script_responses, total=total, page=page, page_size=page_size)


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
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
    return await _script_to_response(db, script)


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    data: ScriptCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_dict = data.content.model_dump()
    errors = engine.validate_script(content_dict)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"validation_errors": errors})

    script = Script(
        company_id=user.company_id,
        name=data.name,
        description=data.description,
        content=content_dict,
        audio_status="pending",
    )
    db.add(script)
    await db.flush()
    return await _script_to_response(db, script)


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: uuid.UUID,
    data: ScriptUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    if data.name is not None:
        script.name = data.name
    if data.description is not None:
        script.description = data.description
    if data.is_active is not None:
        script.is_active = data.is_active
    if data.content is not None:
        content_dict = data.content.model_dump()
        errors = engine.validate_script(content_dict)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"validation_errors": errors},
            )
        script.content = content_dict
        script.audio_status = "pending"
        script.version += 1

    await db.flush()
    return await _script_to_response(db, script)


@router.delete("/{script_id}")
async def delete_script(
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

    script.is_active = False
    await db.flush()
    return {"message": "Script deleted"}


@router.post("/{script_id}/duplicate", response_model=ScriptResponse)
async def duplicate_script(
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

    new_script = Script(
        company_id=user.company_id,
        name=f"Copy of {script.name}",
        description=script.description,
        content=script.content,
        audio_status="pending",
    )
    db.add(new_script)
    await db.flush()
    return await _script_to_response(db, new_script)


@router.get("/{script_id}/nodes")
async def list_script_nodes(
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
    audio_map = {}
    for af in audio_files:
        key = f"{af.node_key}_{af.language_code}"
        audio_map[key] = {"status": af.status, "audio_url": af.audio_url, "duration_ms": af.audio_duration_ms}

    nodes = script.content.get("nodes", {})
    languages = script.content.get("supported_languages", [])
    node_list = []
    for node_key, node_config in nodes.items():
        lang_status = {}
        for lang in languages:
            key = f"{node_key}_{lang}"
            lang_status[lang] = audio_map.get(key, {"status": "pending"})
        node_list.append({
            "node_key": node_key,
            "text": node_config.get("text", {}),
            "dynamic_slots": node_config.get("dynamic_slots", []),
            "next_action": node_config.get("next_action", "listen"),
            "audio_status": lang_status,
        })

    return {"nodes": node_list, "supported_languages": languages}


class TestIntentRequest(BaseModel):
    text: str
    language: str = "auto"


@router.post("/{script_id}/test-intent")
async def test_intent(
    script_id: uuid.UUID,
    body: TestIntentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.company_id == user.company_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    intent_map = script.content.get("intent_map", {})
    classifier = GeminiIntentClassifier()
    classification = await classifier.classify_intent(body.text, intent_map, body.language)
    return classification
