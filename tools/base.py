# 파일명: tools/base.py
from abc import ABC, abstractmethod

class ToolBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """도구의 이름 (AI가 호출할 이름)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """도구의 기능에 대한 설명"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """도구가 받는 파라미터 명세 (JSON Schema)"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """도구의 실제 로직을 수행하는 메소드"""
        pass