from openai import OpenAI
import json
from .utils.SystemUtils import ConfigLoader

# OpenAI 를 이용해서 도구(명세서)를 만드는 class

class OpenAISpecGenerator:
    """OpenAI API를 이용해 사용자 요청에 맞는 도구 명세서를 생성합니다."""
    def __init__(self):
        self.client = ConfigLoader().get_openai_client()

    def generate_spec(self, user_query: str, existing_tools: list) -> dict | None:
        prompt = f"""
        사용자 요청을 해결하기 위해 기존 도구 목록에 없는 새로운 도구가 필요한지 판단하고, 필요하다면 완벽한 JSON 명세서를 생성하세요.

        [사용자 요청]
        {user_query}

        [기존 도구 목록]
        {", ".join(existing_tools)}

        [출력 형식]
        - 새 도구가 필요 없으면: null
        - 새 도구가 필요하면: 'name', 'description', 'parameters' (JSON Schema 형식)를 포함한 JSON 객체
        """
        response = self.client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        print(f"[도구 생성용 OPENAI response] {response}")
        
        return json.loads(response.choices[0].message.content)