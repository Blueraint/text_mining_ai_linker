# 파일명: tools/synchronize_knowledge_base_tool.py

import json  # <-- [해결 방안] 누락된 json 라이브러리 import 추가
from .base import ToolBase
from openai import OpenAI


class SynchronizeKnowledgeBaseTool_AI(ToolBase):
    name = "synchronize_knowledge_base"
    description = "외부 소스로부터 RAG 지식 베이스를 최신 상태로 동기화합니다."
    parameters = {
        "type": "object",
        "properties": {"filepath": {"type": "string", "description": "동기화할 데이터 파일의 경로 (예: latest_policies.json)"}},
        "required": ["filepath"]
    }

    # 이 Class는 Tool 이므로, 외부의 agent 가 이용하는 LLM client 를 상속받아서 질문을 이어서 한다. (api_key 를 직접 받아서 새로운 세션을 만들지 않는다!)
    def __init__(self, rag_system, _client):
        self.rag_system = rag_system
        self.client = _client

    def execute(self, filepath: str) -> str:
        """크롤링된 최신 데이터 파일과 현재 지식 베이스를 비교하여 동기화합니다."""
        print(f"  [Tool: RAG Sync] '{filepath}' 파일과 동기화를 시작합니다...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                latest_policies = json.load(f)
        except FileNotFoundError:
            return "오류: 동기화할 파일을 찾을 수 없습니다. 크롤러가 먼저 실행되어야 합니다."

        # 이하 AI를 이용한 동기화 계획 수립 및 실행 로직
        current_docs_summary = json.dumps(list(self.rag_system.db.documents.keys()))
        latest_policies_summary = json.dumps([p.get("policy_id") for p in latest_policies])

        prompt = f"""
        당신은 RAG 데이터베이스를 관리하는 AI입니다. 당신의 임무는 현재 DB 상태와 최신 파일 상태를 비교하여 동기화 계획을 JSON으로 수립하는 것입니다.

        ### 동기화 규칙
        1.  **'add'**: '최신 파일 ID' 목록에는 있지만 '현재 DB ID' 목록에는 없는 ID입니다.

        ### 데이터
        - 현재 DB ID: {current_docs_summary}
        - 최신 파일 ID: {latest_policies_summary}

        ### 출력
        위 규칙에 따라 'add' 해야 할 'policy_id' 목록을 JSON 형식으로만 응답하세요.
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        sync_plan = json.loads(response.choices[0].message.content)
        
        # 동기화 계획 실행
        added_count, deleted_count, updated_count = 0, 0, 0
        latest_policies_map = {p["policy_id"]: p for p in latest_policies}
        
        for doc_id in sync_plan.get("delete", []):
            self.rag_system.delete_document(doc_id, build_index=False)
            deleted_count += 1
            
        for doc_id in sync_plan.get("add", []):
            policy = latest_policies_map[doc_id]
            self.rag_system.add_document(
                doc_id=policy["policy_id"],
                content=f"{policy['title']}: {policy['summary']}",
                metadata={"source": "소진공(자동 동기화)", "required_docs": policy['required_docs']},
                build_index=False
            )
            added_count += 1
            
        for doc_id in sync_plan.get("update", []):
            # 실제로는 수정이지만, 간단하게 삭제 후 추가로 구현
            self.rag_system.delete_document(doc_id, build_index=False)
            policy = latest_policies_map[doc_id]
            self.rag_system.add_document(
                doc_id=policy["policy_id"],
                content=f"{policy['title']}: {policy['summary']}",
                metadata={"source": "소진공(자동 동기화)", "required_docs": policy['required_docs']},
                build_index=False
            )
            updated_count += 1
            
        self.rag_system.db.build_index()
        result_message = f"동기화 완료: {added_count}개 추가, {updated_count}개 수정, {deleted_count}개 삭제됨."
        print(f"  [Tool: RAG Sync] {result_message}")
        return result_message