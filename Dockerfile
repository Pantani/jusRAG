FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY packages ./packages

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
 && pip install --no-cache-dir ".[local]"

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
