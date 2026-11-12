import secrets
from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import (
    Payment, PaymentStatus, PurchaseKind,
    Topic, TopicPurchase, ExamAttempt, AttemptStatus,
)
from app.services.paystack import paystack

router = APIRouter(prefix="/payments", tags=["payments"])

class InitiateIn(BaseModel):
    kind: PurchaseKind
    target_id: str

@router.post("/initiate")
async def initiate(payload: InitiateIn, user: CurrentUser,
                   db: Annotated[AsyncSession, Depends(get_db)]):
    amount = 0

    if payload.kind == PurchaseKind.TOPIC:
        t = await db.get(Topic, payload.target_id)
        if not t:
            raise HTTPException(404, "Topic not found")
        owned = await db.scalar(select(TopicPurchase).where(
            TopicPurchase.user_id == user.id,
            TopicPurchase.topic_id == t.id,
        ))
        if owned:
            raise HTTPException(409, "Topic already owned")
        amount = t.price_kobo

    elif payload.kind == PurchaseKind.EXAM:
        attempt = await db.get(ExamAttempt, payload.target_id)
        if not attempt or attempt.user_id != user.id:
            raise HTTPException(404, "Attempt not found")
        if attempt.status != AttemptStatus.PENDING_PAYMENT:
            raise HTTPException(409, "Attempt already paid or started")
        amount = settings.DEFAULT_EXAM_FEE_KOBO

    reference = f"eduplat_{user.id[:8]}_{secrets.token_hex(8)}"
    payment = Payment(
        user_id=user.id,
        reference=reference,
        kind=payload.kind,
        target_id=payload.target_id,
        amount_kobo=amount,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.flush()

    callback = f"{settings.FRONTEND_ORIGIN}/payment-callback.html?ref={reference}"

    # Dev fallback when Paystack keys not set
    if not settings.PAYSTACK_SECRET_KEY or settings.PAYSTACK_SECRET_KEY.startswith("sk_test_xxx"):
        return {
            "authorization_url": f"{settings.FRONTEND_ORIGIN}/payment-callback.html?ref={reference}&dev=1",
            "reference": reference,
            "dev_mode": True,
            "amount_kobo": amount,
        }

    init = await paystack.initialize(
        email=user.email,
        amount_kobo=amount,
        reference=reference,
        callback_url=callback,
        metadata={"kind": payload.kind.value, "target_id": payload.target_id, "user_id": user.id},
    )
    return {"authorization_url": init["authorization_url"], "reference": reference}

@router.get("/verify/{reference}")
async def verify_payment(reference: str, db: Annotated[AsyncSession, Depends(get_db)]):
    # NOTE: 'user: CurrentUser' has been removed here. 
    # Paystack redirects from their domain back to ours. Browsers sometimes drop the auth cookie 
    # during this redirect. The unique reference guarantees security.
    
    payment = await db.scalar(select(Payment).where(Payment.reference == reference))
    if not payment:
        raise HTTPException(404, "Payment not found")

    if payment.status == PaymentStatus.SUCCESS:
        return {"status": "success", "reference": reference}

    # Dev bypass
    if not settings.PAYSTACK_SECRET_KEY or settings.PAYSTACK_SECRET_KEY.startswith("sk_test_xxx"):
        await _finalize_payment(db, payment, {"reference": reference, "channel": "dev"})
        return {"status": "success", "reference": reference}

    result = await paystack.verify(reference)
    if result.get("status") != "success" or result.get("amount") != payment.amount_kobo:
        payment.status = PaymentStatus.FAILED
        await db.flush()
        raise HTTPException(400, "Payment not verified")

    await _finalize_payment(db, payment, result)
    return {"status": "success", "reference": reference}

async def _finalize_payment(db: AsyncSession, payment: Payment, gateway_data: dict):
    if payment.status == PaymentStatus.SUCCESS:
        return
    payment.status = PaymentStatus.SUCCESS
    payment.gateway_reference = gateway_data.get("reference")
    payment.gateway_payload = {"id": gateway_data.get("id"), "channel": gateway_data.get("channel")}
    payment.verified_at = datetime.now(timezone.utc)

    if payment.kind == PurchaseKind.TOPIC:
        already = await db.scalar(select(TopicPurchase).where(
            TopicPurchase.user_id == payment.user_id,
            TopicPurchase.topic_id == payment.target_id,
        ))
        if not already:
            db.add(TopicPurchase(
                user_id=payment.user_id,
                topic_id=payment.target_id,
                payment_id=payment.id,
            ))

    elif payment.kind == PurchaseKind.EXAM:
        attempt = await db.get(ExamAttempt, payment.target_id)
        if attempt and attempt.status == AttemptStatus.PENDING_PAYMENT:
            attempt.payment_id = payment.id
            attempt.status = AttemptStatus.READY

    await db.flush()

@router.post("/webhook/paystack", include_in_schema=False)
async def paystack_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    raw = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    if not paystack.verify_webhook_signature(raw, signature):
        raise HTTPException(401, "Bad signature")
    event = await request.json()
    if event.get("event") != "charge.success":
        return {"ok": True}
    data = event["data"]
    ref = data.get("reference")
    payment = await db.scalar(select(Payment).where(Payment.reference == ref))
    if not payment or payment.amount_kobo != data.get("amount"):
        return {"ok": True}
    await _finalize_payment(db, payment, data)
    return {"ok": True}

