from .base import ToolBase
import time, json
import numpy as np
# {"type": "function", "function": {"name": "fetch_document_from_mcp", "description": "필요한 서류를 MCP를 통해 기관에서 가져옵니다.", "parameters": {"type": "object", "properties": {"document_name": {"type": "string", "description": "가져올 서류의 정확한 이름"},…cription": "검증할 서류의 확인 토큰"}, "issue_date_str": {"type": "string", "description": "서류의 발급일자(YYYY-MM-DD 형식)"}}, "required": ["doc_token", "issue_date_str"]}}},

class FetchDocumentFromMcpTool(ToolBase) :
    name = "fetch_document_from_mcp"
    description = "필요한 서류를 MCP를 통해 기관에서 가져옵니다."
    parameters = {
        "type": "object",
        "properties": {"document_name": {"type": "string", "description": "가져올 서류의 정확한 이름"}, "user_id": {"type": "string", "description": "요청하는 사용자의 ID"}},
        "required": ["doc_token", "issue_date_str"]
    }

    def execute(self, document_name: str, user_id: str) -> str:
        # 임의로 Mocking 한 서비스
        print(f"  [Tool: MCP] '{document_name}' 전송 요청 (사용자: {user_id})... 사용자 동의 획득...")

        time.sleep(1) # 시뮬레이션 딜레이

        # 데이터 원문 대신, 유효기간 등 메타데이터를 포함한 확인 토큰 반환
        return json.dumps({
            "status": "success", "doc_token": f"TOKEN_{np.random.randint(1000, 9999)}",
            "doc_name": document_name, "issue_date": "2025-07-15",
            "message": "서류 발급 성공"
        })