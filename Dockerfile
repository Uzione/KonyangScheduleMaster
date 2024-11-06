# 베이스 이미지로 Python 3.11 이미지를 사용
FROM python:3.11-slim

# 필수 패키지 및 의존성 설치
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    ca-certificates \
    libx11-dev \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libgtksourceview2.0-0 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Chrome과 ChromeDriver 설치
RUN GOOGLE_CHROME_VERSION=116.0.5845.96 && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb && \
    apt-get -y -f install && \
    rm google-chrome-stable_current_amd64.deb

# ChromeDriver 다운로드
RUN CHROMEDRIVER_VERSION=116.0.5845.96 && \
    wget https://chromedriver.storage.googleapis.com/116.0.5845.96/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip -d /usr/local/bin && \
    rm chromedriver_linux64.zip

# 작업 디렉토리 설정
WORKDIR /app

# 현재 디렉토리의 파일들을 컨테이너의 /app 디렉토리로 복사
COPY . /app

# 의존성 설치 (selenium, BeautifulSoup 등)
RUN pip install --no-cache-dir -r requirements.txt

# 크롬을 헤드리스 모드로 실행하기 위해 환경변수 설정
ENV DISPLAY=:99

# 크롬을 실행할 때 사용할 기본 명령어 설정
CMD ["python", "your_script_name.py"]
