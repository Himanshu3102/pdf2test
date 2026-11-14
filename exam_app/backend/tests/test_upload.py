import io
from tests.fixtures import make_text_pdf


def test_upload_valid_pdf(client):
    data = make_text_pdf()
    files = {"file": ("sample.pdf", data, "application/pdf")}
    r = client.post("/api/v1/exams/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "exam_id" in body
    assert body["exam"]["status"] == "draft"


def test_upload_invalid_signature(client):
    files = {"file": ("bad.pdf", b"not a pdf", "application/pdf")}
    r = client.post("/api/v1/exams/upload", files=files)
    assert r.status_code == 400


def test_upload_too_large(client, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, "MAX_UPLOAD_MB", 0)  # 0 MB -> any data too large? max_bytes 0
    # Actually max_bytes = 0*1024*1024 = 0, so any non-empty rejected
    data = make_text_pdf()
    files = {"file": ("big.pdf", data, "application/pdf")}
    r = client.post("/api/v1/exams/upload", files=files)
    assert r.status_code == 413
