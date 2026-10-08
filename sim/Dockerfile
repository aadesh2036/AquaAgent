# aquaagent-sim — BACKBONE §3.2. ENTRYPOINT modes: serve | generate | merge.
# Build context = repo root:  docker build -f sim/Dockerfile -t aquaagent-sim .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY sim/requirements.txt sim/requirements.txt
RUN pip install --no-cache-dir -r sim/requirements.txt
COPY shared/ shared/
COPY config/ config/
COPY sim/ sim/
EXPOSE 8000
ENTRYPOINT ["python", "-m", "sim.cli"]
CMD ["serve", "--port", "8000"]
