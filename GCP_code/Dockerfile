# Python 3.11 기반의 이미지를 사용
FROM python:3.11-slim

# 필수 패키지 설치 (curl, Chromium 등)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    ca-certificates \
    libx11-dev \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Flask 앱을 위한 디렉토리 생성
WORKDIR /app

# `requirements.txt` 복사 및 패키지 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . /app/

# ChromeDriver 경로 설정 (Cloud Run 환경에서는 기본 경로 사용)
ENV CHROMEDRIVER_PATH=/usr/lib/chromium-driver
ENV DISPLAY=:99

# Flask 앱 실행
CMD ["python", "app.py"]
