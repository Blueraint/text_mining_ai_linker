from .base import ToolBase
from .utils.hybriddb import VectorDB_hybrid
import json
# {"type": "function", "function": {"name": "search_knowledge_base", "description": "사용자 질문과 가장 관련된 정책 정보를 지식 베이스에서 검색합니다.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "사용자의 원본 질문"}}, "required": ["query"]}}},

class SearchKnowledgeBaseTool(ToolBase) :
    name = "search_knowledge_base"
    description = "사용자 질문과 가장 관련된 정책 정보를 지식 베이스에서 검색합니다."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "사용자의 원본 질문"}},
        "required": ["query"]
    }

    def __init__(self, rag_system) :
        self.rag_system = rag_system

    def execute(self, query: str) -> str :
        print(f"RAG : {self.rag_system}")

        if(isinstance(self.rag_system.db, VectorDB_hybrid)) :
            results = self.rag_system.db.hybrid_search(query, k=1)
        else :
            results = self.rag_system.db.search(query, k=1)

        if not results: return "관련 정보를 찾지 못했습니다."
        score, doc_id = results[0]
        if score < 0.1: return "관련 정보를 찾지 못했습니다. 좀 더 구체적인 키워드로 질문해주세요."

        content = self.rag_system.db.documents[doc_id]
        metadata = self.rag_system.db.metadata_store[doc_id]
        return json.dumps({"content": content, "metadata": metadata}, ensure_ascii=False)