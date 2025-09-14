from .base import ToolBase
import time, json
import numpy as np
# {"type": "function", "function": {"name": "submit_application", "description": "모든 검증된 서류를 모아 최종 목적지에 제출합니다.", "parameters": {"type": "object", "properties": {"doc_tokens": {"type": "array", "items": {"type": "string"}}, "destination": {"type": "string", "description": "제출할 기관 이름"}}, "required": ["doc_tokens", "destination"]}}},

from tools.utils.log_util import LoggingMixin
# self._log 는 'print'와 logging 을 포함하는 함수이다.
# logging.을 통해 외부 api response 로 과정을 보여준다

class SubmitApplicationTool(LoggingMixin, ToolBase) :
    name = "submit_application"
    description = "모든 검증된 서류를 모아 최종 목적지에 제출합니다."
    parameters = {
        "type": "object",
        "properties": {"doc_tokens": {"type": "array", "items": {"type": "string"}}, "destination": {"type": "string", "description": "제출할 기관 이름"}},
        "required": ["doc_tokens", "destination"]
    }

    def execute(self, doc_tokens: list, destination: str) -> str:
        # 임의로 Mocking 한 서비스
        self._log(f"  [Tool: Submitter] 서류({doc_tokens})를 '{destination}'에 제출합니다...")

        time.sleep(1)

        return json.dumps({"submission_status": "success", "application_id": f"APP_{np.random.randint(1000,9999)}"})