FROM python:3.11-slim

LABEL org.opencontainers.image.authors="LEE seungki <seungki.1215@gmail.com>"
LABEL org.opencontainers.image.version="0.1"
LABEL org.opencontainers.image.description="EKS POD 의 환경변수 주입 operator"
LABEL org.opencontainers.image.source="https://github.com/seungki/env-inject-operator"

# 필수 패키지 설치 (git 포함)
RUN apt-get update && apt-get install -y \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["kopf", "run", "--standalone", "main.py"]