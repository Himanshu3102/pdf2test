import os
import time
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.db import get_db, SessionLocal
from app.config import settings
from app.models import Exam, Question, User
from app.schemas import (
    ExamAuthoring, ExamUpdate, QuestionAuthoring, UploadResponse, ParsedExam, ExamSettings,
    ExamHistory, AttemptSummary,
)
from app.security import get_current_user, get_owned_exam
from app.services import storage, pdf_extraction
from app.services.parser import parse_text, heuristic_parse, parse_pdf_with_vision
from app.services.llm import LLMError
from app.logging_config import get_logger, log_event

logger = get_logger("exams")

router = APIRouter()


def _exam_to_authoring(exam: Exam) -> ExamAuthoring:
    qs = []
    for q in exam.questions:
        qs.append(QuestionAuthoring(
            id=q.id,
            order_index=q.order_index,
            qtype=q.qtype,
            prompt=q.prompt,
            options=q.options or [],
            answer_key=q.answer_key,
            explanation=q.explanation,
            points=q.points,
            negative_points=q.negative_points,
            tolerance=q.tolerance,
            topic_tags=q.topic_tags or [],
            section=q.section,
            source_page=q.source_page,
            parse_confidence=q.parse_confidence,
            review_status=q.review_status,
        ))
    settings_obj = exam.settings or {}
    try:
        es = ExamSettings.model_validate(settings_obj)
    except Exception:
        es = ExamSettings()
    return ExamAuthoring(
        id=exam.id,
        title=exam.title,
        instructions=exam.instructions,
        status=exam.status,
        settings=es,
        settings_confirmed=exam.settings_confirmed,
        source_filename=exam.source_filename,
        gate_branch=exam.gate_branch,
        questions=qs,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.post("/exams/upload", response_model=UploadResponse)
async def upload_exam(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
):
    t_start = time.perf_counter()
    data = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit.")
    if not storage.validate_pdf_bytes(data):
        raise HTTPException(status_code=400, detail="Invalid PDF file (bad signature).")

    storage_name = storage.save_upload(data, file.filename or "upload.pdf")

    exam = Exam(
        title="Processing...",
        instructions=None,
        source_filename=file.filename,
        source_storage_name=storage_name,
        status="processing",
        settings=ExamSettings().model_dump(),
        settings_confirmed=False,
        owner_id=user.id,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    if background_tasks is not None:
        background_tasks.add_task(_process_upload, exam.id, storage_name)
    else:
        _process_upload(exam.id, storage_name)

    elapsed = round((time.perf_counter() - t_start) * 1000, 1)
    log_event(logger, "upload_accepted", exam_id=exam.id, file_size=len(data), user_id=user.id, duration_ms=elapsed)

    return UploadResponse(
        exam_id=exam.id,
        status=exam.status,
        warnings=[],
        exam=_exam_to_authoring(exam),
    )


def _process_upload(exam_id: str, storage_name: str) -> None:
    db = SessionLocal()
    t_start = time.perf_counter()
    try:
        exam = db.get(Exam, exam_id)
        if exam is None:
            return
        path = storage.get_upload_path(storage_name)

        t0 = time.perf_counter()
        extraction = pdf_extraction.extract_text(path, ocr_enabled=settings.OCR_ENABLED)
        text = pdf_extraction.extraction_to_text(extraction)
        t_extract = round((time.perf_counter() - t0) * 1000, 1)

        if settings.VISION_ENABLED:
            try:
                t0 = time.perf_counter()
                parsed = parse_pdf_with_vision(path)
                parse_warnings = ["Parsed via Gemini vision."]
                t_parse = round((time.perf_counter() - t0) * 1000, 1)
            except Exception as e:
                parsed, parse_warnings = parse_text(text)
                parse_warnings = [f"Vision parse failed: {e}; falling back to text parse."] + (parse_warnings or [])
                t_parse = round((time.perf_counter() - t0) * 1000, 1)
        else:
            t0 = time.perf_counter()
            parsed, parse_warnings = parse_text(text)
            t_parse = round((time.perf_counter() - t0) * 1000, 1)

        warnings = list(dict.fromkeys(list(extraction.warnings) + list(parse_warnings) + (parsed.warnings or [])))

        exam.title = parsed.title or "Untitled Exam"
        exam.instructions = parsed.instructions
        exam.status = "draft"
        for q in list(exam.questions):
            db.delete(q)
        db.flush()
        for idx, pq in enumerate(parsed.questions):
            q = Question(
                exam_id=exam.id,
                order_index=idx,
                qtype=pq.qtype,
                prompt=pq.prompt,
                options=[o.model_dump() for o in pq.options],
                answer_key=pq.answer_key,
                explanation=pq.explanation,
                points=pq.points if pq.points is not None else settings.DEFAULT_CORRECT_POINTS,
                negative_points=pq.negative_points if pq.negative_points is not None else settings.DEFAULT_INCORRECT_POINTS,
                tolerance=pq.tolerance,
                topic_tags=pq.topic_tags or [],
                section=pq.section,
                source_page=pq.source_page,
                parse_confidence=pq.confidence,
                review_status="needs_review",
            )
            db.add(q)
        db.commit()

        elapsed = round((time.perf_counter() - t_start) * 1000, 1)
        log_event(logger, "upload_processed", exam_id=exam.id, status="draft",
                    question_count=len(parsed.questions), used_ocr=extraction.used_ocr,
                    extract_ms=t_extract, parse_ms=t_parse, total_ms=elapsed,
                    warnings=warnings)
    except Exception as e:
        try:
            exam = db.get(Exam, exam_id)
            if exam is not None:
                exam.status = "failed"
                exam.title = "Processing failed"
                exam.instructions = str(e)
                db.commit()
        except Exception:
            pass
        log_event(logger, "upload_failed", level=logging.ERROR, exam_id=exam_id, error=str(e))
    finally:
        db.close()


@router.get("/exams/{exam_id}", response_model=ExamAuthoring)
def get_exam(exam_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _exam_to_authoring(get_owned_exam(exam_id, user, db))


@router.patch("/exams/{exam_id}", response_model=ExamAuthoring)
def update_exam(
    exam_id: str,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exam = get_owned_exam(exam_id, user, db)
    if exam.status not in ("draft",):
        pass

    if payload.title is not None:
        exam.title = payload.title
    if payload.instructions is not None:
        exam.instructions = payload.instructions
    if payload.settings is not None:
        exam.settings = payload.settings.model_dump()
    if payload.settings_confirmed is not None:
        exam.settings_confirmed = payload.settings_confirmed
    if payload.gate_branch is not None:
        exam.gate_branch = payload.gate_branch
    if payload.questions is not None:
        for q in list(exam.questions):
            db.delete(q)
        db.flush()
        for idx, qd in enumerate(payload.questions):
            q_kwargs = {"exam_id": exam.id, "order_index": qd.order_index if qd.order_index is not None else idx}
            if qd.id:
                q_kwargs["id"] = qd.id
            q = Question(
                **q_kwargs,
                qtype=qd.qtype,
                prompt=qd.prompt,
                options=[o.model_dump() for o in qd.options],
                answer_key=qd.answer_key,
                explanation=qd.explanation,
                points=qd.points if qd.points is not None else settings.DEFAULT_CORRECT_POINTS,
                negative_points=qd.negative_points if qd.negative_points is not None else settings.DEFAULT_INCORRECT_POINTS,
                tolerance=qd.tolerance,
                topic_tags=qd.topic_tags or [],
                section=qd.section,
                source_page=qd.source_page,
                parse_confidence=qd.parse_confidence,
                review_status=qd.review_status,
            )
            db.add(q)
    db.commit()
    db.refresh(exam)
    return _exam_to_authoring(exam)


@router.post("/exams/{exam_id}/publish")
def publish_exam(exam_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exam = get_owned_exam(exam_id, user, db)
    if exam.status != "draft":
        raise HTTPException(status_code=400, detail="Exam is not in draft state.")
    if not exam.settings_confirmed:
        raise HTTPException(status_code=400, detail="Settings must be confirmed before publishing.")
    if len(exam.questions) == 0:
        raise HTTPException(status_code=400, detail="Cannot publish an exam with no questions.")
    exam.status = "published"
    db.commit()
    db.refresh(exam)
    return {"exam_id": exam.id, "status": exam.status}


@router.get("/exams/{exam_id}/attempts")
def list_attempts(exam_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models import Attempt
    exam = get_owned_exam(exam_id, user, db)
    attempts = db.query(Attempt).filter(Attempt.exam_id == exam.id).order_by(Attempt.created_at.desc()).all()
    return [
        {
            "attempt_id": a.id,
            "status": a.status,
            "started_at": a.started_at,
            "submitted_at": a.submitted_at,
            "score": a.score,
            "max_score": a.max_score,
            "percentage": a.percentage,
        }
        for a in attempts
    ]


@router.get("/me/exams", response_model=list[ExamHistory])
def my_exams(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models import Attempt
    exams = (
        db.query(Exam)
        .filter(Exam.owner_id == user.id)
        .order_by(Exam.created_at.desc())
        .all()
    )
    out: list[ExamHistory] = []
    for exam in exams:
        attempts = (
            db.query(Attempt)
            .filter(Attempt.exam_id == exam.id)
            .order_by(Attempt.created_at.desc())
            .all()
        )
        out.append(
            ExamHistory(
                id=exam.id,
                title=exam.title,
                status=exam.status,
                created_at=exam.created_at,
                updated_at=exam.updated_at,
                question_count=len(exam.questions or []),
                attempts=[
                    AttemptSummary(
                        attempt_id=a.id,
                        status=a.status,
                        started_at=a.started_at,
                        submitted_at=a.submitted_at,
                        score=a.score,
                        max_score=a.max_score,
                        percentage=a.percentage,
                    )
                    for a in attempts
                ],
            )
        )
    return out
