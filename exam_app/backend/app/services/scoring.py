from typing import Any
from datetime import datetime, timezone


def grade_question(question, response, settings) -> tuple[bool | None, float]:
    """Return (is_correct, awarded_points)."""
    qtype = question.qtype
    marking = settings.get("marking", {}) if isinstance(settings, dict) else getattr(settings, "marking", {}) if hasattr(settings, "marking") else {}
    # normalize marking
    if hasattr(marking, "model_dump"):
        marking = marking.model_dump()
    correct_pts = marking.get("correct", 4.0) if isinstance(marking, dict) else 4.0
    incorrect_pts = marking.get("incorrect", -1.0) if isinstance(marking, dict) else -1.0
    unanswered_pts = marking.get("unanswered", 0.0) if isinstance(marking, dict) else 0.0
    partial = marking.get("partial_credit", False) if isinstance(marking, dict) else False

    # use question-level points if set
    q_points = getattr(question, "points", None)
    if q_points is None and isinstance(question, dict):
        q_points = question.get("points")
    if q_points is not None:
        correct_pts = q_points
    q_neg = getattr(question, "negative_points", None)
    if q_neg is None and isinstance(question, dict):
        q_neg = question.get("negative_points")
    if q_neg is not None:
        incorrect_pts = q_neg

    ak = question.answer_key if not isinstance(question, dict) else question.get("answer_key")
    tol = question.tolerance if not isinstance(question, dict) else question.get("tolerance")

    # unanswered
    if response is None or response == "" or response == [] or response == {}:
        return None, unanswered_pts

    if qtype == "single_choice":
        is_correct = (str(response).strip().lower() == str(ak).strip().lower())
        return is_correct, (correct_pts if is_correct else incorrect_pts)

    if qtype == "multiple_select":
        resp_set = set(str(x).strip().lower() for x in (response if isinstance(response, list) else [response]))
        key_set = set(str(x).strip().lower() for x in (ak if isinstance(ak, list) else [ak]))
        if resp_set == key_set:
            return True, correct_pts
        if partial:
            # partial credit: proportion of correct selections minus wrong
            correct_sel = len(resp_set & key_set)
            wrong_sel = len(resp_set - key_set)
            total = len(key_set) if key_set else 1
            frac = max(0.0, (correct_sel - wrong_sel) / total)
            return False, correct_pts * frac
        return False, incorrect_pts

    if qtype == "numeric":
        try:
            val = float(response)
            exp = float(ak)
        except (TypeError, ValueError):
            return False, incorrect_pts
        tolerance = tol if tol is not None else 0.01
        # tolerance as absolute or relative? treat as absolute; if <1 and exp large, maybe relative
        if abs(val - exp) <= tolerance:
            return True, correct_pts
        # also support relative tolerance (1%)
        if exp != 0 and abs(val - exp) / abs(exp) <= 0.01 and tolerance < 1:
            return True, correct_pts
        return False, incorrect_pts

    return None, 0.0


def compute_results(attempt, exam, answers_map, questions) -> dict:
    score = 0.0
    max_score = 0.0
    correct = 0
    incorrect = 0
    unanswered = 0
    per_question = {}
    by_topic: dict[str, dict[str, float]] = {}
    timing: dict[str, float] = {}

    qmap = {q.id if not isinstance(q, dict) else q["id"]: q for q in questions}

    for q in questions:
        qid = q.id if not isinstance(q, dict) else q["id"]
        pts = q.points if not isinstance(q, dict) else q.get("points", 4.0)
        max_score += pts
        ans = answers_map.get(qid)
        response = ans.response if ans is not None and hasattr(ans, "response") else (ans.get("response") if isinstance(ans, dict) else None)
        is_correct, awarded = grade_question(q, response, exam.settings if hasattr(exam, "settings") else exam.get("settings", {}))
        if ans is not None:
            if hasattr(ans, "is_correct"):
                ans.is_correct = is_correct
                ans.awarded_points = awarded
            if hasattr(ans, "time_spent_seconds"):
                timing[qid] = ans.time_spent_seconds
        score += awarded
        if response is None or response == "" or response == [] or response == {}:
            unanswered += 1
        elif is_correct:
            correct += 1
        else:
            incorrect += 1
        per_question[qid] = {"is_correct": is_correct, "awarded": awarded}
        # topic
        tags = q.topic_tags if not isinstance(q, dict) else q.get("topic_tags", [])
        for tag in (tags or []):
            by_topic.setdefault(tag, {"correct": 0, "total": 0, "score": 0.0})
            by_topic[tag]["total"] += 1
            if is_correct:
                by_topic[tag]["correct"] += 1
            by_topic[tag]["score"] += awarded

    total = len(questions) or 1
    percentage = (score / max_score * 100) if max_score else 0.0
    return {
        "score": round(score, 4),
        "max_score": round(max_score, 4),
        "percentage": round(percentage, 2),
        "correct_count": correct,
        "incorrect_count": incorrect,
        "unanswered_count": unanswered,
        "by_topic": by_topic,
        "timing": timing,
    }
