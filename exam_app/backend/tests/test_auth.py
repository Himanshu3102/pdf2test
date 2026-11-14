import uuid

from tests.conftest import TEST_PASSWORD
from tests.fixtures import make_text_pdf


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _register(anon_client, username: str) -> str:
    r = anon_client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _make_exam(client) -> str:
    r = client.post(
        "/api/v1/exams/upload",
        files={"file": ("sample.pdf", make_text_pdf(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    return r.json()["exam_id"]


def _publish_with_question(client, exam_id: str) -> None:
    questions = [
        {
            "order_index": 0,
            "qtype": "single_choice",
            "prompt": "2+2?",
            "options": [{"id": "A", "text": "3"}, {"id": "B", "text": "4"}],
            "answer_key": "B",
            "points": 4.0,
            "negative_points": -1.0,
            "review_status": "reviewed",
        }
    ]
    settings = {
        "mode": "exam",
        "duration_minutes": 10,
        "marking": {"correct": 4.0, "incorrect": -1.0, "unanswered": 0.0, "partial_credit": False},
    }
    r = client.patch(
        f"/api/v1/exams/{exam_id}",
        json={"title": "Auth Test", "questions": questions, "settings": settings, "settings_confirmed": True},
    )
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/exams/{exam_id}/publish")
    assert r.status_code == 200, r.text


def test_protected_endpoints_require_auth(anon_client):
    assert anon_client.get("/api/v1/me/exams").status_code == 401
    r = anon_client.post(
        "/api/v1/exams/upload",
        files={"file": ("sample.pdf", make_text_pdf(), "application/pdf")},
    )
    assert r.status_code == 401


def test_register_login_and_me(anon_client):
    username = _unique("alice")
    token = _register(anon_client, username)

    me = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == username

    # usernames are case-insensitive
    login = anon_client.post(
        "/api/v1/auth/login",
        json={"username": username.upper(), "password": TEST_PASSWORD},
    )
    assert login.status_code == 200

    bad = anon_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "wrong-password"},
    )
    assert bad.status_code == 401

    duplicate = anon_client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert duplicate.status_code == 409


def test_exams_are_private_to_their_owner(client, anon_client):
    exam_id = _make_exam(client)

    other_token = _register(anon_client, _unique("bob"))
    r = anon_client.get(
        f"/api/v1/exams/{exam_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 404

    own = client.get(f"/api/v1/exams/{exam_id}")
    assert own.status_code == 200


def test_history_lists_exams_and_attempts(client):
    exam_id = _make_exam(client)
    _publish_with_question(client, exam_id)
    start = client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert start.status_code == 200, start.text
    attempt_id = start.json()["attempt_id"]
    qid = start.json()["questions"][0]["id"]

    client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"response": "B"})
    client.post(f"/api/v1/attempts/{attempt_id}/submit")

    history = client.get("/api/v1/me/exams")
    assert history.status_code == 200
    items = history.json()
    mine = next(item for item in items if item["id"] == exam_id)
    assert mine["question_count"] == 1
    assert len(mine["attempts"]) == 1
    assert mine["attempts"][0]["status"] == "submitted"
    assert mine["attempts"][0]["score"] == 4.0


def test_attempts_are_private_to_the_exam_owner(client, anon_client):
    exam_id = _make_exam(client)
    _publish_with_question(client, exam_id)
    start = client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = start.json()["attempt_id"]

    other_token = _register(anon_client, _unique("carol"))
    r = anon_client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 404
