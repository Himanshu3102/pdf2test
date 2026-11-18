# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY exam_app/frontend/package*.json ./
RUN npm ci
COPY exam_app/frontend/ ./
RUN npm run build

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for PyMuPDF and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY exam_app/backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Create data directory
RUN mkdir -p /data/uploads

# Environment
ENV DATABASE_URL=sqlite:////data/exam_app.db
ENV STORAGE_DIR=/data/uploads
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD cd /app/backend && python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000