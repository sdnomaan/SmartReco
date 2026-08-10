from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from sqlalchemy.orm import Session

from app.db.repositories import get_product_by_id
from app.retrieval.chroma_store import ProductVectorStore
from app.services.product_service import ProductService


@dataclass(frozen=True)
class CatalogSyncReport:
    product_id: int
    exists_in_db: bool
    exists_in_chroma: bool
    is_in_sync: bool
    reason: str | None = None


def verify_product_sync(product_id: int, db: Session, vector_store: ProductVectorStore | None = None) -> CatalogSyncReport:
    store = vector_store or ProductVectorStore()
    product = get_product_by_id(db, product_id)
    chroma_record = store.get(product_id)

    if product is None:
        return CatalogSyncReport(product_id=product_id, exists_in_db=False, exists_in_chroma=chroma_record is not None, is_in_sync=False, reason="missing_db_product")

    if chroma_record is None:
        return CatalogSyncReport(product_id=product_id, exists_in_db=True, exists_in_chroma=False, is_in_sync=False, reason="missing_chroma_record")

    metadata = chroma_record.get("metadata") or {}
    expected_updated_at = product.updated_at or product.created_at
    if expected_updated_at.tzinfo is None:
        expected_updated_at = expected_updated_at.replace(tzinfo=timezone.utc)
    is_in_sync = (
        int(metadata.get("product_id", -1)) == product.id
        and bool(metadata.get("active", False)) == bool(product.active)
        and metadata.get("updated_at") == expected_updated_at.isoformat()
    )
    return CatalogSyncReport(
        product_id=product_id,
        exists_in_db=True,
        exists_in_chroma=True,
        is_in_sync=is_in_sync,
        reason=None if is_in_sync else "stale_or_mismatched_metadata",
    )


def sync_product(product_id: int, db: Session, vector_store: ProductVectorStore | None = None) -> CatalogSyncReport:
    store = vector_store or ProductVectorStore()
    service = ProductService(db=db, vector_store=store)
    product = service.get_product(product_id, include_inactive=True)
    if product is None:
        return CatalogSyncReport(product_id=product_id, exists_in_db=False, exists_in_chroma=False, is_in_sync=False, reason="missing_db_product")

    store.update_product(product)
    return verify_product_sync(product_id, db=db, vector_store=store)