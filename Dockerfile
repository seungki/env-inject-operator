FROM python:3.11-slim

LABEL org.opencontainers.image.authors="LEE seungki <seungki.1215@gmail.com>"
LABEL org.opencontainers.image.version="0.1"
LABEL org.opencontainers.image.description="EKS POD 의 환경변수 주입 operator"
LABEL org.opencontainers.image.source="https://github.com/seungki/env-inject-operator"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["kopf", "run", "--standalone", "main.py"]