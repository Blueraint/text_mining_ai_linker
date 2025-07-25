import json
import sys, os
import subprocess
# --- 3. 도구 생성 파이프라인 (tool_generator.py) ---

class ToolGenerationPipeline:
    def __init__(self, _client) :
        self.client = _client
        
    def _generate_tool_code(self, tool_spec: dict) -> str:
        print(f"  [Generator] LLM에게 '{tool_spec['name']}' 도구 코드 생성을 요청합니다...")
        
        # 코드 제작 프롬프트 정의
        prompt = f"""
        당신은 'ToolBase'를 상속받는 파이썬 클래스 코드를 생성하는 고도로 숙련된 AI 개발자입니다.
        아래 [도구 명세서]와 [코드 생성 규칙]을 단 하나의 예외도 없이 엄격하게 준수하여 완전한 파이썬 코드 파일을 생성하세요.

        [도구 명세서]
        {json.dumps(tool_spec, ensure_ascii=False, indent=2)}

        [코드 생성 규칙]
        1.  생성할 클래스의 이름은 반드시 **'{class_name}'** 이어야 합니다.
        2.  **파일 구조:** 필요한 모든 라이브러리를 import하고, 그 다음에 클래스를 정의합니다. 다른 내용은 포함하지 마세요.
        3.  **상속:** 클래스는 반드시 'tools.base'의 'ToolBase'를 상속받아야 합니다. (`from .base import ToolBase`)
        4.  **클래스 속성:** `name`, `description`, `parameters`는 반드시 `__init__` 메소드 외부, 즉 클래스 레벨의 속성으로 정의해야 합니다.
        5.  **`parameters` 형식:** `parameters`는 반드시 JSON Schema 형식의 딕셔너리여야 합니다. (e.g., `{{"type": "object", "properties": {{...}}}}`)
        6.  **`execute` 메소드:** 명세서의 `parameters`에 정의된 모든 인자를 파라미터로 받아야 하며, 타입 힌트를 포함해야 합니다.
        7.  **출력:** 다른 설명 없이 오직 완전한 파이썬 코드만 응답해야 합니다.

        [코드 구조 템플릿]
        ```python
        import json
        # 필요한 다른 라이브러리 import (예: requests)
        from .base import ToolBase

        class <ClassName>(ToolBase):
            name = "<tool_name>"
            description = "<tool_description>"
            parameters = <parameters_json_schema>

            def execute(self, <arguments>) -> str:
                # 여기에 시뮬레이션 또는 실제 API 호출 로직 구현
                # ...
                # 최종 결과는 반드시 json.dumps()를 사용하여 문자열로 반환
                return json.dumps({{"result": "success"}}, ensure_ascii=False)
        ```
        
        [코드 구조 예시 1]
        ```python
        # 작업이 종료되었음을 알리는 선언성 툴
        import json
        from .base import ToolBase

        class FinishTaskTool(ToolBase):
            name = "finish_task"
            description = "사용자의 모든 요청이 성공적으로 완료되었을 때, 최종 요약 메시지와 함께 호출하는 도구입니다."
            parameters = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "사용자에게 전달할 최종 성공 메시지"}
                },
                "required": ["summary"]
            }

            def execute(self, summary: str) -> str:
                # 이 도구는 받은 메시지를 그대로 반환하여, 작업이 성공적으로 끝났음을 알립니다.
                return json.dumps({"status": "SUCCESS", "message": summary})

        ```
        
        [코드 구조 예시 2]
        ```python
        # 필요한 서류를 MCP를 통해 기관에서 가져오는 툴
        # 예시 코드는 시뮬레이션용 개념 코드임
        from .base import ToolBase
        import time, json
        import numpy as np
        
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

                # 데이터 원문 대신, 유효기간 등 메타데이터를 포함한 확인 토큰 반환
                return json.dumps({
                    "status": "success", "doc_token": f"TOKEN_{np.random.randint(1000, 9999)}",
                    "doc_name": document_name, "issue_date": "2025-07-15",
                    "message": "서류 발급 성공"
                })
        ```
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.0
        )
        return response.choices[0].message.content.replace("```python", "").replace("```", "").strip()

    def _test_generated_code(self, code: str, tool_name: str) -> bool:
        print(f"  [Generator] 생성된 '{tool_name}' 코드를 샌드박스에서 테스트합니다...")
        test_filepath = f"temp_test_{tool_name}.py"
        with open(test_filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        try:
            # 별도 프로세스에서 import 테스트를 수행하여 문법 및 기본 실행 오류 확인
            result = subprocess.run(
                [sys.executable, "-c", f"import {test_filepath[:-3]}"],
                capture_output=True, text=True, timeout=10, check=True
            )
            print(f"  [Generator] 테스트 성공.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  [Generator] 테스트 실패 (컴파일/실행 오류): {e.stderr}")
            return False
        finally:
            if os.path.exists(test_filepath):
                os.remove(test_filepath)

    def create_and_register_tool(self, tool_spec: dict, tool_directory: str = "tools") -> bool:
        tool_name = tool_spec.get("name")
        if not tool_name: return False
        
        generated_code = self._generate_tool_code(tool_spec)
        
        if self._test_generated_code(generated_code, tool_name):
            plugin_path = os.path.join(tool_directory, f"{tool_name}_tool.py")
            with open(plugin_path, 'w', encoding='utf-8') as f:
                f.write(generated_code)
            print(f"  [Generator] 새 도구 '{tool_name}'을 '{plugin_path}'에 성공적으로 등록했습니다.")
            return True
        return False