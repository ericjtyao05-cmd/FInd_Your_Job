FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY . /app

RUN python -m pip install --upgrade pip \
    && python -m pip install -r apps/worker/requirements.txt \
    && python -m pip install -e . \
    && python -m playwright install --with-deps chromium

WORKDIR /app/apps/worker

CMD ["python", "main.py"]
