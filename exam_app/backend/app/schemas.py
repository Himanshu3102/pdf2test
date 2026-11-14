from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ---- Question ----
class OptionIn(BaseModel):
    id: str
    text: str


class OptionOut(OptionIn):
    pass


QuestionType = Literal["single_choice", "multiple_select", "numeric"]


class QuestionAuthoring(BaseModel):
    """Authoring view: includes answer key."""
    id: str | None = None
    order_index: int | None = None
    qtype: QuestionType
    prompt: str
    options: list[OptionOut] = []
    answer_key: Any = None
    explanation: str | None = None
    points: float = 4.0
    negative_points: float = 0.0
    tolerance: float | None = None
    topic_tags: list[str] = []
    source_page: int | None = None
    parse_confidence: float | None = None
    review_status: str = "needs_review"


class QuestionTaking(BaseModel):
    """Taking view: no answer key."""
    id: str
    order_index: int
    qtype: QuestionType
    prompt: str
    options: list[OptionOut] = []
    points: float = 4.0
    negative_points: float = 0.0
    topic_tags: list[str] = []
    source_page: int | None = None


class QuestionReview(BaseModel):
    """Review view: includes answer key + correctness."""
    id: str
    order_index: int
    qtype: QuestionType
    prompt: str
    options: list[OptionOut] = []
    answer_key: Any = None
    explanation: str | None = None
    points: float = 4.0
    awarded_points: float | None = None
    is_correct: bool | None = None
    user_response: Any = None
    topic_tags: list[str] = []
    source_page: int | None = None
    time_spent_seconds: float = 0.0


# ---- Exam settings ----
class MarkingSettings(BaseModel):
    correct: float = 4.0
    incorrect: float = -1.0
    unanswered: float = 0.0
    partial_credit: bool = False


class ExamSettings(BaseModel):
    mode: Literal["exam", "practice"] = "exam"
    duration_minutes: int | None = None  # None = untimed
    marking: MarkingSettings = Field(default_factory=MarkingSettings)
    allow_hints: bool | None = None  # derived from mode if None


class ExamAuthoring(BaseModel):
    id: str
    title: str
    instructions: str | None = None
    status: str
    settings: ExamSettings
    settings_confirmed: bool
    source_filename: str | None = None
    questions: list[QuestionAuthoring] = []
    created_at: datetime
    updated_at: datetime


class ExamTakingMeta(BaseModel):
    id: str
    title: str
    instructions: str | None = None
    settings: ExamSettings


class ExamUpdate(BaseModel):
    title: str | None = None
    instructions: str | None = None
    settings: ExamSettings | None = None
    settings_confirmed: bool | None = None
    questions: list[QuestionAuthoring] | None = None


class QuestionCreate(BaseModel):
    qtype: QuestionType = "single_choice"
    prompt: str
    options: list[OptionIn] = []
    answer_key: Any = None
    explanation: str | None = None
    points: float = 4.0
    negative_points: float = 0.0
    tolerance: float | None = None
    topic_tags: list[str] = []
    source_page: int | None = None


# ---- Parsed (LLM) ----
class ParsedOption(BaseModel):
    id: str
    text: str


class ParsedQuestion(BaseModel):
    qtype: QuestionType = "single_choice"
    prompt: str
    options: list[ParsedOption] = []
    answer_key: Any = None
    explanation: str | None = None
    points: float | None = None
    negative_points: float | None = None
    tolerance: float | None = None
    topic_tags: list[str] = []
    source_page: int | None = None
    confidence: float = 0.5
    warnings: list[str] = []


class ParsedExam(BaseModel):
    title: str | None = None
    instructions: str | None = None
    questions: list[ParsedQuestion] = []
    warnings: list[str] = []


# ---- Attempts ----
class AttemptStartResponse(BaseModel):
    attempt_id: str
    exam: ExamTakingMeta
    questions: list[QuestionTaking]
    started_at: datetime
    deadline: datetime | None = None
    answers: dict[str, Any] = {}  # question_id -> response


class AttemptResumeResponse(AttemptStartResponse):
    status: str = "in_progress"
    time_remaining_seconds: int | None = None
    marked_for_review: dict[str, bool] = {}


class SaveAnswerRequest(BaseModel):
    response: Any = None
    marked_for_review: bool | None = None


class SaveAnswerResponse(BaseModel):
    saved: bool = True
    last_saved_at: datetime
    feedback: dict[str, Any] | None = None


class TimingEventRequest(BaseModel):
    started_at_ms: int
    ended_at_ms: int


class SubmitResponse(BaseModel):
    attempt_id: str
    status: str
    score: float
    max_score: float
    percentage: float
    submitted_at: datetime


class ResultsResponse(BaseModel):
    attempt_id: str
    exam_title: str
    status: str
    started_at: datetime
    submitted_at: datetime | None = None
    total_time_seconds: float
    score: float
    max_score: float
    percentage: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    questions: list[QuestionReview]
    by_topic: dict[str, dict[str, float]] = {}
    timing_per_question: dict[str, float] = {}


class ChatRequest(BaseModel):
    message: str | None = None
    mode: Literal["hint", "solution"] = "hint"
    graduated: bool = False


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    chat_history: list[dict[str, Any]] = []


# ---- Auth & history ----
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AttemptSummary(BaseModel):
    attempt_id: str
    status: str
    started_at: datetime
    submitted_at: datetime | None = None
    score: float | None = None
    max_score: float | None = None
    percentage: float | None = None


class ExamHistory(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    question_count: int
    attempts: list[AttemptSummary] = []



class UploadResponse(BaseModel):
    exam_id: str
    status: str
    warnings: list[str] = []
    exam: ExamAuthoring


class ErrorResponse(BaseModel):
    detail: str
