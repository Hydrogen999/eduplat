from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ExamAttempt, Question, ExamResponse, AttemptStatus

async def mark_attempt(db: AsyncSession, attempt: ExamAttempt) -> None:
    if attempt.status == AttemptStatus.SUBMITTED:
        return

    questions = (await db.scalars(
        select(Question).where(Question.id.in_(attempt.question_ids))
    )).all()
    qmap = {q.id: q for q in questions}

    responses = (await db.scalars(
        select(ExamResponse).where(ExamResponse.attempt_id == attempt.id)
    )).all()
    rmap = {r.question_id: r for r in responses}

    correct = 0
    for qid in attempt.question_ids:
        q = qmap.get(qid)
        if not q:
            continue
        r = rmap.get(qid)
        is_correct = bool(r and r.selected_key == q.correct_key)
        if r:
            r.is_correct = is_correct
        else:
            db.add(ExamResponse(
                attempt_id=attempt.id,
                question_id=qid,
                selected_key=None,
                is_correct=False,
            ))
        if is_correct:
            correct += 1

    total = len(attempt.question_ids)
    attempt.score_correct = correct
    attempt.score_total = total
    attempt.score_percent = round(correct / total * 100, 2) if total else 0.0
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = datetime.now(timezone.utc)
    await db.flush()