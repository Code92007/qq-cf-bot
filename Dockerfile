FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_HOST=0.0.0.0 \
    BOT_PORT=8088

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e . \
    && playwright install --with-deps chromium

VOLUME ["/app/data"]
EXPOSE 8088

CMD ["python", "-m", "qq_cf_bot"]
