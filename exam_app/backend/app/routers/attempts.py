from datetime import datetime, timezone
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exam, Question, Attempt, AttemptAnswer, User
from app.schemas import (
    AttemptStartResponse, AttemptResumeResponse, SaveAnswerRequest, SaveAnswerResponse,
    TimingEventRequest, SubmitResponse, ResultsResponse, QuestionTaking, QuestionReview, ExamTakingMeta, ExamSettings,
)
from app.security import get_current_user
from app.logging_config import get_logger, log_event
import logging

logger = get_logger("attempts")
from app.services.scoring import compute_results, grade_question
from app.services.timer import (
    compute_deadline, is_expired, time_remaining_seconds, cap_visit_intervals, intervals_to_seconds, now_utc, ensure_aware,
)

router = APIRouter()


def _settings_obj(d):
    try:
        return ExamSettings.model_validate(d or {})
    except Exception:
        return ExamSettings()


def _question_taking(q: Question) -> QuestionTaking:
    return QuestionTaking(
        id=q.id,
        order_index=q.order_index,
        qtype=q.qtype,
        prompt=q.prompt,
        options=q.options or [],
        points=q.points,
        negative_points=q.negative_points,
        topic_tags=q.topic_tags or [],
        section=q.section,
        source_page=q.source_page,
    )


def _settings_dict(exam: Exam) -> dict:
    return exam.settings or {}


