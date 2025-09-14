# 파일명: main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import json
import sys
from typing import List, Dict, Any
from tools.utils.hybriddb import VectorDB_hybrid
import logging 
from io import StringIO

# --- 기존 AI-Linker 모듈 import ---
from ai_linker_agent import AIAgent
from tools.utils.ragsystem import RAG_System
from tools.utils.SystemUtils import ConfigLoader 
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader


try:
    # ConfigLoader를 통해 안전하게 API 키를 가져옵니다.
    # API_KEY = ConfigLoader().get_api_key('agent.api.key')
    API_KEY = ConfigLoader()._get_priority_key('AGENT_API_KEY', 'agent.api.key')

except (FileNotFoundError, ValueError) as e:
    print(f"[CRITICAL] API 키 로드 실패: {e}")
    sys.exit(1) # 키가 없으면 서버 실행 중단

API_KEY_NAME = "API_KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# --- FastAPI 앱 초기화 ---
app = FastAPI(title="AI-Linker API")

# --- API 요청/응답 모델 정의 ---
class AgentRequest(BaseModel):
    user_id: str
    query: str

class AgentResponse(BaseModel):
    status: str
    final_result: Dict[str, Any]
    execution_log: List[str]

# --- 시스템 초기화 ---
# [개선] 전역 변수로 핵심 객체들을 선언
config = None
rag_system = None
USER_DATABASE = None
openai_client = None

try:
    print("AI-Linker 시스템을 초기화합니다...")
    config = ConfigLoader()
    openai_client = config.get_openai_client()
        
    # user_data.json 파일에서 사용자 DB 로드
    with open('user_data.json', 'r', encoding='utf-8') as f:
        USER_DATABASE = json.load(f)
    print(f"사용자 DB 로드 완료. ({len(USER_DATABASE)}명)")

    # rag_data.json 파일에서 RAG 지식 베이스 로드
    rag_system = RAG_System()
    # Hybrid Database 장착
    rag_system.set_database = VectorDB_hybrid()

    
    with open('rag_data.json', 'r', encoding='utf-8') as f:
        policies = json.load(f)
    
    for policy in policies:
        rag_system.add_document(
            doc_id=policy['doc_id'],
            content=policy['content'],
            metadata=policy['metadata'],
            build_index=False # 모든 데이터 추가 후 한번에 빌드
        )
    rag_system.db.build_index()
    print(f"RAG 지식 베이스 로드 완료. ({len(policies)}개 정책)")
    
    print("시스템 초기화 완료.")

except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    print(f"[CRITICAL] 시스템 초기화 실패: {e}")
    print("서버를 시작할 수 없습니다. 설정 또는 데이터 파일을 확인하세요.")
    sys.exit(1) # [개선] 프로그램 종료


# --- API 키 검증 함수 ---
async def get_api_key(key: str = Security(api_key_header)):
    """요청 헤더의 API 키가 유효한지 검증합니다."""
    if key == API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=403, detail="Could not validate credentials"
        )

# API 처리
@app.post("/run-agent", response_model=AgentResponse)
async def run_agent_process(request: AgentRequest, api_key: str = Depends(get_api_key)):
    print(f"수신된 요청: user_id={request.user_id}, query='{request.query}'")
    
    try:
        if request.user_id not in USER_DATABASE:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        # 1. 이 요청만을 위한 임시 '로그 수집기'(Stream) 생성
        log_stream = StringIO()
        
        # 2. 모든 로그 메시지가 이 수집기로 향하도록 로거(Logger) 설정
        # (기존 핸들러를 잠시 비활성화하고, 우리 수집기를 유일한 대상으로 설정)
        linker_logger = logging.getLogger('ai_linker')
        linker_logger.setLevel(logging.INFO)

        original_handlers = linker_logger.handlers[:]
        
        stream_handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(message)s')
        stream_handler.setFormatter(formatter)
        
        linker_logger.handlers = [stream_handler]
        
        try:
            agent = AIAgent(
                user_id=request.user_id,
                rag_system=rag_system,         # 전역 rag_system 객체 전달
                user_database=USER_DATABASE,   # 전역 USER_DATABASE 객체 전달
                _client=openai_client          # 전역 openai_client 객체 전달
            )

            final_result_dict = agent.run(request.query)

            captured_logs = log_stream.getvalue().strip().split('\n')
            
            return AgentResponse(
                status="success",
                final_result=final_result_dict.get("final_result", {}),
                execution_log=captured_logs
            )
        finally:
            # 4. 요청 처리가 끝나면, 원래의 로거 설정으로 복원
            linker_logger.handlers = original_handlers

    except Exception as e:
        print(f"에이전트 실행 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {e}")


#  RAG 시스템 내용 조회 API
@app.get("/rag-content")
async def get_rag_content():
    """
    현재 RAG 지식 베이스에 저장된 모든 정책 문서의 내용을 반환합니다.
    """
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG 시스템이 초기화되지 않았습니다.")
    
    content = rag_system.get_all_documents_as_dict()
    return {"rag_documents": content}


# 등록된 사용자 목록 조회 API
@app.get("/users")
async def get_user_list():
    """
    현재 시스템에 등록된 모든 사용자의 ID 목록을 반환합니다.
    """
    if not USER_DATABASE:
        raise HTTPException(status_code=500, detail="사용자 DB가 초기화되지 않았습니다.")
    
    user_ids = list(USER_DATABASE.keys())
    return {"user_ids": user_ids}

# 로컬 테스트용 실행 코드
if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
