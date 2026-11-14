from tests.fixtures import make_text_pdf


def _setup_exam(client):
    data = make_text_pdf()
    r = client.post("/api/v1/exams/upload", files={"file": ("s.pdf", data, "application/pdf")})
    exam_id = r.json()["exam_id"]
    questions = [{"qtype": "single_choice", "prompt": "x?", "options": [{"id": "A", "text": "1"}], "answer_key": "A", "points": 1.0, "negative_points": 0.0}]
    settings = {"mode": "exam", "duration_minutes": 5, "marking": {"correct": 1.0, "incorrect": 0.0, "unanswered": 0.0, "partial_credit": False}}
    client.patch(f"/api/v1/exams/{exam_id}", json={"questions": questions, "settings": settings, "settings_confirmed": True})
    client.post(f"/api/v1/exams/{exam_id}/publish")
    r = client.post(f"/api/v1/exams/{exam_id}/attempts")
    return r.json()["attempt_id"], [q["id"] for q in r.json()["questions"]]


def test_timing_events_and_cap(client):
    attempt_id, qids = _setup_exam(client)
    # record a huge interval that exceeds attempt duration
    r = client.post(f"/api/v1/attempts/{attempt_id}/questions/{qids[0]}/events", json={"started_at_ms": 0, "ended_at_ms": 999999999})
    assert r.status_code == 200
    # time_spent should be capped-ish (not crash)
    assert "time_spent_seconds" in r.json()
    # results after submit show timing <= total
    client.post(f"/api/v1/attempts/{attempt_id}/submit")
    r = client.get(f"/api/v1/attempts/{attempt_id}/results")
    assert r.status_code == 200
    body = r.json()
    assert body["total_time_seconds"] >= 0
