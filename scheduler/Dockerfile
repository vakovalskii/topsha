FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    aiohttp

COPY main.py .

EXPOSE 8400

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8400"]
