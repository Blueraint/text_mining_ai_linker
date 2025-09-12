# 파일명: main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import json
import sys

# --- 기존 AI-Linker 모듈 import ---
from ai_linker_agent import AIAgent
from tools.utils.ragsystem import RAG_System
from tools.utils.SystemUtils import ConfigLoader 
from tools.utils.hybriddb import VectorDB_hybrid

# --- FastAPI 앱 초기화 ---
app = FastAPI(title="AI-Linker API")

# --- API 요청/응답 모델 정의 ---
class AgentRequest(BaseModel):
    user_id: str
    query: str

class AgentResponse(BaseModel):
    status: str
    result: dict # 최종 결과는 JSON 객체일 가능성이 높으므로 dict로 변경

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

# API 처리
@app.post("/run-agent", response_model=AgentResponse)
async def run_agent_process(request: AgentRequest):
    print(f"수신된 요청: user_id={request.user_id}, query='{request.query}'")
    
    try:
        if request.user_id not in USER_DATABASE:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        agent = AIAgent(
            user_id=request.user_id,
            rag_system=rag_system,
            user_database=USER_DATABASE,
            _client=openai_client
        )
        
        final_result = agent.run(request.query)
        
        # agent.run()의 최종 결과가 JSON 문자열이라고 가정하고 파싱
        result_json = json.loads(final_result)
        return AgentResponse(status="success", result=result_json)

    except Exception as e:
        print(f"에이전트 실행 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {e}")

# 로컬 테스트용 실행 코드
if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)

