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
        """[개선] 내용 변경이 감지된 정책만 지능적으로 동기화합니다."""
        print(f"  [Tool: RAG Sync] '{filepath}' 파일과 지능형 동기화를 시작합니다...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                latest_policies = json.load(f)
        except FileNotFoundError:
            return "오류: 동기화할 파일을 찾을 수 없습니다. 크롤러가 먼저 실행되어야 합니다."

        # 현재 DB와 최신 파일의 ID 및 콘텐츠 맵 준비
        current_docs = self.rag_system.db.documents
        current_doc_ids = set(current_docs.keys())
        latest_policies_map = {p.get("policy_id"): p for p in latest_policies if p.get("policy_id")}
        latest_policy_ids = set(latest_policies_map.keys())

        # Python 집합 연산으로 추가/삭제 대상 ID 결정
        ids_to_add = latest_policy_ids - current_doc_ids
        ids_to_delete = current_doc_ids - latest_policy_ids
        ids_to_check_for_update = current_doc_ids.intersection(latest_policy_ids)
        
        #  내용이 실제로 변경된 업데이트 대상 ID만 선별
        ids_to_update = []
        for doc_id in ids_to_check_for_update:
            # 새로운 콘텐츠 생성 (title + summary)
            new_policy = latest_policies_map[doc_id]
            new_content = f"{new_policy.get('title', '')}: {new_policy.get('summary', '')}"
            
            # 기존 콘텐츠와 비교
            if current_docs.get(doc_id) != new_content:
                ids_to_update.append(doc_id)

        print(f"  [Sync Plan] Add: {list(ids_to_add)}, Delete(X): {list(ids_to_delete)}, Update: {list(ids_to_update)}")
        
        # 동기화 계획 실행
        if not (ids_to_add or ids_to_delete or ids_to_update):
            result_message = "동기화 완료: 변경된 내용이 없습니다."
        else:
            # Delete 는 수행하지 않음
            # for doc_id in ids_to_delete:
                # self.rag_system.delete_document(doc_id, build_index=False)
            
            for doc_id in ids_to_add.union(ids_to_update): # 추가 및 업데이트 대상을 한번에 처리
                policy = latest_policies_map[doc_id]
                self.rag_system.add_document(
                    doc_id=policy["policy_id"],
                    content=f"{policy.get('title', '')}: {policy.get('summary', '')}",
                    metadata={"source": "소진공(자동 동기화)", "required_docs": policy.get('required_docs', [])},
                    build_index=False
                )
            
            self.rag_system.db.build_index()
            result_message = f"동기화 완료: {len(ids_to_add)}개 추가, {len(ids_to_update)}개 수정, {len(ids_to_delete)}개 삭제됨(X)."

        print(f"  [Tool: RAG Sync] {result_message}")
        return result_message
