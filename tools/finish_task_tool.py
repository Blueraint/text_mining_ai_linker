import json
from .base import ToolBase

class FinishTaskTool(ToolBase) :
    name = "finish_task"
    description = "사용자의 모든 요청이 성공적으로 완료되었을 때, 최종 요약 메세지와 함께 호출하는 도구입니다."
    parameters = {
        "type" : "object",
        "properties" : {
            "summary" : {"type" : "string", "description" : "사용자에게 전달할 최종 성공 메세지"}
        },
        "required" : ["summary"]
    }
    
    def execute(self, summary: str) -> str :
        # 받은 메세지를 그대로 반환하여 작업이 성공적으로 끝남을 알림
        return json.dumps({"status" : "SUCCESS", "message" : summary})