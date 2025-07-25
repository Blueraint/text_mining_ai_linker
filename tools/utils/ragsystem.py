
from .tfidfdb import VectorDB_tfidf
import json

# LLM에 쓰일 RAG 를 정의한다
class RAG_System:
    def __init__(self):
        # 기본은 tf-idf 이용
        self.db = VectorDB_tfidf()

    def set_database(db) :
        """RAG 시스템에 쓰일 데이터베이스를 설정한다"""
        self.db = db

    def add_document(self, doc_id: str, content: str, metadata: dict, build_index: bool = True):
        """외부에서 문서 추가"""
        print(f"  [Knowledge Base] ADD: '{doc_id}' 문서 추가")
        self.db.documents[doc_id] = content
        self.db.metadata_store[doc_id] = metadata
        if build_index: self.db.build_index()

    def delete_document(self, doc_id: str, build_index: bool = True):
        """외부에서 문서 삭제"""
        if doc_id in self.db.documents:
            print(f"  [Knowledge Base] DELETE: '{doc_id}' 문서 삭제")
            del self.db.documents[doc_id]
            del self.db.metadata_store[doc_id]
            if build_index: self.db.build_index()

    def print_documents(self):
        """벡터DB 전체 내용 출력"""
        print("\n" + "="*20 + " RAG Knowledge Base Full Dump " + "="*20)
        if not self.db.documents:
            print("지식 베이스가 비어있습니다.")
        for doc_id, content in self.db.documents.items():
            print(f"\n--- Document ID: {doc_id} ---")
            print(f"  [Content] - {content}")
            print(f"  [Metadata] - {json.dumps(self.db.metadata_store.get(doc_id, {}), ensure_ascii=False)}")
        print("\n" + "="*64)

    # hybrid 검색엔진 이용을 위한 함수 정의
    def hybrid_search(self, query: str, k: int = 5) -> list[str]:
        """ VectorDB 의 두개의 index 검색 결과를 조합하여 최종 순위를 매기는 하이브리드 검색"""
        # 1. 각 엔진으로 K개의 결과 검색
        semantic_results = self.db.semantic_search(query, k=k)
        keyword_results = self.db.keyword_search(query, k=k)

        # 2. RRF(Reciprocal Rank Fusion)를 이용한 점수 재계산
        rrf_scores = {}
        k_rrf = 60  # RRF 알고리즘의 상수로, 보통 60을 사용

        # 의미 검색 결과에 대한 RRF 점수 계산
        for rank, (score, doc_id) in enumerate(semantic_results):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0
            rrf_scores[doc_id] += 1 / (k_rrf + rank + 1)

        # 키워드 검색 결과에 대한 RRF 점수 계산
        for rank, (score, doc_id) in enumerate(keyword_results):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0
            rrf_scores[doc_id] += 1 / (k_rrf + rank + 1)

        if not rrf_scores:
            return []

        # 3. 최종 점수가 높은 순으로 정렬하여 문서 ID 반환
        sorted_docs = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return sorted_docs

