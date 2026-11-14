from tests.fixtures import make_text_pdf


def _create_exam(client):
    data = make_text_pdf()
    files = {"file": ("sample.pdf", data, "application/pdf")}
    r = client.post("/api/v1/exams/upload", files=files)
    assert r.status_code == 200
    return r.json()["exam_id"]


def test_full_flow_and_no_leak(client):
    exam_id = _create_exam(client)
    # Replace questions with known ones
    questions = [
        {
            "order_index": 0,
            "qtype": "single_choice",
            "prompt": "2+2?",
            "options": [{"id": "A", "text": "3"}, {"id": "B", "text": "4"}],
            "answer_key": "B",
            "explanation": "2+2=4",
            "points": 4.0,
            "negative_points": -1.0,
            "tolerance": None,
            "topic_tags": ["math"],
            "source_page": 1,
            "review_status": "reviewed",
        },
        {
            "order_index": 1,
            "qtype": "numeric",
            "prompt": "pi?",
            "options": [],
            "answer_key": 3.14,
            "explanation": None,
            "points": 2.0,
            "negative_points": 0.0,
            "tolerance": 0.01,
            "topic_tags": ["math"],
            "source_page": 1,
            "review_status": "reviewed",
        },
    ]
    settings = {
        "mode": "exam",
        "duration_minutes": 10,
        "marking": {"correct": 4.0, "incorrect": -1.0, "unanswered": 0.0, "partial_credit": False},
    }
    patch = {"title": "Test Exam", "questions": questions, "settings": settings, "settings_confirmed": True}
    r = client.patch(f"/api/v1/exams/{exam_id}", json=patch)
    assert r.status_code == 200, r.text

    # publish
    r = client.post(f"/api/v1/exams/{exam_id}/publish")
    assert r.status_code == 200, r.text

    # start attempt
    r = client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert r.status_code == 200, r.text
    attempt = r.json()
    attempt_id = attempt["attempt_id"]
    # answer key must not be in taking response
    for q in attempt["questions"]:
        assert "answer_key" not in q

    # get attempt (resume) no answer key
    r = client.get(f"/api/v1/attempts/{attempt_id}")
    assert r.status_code == 200
    for q in r.json()["questions"]:
        assert "answer_key" not in q

    qids = [q["id"] for q in attempt["questions"]]
    # save answers
    r = client.put(f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}", json={"response": "B"})
    assert r.status_code == 200
    # exam mode: no feedback
    assert r.json().get("feedback") is None

    r = client.put(f"/api/v1/attempts/{attempt_id}/answers/{qids[1]}", json={"response": 3.14})
    assert r.status_code == 200

    # submit
    r = client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert r.status_code == 200
    res = r.json()
    assert res["score"] == 6.0
    assert res["max_score"] == 6.0

    # results include answer keys now
    r = client.get(f"/api/v1/attempts/{attempt_id}/results")
    assert r.status_code == 200
    body = r.json()
    assert body["correct_count"] == 2
    for q in body["questions"]:
        assert "answer_key" in q


def test_duplicate_submit(client):
    exam_id = _create_exam(client)
    questions = [{"order_index": 0, "qtype": "single_choice", "prompt": "x?", "options": [{"id": "A", "text": "1"}], "answer_key": "A", "points": 1.0, "negative_points": 0.0, "review_status": "reviewed"}]
    settings = {"mode": "exam", "duration_minutes": None, "marking": {"correct": 1.0, "incorrect": 0.0, "unanswered": 0.0, "partial_credit": False}}
    client.patch(f"/api/v1/exams/{exam_id}", json={"questions": questions, "settings": settings, "settings_confirmed": True})
    client.post(f"/api/v1/exams/{exam_id}/publish")
    r = client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = r.json()["attempt_id"]
    r1 = client.post(f"/api/v1/attempts/{attempt_id}/submit")
    r2 = client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["score"] == r2.json()["score"]
