import numpy as np
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import torch

# 하이브리드(tfidf + semantic) 검색을 위한 dual-index VectorDB
# 시멘틱 기법은 문장의 의미에만 집중하므로, 정확한 의도 파악이 어려울 수 있다
# 시멘틱 검색으로 문장 단위의 해석 수행하고, tfidf 로 사용자가 필요로 하는 키워드를 탐색
class VectorDB_hybrid:
    def __init__(self, model_name='jhgan/ko-sroberta-multitask'):
        # 1. 의미 기반 검색 엔진
        print(f"  [VectorDB] 시맨틱 검색 모델 '{model_name}' 로드 중...")
        # GPU(or CPU) 설정
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        self.semantic_model = SentenceTransformer(model_name, device=device)
        self.faiss_index = faiss.IndexIDMap(faiss.IndexFlatIP(self.semantic_model.get_sentence_embedding_dimension()))

        # 2. 키워드 기반 검색 엔진
        self.keyword_vectorizer = TfidfVectorizer()
        self.tfidf_matrix = None

        # 공통 데이터 저장소
        self.documents = {}
        self.metadata_store = {}
        self.doc_ids = []

    def build_index(self):
        if not self.documents: return

        self.doc_ids = list(self.documents.keys())
        doc_contents = [self.documents[id] for id in self.doc_ids]

        # 의미 기반 인덱스 구축
        print("  [VectorDB] 의미 기반 인덱스(FAISS) 구축 중...")
        semantic_vectors = self.semantic_model.encode(doc_contents, convert_to_tensor=False, normalize_embeddings=True)
        self.faiss_index.reset()
        self.faiss_index.add_with_ids(semantic_vectors.astype('float32'), np.arange(len(self.doc_ids)))

        # 키워드 기반 인덱스 구축
        print("  [VectorDB] 키워드 기반 인덱스(TF-IDF) 구축 중...")
        self.tfidf_matrix = self.keyword_vectorizer.fit_transform(doc_contents)
        print("  [VectorDB] 모든 인덱스 구축 완료.")

    def semantic_search(self, query: str, k: int) -> list[tuple[float, str]]:
        """의미가 유사한 문서를 검색"""
        if self.faiss_index.ntotal == 0: return []
        query_vector = self.semantic_model.encode([query], convert_to_tensor=False, normalize_embeddings=True)
        scores, indices = self.faiss_index.search(query_vector.astype('float32'), k)
        return [(scores[0][i], self.doc_ids[idx]) for i, idx in enumerate(indices[0]) if idx != -1]

    def keyword_search(self, query: str, k: int) -> list[tuple[float, str]]:
        """키워드가 일치하는 문서를 검색"""
        if self.tfidf_matrix is None: return []
        query_vector = self.keyword_vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        top_k_indices = scores.argsort()[-k:][::-1]
        return [(scores[i], self.doc_ids[i]) for i in top_k_indices if scores[i] > 0]
