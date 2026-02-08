# Userbot - Telethon-based agent
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY main.py .

# Create session directory
RUN mkdir -p session

CMD ["python", "-u", "main.py"]
