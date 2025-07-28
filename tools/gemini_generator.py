# 파일명: gemini_generator.py

import json
from .base_generator import BaseToolGenerator
from .utils.SystemUtils import ConfigLoader
import time
import textwrap
import re

class GeminiCodeGenerator(BaseToolGenerator):
    """Gemini API를 이용해 고품질 파이썬 '실행 로직'을 생성하고, Python이 최종 코드를 조립합니다."""
    
    def __init__(self):
        self.model = ConfigLoader().get_gemini_model()

    def generate_code(self, tool_spec: dict) -> str:
        tool_name = tool_spec.get("name", "UnknownTool")
        class_name = "".join(word.capitalize() for word in tool_name.split('_')) + "Tool"
        
        print(f"  [Generator-Gemini] '{tool_name}' 도구의 핵심 실행 로직 생성을 요청합니다...")

        prompt = f"""
        당신은 파이썬 함수의 '본문(body)'만 작성하는 AI 코딩 전문가입니다.
        다음 [도구 명세서]를 보고, `execute` 메소드 안에 들어갈 파이썬 코드 '본문'을 작성해주세요.

        ### 매우 중요한 규칙
        1.  다른 import, 클래스, 함수 정의 없이 오직 `execute` 메소드의 내용만 작성하세요.
        2.  들여쓰기는 4칸 공백을 사용하세요.
        3.  최종 결과는 반드시 `return json.dumps(...)` 구문을 사용하여 JSON 형식의 '문자열'을 반환해야 합니다.
        

        ### 모범 코드 예시 (이런 형식으로 작성해야 합니다)
        ```python
        # 시뮬레이션 데이터 정의
        mock_data = [
            {{"id": 1, "name": "혁신성장 바우처"}},
            {{"id": 2, "name": "청년 창업 지원금"}}
        ]
        
        # 입력 파라미터를 이용한 데이터 필터링 로직
        results = [p for p in mock_data if query.lower() in p['name'].lower()]
        
        # 최종 결과를 json.dumps를 이용해 문자열로 반환
        return json.dumps(results, ensure_ascii=False)
        ```

        ### [도구 명세서]
        {json.dumps(tool_spec, ensure_ascii=False, indent=2)}
        """
        
        time.sleep(31) # API 속도 제한 준수
        response = self.model.generate_content(prompt)
        execute_body_raw = response.text.replace("```python", "").replace("```", "").strip()
        
        # AI가 실수로 생성할 수 있는 불필요한 import 구문 제거
        execute_body_cleaned = re.sub(r'^\s*import.*\n?', '', execute_body_raw, flags=re.MULTILINE)
        execute_body = textwrap.indent(execute_body_cleaned, '    ')
        
        print(f"  [Generator-Gemini] execute 메소드 본문 생성 및 정제 완료.")
        
        # 2. [Python의 역할] AI가 만든 로직을 '완벽한 템플릿'에 삽입하여 최종 코드 조립
        
        # execute 메소드의 파라미터 문자열 생성
        params_dict = tool_spec.get("parameters", {}).get("properties", {})
        execute_args = ", ".join([f"{name}: {prop.get('type', 'str')}" for name, prop in params_dict.items()])

        # 최종 코드 조립
        final_code = f"""
import json
from tool.base import ToolBase
# 필요하다면 다른 라이브러리 import (예: requests)

class {class_name}(ToolBase):
    name = "{tool_name}"
    description = "{tool_spec.get('description', '')}"
    parameters = {json.dumps(tool_spec.get('parameters', {}), indent=8)}

    def execute(self, {execute_args}) -> str:
{execute_body}
"""

        
        print(f"  [Code Builder] '{tool_name}'의 최종 코드를 성공적으로 조립했습니다.")
        print(f"Code 내용 : \n{final_code.strip()}")
        return final_code.strip()