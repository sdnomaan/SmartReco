from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from app.config import get_settings
from app.db.models import Product
from app.retrieval.embeddings import MeshEmbeddingClient


@dataclass(frozen=True)
class VectorSearchResult:
    product_id: int
    score: float | None
    document: str | None
    metadata: dict[str, Any]


class ProductVectorStore:
    def __init__(self, chroma_path: str | Path | None = None, embedding_client: MeshEmbeddingClient | None = None) -> None:
        settings = get_settings()
        self.chroma_path = Path(chroma_path or settings.chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_path))
        self.collection = self.client.get_or_create_collection(name="products", metadata={"hnsw:space": "cosine"})
        self.embedding_client = embedding_client or MeshEmbeddingClient()

    @staticmethod
    def build_document(product: Product) -> str:
        tags = ", ".join(product.tags) if isinstance(product.tags, list) else (str(product.tags) if product.tags else "")
        return (
            f"Title: {product.title}\n"
            f"Description: {product.description}\n"
            f"Category: {product.category}\n"
            f"Subcategory: {product.subcategory or ''}\n"
            f"Difficulty: {product.difficulty or ''}\n"
            f"Tags: {tags}\n"
            f"Duration: {product.duration or ''}\n"
            f"Instructor: {product.instructor or ''}"
        )

    @staticmethod
    def build_metadata(product: Product) -> dict[str, Any]:
        updated_at = product.updated_at or product.created_at
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return {
            "product_id": product.id,
            "category": product.category,
            "subcategory": product.subcategory or "",
            "difficulty": product.difficulty or "",
            "active": bool(product.active),
            "title": product.title,
            "updated_at": updated_at.astimezone(timezone.utc).isoformat() if updated_at else None,
        }

    def _ensure_product_id(self, product: Product) -> str:
        if product.id is None:
            raise ValueError("product must have an id before vector sync")
        return str(product.id)

    def _embed(self, document: str) -> list[float]:
        return self.embedding_client.embed_text(document)

    def add_product(self, product: Product) -> None:
        document = self.build_document(product)
        metadata = self.build_metadata(product)
        embedding = self._embed(document)
        self.collection.upsert(
            ids=[self._ensure_product_id(product)],
            documents=[document],
            metadatas=[metadata],
            embeddings=[embedding],
        )
        if self.get(product.id) is None:
            raise RuntimeError("Chroma verification failed after product upsert")

    def update_product(self, product: Product) -> None:
        self.add_product(product)

    def delete_product(self, product_id: int) -> None:
        self.collection.delete(ids=[str(product_id)])

    def search(self, query: str, filters: dict[str, Any] | None = None, top_k: int = 10) -> list[VectorSearchResult]:
        embedding = self._embed(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filters or None,
            include=["documents", "metadatas", "distances"],
        )
        matches: list[VectorSearchResult] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for index, raw_id in enumerate(ids):
            metadata = metadatas[index] or {}
            matches.append(
                VectorSearchResult(
                    product_id=int(raw_id),
                    score=None if distances[index] is None else float(1.0 - distances[index]),
                    document=documents[index],
                    metadata=metadata,
                )
            )
        return matches

    def get(self, product_id: int) -> dict[str, Any] | None:
        result = self.collection.get(ids=[str(product_id)], include=["documents", "metadatas", "embeddings"])
        ids = result.get("ids", [])
        if not ids:
            return None
        documents = result.get("documents")
        metadatas = result.get("metadatas")
        embeddings = result.get("embeddings")
        return {
            "product_id": int(ids[0]),
            "document": documents[0] if documents is not None and len(documents) > 0 else None,
            "metadata": metadatas[0] if metadatas is not None and len(metadatas) > 0 else None,
            "embedding": embeddings[0] if embeddings is not None and len(embeddings) > 0 else None,
        }