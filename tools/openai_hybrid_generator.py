# 파일명: openai_hybrid_generator.py

import json, re
import textwrap
from .base_generator import BaseToolGenerator
from .utils.SystemUtils import ConfigLoader 

class OpenAIHybridCodeGenerator(BaseToolGenerator):
    """
    [개선된 아키텍처]
    Python이 'spec'을 기반으로 모든 '틀(Shell)'을 만들고,
    OpenAI(GPT-4o)는 'execute' 메소드의 '핵심 로직(Body)'만 생성합니다.
    """
    
    def __init__(self):
        self.client = ConfigLoader().get_openai_client()
        self.model_name = "gpt-4o"

    def _get_execute_body_from_ai(self, tool_spec: dict) -> dict:
        """[개선] AI에게 'execute 본문'과 '필요한 import'만 생성하도록 요청합니다."""
        print(f"  [Generator-OpenAI] '{tool_spec['name']}' 도구의 '핵심 실행 로직' 생성을 요청합니다...")
        
        # AI에게 전달할 파라미터 정보를 더 단순하게 가공
        simple_params_desc = []
        for name, props in tool_spec.get("parameters", {}).get("properties", {}).items():
            simple_params_desc.append(f"- {name} ({props.get('type')})")
        
        prompt = f"""
        You are a Python expert who writes ONLY the internal logic for a function body.
        Based on the [Tool Specification] and [Parameter List] below, write the Python code logic for the 'execute' method.

        [Tool Specification]
        - Name: {tool_spec.get('name')}
        - Description: {tool_spec.get('description')}
        - Parameters: {', '.join(simple_params_desc)}

        [Rules]
        1.  Respond with a JSON object containing two keys: "imports_list" and "execute_body".
        2.  "imports_list": A list of standard Python libraries needed for your code (e.g., ["requests", "datetime"]).
        3.  "execute_body": The raw Python code (4-space indented) that should go INSIDE the execute method.
        4.  Do NOT include the 'def execute(...)' line, class definitions, or any imports inside the execute_body.
        5.  The logic MUST return a JSON string using `json.dumps(..., ensure_ascii=False)`.

        [Example Output Format]
        {{
            "imports_list": ["requests"],
            "execute_body": "    # Core logic here\\n    print('Calling API...')\\n    return json.dumps({{'status': 'success'}})"
        }}
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def generate_code(self, tool_spec: dict) -> str:
        """AI가 만든 로직을 Python 코드로 100% 완벽하게 조립합니다."""
        
        # 1. AI에게 창의적인 부분(로직 본문)을 받아옴
        components = self._get_execute_body_from_ai(tool_spec)

        # 2. Python이 '틀'을 만듦 (AI가 만든 명세서를 100% 신뢰)
        tool_name = tool_spec["name"]
        class_name = "".join(word.capitalize() for word in tool_name.split('_')) + "Tool"

        # 2-1. Imports 조립
        imports = ["import json", "from .base import ToolBase"] + [f"import {lib}" for lib in components.get("imports_list", [])]
        imports_str = "\n".join(sorted(list(set(imports))))

        # 2-2. Parameters (JSON Schema) 조립 - AI가 만든 명세서를 그대로 사용
        parameters_str = json.dumps(tool_spec.get("parameters", {}), indent=8)
        
        # 2-3. execute 메소드 시그니처 조립 - 100% 신뢰성 보장
        params_dict = tool_spec.get("parameters", {}).get("properties", {})
        type_mapping = {"string": "str", "number": "float", "integer": "int", "boolean": "bool", "array": "list", "object": "dict"}
        
        execute_args_list = []
        for name, prop in params_dict.items():
            py_type = type_mapping.get(prop.get("type"), "str") # 기본값은 str
            if name in tool_spec.get("parameters", {}).get("required", []):
                 execute_args_list.append(f"{name}: {py_type}")
            else:
                 execute_args_list.append(f"{name}: {py_type} = None") # 선택적 파라미터 처리
        execute_args = ", ".join(execute_args_list)

        # 2-4. execute 본문 들여쓰기 적용
        execute_body_raw = components.get("execute_body", "        pass")
        execute_body_cleaned = re.sub(r'^\s*import.*\n?', '', execute_body_raw, flags=re.MULTILINE) # 이중 안전장치
        execute_body = textwrap.indent(execute_body_cleaned, '    ')

        # 2-5. 전체 코드 템플릿에 삽입
        final_code = f"""
{imports_str}

class {class_name}(ToolBase):
    name = "{tool_name}"
    description = "{tool_spec.get('description', '')}"
    parameters = {parameters_str}

    def execute(self, {execute_args}) -> str:
{execute_body}
"""
        print(f"  [Code Builder] '{tool_name}'의 최종 코드를 성공적으로 조립했습니다.")
        print(f"  [Code Source]\n'{final_code.strip()}")
        return final_code.strip()