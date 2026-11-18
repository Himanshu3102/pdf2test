from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import GatePaper, GateSyllabusTopic, User, Exam
from app.security import get_current_user
from app.gate_syllabus import GATE_SYLLABUS, GATE_BRANCHES
from app.logging_config import get_logger, log_event

logger = get_logger("gate")
router = APIRouter()


@router.get("/gate/branches")
def list_branches():
    """List all GATE branches."""
    return [
        {"code": code, "name": name}
        for code, name in sorted(GATE_BRANCHES.items(), key=lambda x: x[1])
    ]


@router.get("/gate/syllabus/{branch}")
def get_syllabus(branch: str, db: Session = Depends(get_db)):
    """Get syllabus topics for a branch."""
    branch = branch.upper()
    if branch not in GATE_BRANCHES:
        raise HTTPException(status_code=404, detail="Unknown branch.")
    # Try DB first
    topics = db.query(GateSyllabusTopic).filter(GateSyllabusTopic.branch == branch).all()
    if topics:
        subjects = {}
        for t in topics:
            subjects.setdefault(t.subject, []).append(t.topic)
        return {
            "branch": branch,
            "branch_name": GATE_BRANCHES[branch],
            "subjects": subjects,
        }
    # Fallback to static syllabus
    static = GATE_SYLLABUS.get(branch)
    if static:
        return {
            "branch": branch,
            "branch_name": static["name"],
            "subjects": static["subjects"],
        }
    return {
        "branch": branch,
        "branch_name": GATE_BRANCHES[branch],
        "subjects": {},
    }


