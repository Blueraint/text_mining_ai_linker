# 파일명: claude_generator.py

import json
from .base_generator import BaseToolGenerator
from .utils.SystemUtils import ConfigLoader
import time
import textwrap
import re

class ClaudeCodeGenerator(BaseToolGenerator):
    """Claude 3 Sonnet API를 이용해 고품질 파이썬 '실행 로직'을 생성하고, Python이 최종 코드를 조립합니다."""
    
    def __init__(self):
        # ConfigLoader를 통해 Claude 클라이언트를 가져옴
        self.client = ConfigLoader().get_claude_client()
        self.model_name = "claude-3-sonnet-20240229"

    def generate_code(self, tool_spec: dict) -> str:
        tool_name = tool_spec.get("name", "UnknownTool")
        class_name = "".join(word.capitalize() for word in tool_name.split('_')) + "Tool"
        
        print(f"  [Generator-Claude] '{tool_name}' 도구의 핵심 실행 로직 생성을 요청합니다...")

        # 프롬프트는 Gemini와 동일하게 사용 가능
        prompt = f"""
        ### 페르소나 (Persona) ###
        당신은 대한민국 스타트업 생태계를 위한 파이썬 도구를 개발하는, 경험 많은 한국인 시니어 개발자입니다.
        
        ### 매우 중요한 코드 생성 규칙
        1.  **언어:** 모든 코드, 주석, 변수명, 결과 메시지는 **반드시 한국어 또는 영어**로만 작성해야 합니다. 다른 언어(특히 중국어)는 절대 사용해서는 안 됩니다.
        2.  **문법:** `execute` 메소드의 타입 힌트는 반드시 `str`, `int`, `float` 등 표준 파이썬 타입만 사용하세요. (`string`, `number` 등은 사용 금지)
        3.  **내용:** `execute` 메소드의 본문은 [도구 명세서]의 목적에 맞는, 논리적으로 타당한 모의(Mock) 로직을 포함해야 합니다. `pass`만 있는 빈 함수는 허용되지 않습니다.
        4.  **출력:** 최종 결과는 반드시 `json.dumps(..., ensure_ascii=False)` 구문을 사용하여 JSON 형식의 '문자열'을 반환해야 합니다.
        
        ### [도구 명세서]
        {json.dumps(tool_spec, ensure_ascii=False, indent=2)}
        
        ### [최종 출력]
        다른 설명 없이, 위의 모든 규칙을 준수한 최종 파이썬 코드만 응답하세요.
        """

        
        # time.sleep(10) # API 속도 제한 준수

        # [수정] Claude API 호출 방식으로 변경
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=2048, # 최대 출력 토큰 수 설정
            temperature=0.0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # [수정] Claude 응답 파싱 방식으로 변경
        execute_body_raw = response.content[0].text.replace("```python", "").replace("```", "").strip()
        
        execute_body_cleaned = re.sub(r'^\s*import.*\n?', '', execute_body_raw, flags=re.MULTILINE)
        execute_body = textwrap.indent(execute_body_cleaned, '    ')
        
        print(f"  [Generator-Claude] execute 메소드 본문 생성 및 정제 완료.")

        # 이하 Python 코드 조립 로직은 Gemini 버전과 완전히 동일합니다.
        params_dict = tool_spec.get("parameters", {}).get("properties", {})
        execute_args = ", ".join([f"{name}: {prop.get('type', 'str')}" for name, prop in params_dict.items()])

        final_code = f"""
import json
from tools.base import ToolBase
# 필요하다면 다른 라이브러리 import (예: requests)

class {class_name}(ToolBase):
    name = "{tool_name}"
    description = "{tool_spec.get('description', '')}"
    parameters = {json.dumps(tool_spec.get('parameters', {}), indent=8)}

    def execute(self, {execute_args}) -> str:
{execute_body}
"""
        print(f"  [Code Builder] '{tool_name}'의 최종 코드를 성공적으로 조립했습니다.")
        print(f"  [Code Source]\n{final_code.strip()}")
        return final_code.strip()