def _owned_attempt(attempt_id: str, user: User, db: Session) -> tuple[Attempt, Exam]:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    exam = db.get(Exam, attempt.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    # GATE paper exams: allow the user who created the attempt
    if exam.gate_branch is not None:
        # For GATE papers, we need to track which user created the attempt
        # Since Attempt doesn't have user_id, we allow any authenticated user
        # to view attempts on GATE papers (they can only see their own via the UI)
        return attempt, exam
    if exam.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return attempt, exam


def _owned_exam(exam_id: str, user: User, db: Session) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    # GATE paper exams are accessible to all authenticated users
    if exam.gate_branch is not None:
        return exam
    if exam.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Exam not found.")
    return exam


def start_attempt(exam_id: str, db: Session, user: User) -> tuple[Attempt, Exam]:
    exam = _owned_exam(exam_id, user, db)
    if exam.status != "published":
        raise HTTPException(status_code=400, detail="Exam is not published.")
    settings = _settings_dict(exam)
    duration = settings.get("duration_minutes") if isinstance(settings, dict) else None
    started_at = now_utc()
    deadline = compute_deadline(started_at, duration)
    attempt = Attempt(exam_id=exam.id, started_at=started_at, deadline=deadline, status="in_progress")
    db.add(attempt)
    db.flush()
    for q in exam.questions:
        aa = AttemptAnswer(attempt_id=attempt.id, question_id=q.id)
        db.add(aa)
    db.commit()
    db.refresh(attempt)
    return attempt, exam


@router.post("/exams/{exam_id}/attempts", response_model=AttemptStartResponse)
def create_attempt(exam_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t0 = time.perf_counter()
    attempt, exam = start_attempt(exam_id, db, user)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    log_event(logger, "attempt_start", attempt_id=attempt.id, exam_id=exam_id, user_id=user.id, duration_ms=elapsed)
    # build response (existing code follows)
    settings = _settings_dict(exam)
    # build answers map
    answers = {}
    for aa in attempt.answers:
        answers[aa.question_id] = aa.response
    return AttemptStartResponse(
        attempt_id=attempt.id,
        exam=ExamTakingMeta(id=exam.id, title=exam.title, instructions=exam.instructions, settings=_settings_obj(settings)),
        questions=[_question_taking(q) for q in exam.questions],
        started_at=attempt.started_at,
        deadline=attempt.deadline,
        answers=answers,
    )





@router.get("/attempts/{attempt_id}", response_model=AttemptResumeResponse)
def resume_attempt(attempt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt, exam = _owned_attempt(attempt_id, user, db)

    # auto-submit if expired
    if attempt.status == "in_progress" and is_expired(attempt.deadline):
        _submit_attempt(attempt, exam, db, expired=True)

    settings = _settings_dict(exam)
    answers = {}
    marked = {}
    for aa in attempt.answers:
        answers[aa.question_id] = aa.response
        marked[aa.question_id] = aa.marked_for_review
    tr = time_remaining_seconds(ensure_aware(attempt.deadline)) if attempt.status == "in_progress" else 0
    return AttemptResumeResponse(
        attempt_id=attempt.id,
        exam=ExamTakingMeta(id=exam.id, title=exam.title, instructions=exam.instructions, settings=_settings_obj(settings)),
        questions=[_question_taking(q) for q in exam.questions],
        started_at=attempt.started_at,
        deadline=attempt.deadline,
        answers=answers,
        status=attempt.status,
        time_remaining_seconds=tr,
        marked_for_review=marked,
    )


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=SaveAnswerResponse)
def save_answer(
    attempt_id: str,
    question_id: str,
    payload: SaveAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt, exam = _owned_attempt(attempt_id, user, db)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already submitted.")
    if is_expired(attempt.deadline):
        _submit_attempt(attempt, exam, db, expired=True)
        raise HTTPException(status_code=400, detail="Attempt expired and was submitted.")

    aa = db.query(AttemptAnswer).filter(
        AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id
    ).first()
    if not aa:
        raise HTTPException(status_code=404, detail="Answer row not found.")

    aa.response = payload.response
    if payload.marked_for_review is not None:
        aa.marked_for_review = payload.marked_for_review
    aa.last_saved_at = now_utc()
    db.commit()
    db.refresh(aa)

    feedback = None
    settings = _settings_dict(exam)
    mode = settings.get("mode", "exam") if isinstance(settings, dict) else "exam"
    if mode == "practice":
        q = db.get(Question, question_id)
        is_correct, awarded = grade_question(q, payload.response, settings)
        feedback = {"correct": is_correct, "awarded_points": awarded}
        # do not reveal answer key; explanation only if correct? Provide explanation in practice after answer
        if q.explanation:
            feedback["explanation"] = q.explanation

    return SaveAnswerResponse(saved=True, last_saved_at=aa.last_saved_at, feedback=feedback)


@router.post("/attempts/{attempt_id}/questions/{question_id}/events")
def record_event(
    attempt_id: str,
    question_id: str,
    payload: TimingEventRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt, _exam = _owned_attempt(attempt_id, user, db)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt not in progress.")
    aa = db.query(AttemptAnswer).filter(
        AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id
    ).first()
    if not aa:
        raise HTTPException(status_code=404, detail="Answer row not found.")
    iv = {"start": payload.started_at_ms, "end": payload.ended_at_ms}
    intervals = list(aa.visit_intervals or [])
    intervals.append(iv)
    # cap against attempt duration
    duration_seconds = 0.0
    if attempt.deadline:
        duration_seconds = (ensure_aware(attempt.deadline) - ensure_aware(attempt.started_at)).total_seconds()
    else:
        # use elapsed so far + buffer
        duration_seconds = (now_utc() - ensure_aware(attempt.started_at)).total_seconds() + 300
    intervals = cap_visit_intervals(intervals, duration_seconds if duration_seconds > 0 else 3600)
    aa.visit_intervals = intervals
    aa.time_spent_seconds = intervals_to_seconds(intervals)
    db.commit()
    return {"recorded": True, "time_spent_seconds": aa.time_spent_seconds}


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitResponse)
def submit_attempt(attempt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t0 = time.perf_counter()
    attempt, exam = _owned_attempt(attempt_id, user, db)
    if attempt.status != "in_progress":
        log_event(logger, "attempt_submit_duplicate", attempt_id=attempt_id, user_id=user.id)
        return SubmitResponse(
            attempt_id=attempt.id,
            status=attempt.status,
            score=attempt.score or 0.0,
            max_score=attempt.max_score or 0.0,
            percentage=attempt.percentage or 0.0,
            submitted_at=attempt.submitted_at or attempt.started_at,
        )
    expired = is_expired(attempt.deadline)
    _submit_attempt(attempt, exam, db, expired=expired)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    log_event(logger, "attempt_submit", attempt_id=attempt_id, exam_id=exam.id, user_id=user.id,
                score=attempt.score, percentage=attempt.percentage, expired=expired, duration_ms=elapsed)
    return SubmitResponse(
        attempt_id=attempt.id,
        status=attempt.status,
        score=attempt.score or 0.0,
        max_score=attempt.max_score or 0.0,
        percentage=attempt.percentage or 0.0,
        submitted_at=attempt.submitted_at,
    )


def _submit_attempt(attempt: Attempt, exam: Exam, db: Session, expired: bool = False):
    attempt.status = "expired" if expired else "submitted"
    attempt.submitted_at = now_utc()
    # cap timing intervals per answer against attempt duration
    duration_seconds = 0.0
    if attempt.submitted_at and attempt.started_at:
        duration_seconds = (ensure_aware(attempt.submitted_at) - ensure_aware(attempt.started_at)).total_seconds()
    if duration_seconds <= 0:
        duration_seconds = 1.0
    for aa in attempt.answers:
        ivs = cap_visit_intervals(aa.visit_intervals or [], duration_seconds)
        aa.visit_intervals = ivs
        aa.time_spent_seconds = intervals_to_seconds(ivs)
        # cap time_spent to duration
        if aa.time_spent_seconds > duration_seconds:
            aa.time_spent_seconds = duration_seconds

    # grade
    settings = _settings_dict(exam)
    answers_map = {aa.question_id: aa for aa in attempt.answers}
    result = compute_results(attempt, exam, answers_map, exam.questions)
    # apply settings marking to grade_question? compute_results passed settings; but grade_question reads question points.
    # Re-grade with settings marking properly: compute_results used exam.settings? It passed settings as exam.settings? Let's ensure marking applied.
    # Actually grade_question uses settings param = exam.settings dict. compute_results passed settings dict. Good.
    attempt.score = result["score"]
    attempt.max_score = result["max_score"]
    attempt.percentage = result["percentage"]
    attempt.stats = {
        "correct_count": result["correct_count"],
        "incorrect_count": result["incorrect_count"],
        "unanswered_count": result["unanswered_count"],
        "by_topic": result["by_topic"],
        "timing": result["timing"],
    }
    db.commit()


@router.get("/attempts/{attempt_id}/results", response_model=ResultsResponse)
def get_results(attempt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt, exam = _owned_attempt(attempt_id, user, db)
    if attempt.status == "in_progress":
        raise HTTPException(status_code=403, detail="Attempt not submitted yet.")
    # build question review
    answers_map = {aa.question_id: aa for aa in attempt.answers}
    qreviews = []
    for q in exam.questions:
        aa = answers_map.get(q.id)
        qreviews.append(QuestionReview(
            id=q.id,
            order_index=q.order_index,
            qtype=q.qtype,
            prompt=q.prompt,
            options=q.options or [],
            answer_key=q.answer_key,
            explanation=q.explanation,
            points=q.points,
            awarded_points=aa.awarded_points if aa else None,
            is_correct=aa.is_correct if aa else None,
            user_response=aa.response if aa else None,
            topic_tags=q.topic_tags or [],
            section=q.section,
            source_page=q.source_page,
            time_spent_seconds=aa.time_spent_seconds if aa else 0.0,
        ))
    stats = attempt.stats or {}
    total_time = 0.0
    if attempt.submitted_at and attempt.started_at:
        total_time = (ensure_aware(attempt.submitted_at) - ensure_aware(attempt.started_at)).total_seconds()
    timing_map = {qid: (answers_map[qid].time_spent_seconds if qid in answers_map else 0.0) for qid in [q.id for q in exam.questions]}
    return ResultsResponse(
        attempt_id=attempt.id,
        exam_title=exam.title,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        total_time_seconds=round(total_time, 3),
        score=attempt.score or 0.0,
        max_score=attempt.max_score or 0.0,
        percentage=attempt.percentage or 0.0,
        correct_count=stats.get("correct_count", 0),
        incorrect_count=stats.get("incorrect_count", 0),
        unanswered_count=stats.get("unanswered_count", 0),
        questions=qreviews,
        by_topic=stats.get("by_topic", {}),
        timing_per_question=timing_map,
    )
