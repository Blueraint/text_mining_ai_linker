import os
import sys
import subprocess
import json
import re
from abc import ABC, abstractmethod

SAFE_NAME_PATTERN = re.compile(r'[^a-zA-Z0-9_]')

def sanitize_tool_name(name: str) -> str:
    if not name:
        return "tool_"
    safe = SAFE_NAME_PATTERN.sub('_', name).strip('_').lower()
    return safe or "tool_"

def normalize_tool_spec(spec: dict) -> dict:
    """
    스펙 정규화:
      - name 정규화
      - parameters.properties/required 정합성 보정
      - 타입 누락/오타 기본 string으로 보정
    """
    spec = dict(spec or {})
    spec["name"] = sanitize_tool_name(spec.get("name", ""))

    params = dict((spec.get("parameters") or {}))
    props = dict((params.get("properties") or {}))
    req = list((params.get("required") or []))

    # properties 타입 보정
    for k, v in list(props.items()):
        if not isinstance(v, dict):
            props[k] = {"type": "string"}
        else:
            t = props[k].get("type")
            if t not in ("string", "number", "integer", "boolean", "array", "object"):
                props[k]["type"] = "string"

    # required에 properties에 없는 키 제거
    req = [k for k in req if k in props]

    params["properties"] = props
    params["required"] = req
    spec["parameters"] = params
    return spec

class BaseToolGenerator(ABC):
    """도구 생성기의 공통 기능을 정의하는 추상 클래스"""

    @abstractmethod
    def generate_code(self, tool_spec: dict) -> str:
        """tool_spec을 받아 최종 파이썬 코드 문자열을 생성"""
        raise NotImplementedError

    def _test_generated_code(self, code: str, tool_name: str, tool_spec: dict, tool_directory: str = "tools") -> bool:
        """
        생성된 코드를 샌드박스에서 문법+런타임 검증:
          1) 임시 파일로 저장 (tools/temp_test_{name}.py)
          2) PYTHONPATH 추가 후 import 테스트
          3) **tool_spec 기반** 더미 kwargs 구성 → execute(**kwargs) 호출 → json.loads 검증
        """
        print(f"  [Generator] 생성된 '{tool_name}' 코드를 샌드박스에서 테스트합니다...")

        # 디렉토리 보장
        os.makedirs(tool_directory, exist_ok=True)
        test_module_name = f"temp_test_{tool_name}"
        test_filepath = os.path.join(tool_directory, f"{test_module_name}.py")

        try:
            with open(test_filepath, "w", encoding="utf-8") as f:
                f.write(code)

            # tool_spec을 런타임 테스터로 전달
            spec_json = json.dumps(tool_spec, ensure_ascii=False)

            runtime_tester = f"""
import os, sys, json
sys.path.insert(0, os.getcwd())
mod = __import__('{tool_directory}.{test_module_name}', fromlist=['*'])

# ToolBase 서브클래스 탐색
tool_cls = None
from {tool_directory}.base import ToolBase
for name in dir(mod):
    obj = getattr(mod, name)
    try:
        if isinstance(obj, type) and issubclass(obj, ToolBase) and obj is not ToolBase:
            tool_cls = obj
            break
    except Exception:
        pass
if tool_cls is None:
    raise RuntimeError('Tool class not found')

tool = tool_cls()

tool_spec = json.loads({json.dumps(spec_json)})
params = (tool_spec.get("parameters") or {{}})
props = (params.get("properties") or {{}})
required = (params.get("required") or [])

def default_for(prop):
    t = (prop or {{}}).get("type")
    if t == "string": return ""
    if t == "number": return 0.0
    if t == "integer": return 0
    if t == "boolean": return False
    if t == "array": return []
    if t == "object": return {{}}
    return None

kwargs = {{}}
# 필수 먼저
for k in required:
    if k in props:
        kwargs[k] = default_for(props.get(k))
# 선택도 채움
for k, v in props.items():
    if k not in kwargs:
        kwargs[k] = default_for(v)

out = tool.execute(**kwargs) if kwargs else tool.execute()
json.loads(out)
print('OK')
"""
            proc = subprocess.run(
                [sys.executable, "-c", runtime_tester],
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if proc.returncode != 0:
                print("  [Generator] 테스트 실패 (컴파일/실행 오류):")
                print(proc.stdout)
                print(proc.stderr)
                return False
            print("  [Generator] 테스트 성공: OK")
            return True
        finally:
            try:
                os.remove(test_filepath)
            except Exception:
                pass

    def create_and_register_tool(self, tool_spec: dict, tool_directory: str = "tools") -> bool:
        """
        1) 스펙 정규화(이름/required/타입)
        2) 코드 생성
        3) 샌드박스 문법/런타임 테스트 (spec 기반 더미 인자)
        4) 통과 시 {tool_name}_tool.py 로 저장
        """
        tool_spec = normalize_tool_spec(tool_spec)
        raw_name = tool_spec["name"]
        safe_name = raw_name or f"tool_{os.urandom(4).hex()}"

        generated_code = self.generate_code(tool_spec)
        if self._test_generated_code(generated_code, safe_name, tool_spec, tool_directory=tool_directory):
            plugin_path = os.path.join(tool_directory, f"{safe_name}_tool.py")
            with open(plugin_path, 'w', encoding='utf-8') as f:
                f.write(generated_code)
            print(f"  [Generator] 새 도구 '{safe_name}'을 '{plugin_path}'에 성공적으로 등록했습니다.")
            return True
        return False
