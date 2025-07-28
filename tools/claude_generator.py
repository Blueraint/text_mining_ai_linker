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
        당신은 파이썬 함수의 핵심 로직을 작성하는 AI입니다.
        다음 [도구 명세서]를 보고, 이 도구의 `execute` 메소드 안에 들어갈 파이썬 코드 '본문'만 작성해주세요.
        - 다른 import 구문, 클래스 정의, 함수 정의는 절대 포함하지 마세요.
        - 들여쓰기는 4칸 공백을 사용하세요.
        - 최종 결과는 반드시 JSON 형식의 문자열을 반환해야 합니다.

        [도구 명세서]
        {json.dumps(tool_spec, ensure_ascii=False, indent=2)}
        """
        
        time.sleep(10) # API 속도 제한 준수

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
        return final_code.strip()