# 파일명: openai_hybrid_generator.py

import json, re, textwrap, ast
from .base_generator import BaseToolGenerator, sanitize_tool_name, normalize_tool_spec
from .utils.SystemUtils import ConfigLoader

def _normalize_execute_body(raw: str) -> str:
    """
    AI가 준 본문을 안전하게 정규화:
      - CRLF → LF, 탭 → 4스페이스
      - 선행/공통 들여쓰기 제거(dedent)
      - 모든 라인 4칸 배수로 보정
    """
    if not isinstance(raw, str):
        raw = ""
    s = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    s = textwrap.dedent(s)

    lines = s.split("\n")
    fixed = []
    for ln in lines:
        # 좌측 공백 수 카운트
        space_count = len(ln) - len(ln.lstrip(" "))
        # 4의 배수로 내림 보정 (혼합 들여쓰기 방지)
        if space_count % 4 != 0:
            space_count = (space_count // 4) * 4
        new_line = (" " * space_count) + ln.lstrip(" ")
        fixed.append(new_line)
    return "\n".join(fixed).strip("\n")

class OpenAIHybridCodeGenerator(BaseToolGenerator):
    """
    Python이 'spec'을 기반으로 '틀(Shell)'을 만들고,
    OpenAI는 'execute' 메소드의 '핵심 로직(본문)'만 생성합니다.
    """

    def __init__(self):
        self.client = ConfigLoader().get_openai_client()
        self.model_name = "gpt-4o"

    def _get_execute_body_from_ai(self, tool_spec: dict) -> dict:
        print(f"  [Generator-OpenAI] '{tool_spec['name']}' 도구의 '핵심 실행 로직' 생성을 요청합니다...")

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
1. Respond with a JSON object containing two keys: "imports_list" and "execute_body".
2. "imports_list": A list of standard Python libraries needed for your code (e.g., ["datetime"]).
3. "execute_body": The raw Python code (no leading 'def' line) that should go INSIDE the execute method.
4. Do NOT include class definitions or any import lines inside the execute_body.
5. The logic MUST return a JSON string using `json.dumps(..., ensure_ascii=False)`.
6. Do NOT define nested helper functions inside the body; inline simple logic.
7. OPTIONAL numeric params can be None; coerce them to 0 before arithmetic.
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        msg = response.choices[0].message.content
        try:
            payload = json.loads(msg)
        except Exception:
            payload = {"imports_list": [], "execute_body": "result={'status':'error','message':'internal logic gen failed'}\nreturn json.dumps(result, ensure_ascii=False)"}
        return payload

    def generate_code(self, tool_spec: dict) -> str:
        # 스펙 정규화
        tool_spec = normalize_tool_spec(tool_spec)
        tool_name = tool_spec["name"]
        class_name = "".join(word.capitalize() for word in tool_name.split('_')) + "Tool"

        # AI 본문 + 정규화
        components = self._get_execute_body_from_ai(tool_spec)
        imports = ["import json", "from .base import ToolBase"]
        for lib in components.get("imports_list", []):
            lib = (lib or "").strip()
            if lib and not lib.startswith(("from ", "import ")):
                imports.append(f"import {lib}")
            elif lib:
                imports.append(lib)
        imports_str = "\n".join(sorted(set(imports)))

        # parameters
        parameters_str = json.dumps(tool_spec.get("parameters", {}), ensure_ascii=False, indent=8)

        # execute 시그니처
        params_dict = tool_spec["parameters"]["properties"]
        required = tool_spec["parameters"]["required"]

        type_mapping = {"string": "str", "number": "float", "integer": "int",
                        "boolean": "bool", "array": "list", "object": "dict"}

        ordered = []
        for k in required:
            ordered.append((k, params_dict[k], True))
        for k, v in params_dict.items():
            if k not in required:
                ordered.append((k, v, False))

        execute_args_list = []
        numeric_optional = []
        for name, prop, is_req in ordered:
            py_type = type_mapping.get((prop or {}).get("type"), "str")
            if is_req:
                execute_args_list.append(f"{name}: {py_type}")
            else:
                execute_args_list.append(f"{name}: {py_type} = None")
                if (prop or {}).get("type") in ("number", "integer"):
                    numeric_optional.append(name)

        execute_args = ", ".join(execute_args_list)
        signature = f"def execute(self, {execute_args}) -> str:" if execute_args.strip() else "def execute(self) -> str:"

        # 본문 정규화 + 프렐류드
        raw_body = components.get("execute_body", "result={'status':'error','message':'no body'}\nreturn json.dumps(result, ensure_ascii=False)")
        cleaned = re.sub(r'^\s*import[^\n]*\n?', '', raw_body, flags=re.MULTILINE)
        cleaned = _normalize_execute_body(cleaned)

        prelude_lines = []
        for nm in numeric_optional:
            prelude_lines.append(f"if {nm} is None:\n    {nm} = 0")
        prelude = "\n".join(prelude_lines).strip("\n")
        if prelude:
            cleaned = f"{prelude}\n{cleaned}"

        # 메서드 내부 8칸 들여쓰기 적용
        indented_body = textwrap.indent(cleaned, '        ')

        # 최종 조립
        final_code = f"""{imports_str}

class {class_name}(ToolBase):
    name = "{tool_name}"
    description = "{tool_spec.get('description', '').replace('"','\\\"')}"
    parameters = {parameters_str}

    {signature}
{indented_body}
"""

        # 메모리 구문 검사(사전 탐지)
        try:
            ast.parse(final_code)
        except SyntaxError:
            # 한 번 더 강제 정리 후 재시도
            cleaned2 = _normalize_execute_body(cleaned)
            indented2 = textwrap.indent(cleaned2, '        ')
            final_code = f"""{imports_str}

class {class_name}(ToolBase):
    name = "{tool_name}"
    description = "{tool_spec.get('description', '').replace('"','\\\"')}"
    parameters = {parameters_str}

    {signature}
{indented2}
"""
            ast.parse(final_code)  # 실패 시 예외 전파

        print(f"  [Code Builder] '{tool_name}'의 최종 코드를 성공적으로 조립했습니다.")
        print(f"  [Code Source]\n'{final_code.strip()}")
        return final_code.strip()
