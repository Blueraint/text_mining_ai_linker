
import os
import sys
import subprocess
import json
from abc import ABC, abstractmethod

# tool_generator.py 도구 생성기의 공통 추상화 클래스

class BaseToolGenerator(ABC):
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
                

    @abstractmethod
    def generate_code(self, tool_spec: dict) -> str:
        """실제 코드 생성 로직 (자식 클래스에서 구현)"""
        pass

    def create_and_register_tool(self, tool_spec: dict, tool_directory: str = "tools") -> bool:
        tool_name = tool_spec.get("name")
        if not tool_name: return False
        
        generated_code = self.generate_code(tool_spec)
        
        if self._test_generated_code(generated_code, tool_name):
            plugin_path = os.path.join(tool_directory, f"{tool_name}_tool.py")
            with open(plugin_path, 'w', encoding='utf-8') as f:
                f.write(generated_code)
            print(f"  [Generator] 새 도구 '{tool_name}'을 '{plugin_path}'에 성공적으로 등록했습니다.")
            return True
        return False