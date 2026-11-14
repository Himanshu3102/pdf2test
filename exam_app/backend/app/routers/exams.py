import os
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
    # size check
    data = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit.")
    if not storage.validate_pdf_bytes(data):
        raise HTTPException(status_code=400, detail="Invalid PDF file (bad signature).")

    storage_name = storage.save_upload(data, file.filename or "upload.pdf")

    # Create exam immediately; process extraction in the background so the
    # request does not time out on free hosting tiers.
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

    return UploadResponse(
        exam_id=exam.id,
        status=exam.status,
        warnings=[],
        exam=_exam_to_authoring(exam),
    )


def _process_upload(exam_id: str, storage_name: str) -> None:
    db = SessionLocal()
    try:
        exam = db.get(Exam, exam_id)
        if exam is None:
            return
        path = storage.get_upload_path(storage_name)
        extraction = pdf_extraction.extract_text(path, ocr_enabled=settings.OCR_ENABLED)
        text = pdf_extraction.extraction_to_text(extraction)

        if extraction.used_ocr and settings.VISION_ENABLED:
            try:
                parsed = parse_pdf_with_vision(path)
                parse_warnings = ["Parsed from scanned PDF via Gemini vision."]
            except Exception as e:
                parsed = heuristic_parse(text)
                parse_warnings = [f"Vision parse failed: {e}; falling back to local OCR heuristic."]
        else:
            parsed, parse_warnings = parse_text(text)

        warnings = list(dict.fromkeys(list(extraction.warnings) + list(parse_warnings) + (parsed.warnings or [])))

        exam.title = parsed.title or "Untitled Exam"
        exam.instructions = parsed.instructions
        exam.status = "draft"
        # replace any existing questions
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
        # allow settings edits only draft; but allow? keep draft-only for questions
        pass

    if payload.title is not None:
        exam.title = payload.title
    if payload.instructions is not None:
        exam.instructions = payload.instructions
    if payload.settings is not None:
        exam.settings = payload.settings.model_dump()
    if payload.settings_confirmed is not None:
        exam.settings_confirmed = payload.settings_confirmed
    if payload.questions is not None:
        # replace all
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
                points=qd.points,
                negative_points=qd.negative_points,
                tolerance=qd.tolerance,
                topic_tags=qd.topic_tags or [],
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
        raise HTTPException(status_code=400, detail="Only draft exams can be published.")
    if not exam.settings_confirmed:
        raise HTTPException(status_code=400, detail="Settings must be confirmed before publishing.")
    if not exam.questions:
        raise HTTPException(status_code=400, detail="Exam has no questions.")
    # validate answer keys? warn only
    exam.status = "published"
    db.commit()
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
    """Every exam owned by the current user, with a compact attempt history."""
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
