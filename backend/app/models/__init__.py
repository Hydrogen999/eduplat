import enum, uuid
from datetime import datetime, date, timezone
from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, Date, ForeignKey,
    Enum as SAEnum, UniqueConstraint, Index, JSON, Numeric
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.now(timezone.utc)

class Role(str, enum.Enum):
    STUDENT = "student"
    CONTENT_EDITOR = "content_editor"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"

class PurchaseKind(str, enum.Enum):
    TOPIC = "topic"
    EXAM = "exam"

class ExamCategory(str, enum.Enum):
    WAEC = "waec"
    NECO = "neco"
    JAMB = "jamb"
    JUNIOR = "junior"

class AttemptStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"

class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30))
    hashed_password: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date] = mapped_column(Date)
    school_name: Mapped[str | None] = mapped_column(String(255))
    class_level: Mapped[str] = mapped_column(String(50))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.STUDENT, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    purchases: Mapped[list["TopicPurchase"]] = relationship(back_populates="user")
    attempts: Mapped[list["ExamAttempt"]] = relationship(back_populates="user")

class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("department_id", "slug", name="uq_subject_dept_slug"),)

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    slug: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    price_kobo: Mapped[int] = mapped_column(Integer, default=200_000)
    is_free_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("subject_id", "slug", name="uq_topic_subject_slug"),)

class LearningMaterial(Base):
    __tablename__ = "learning_materials"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), unique=True)
    content_blocks: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    kind: Mapped[PurchaseKind] = mapped_column(SAEnum(PurchaseKind))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    amount_kobo: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, index=True)
    gateway: Mapped[str] = mapped_column(String(30), default="paystack")
    gateway_reference: Mapped[str | None] = mapped_column(String(100), index=True)
    gateway_payload: Mapped[dict | None] = mapped_column(JSON)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class TopicPurchase(Base):
    __tablename__ = "topic_purchases"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic"),)
    user: Mapped["User"] = relationship(back_populates="purchases")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), index=True)
    exam_category: Mapped[ExamCategory] = mapped_column(SAEnum(ExamCategory), index=True)
    difficulty: Mapped[Difficulty] = mapped_column(SAEnum(Difficulty), default=Difficulty.MEDIUM)
    question_type: Mapped[str] = mapped_column(String(20), default="mcq")
    year: Mapped[int | None] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    options: Mapped[list] = mapped_column(JSON)
    correct_key: Mapped[str] = mapped_column(String(5))
    explanation: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (Index("ix_q_subject_cat", "subject_id", "exam_category"),)

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    exam_category: Mapped[ExamCategory] = mapped_column(SAEnum(ExamCategory))
    subject_ids: Mapped[list] = mapped_column(JSON)
    question_count: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(SAEnum(AttemptStatus), default=AttemptStatus.PENDING_PAYMENT, index=True)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"))
    question_ids: Mapped[list | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score_correct: Mapped[int | None] = mapped_column(Integer)
    score_total: Mapped[int | None] = mapped_column(Integer)
    score_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped["User"] = relationship(back_populates="attempts")
    responses: Mapped[list["ExamResponse"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")

class ExamResponse(Base):
    __tablename__ = "exam_responses"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    selected_key: Mapped[str | None] = mapped_column(String(5))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    attempt: Mapped["ExamAttempt"] = relationship(back_populates="responses")
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(100))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)