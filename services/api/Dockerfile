# Build from repository root: docker build -f services/api/Dockerfile .
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY python/ /app/python/
COPY services/api/ /app/services/api/

WORKDIR /app/services/api
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -e /app/python \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
# Antigravity OAuth loopback (opencode-antigravity-auth default redirect)
EXPOSE 51121

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
