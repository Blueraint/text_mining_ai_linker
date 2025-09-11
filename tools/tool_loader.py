import os
import importlib
import inspect
from tools.utils.SystemUtils import ConfigLoader
from tools.base import ToolBase

class ToolLoader:
    def __init__(self, rag_system, user_database, tool_directory: str = "tools"):
        # tool 에 넘길 변수를 설정하는 경우 아래에다 설정
        self.services = {
            "rag_system": rag_system,
            "user_database": user_database
        }
        self.tools = self._load_tools(tool_directory)

    def _load_tools(self, tool_directory):
        loaded_tools = []

        if not os.path.isdir(tool_directory):
            print(f"[ToolLoader Error] '{tool_directory}' 디렉토리를 찾을 수 없습니다. 현재 작업 경로는 '{os.getcwd()}' 입니다.")
            return loaded_tools

        print(f"[ToolLoader] '{tool_directory}' 디렉토리에서 도구를 검색합니다...")

        for filename in os.listdir(tool_directory):
            if filename.endswith("_tool.py"):
                module_name = f"{tool_directory}.{filename[:-3]}"

                try:
                    module = importlib.import_module(module_name)
                    print(f"  - 모듈 로드 성공: {module_name}")

                    for attribute_name in dir(module):
                        attribute = getattr(module, attribute_name)
                        if (isinstance(attribute, type) and
                            issubclass(attribute, ToolBase) and
                            attribute is not ToolBase): # ToolBase 자체는 제외

                            sig = inspect.signature(attribute.__init__)
                            params = sig.parameters

                            dependencies = {}
                            for param_name in params:
                                if param_name in self.services:
                                    dependencies[param_name] = self.services[param_name]

                            tool_instance = attribute(**dependencies)
                            loaded_tools.append(tool_instance)
                            print(f"    - 도구 등록 완료: {tool_instance.name}")

                except ImportError as e:
                    print(f"[ToolLoader Error] 모듈 '{module_name}'을 import하는 중 오류 발생: {e}")

        if not loaded_tools:
            print("[ToolLoader Warning] 로드된 도구가 없습니다. 'tools' 디렉토리 구조와 파일명(_tool.py)을 확인하세요.")

        return loaded_tools