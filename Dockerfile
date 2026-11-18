# Stage 1: Build React + Three.js Frontend
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Production FastAPI + 20Hz Telemetry & Static SPA Server
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "numpy>=2.0.0" \
    "pydantic>=2.9.0" \
    "python-multipart>=0.0.12"

COPY backend/ /app/
COPY --from=frontend-builder /frontend/dist /app/static

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
