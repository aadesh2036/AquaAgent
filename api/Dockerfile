# aquaagent-api — BACKBONE §3.2. Build context = repo root:
#   docker build -f api/Dockerfile -t aquaagent-api .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY shared/ shared/
COPY config/ config/
COPY ml/ ml/
COPY api/ api/
EXPOSE 8080
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
