# aquaagent-predictor — the model image (BI-26/27): predictor (default, :8001) and detector+localiser
# (entrypoint python -m ml.serve.detector_app, :8002) run from the SAME image. Build context = repo root:
#   docker build -f ml/serve/Dockerfile -t aquaagent-predictor .
# The model is NOT baked in: AQUA_PREDICTOR_ARTIFACT points at s3://…/model.tar.gz (ECS) or a mounted dir (local).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
ARG TORCH_VERSION=2.8.0
RUN pip install --no-cache-dir "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu
COPY ml/serve/requirements.txt ml/serve/requirements.txt
RUN pip install --no-cache-dir -r ml/serve/requirements.txt
COPY shared/ shared/
COPY ml/__init__.py ml/__init__.py
COPY ml/features/__init__.py ml/features/tensorize.py ml/features/
COPY ml/predictor/__init__.py ml/predictor/masking.py ml/predictor/mlp.py ml/predictor/gnn.py ml/predictor/train.py ml/predictor/predict.py ml/predictor/
COPY ml/anomaly/__init__.py ml/anomaly/setnet.py ml/anomaly/sensorset.py ml/anomaly/frames.py ml/anomaly/
COPY ml/localisation/__init__.py ml/localisation/matcher.py ml/localisation/
COPY ml/serve/ ml/serve/
RUN useradd --create-home --uid 10001 aqua && chown -R aqua /app
USER aqua
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/predictor/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["python", "-m", "ml.serve.app"]
CMD ["--port", "8001"]
