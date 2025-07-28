import json
import textwrap
from .base_generator import BaseToolGenerator
from .utils.SystemUtils import ConfigLoader

class OpenAIHybridCodeGenerator(BaseToolGenerator):
    """OpenAI(GPT-4o) API를 이용해 고품질 파이썬 '실행 로직'을 생성하고, Python이 최종 코드를 조립합니다."""
    
    def __init__(self):
        self.client = ConfigLoader().get_openai_client()
        self.model_name = "gpt-4o"

    def _get_code_components_from_ai(self, tool_spec: dict) -> dict:
        """1단계: AI에게 코드의 '내용물'(로직, 파라미터 목록 등)만 생성하도록 요청합니다."""
        print(f"  [Generator-OpenAI] '{tool_spec['name']}' 도구의 핵심 구성요소 생성을 요청합니다...")
        
        prompt = f"""
        You are a Python expert who writes the core logic for a tool.
        Based on the provided [Tool Specification], return a JSON object containing the `imports` list, a simple `simple_parameters` dictionary, and the `execute_body` string.

        [Tool Specification]
        {json.dumps(tool_spec, ensure_ascii=False, indent=2)}

        [Output JSON Format]
        {{
            "imports": ["requests", "datetime"],
            "simple_parameters": {{
                "query": "string",
                "limit": "integer"
            }},
            "execute_body": "# Core logic goes here\\n    results = {{'status': 'success'}}\\n    return json.dumps(results, ensure_ascii=False)"
        }}
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def generate_code(self, tool_spec: dict) -> str:
        """AI가 만든 내용물을 Python 코드로 100% 완벽하게 조립합니다."""
        # 1. AI에게 창의적인 부분(내용물)을 받아옴
        components = self._get_code_components_from_ai(tool_spec)

        # 2. Python이 '틀'을 만듦
        tool_name = tool_spec["name"]
        class_name = "".join(word.capitalize() for word in tool_name.split('_')) + "Tool"

        # 2-1. Imports 조립
        imports = ["import json", "from .base import ToolBase"] + [f"import {lib}" for lib in components.get("imports", [])]
        imports_str = "\n".join(sorted(list(set(imports)))) # 중복 제거 후 정렬

        # 2-2. Parameters (JSON Schema) 조립 - 100% 신뢰성 보장
        properties = {
            name: {"type": dtype, "description": ""} 
            for name, dtype in components.get("simple_parameters", {}).items()
        }
        parameters_schema = {
            "type": "object",
            "properties": properties,
            "required": list(components.get("simple_parameters", {}).keys())
        }
        parameters_str = json.dumps(parameters_schema, indent=8)
        
        # 2-3. execute 메소드 시그니처 조립 - 100% 신뢰성 보장
        type_mapping = {"string": "str", "number": "float", "integer": "int", "boolean": "bool", "array": "list", "object": "dict"}
        execute_args_list = [f"{name}: {type_mapping.get(dtype, 'str')}" for name, dtype in components.get("simple_parameters", {}).items()]
        execute_args = ", ".join(execute_args_list)

        # 2-4. execute 본문 들여쓰기 적용
        execute_body = textwrap.indent(components.get("execute_body", "        pass"), '    ')

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
