import os
import shutil
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser
from app.db.session import get_db
from app.models import (
    User, Topic, Subject, Question, Payment, ExamAttempt, AttemptStatus,
    AuditLog, ExamCategory, Difficulty, LearningMaterial,
)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats")
async def stats(_: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return {
        "users": await db.scalar(select(func.count()).select_from(User)),
        "topics": await db.scalar(select(func.count()).select_from(Topic)),
        "questions": await db.scalar(select(func.count()).select_from(Question)),
        "payments_success": await db.scalar(
            select(func.count()).select_from(Payment).where(Payment.status == "success")
        ),
        "attempts_submitted": await db.scalar(
            select(func.count()).select_from(ExamAttempt)
            .where(ExamAttempt.status == AttemptStatus.SUBMITTED)
        ),
    }

@router.get("/users")
async def list_users(_: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.scalars(select(User).order_by(User.created_at.desc()).limit(200))).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "is_email_verified": u.is_email_verified,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]

class TopicUpdate(BaseModel):
    title: str | None = None
    price_kobo: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

@router.patch("/topics/{topic_id}")
async def update_topic(topic_id: str, payload: TopicUpdate,
                       admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404, "Topic not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.add(AuditLog(
        actor_id=admin.id,
        action="topic.update",
        target=topic_id,
        metadata_=payload.model_dump(exclude_unset=True),
    ))
    await db.flush()
    return {"ok": True}

class TopicCreate(BaseModel):
    subject_id: str
    title: str
    price_kobo: int = 200000
    is_free_preview: bool = False

@router.post("/topics", status_code=201)
async def create_topic(payload: TopicCreate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    slug = payload.title.lower().replace(" ", "-").replace("?", "")
    t = Topic(
        subject_id=payload.subject_id,
        title=payload.title,
        slug=slug,
        price_kobo=payload.price_kobo,
        is_free_preview=payload.is_free_preview,
    )
    db.add(t)
    await db.flush()
    db.add(AuditLog(actor_id=admin.id, action="topic.create", target=t.id))
    await db.flush()
    return {"id": t.id}

class QuestionCreate(BaseModel):
    subject_id: str
    exam_category: ExamCategory
    question_text: str
    options: list[dict]
    correct_key: str
    explanation: str
    difficulty: Difficulty = Difficulty.MEDIUM

@router.post("/questions", status_code=201)
async def create_question(payload: QuestionCreate,
                          admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    q = Question(
        subject_id=payload.subject_id,
        exam_category=payload.exam_category,
        question_text=payload.question_text,
        options=payload.options,
        correct_key=payload.correct_key,
        explanation=payload.explanation,
        difficulty=payload.difficulty,
    )
    db.add(q)
    await db.flush()
    db.add(AuditLog(actor_id=admin.id, action="question.create", target=q.id))
    await db.flush()
    return {"id": q.id}

class MaterialCreate(BaseModel):
    topic_id: str
    intro: str
    objectives: list[str]
    explanation: str
    pdf_url: str | None = None   # <--- ADDED THIS

@router.post("/materials", status_code=201)
async def create_material(payload: MaterialCreate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if not payload.topic_id:
        raise HTTPException(400, "Topic ID is missing")

    # Check if topic exists
    topic = await db.get(Topic, payload.topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")

    # Build the JSON block structure
    blocks_list = [
        {"type": "intro", "text": payload.intro},
        {"type": "objectives", "items": payload.objectives},
        {"type": "explanation", "text": payload.explanation}
    ]
    
    # If a PDF was uploaded, add it to the blocks
    if payload.pdf_url:
        blocks_list.append({"type": "pdf", "url": payload.pdf_url})

    blocks = {"blocks": blocks_list}

    # Upsert (update if exists, insert if not)
    existing = await db.scalar(select(LearningMaterial).where(LearningMaterial.topic_id == payload.topic_id))
    if existing:
        existing.content_blocks = blocks
    else:
        db.add(LearningMaterial(topic_id=payload.topic_id, content_blocks=blocks))
    
    db.add(AuditLog(actor_id=admin.id, action="material.create", target=payload.topic_id))
    await db.flush()
    return {"ok": True}

@router.get("/payments")
async def list_payments(_: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.scalars(
        select(Payment).order_by(Payment.created_at.desc()).limit(200)
    )).all()
    return [
        {
            "reference": p.reference,
            "user_id": p.user_id,
            "kind": p.kind.value,
            "amount_kobo": p.amount_kobo,
            "status": p.status.value,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]

# --- NEW PDF UPLOAD ENDPOINT ---
@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), admin: AdminUser = None):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")
    
    os.makedirs("uploads/pdfs", exist_ok=True)
    
    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join("uploads/pdfs", filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"url": f"/api/v1/study/pdf/{filename}"}
