from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.db.models import Product
from app.db.repositories import get_product_by_id, list_products
from app.db.schemas import ProductCreate
from app.retrieval.chroma_store import ProductVectorStore


class ProductSyncError(RuntimeError):
    pass


def _clean_error(message: str) -> str:
    return message[:1000]


class ProductService:
    def __init__(self, db: Session, vector_store: ProductVectorStore | None = None) -> None:
        self.db = db
        self.vector_store = vector_store or ProductVectorStore()

    def _persist_sync_state(self, product: Product, status: str, error: str | None = None) -> Product:
        product.vector_sync_status = status
        product.vector_sync_error = error
        product.vector_synced_at = datetime.now(timezone.utc) if status == "SYNCED" else None
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def _sync_vector_store(self, product: Product) -> None:
        self.vector_store.update_product(product)

    def create_product(self, product_in: ProductCreate) -> Product:
        product = Product(
            title=product_in.title,
            description=product_in.description,
            category=product_in.category,
            subcategory=product_in.subcategory,
            price=product_in.price,
            difficulty=product_in.difficulty,
            tags=product_in.tags or [],
            duration=product_in.duration,
            instructor=product_in.instructor,
            active=product_in.active,
            vector_sync_status="PENDING",
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)

        try:
            self._sync_vector_store(product)
        except Exception as exc:  # noqa: BLE001
            error_message = _clean_error(str(exc))
            self._persist_sync_state(product, "FAILED", error_message)
            raise ProductSyncError(f"Failed to sync product {product.id} to Chroma") from exc

        return self._persist_sync_state(product, "SYNCED")

    def update_product(self, product_id: int, product_in: ProductCreate) -> Product:
        product = self.get_product(product_id, include_inactive=True)
        if product is None:
            raise ValueError("Product not found")

        product.title = product_in.title
        product.description = product_in.description
        product.category = product_in.category
        product.subcategory = product_in.subcategory
        product.price = product_in.price
        product.difficulty = product_in.difficulty
        product.tags = product_in.tags or []
        product.duration = product_in.duration
        product.instructor = product_in.instructor
        product.active = product_in.active
        product.vector_sync_status = "PENDING"
        self.db.commit()
        self.db.refresh(product)

        try:
            self._sync_vector_store(product)
        except Exception as exc:  # noqa: BLE001
            error_message = _clean_error(str(exc))
            self._persist_sync_state(product, "FAILED", error_message)
            raise ProductSyncError(f"Failed to sync updated product {product.id} to Chroma") from exc

        return self._persist_sync_state(product, "SYNCED")

    def deactivate_product(self, product_id: int) -> Product:
        product = self.get_product(product_id, include_inactive=True)
        if product is None:
            raise ValueError("Product not found")

        product.active = False
        product.vector_sync_status = "PENDING"
        self.db.commit()
        self.db.refresh(product)

        try:
            self._sync_vector_store(product)
        except Exception as exc:  # noqa: BLE001
            error_message = _clean_error(str(exc))
            self._persist_sync_state(product, "FAILED", error_message)
            raise ProductSyncError(f"Failed to deactivate product {product.id} in Chroma") from exc

        return self._persist_sync_state(product, "SYNCED")

    def delete_product(self, product_id: int) -> None:
        self.vector_store.delete_product(product_id)
        product = self.get_product(product_id, include_inactive=True)
        if product is not None:
            self.db.delete(product)
            self.db.commit()

    def get_product(self, product_id: int, include_inactive: bool = False) -> Product | None:
        product = get_product_by_id(self.db, product_id)
        if product is None:
            return None
        if not include_inactive and not product.active:
            return None
        return product

    def list_products(self, active_only: bool = True) -> list[Product]:
        return list_products(self.db, active_only=active_only)


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    settings = get_settings()
    _ = settings  # Keep settings loading explicit for future extension without logging secrets.
    return ProductService(db=db)
