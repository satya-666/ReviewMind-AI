FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && useradd --create-home --uid 10001 appuser
COPY backend backend
COPY frontend frontend
COPY src src
COPY scripts/clean_data.py scripts/categorize.py scripts/fetch_serving_model.py scripts/
COPY configs/aspect_taxonomy.yaml configs/aspect_taxonomy.yaml
RUN mkdir -p /app/runtime /app/.cache && chown -R appuser:appuser /app/runtime /app/.cache
USER appuser
EXPOSE 8000
CMD ["sh", "backend/start.sh"]
