# Exam Practice App

FastAPI backend + React/Vite frontend for practicing exams from PDFs.

## Backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173 and proxies /api to backend.

## Accounts

Register once from the login screen, then log in with the same username and password.
- Usernames are case-insensitive and unique (3–32 characters: letters, numbers, `.`, `_`, `-`).
- Passwords are stored as PBKDF2-SHA256 hashes; sessions use HMAC-signed bearer tokens kept in `localStorage`.
- Every exam, attempt, result, and chat is scoped to its owner. Other users' data returns 404.
- The dashboard lists your tests with their attempts; drafts can be edited, published tests can be started, in-progress attempts can be resumed, and submitted attempts open their full result.
- Attempts are saved server-side, so a page reload or `?attempt=<attempt-id>` link resumes the same test.

Set `AUTH_SECRET_KEY` to a long random value before deploying. Changing it invalidates all existing tokens.

## Tests

Backend:
```bash
cd backend
python -m pytest
```

Frontend:
```bash
cd frontend
npm test
```

## Environment

Copy `.env.example` to `backend/.env` and set `OPENAI_API_KEY` for LLM features. Set a unique
`AUTH_SECRET_KEY` in any shared or deployed environment.

## Notes

- Uploaded PDFs stored outside public web root in `data/uploads`.
- Answer keys are never returned before submission except practice-mode feedback.
- The first account registered adopts exams created before accounts existed (`owner_id IS NULL`).
