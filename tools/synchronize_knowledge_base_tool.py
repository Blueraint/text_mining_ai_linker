# 파일명: tools/synchronize_knowledge_base_tool.py

import json
from .base import ToolBase
# 이 도구는 더 이상 OpenAI 라이브러리가 필요 없습니다.
# LLM AI는 두 데이터를 단순비교하는 것에는 약점을 보이기 때문에, 완전히 정해진 rule 에 따라 DB를 업데이트하는 정적인 규칙의 코드를 작성
# 단, 크롤러는 AI를 통해 가져온다

class SynchronizeKnowledgeBaseTool(ToolBase):
    name = "synchronize_knowledge_base"
    description = "외부 소스로부터 RAG 지식 베이스를 최신 상태로 동기화합니다."
    parameters = {
        "type": "object",
        "properties": {"filepath": {"type": "string", "description": "동기화할 데이터 파일의 경로 (예: latest_policies.json)"}},
        "required": ["filepath"]
    }

    def __init__(self, rag_system):
        self.rag_system = rag_system

    def execute(self, filepath: str) -> str:
        """[개선] Python 코드로 직접 비교하여 RAG 지식 베이스를 동기화합니다."""
        print(f"  [Tool: RAG Sync] '{filepath}' 파일과 동기화를 시작합니다...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                latest_policies = json.load(f)
        except FileNotFoundError:
            return "오류: 동기화할 파일을 찾을 수 없습니다. 크롤러가 먼저 실행되어야 합니다."

        # 1. 현재 DB와 최신 파일의 ID를 집합(set)으로 변환
        current_doc_ids = set(self.rag_system.db.documents.keys())
        latest_policy_ids = {p.get("policy_id") for p in latest_policies if p.get("policy_id")}
        latest_policies_map = {p["policy_id"]: p for p in latest_policies if p.get("policy_id")}

        # 2. Python 집합 연산을 이용해 신뢰할 수 있는 동기화 계획 수립
        ids_to_add = latest_policy_ids - current_doc_ids
        ids_to_delete = current_doc_ids - latest_policy_ids
        ids_to_update = current_doc_ids.intersection(latest_policy_ids)
        
        print(f"  [Sync Plan] Add: {list(ids_to_add)}, Delete: {list(ids_to_delete)}, Update: {list(ids_to_update)}")

        # 3. 동기화 계획 실행
        # for doc_id in ids_to_delete:
        #     self.rag_system.delete_document(doc_id, build_index=False)
            
        for doc_id in ids_to_add:
            policy = latest_policies_map[doc_id]
            self.rag_system.add_document(
                doc_id=policy["policy_id"],
                content=f"{policy['title']}: {policy['summary']}",
                metadata={"source": "소진공(자동 동기화)", "required_docs": policy.get('required_docs', [])},
                build_index=False
            )
            
        for doc_id in ids_to_update:
            # 업데이트는 간단하게 삭제 후 추가로 구현
            self.rag_system.delete_document(doc_id, build_index=False)
            policy = latest_policies_map[doc_id]
            self.rag_system.add_document(
                doc_id=policy["policy_id"],
                content=f"{policy['title']}: {policy['summary']}",
                metadata={"source": "소진공(자동 동기화)", "required_docs": policy.get('required_docs', [])},
                build_index=False
            )
            
        self.rag_system.db.build_index()
        
        result_message = f"동기화 완료: {len(ids_to_add)}개 추가, {len(ids_to_update)}개 수정, {len(ids_to_delete)}개 삭제됨."
        print(f"  [Tool: RAG Sync] {result_message}")
        return result_message