@router.post("/gate/syllabus/seed")
def seed_syllabus(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Seed the syllabus table from static data (idempotent)."""
    count = 0
    for branch, data in GATE_SYLLABUS.items():
        for subject, topics in data["subjects"].items():
            for topic in topics:
                existing = db.query(GateSyllabusTopic).filter(
                    GateSyllabusTopic.branch == branch,
                    GateSyllabusTopic.subject == subject,
                    GateSyllabusTopic.topic == topic,
                ).first()
                if not existing:
                    db.add(GateSyllabusTopic(
                        branch=branch,
                        branch_name=data["name"],
                        subject=subject,
                        topic=topic,
                    ))
                    count += 1
    # Also seed branches without detailed syllabus
    for code, name in GATE_BRANCHES.items():
        if code not in GATE_SYLLABUS:
            existing = db.query(GateSyllabusTopic).filter(GateSyllabusTopic.branch == code).first()
            if not existing:
                db.add(GateSyllabusTopic(
                    branch=code,
                    branch_name=name,
                    subject="General",
                    topic="General",
                ))
                count += 1
    db.commit()
    log_event(logger, "syllabus_seeded", topics_added=count, user_id=user.id)
    return {"topics_added": count}


@router.get("/gate/papers")
def list_papers(
    branch: str | None = Query(None),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """List GATE papers, optionally filtered by branch and year."""
    q = db.query(GatePaper)
    if branch:
        q = q.filter(GatePaper.branch == branch.upper())
    if year:
        q = q.filter(GatePaper.year == year)
    papers = q.order_by(GatePaper.year.desc(), GatePaper.branch).all()
    return [
        {
            "id": p.id,
            "branch": p.branch,
            "branch_name": p.branch_name,
            "year": p.year,
            "paper_type": p.paper_type,
            "title": p.title,
            "source_url": p.source_url,
            "has_solutions": p.has_solutions,
            "question_count": p.question_count,
            "status": p.status,
            "exam_id": p.exam_id,
        }
        for p in papers
    ]


@router.get("/gate/papers/{paper_id}")
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    paper = db.query(GatePaper).filter(GatePaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return {
        "id": paper.id,
        "branch": paper.branch,
        "branch_name": paper.branch_name,
        "year": paper.year,
        "paper_type": paper.paper_type,
        "title": paper.title,
        "source_url": paper.source_url,
        "has_solutions": paper.has_solutions,
        "question_count": paper.question_count,
        "status": paper.status,
        "exam_id": paper.exam_id,
    }


@router.post("/gate/papers")
def create_paper(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Register a GATE paper in the library."""
    branch = payload.get("branch", "").upper()
    if branch not in GATE_BRANCHES:
        raise HTTPException(status_code=422, detail="Unknown branch.")
    year = payload.get("year")
    if not year:
        raise HTTPException(status_code=422, detail="Year is required.")
    paper = GatePaper(
        branch=branch,
        branch_name=GATE_BRANCHES[branch],
        year=year,
        paper_type=payload.get("paper_type", "main"),
        title=payload.get("title", f"GATE {year} - {GATE_BRANCHES[branch]}"),
        source_url=payload.get("source_url"),
        has_solutions=payload.get("has_solutions", False),
        question_count=payload.get("question_count"),
        status=payload.get("status", "available"),
        exam_id=payload.get("exam_id"),
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    log_event(logger, "gate_paper_created", paper_id=paper.id, branch=branch, year=year, user_id=user.id)
    return {"id": paper.id, "title": paper.title}


@router.get("/gate/analytics/{attempt_id}")
def gate_analytics(attempt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Comprehensive analytics for a GATE attempt, grouped by syllabus topic."""
    from app.models import Attempt, AttemptAnswer, Question
    from app.security import get_owned_attempt
    attempt, exam = get_owned_attempt(attempt_id, user, db)

    # Build topic map from syllabus
    syllabus = GATE_SYLLABUS.get(exam.gate_branch if hasattr(exam, 'gate_branch') else None, {})
    subjects = syllabus.get("subjects", {}) if syllabus else {}

    # Group questions by topic tag
    topic_map = {}
    for q in exam.questions:
        tags = q.topic_tags or ["General"]
        for tag in tags:
            if tag not in topic_map:
                topic_map[tag] = {
                    "topic": tag,
                    "subject": None,
                    "total": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                    "score": 0.0,
                    "max_score": 0.0,
                    "time_spent": 0.0,
                    "questions": [],
                }
            t = topic_map[tag]
            t["total"] += 1
            t["max_score"] += q.points or 0

    # Map answer data
    answer_map = {a.question_id: a for a in attempt.answers}
    for q in exam.questions:
        tags = q.topic_tags or ["General"]
        aa = answer_map.get(q.id)
        is_unanswered = aa is None or aa.response is None or aa.response == "" or (isinstance(aa.response, list) and len(aa.response) == 0)
        for tag in tags:
            t = topic_map[tag]
            if aa:
                t["score"] += aa.awarded_points or 0
                t["time_spent"] += aa.time_spent_seconds or 0
                if is_unanswered:
                    t["unanswered"] += 1
                elif aa.is_correct:
                    t["correct"] += 1
                else:
                    t["incorrect"] += 1
            else:
                t["unanswered"] += 1
            t["questions"].append({
                "id": q.id,
                "prompt_preview": (q.prompt or "")[:120],
                "is_correct": aa.is_correct if aa else None,
                "awarded_points": aa.awarded_points if aa else 0,
                "time_spent": aa.time_spent_seconds if aa else 0,
            })

    topics = []
    for t in topic_map.values():
        t["percentage"] = round((t["score"] / t["max_score"]) * 100, 1) if t["max_score"] > 0 else 0
        t["accuracy"] = round((t["correct"] / t["total"]) * 100, 1) if t["total"] > 0 else 0
        topics.append(t)

    topics.sort(key=lambda x: x["percentage"])

    # Subject-level aggregation
    subject_map = {}
    for t in topics:
        # Find which subject this topic belongs to
        subj = "General"
        for s, ts in subjects.items():
            if t["topic"] in ts:
                subj = s
                break
        if subj not in subject_map:
            subject_map[subj] = {
                "subject": subj,
                "total": 0, "correct": 0, "incorrect": 0, "unanswered": 0,
                "score": 0.0, "max_score": 0.0, "time_spent": 0.0,
            }
        s = subject_map[subj]
        s["total"] += t["total"]
        s["correct"] += t["correct"]
        s["incorrect"] += t["incorrect"]
        s["unanswered"] += t["unanswered"]
        s["score"] += t["score"]
        s["max_score"] += t["max_score"]
        s["time_spent"] += t["time_spent"]

    subjects_list = []
    for s in subject_map.values():
        s["percentage"] = round((s["score"] / s["max_score"]) * 100, 1) if s["max_score"] > 0 else 0
        s["accuracy"] = round((s["correct"] / s["total"]) * 100, 1) if s["total"] > 0 else 0
        subjects_list.append(s)
    subjects_list.sort(key=lambda x: x["percentage"])

    return {
        "attempt_id": attempt_id,
        "exam_title": exam.title,
        "branch": getattr(exam, 'gate_branch', None),
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percentage": attempt.percentage,
        "correct_count": sum(1 for a in attempt.answers if a.is_correct),
        "incorrect_count": sum(1 for a in attempt.answers if a.is_correct is False),
        "unanswered_count": sum(1 for a in attempt.answers if a.response is None or a.response == "" or (isinstance(a.response, list) and len(a.response) == 0)),
        "total_time_seconds": sum(a.time_spent_seconds or 0 for a in attempt.answers),
        "topics": topics,
        "subjects": subjects_list,
        "strongest_topic": topics[-1] if topics else None,
        "weakest_topic": topics[0] if topics else None,
        "strongest_subject": subjects_list[-1] if subjects_list else None,
        "weakest_subject": subjects_list[0] if subjects_list else None,
    }
