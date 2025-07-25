from .base import ToolBase
import time, json
# {"type": "function", "function": {"name": "validate_document", "description": "가져온 서류가 유효한지(예: 유효기간) 검증합니다.", "parameters": {"type": "object", "properties": {"doc_token": {"type": "string", "description": "검증할 서류의 확인 토큰"}, "issue_date_str": {"type": "string", "description": "서류의 발급일자(YYYY-MM-DD 형식)"}}, "required": ["doc_token", "issue_date_str"]}}},

class ValidateDocumentTool(ToolBase) :
    name = "validate_document"
    description = "가져온 서류가 유효한지(예: 유효기간) 검증합니다."
    parameters = {
        "type": "object",
        "properties": {"doc_token": {"type": "string", "description": "검증할 서류의 확인 토큰"}, "issue_date_str": {"type": "string", "description": "서류의 발급일자(YYYY-MM-DD 형식)"}},
        "required": ["doc_token", "issue_date_str"]
    }

    def execute(self, doc_token: str, issue_date_str: str) -> str:
        # 임의로 Mocking 한 서비스
        print(f"  [Tool: Validator] '{doc_token}' 유효성 검증 시작 (발급일: {issue_date_str})...")

        time.sleep(1)

        # 시나리오: 발급일이 2025-07-01 이후여야 유효하다고 가정
        if issue_date_str >= "2025-07-01":
            return json.dumps({"is_valid": True, "message": "최신 서류로 확인되어 유효합니다."})
        else:
            return json.dumps({"is_valid": False, "message": "서류 유효기간이 만료되었습니다."})