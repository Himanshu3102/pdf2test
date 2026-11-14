from tests.fixtures import make_text_pdf


def _setup(client, mode="practice"):
    data = make_text_pdf()
    r = client.post("/api/v1/exams/upload", files={"file": ("s.pdf", data, "application/pdf")})
    exam_id = r.json()["exam_id"]
    import time
    for _ in range(60):
        rr = client.get(f"/api/v1/exams/{exam_id}")
        if rr.json()["status"] != "processing":
            break
        time.sleep(0.5)
    questions = [{"qtype": "single_choice", "prompt": "x?", "options": [{"id": "A", "text": "1"}], "answer_key": "A", "points": 1.0, "negative_points": 0.0, "explanation": "because"}]
    settings = {"mode": mode, "duration_minutes": None, "marking": {"correct": 1.0, "incorrect": 0.0, "unanswered": 0.0, "partial_credit": False}}
    client.patch(f"/api/v1/exams/{exam_id}", json={"questions": questions, "settings": settings, "settings_confirmed": True})
    client.post(f"/api/v1/exams/{exam_id}/publish")
    r = client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = r.json()["attempt_id"]
    qid = r.json()["questions"][0]["id"]
    return attempt_id, qid


def test_exam_mode_chat_rejected(client):
    attempt_id, qid = _setup(client, mode="exam")
    r = client.post(f"/api/v1/attempts/{attempt_id}/questions/{qid}/chat", json={"mode": "hint"})
    assert r.status_code == 403


def test_practice_chat_requires_answer(client):
    attempt_id, qid = _setup(client, mode="practice")
    r = client.post(f"/api/v1/attempts/{attempt_id}/questions/{qid}/chat", json={"mode": "hint"})
    assert r.status_code == 403


def test_practice_chat_with_mocked_llm(client, monkeypatch):
    attempt_id, qid = _setup(client, mode="practice")
    # submit an answer
    client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"response": "A"})
    import app.services.llm as llm
    monkeypatch.setattr(llm, "is_configured", lambda: True)
    monkeypatch.setattr(llm, "chat_completion", lambda messages, **kw: "Hint: think about it.")
    r = client.post(f"/api/v1/attempts/{attempt_id}/questions/{qid}/chat", json={"mode": "hint"})
    assert r.status_code == 200, r.text
    assert "Hint" in r.json()["content"]


def test_chat_no_credentials(client, monkeypatch):
    attempt_id, qid = _setup(client, mode="practice")
    client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"response": "A"})
    import app.services.llm as llm
    monkeypatch.setattr(llm, "is_configured", lambda: False)
    r = client.post(f"/api/v1/attempts/{attempt_id}/questions/{qid}/chat", json={"mode": "hint"})
    assert r.status_code == 503
