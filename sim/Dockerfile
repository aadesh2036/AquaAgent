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
RUN useradd --create-home --uid 10001 aqua && chown -R aqua /app
USER aqua
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/sim/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["python", "-m", "sim.cli"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
