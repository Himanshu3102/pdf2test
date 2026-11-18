import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), default="Untitled Exam")
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_storage_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/published/archived
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    settings_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    gate_branch: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    gate_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate_paper_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("gate_papers.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="exam", cascade="all, delete-orphan", order_by="Question.order_index"
    )
    attempts: Mapped[list["Attempt"]] = relationship("Attempt", back_populates="exam", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    qtype: Mapped[str] = mapped_column(String(32))  # single_choice, multiple_select, numeric
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)  # [{id, text}]
    answer_key: Mapped[object] = mapped_column(JSON)  # private
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=4.0)
    negative_points: Mapped[float] = mapped_column(Float, default=0.0)
    tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_tags: Mapped[list] = mapped_column(JSON, default=list)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate_branch: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    gate_topic: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    gate_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate_question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="questions")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")  # in_progress/submitted/expired
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    answers: Mapped[list["AttemptAnswer"]] = relationship("AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="attempt", cascade="all, delete-orphan")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    response: Mapped[object | None] = mapped_column(JSON, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    awarded_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    visit_intervals: Mapped[list] = mapped_column(JSON, default=list)
    time_spent_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    last_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt: Mapped["Attempt"] = relationship("Attempt", back_populates="answers")
    question: Mapped["Question"] = relationship("Question")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    attempt: Mapped["Attempt"] = relationship("Attempt", back_populates="chat_messages")


class GateSyllabusTopic(Base):
    __tablename__ = "gate_syllabus_topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    branch: Mapped[str] = mapped_column(String(8), index=True)  # CS, EC, etc.
    branch_name: Mapped[str] = mapped_column(String(128))
    subject: Mapped[str] = mapped_column(String(128), index=True)
    topic: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GatePaper(Base):
    __tablename__ = "gate_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    branch: Mapped[str] = mapped_column(String(8), index=True)
    branch_name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer, index=True)
    paper_type: Mapped[str] = mapped_column(String(32), default="main")  # main, session1, session2
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    has_solutions: Mapped[bool] = mapped_column(Boolean, default=False)
    question_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="available")  # available/processing/ready
    exam_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exams.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    exam: Mapped["Exam | None"] = relationship("Exam", foreign_keys=[exam_id])
