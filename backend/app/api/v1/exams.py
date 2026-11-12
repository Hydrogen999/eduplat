import random
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import CurrentUser
from app.core.config import settings
from app.models import (
    Question, ExamAttempt, AttemptStatus, ExamCategory,
    ExamResponse, Subject,
)
from app.services.marking import mark_attempt

router = APIRouter(prefix="/exams", tags=["exams"])

class CreateAttemptIn(BaseModel):
    exam_category: ExamCategory
    subject_ids: list[str] = Field(min_length=1, max_length=8)
    question_count: int = Field(ge=5, le=200, default=40)
    duration_minutes: int = Field(ge=5, le=240, default=60)

@router.post("/attempts")
async def create_attempt(payload: CreateAttemptIn, user: CurrentUser,
                         db: Annotated[AsyncSession, Depends(get_db)]):
    for sid in payload.subject_ids:
        subj = await db.get(Subject, sid)
        if not subj:
            raise HTTPException(404, f"Subject {sid} not found")
        has_q = await db.scalar(
            select(Question.id).where(
                Question.subject_id == sid,
                Question.exam_category == payload.exam_category,
                Question.is_active == True,
            ).limit(1)
        )
        if not has_q:
            raise HTTPException(422, f"No questions for {subj.name} ({payload.exam_category.value})")

    attempt = ExamAttempt(
        user_id=user.id,
        exam_category=payload.exam_category,
        subject_ids=payload.subject_ids,
        question_count=payload.question_count,
        duration_minutes=payload.duration_minutes,
        status=AttemptStatus.PENDING_PAYMENT,
    )
    db.add(attempt)
    await db.flush()
    return {
        "attempt_id": attempt.id,
        "fee_kobo": settings.DEFAULT_EXAM_FEE_KOBO,
        "question_count": attempt.question_count,
        "duration_minutes": attempt.duration_minutes,
        "requires_payment": True,
    }

@router.post("/attempts/{attempt_id}/start")
async def start_attempt(attempt_id: str, user: CurrentUser,
                        db: Annotated[AsyncSession, Depends(get_db)]):
    attempt = await db.get(ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404)
    if attempt.status not in (AttemptStatus.READY, AttemptStatus.IN_PROGRESS):
        raise HTTPException(409, "Attempt not payable/startable")
    if attempt.expires_at and attempt.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(410, "Attempt expired")

    if attempt.status == AttemptStatus.READY:
        rows = (await db.scalars(
            select(Question).where(
                Question.subject_id.in_(attempt.subject_ids),
                Question.exam_category == attempt.exam_category,
                Question.is_active == True,
            )
        )).all()
        if len(rows) < attempt.question_count:
            raise HTTPException(
                422,
                f"Not enough questions: {len(rows)} available, {attempt.question_count} required",
            )
        chosen = random.sample(rows, attempt.question_count)
        attempt.question_ids = [q.id for q in chosen]
        attempt.started_at = datetime.now(timezone.utc)
        attempt.expires_at = attempt.started_at + timedelta(minutes=attempt.duration_minutes)
        attempt.status = AttemptStatus.IN_PROGRESS
        await db.flush()
    else:
        rows = (await db.scalars(
            select(Question).where(Question.id.in_(attempt.question_ids))
        )).all()
        qmap = {q.id: q for q in rows}
        chosen = [qmap[qid] for qid in attempt.question_ids]

    questions = [
        {
            "id": q.id,
            "subject_id": q.subject_id,
            "question_text": q.question_text,
            "image_url": q.image_url,
            "options": q.options,
        }
        for q in chosen
    ]

    saved = (await db.scalars(
        select(ExamResponse).where(ExamResponse.attempt_id == attempt.id)
    )).all()

    return {
        "attempt_id": attempt.id,
        "exam_category": attempt.exam_category.value,
        "questions": questions,
        "started_at": attempt.started_at.isoformat(),
        "expires_at": attempt.expires_at.isoformat(),
        "server_now": datetime.now(timezone.utc).isoformat(),
        "saved_responses": {r.question_id: r.selected_key for r in saved},
    }

class SaveAnswerIn(BaseModel):
    question_id: str
    selected_key: str | None = Field(default=None, max_length=5)

@router.post("/attempts/{attempt_id}/answer")
async def save_answer(attempt_id: str, payload: SaveAnswerIn, user: CurrentUser,
                      db: Annotated[AsyncSession, Depends(get_db)]):
    attempt = await db.get(ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(409, "Attempt not in progress")
    if datetime.now(timezone.utc) >= attempt.expires_at:
        raise HTTPException(410, "Time expired")

    if payload.question_id not in (attempt.question_ids or []):
        raise HTTPException(400, "Question not part of this attempt")

    existing = await db.scalar(select(ExamResponse).where(
        ExamResponse.attempt_id == attempt_id,
        ExamResponse.question_id == payload.question_id,
    ))
    if existing:
        existing.selected_key = payload.selected_key
    else:
        db.add(ExamResponse(
            attempt_id=attempt_id,
            question_id=payload.question_id,
            selected_key=payload.selected_key,
        ))
    await db.flush()
    return {"ok": True}

class SubmitIn(BaseModel):
    confirm: bool = True

@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(attempt_id: str, payload: SubmitIn, user: CurrentUser,
                         db: Annotated[AsyncSession, Depends(get_db)]):
    if not payload.confirm:
        raise HTTPException(400, "Submission not confirmed")
    attempt = await db.get(ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404)
    if attempt.status == AttemptStatus.SUBMITTED:
        return _result_payload(attempt)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(409, "Attempt not in progress")

    if datetime.now(timezone.utc) > attempt.expires_at + timedelta(seconds=2):
        attempt.status = AttemptStatus.EXPIRED
        await db.flush()

    await mark_attempt(db, attempt)
    return _result_payload(attempt)

def _result_payload(a: ExamAttempt) -> dict:
    return {
        "attempt_id": a.id,
        "correct": a.score_correct,
        "total": a.score_total,
        "percent": float(a.score_percent or 0),
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
    }

@router.get("/attempts/{attempt_id}/result")
async def result_detail(attempt_id: str, user: CurrentUser,
                        db: Annotated[AsyncSession, Depends(get_db)]):
    attempt = await db.get(ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404)
    if attempt.status not in (AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED):
        raise HTTPException(409, "Result not released")

    rows = (await db.scalars(
        select(Question).where(Question.id.in_(attempt.question_ids))
    )).all()
    qmap = {q.id: q for q in rows}

    responses = (await db.scalars(
        select(ExamResponse).where(ExamResponse.attempt_id == attempt.id)
    )).all()
    rmap = {r.question_id: r for r in responses}

    items = []
    for qid in attempt.question_ids:
        q = qmap[qid]
        r = rmap.get(qid)
        items.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "options": q.options,
            "correct_key": q.correct_key,
            "explanation": q.explanation,
            "selected_key": r.selected_key if r else None,
            "is_correct": r.is_correct if r else False,
        })

    return {**_result_payload(attempt), "items": items}

@router.get("/history")
async def history(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.scalars(
        select(ExamAttempt).where(
            ExamAttempt.user_id == user.id,
            ExamAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
        ).order_by(ExamAttempt.submitted_at.desc())
    )).all()
    return [
        {
            "attempt_id": a.id,
            "exam_category": a.exam_category.value,
            "score_percent": float(a.score_percent or 0),
            "correct": a.score_correct,
            "total": a.score_total,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
        for a in rows
    ]