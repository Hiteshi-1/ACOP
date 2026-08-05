"""
ChromaDB persistent client + collection accessor.

Uses ChromaDB's built-in DefaultEmbeddingFunction (ONNX runtime, runs the
all-MiniLM-L6-v2 model locally) instead of sentence-transformers. This avoids
pulling in torch/transformers entirely -- a much lighter, faster install with
no version-conflict surface, at zero cost, with equivalent embedding quality
for this use case.
"""
import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.core.logging_config import logger


class ChromaManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"description": "ACOP incident runbooks and remediation knowledge base"},
        )
        logger.info(f"ChromaDB collection '{settings.CHROMA_COLLECTION_NAME}' ready "
                    f"({self.collection.count()} documents).")


chroma_manager = ChromaManager()
