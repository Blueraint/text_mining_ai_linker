
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 벡터DB를 정의한다
# Tf-idf 기반
class VectorDB_tfidf:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.documents = {} # {doc_id: content}
        self.metadata_store = {} # {doc_id: metadata}
        self.doc_vectors = None
        self.doc_ids = []

    def build_index(self):
        if not self.documents:
            self.doc_vectors = None
            self.doc_ids = []
            return

        self.doc_ids = list(self.documents.keys())
        doc_contents = [self.documents[id] for id in self.doc_ids]
        self.doc_vectors = self.vectorizer.fit_transform(doc_contents)

    def search(self, query: str, k: int = 1) -> list[tuple[float, dict]]:
        if self.doc_vectors is None or self.doc_vectors.shape[0] == 0:
            return []
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.doc_vectors).flatten()
        top_k_indices = scores.argsort()[-k:][::-1]

        return [(scores[i], self.doc_ids[i]) for i in top_k_indices if scores[i] > 0]
