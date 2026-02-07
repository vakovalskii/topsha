FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir fastapi uvicorn httpx

COPY main.py .

EXPOSE 8100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
