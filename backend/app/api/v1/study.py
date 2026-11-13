import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import CurrentUser
from app.models import Department, Subject, Topic, LearningMaterial, TopicPurchase

router = APIRouter(prefix="/study", tags=["study"])

@router.get("/departments")
async def departments(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.scalars(select(Department).order_by(Department.display_order))).all()
    return [{"id": d.id, "slug": d.slug, "name": d.name, "description": d.description} for d in rows]

@router.get("/departments/{slug}/subjects")
async def subjects(slug: str, db: Annotated[AsyncSession, Depends(get_db)]):
    dept = await db.scalar(select(Department).where(Department.slug == slug))
    if not dept:
        raise HTTPException(404, "Department not found")
    rows = (await db.scalars(
        select(Subject).where(Subject.department_id == dept.id, Subject.is_active == True).order_by(Subject.display_order)
    )).all()
    return [{"id": s.id, "name": s.name, "slug": s.slug, "description": s.description} for s in rows]

@router.get("/subjects/{subject_id}/topics")
async def topics(subject_id: str, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    subj = await db.get(Subject, subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")
    rows = (await db.scalars(
        select(Topic).where(Topic.subject_id == subject_id, Topic.is_active == True).order_by(Topic.display_order)
    )).all()
    owned = set((await db.scalars(
        select(TopicPurchase.topic_id).where(
            TopicPurchase.user_id == user.id,
            TopicPurchase.topic_id.in_([t.id for t in rows]),
        )
    )).all())
    return [
        {
            "id": t.id,
            "title": t.title,
            "summary": t.summary,
            "price_kobo": t.price_kobo,
            "is_free_preview": t.is_free_preview,
            "is_unlocked": t.id in owned or t.is_free_preview,
        }
        for t in rows
    ]

@router.get("/topics/{topic_id}")
async def topic_detail(topic_id: str, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404, "Topic not found")
    unlocked = t.is_free_preview or bool(await db.scalar(
        select(TopicPurchase).where(TopicPurchase.user_id == user.id, TopicPurchase.topic_id == topic_id)
    ))
    return {"id": t.id, "title": t.title, "summary": t.summary, "price_kobo": t.price_kobo, "is_unlocked": unlocked}

@router.get("/topics/{topic_id}/content")
async def topic_content(topic_id: str, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404)
    if not t.is_free_preview:
        owned = await db.scalar(select(TopicPurchase).where(TopicPurchase.user_id == user.id, TopicPurchase.topic_id == topic_id))
        if not owned:
            raise HTTPException(402, "Topic not purchased")
    material = await db.scalar(select(LearningMaterial).where(LearningMaterial.topic_id == topic_id))
    if not material:
        raise HTTPException(404, "Content coming soon")
    return {
        "topic_id": t.id,
        "title": t.title,
        "blocks": material.content_blocks,
        "watermark": f"{user.full_name} · {user.id[:8]}",
    }

@router.get("/pdf/{filename}")
async def get_pdf(filename: str):
    filepath = os.path.join("uploads", "pdfs", filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "PDF not found")
    return FileResponse(filepath, media_type="application/pdf")s
