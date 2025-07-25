import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import torch

# SentenceTransformer를 이용한 개선된 시맨틱 벡터DB
# 단순 tfIdf 기법은 단어 유사도만 파악하므로 시멘틱으로 단어/문장 의미를 파악
class VectorDB_semantic :
    # 'distiluse-base-multilingual-cased-v1' 모델은 범용 문장 이해 능력이 탁월하나, 일반적인 단어 의미에 집중한다(일반화의 함정)
    # ex) 소상공인 정책자금 대출 : '대출', '정책' 에 높은 가중치, '혁신성장 지원평가 대출' 은 '기술평가' 보다 '대출'에 높은 연관성을 주게 됨
    # def __init__(self, model_name='distiluse-base-multilingual-cased-v1'):
    def __init__(self, model_name='jhgan/ko-sroberta-multitask'):
        # GPU(or CPU) 설정
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        # TfidfVectorizer 대신, 의미를 이해하는 언어 모델 로드
        self.model = SentenceTransformer(model_name, device=device)
        self.documents = {}  # {doc_id: content}
        self.metadata_store = {}  # {doc_id: metadata}
        self.doc_vectors = None
        self.doc_ids = []
        # FAISS 인덱스 초기화 (모델의 벡터 차원 수에 맞게)
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.model.get_sentence_embedding_dimension()))

    def build_index(self):
        """저장된 모든 문서를 시맨틱 벡터로 변환하여 FAISS 인덱스에 추가"""

        if not self.documents:
            # 인덱스 초기화
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.model.get_sentence_embedding_dimension()))
            self.doc_ids = []
            return

        self.doc_ids = list(self.documents.keys())
        doc_contents = [self.documents[id] for id in self.doc_ids]

        # model.encode를 사용하여 의미 벡터 생성
        print("  [VectorDB] 문서들을 의미 벡터로 변환 중...")
        self.doc_vectors = self.model.encode(doc_contents, convert_to_tensor=False, normalize_embeddings=True)

        # FAISS 인덱스 재생성
        self.index.reset()
        # FAISS는 numpy array의 ID로 정수만 받으므로, 순차적인 ID를 생성하여 매핑
        self.index.add_with_ids(self.doc_vectors.astype('float32'), np.arange(len(self.doc_ids)))
        print("  [VectorDB] 인덱스 구축 완료.")

    def search(self, query: str, k: int = 1) -> list[tuple[float, dict]]:
        """질문을 의미 벡터로 변환하여 가장 유사한 문서를 검색"""

        if self.index.ntotal == 0:
            return []

        # 질문을 의미 벡터로 변환
        query_vector = self.model.encode([query], convert_to_tensor=False, normalize_embeddings=True)

        # FAISS를 이용한 검색
        scores, indices = self.index.search(query_vector.astype('float32'), k)

        results = []
        for i, score in zip(indices[0], scores[0]):
            if i != -1:
                doc_id = self.doc_ids[i]
                results.append((score, doc_id))
        return results