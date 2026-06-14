import chromadb
from sentence_transformers import SentenceTransformer


def embed_query(text: str) -> list[float]:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chromadb.Client()
    return model.encode(text).tolist()
