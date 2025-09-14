# 파일명: tools/verify_business_tool.py
# 파일을 분리하고 개별적으로 import 하도록 만든다
from .base import ToolBase
import requests
import json
from .utils.SystemUtils import PrivacyUtils
from .utils.SystemUtils import ConfigLoader

from tools.utils.log_util import LoggingMixin
# self._log 는 'print'와 logging 을 포함하는 함수이다.
# logging.을 통해 외부 api response 로 과정을 보여준다

# 위에서 정의내린 ToolBase Class 를 상속받는다
class VerifyBusinessRegistrationTool(LoggingMixin, ToolBase):
    name = "verify_business_registration"
    description = "사용자의 사업자등록 상태가 유효한지 국세청 API로 확인합니다."
    parameters = {
        "type": "object",
        "properties": {"user": {"type": "object"}},
        "required": ["user"]
    }

    def __init__(self) : 
        # self.gov_api_key = ConfigLoader().get_api_key('govdata.api.key')
        self.gov_api_key = ConfigLoader()._get_priority_key('GOV_API_KEY', 'govdata.api.key')

    # [추가] 실제 작동하는 국세청 API 연동 도구(사업자등록번호 상태조회)
    def execute(self, user: dict) -> str:
        self._log(f"  [Tool: 국세청 API] user '{user}'의 사업자 상태 조회 시작...")

        business_id = user.get('business_id')
        user_id = user.get('user_id')
        if not business_id:
            return json.dumps({"status": "error", "message": "user 객체에 business_id가 없습니다."})

        PrivacyUtils.log_securely(f"  [Internal] Securely retrieved business_id: {business_id} for user_id: {user_id}")

        # 2. 조회된 실제 정보로 외부 API 호출
        api_url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={self.gov_api_key}"
        payload = {"b_no": [business_id.replace("-", "")]}

        try:
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("data") and len(data["data"]) > 0:
                status = data["data"][0]
                tax_type = status.get("tax_type", "정보 없음")
                return json.dumps({
                    "status": "success", "business_id": status.get("b_no"),
                    "taxpayer_status": tax_type, "message": f"조회 성공: {tax_type}"
                }, ensure_ascii=False)
            else:
                return json.dumps({"status": "error", "message": data.get("message", "유효하지 않거나 정보가 없는 사업자번호입니다.")})
        except requests.exceptions.RequestException as e:
            return json.dumps({"status": "error", "message": f"API 호출 중 네트워크 오류 발생: {e}"})