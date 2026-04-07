FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN python -m pip install --upgrade pip \
    && python -m pip install -r apps/worker/requirements.txt \
    && python -m pip install -e .

WORKDIR /app/apps/worker

CMD ["python", "main.py"]
