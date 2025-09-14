# 1. Python 3.11을 기본 이미지로 사용
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 프로젝트 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 프로젝트 전체 파일 복사
# (tools, utils, .py 파일, .json, .properties 등 모든 파일)
COPY . .

# 5. FastAPI 서버 실행
#    Uvicorn이 외부에서 접속할 수 있도록 host를 "0.0.0.0"으로 설정
CMD ["uvicorn", "ai_linker_fastapi:app", "--host", "0.0.0.0", "--port", "8080"]