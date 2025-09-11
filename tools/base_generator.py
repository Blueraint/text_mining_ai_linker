import os
import sys
import subprocess
import json
from abc import ABC, abstractmethod

class BaseToolGenerator(ABC):
    """도구 생성기의 공통 기능을 정의하는 추상 클래스"""

    def _test_generated_code(self, code: str, tool_name: str, tool_directory: str = "tools") -> bool:
        """[개선] 샌드박스 테스트 시, 프로젝트 루트 경로를 명시적으로 추가합니다."""
        print(f"  [Generator] 생성된 '{tool_name}' 코드를 샌드박스에서 테스트합니다...")
        
        # 임시 테스트 파일의 전체 경로 생성
        test_filepath = os.path.join(tool_directory, f"temp_test_{tool_name}.py")
        
        with open(test_filepath, 'w', encoding='utf-8') as f:
            f.write(code)
            
        # 프로젝트 루트 경로를 가져옴 (현재 스크립트 위치 기준)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        # 실행할 파이썬 코드 구성
        # 1. sys.path에 프로젝트 루트 추가
        # 2. 임시 모듈 import
        test_command = f"""
import sys
sys.path.append('{project_root}')
import {tool_directory}.temp_test_{tool_name}
print('OK')
"""
        try:
            result = subprocess.run(
                [sys.executable, "-c", test_command],
                capture_output=True, text=True, timeout=10, check=True
            )
            print(f"  [Generator] 테스트 성공: {result.stdout.strip()}")
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
    