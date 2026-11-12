from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import TopicPurchase, Topic, Subject, Payment

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me/profile")
async def profile(user: CurrentUser):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "class_level": user.class_level,
        "school_name": user.school_name,
        "role": user.role.value,
        "is_email_verified": user.is_email_verified,
    }

@router.get("/me/purchases")
async def my_purchases(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(
        select(TopicPurchase, Topic, Subject)
        .join(Topic, Topic.id == TopicPurchase.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .where(TopicPurchase.user_id == user.id)
        .order_by(TopicPurchase.unlocked_at.desc())
    )).all()
    return [
        {
            "topic_id": t.id,
            "topic_title": t.title,
            "subject_name": s.name,
            "unlocked_at": p.unlocked_at.isoformat(),
        }
        for p, t, s in rows
    ]

@router.get("/me/payments")
async def my_payments(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.scalars(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
    )).all()
    return [
        {
            "reference": p.reference,
            "amount_kobo": p.amount_kobo,
            "currency": p.currency,
            "kind": p.kind.value,
            "status": p.status.value,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]