import re
import os
import configparser
from openai import OpenAI
import google.generativeai as genai
import anthropic

# 기본적인 Privacy 를 처리하기 위한 간단Util
class PrivacyUtils:
    @staticmethod
    def mask_pii(text: str) -> str:
        text = re.sub(r"(\d{6})[-]\d{7}", r"\1-*******", text)
        text = re.sub(r"(\d{3})[-]\d{2}[-]\d{5}", r"\1-**-*****", text)
        return text

    @staticmethod
    def log_securely(message: str):
        print(PrivacyUtils.mask_pii(message))
        
        
# Config file(app.properties) 를 처리하기 위한 Loader Util
class ConfigLoader:
    _instance = None

    def __new__(cls, properties_file_path='app.properties'):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._init_config(properties_file_path)
        return cls._instance

    def _init_config(self, properties_file_path):
        """설정 파일을 '선택적으로' 로드합니다."""
        self.config = configparser.ConfigParser(interpolation=None)
        
        # [개선] 파일이 존재하면 읽고, 존재하지 않으면 (클라우드 환경) 경고만 출력하고 넘어갑니다.
        if os.path.exists(properties_file_path):
            self.config.read(properties_file_path, encoding='utf-8')
            print(f"[ConfigLoader] {properties_file_path} 파일을 로드했습니다. (Fallback으로 사용)")
        else:
            print(f"[ConfigLoader Warning] '{properties_file_path}' 파일을 찾을 수 없습니다. 환경 변수만 사용합니다.")

    def _get_priority_key(self, env_key: str, file_key: str) -> str:
        """
        [핵심 로직] 1순위로 환경 변수를 확인하고, 없으면 2순위로 properties 파일을 확인합니다.
        """
        # 1순위: 환경 변수 확인
        api_key = os.environ.get(env_key)
        if api_key:
            return api_key
            
        # 2순위: properties 파일 확인 (환경 변수가 없는 경우)
        try:
            api_key = self.get_api_key(file_key)
            return api_key
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            # 두 곳 모두에 키가 없는 경우 최종 에러 발생
            raise ValueError(f"'{env_key}' 환경 변수와 '{file_key}' 파일 설정이 모두 없습니다. 하나 이상 설정해야 합니다.") from e

    def get_api_key(self, key_name: str) -> str:
        """[API] 섹션에서 지정한 key_name에 해당하는 값을 반환"""
        try:
            api_key = self.config.get('API', key_name)
            if not api_key.strip():
                raise ValueError(f"[ConfigLoader] '{key_name}'의 값이 비어 있습니다.")
            return api_key
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            raise ValueError(f"[ConfigLoader] 'API.{key_name}' 로드 중 오류: {e}") from e

    def get_openai_client(self) -> OpenAI:
        """OpenAI 클라이언트 생성"""
        # api_key = self.get_api_key('openai.api.key')
        api_key = self._get_priority_key('OPENAI_API_KEY', 'openai.api.key')

        return OpenAI(api_key=api_key)

    def get_gemini_model(self):
        """Gemini 모델 객체 생성"""
        # api_key = self.get_api_key('gemini.api.key')
        api_key = self._get_priority_key('GEMINI_API_KEY', 'gemini.api.key')

        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    
    def get_claude_client(self) -> anthropic.Anthropic:
        """Anthropic 클라이언트 객체를 생성하여 반환합니다."""
        try:
            # api_key = self.get_api_key('claude.api.key')
            api_key = self._get_priority_key('CLAUDE_API_KEY', 'claude.api.key')

            return anthropic.Anthropic(api_key=api_key)
        except ValueError as e:
            raise e



# Prompt(Message String) 을 읽어들이는 Loader Util
class PromptLoader:
    _instance = None

    def __new__(cls, properties_file_path='message.properties'):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            cls._instance._init_prompts(properties_file_path)
        return cls._instance

    def _init_prompts(self, properties_file_path):
        """설정 파일을 읽고 프롬프트들을 초기화합니다."""
        self.prompts = configparser.ConfigParser(interpolation=None)
        
        if not os.path.exists(properties_file_path):
            raise FileNotFoundError(f"오류: 프롬프트 파일 '{properties_file_path}'을(를) 찾을 수 없습니다.")
        
        # UTF-8 인코딩으로 파일 읽기
        self.prompts.read(properties_file_path, encoding='utf-8')
        print(f"[PromptLoader] {properties_file_path} 파일을 성공적으로 로드했습니다.")

    def get_prompt(self, key: str) -> str:
        """'Prompts' 섹션에서 특정 프롬프트를 가져옵니다."""
        try:
            prompt = self.prompts.get('Prompts', key)
            if not prompt:
                raise ValueError(f"'{key}' 프롬프트가 비어있습니다.")
            # 여러 줄로 된 프롬프트의 양쪽 공백을 제거하여 반환
            return prompt.strip()
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            raise KeyError(f"프롬프트 파일에서 '{key}'을(를) 읽는 중 오류 발생: {e}") from e
