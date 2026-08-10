from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.product_service import ProductService, get_product_service


router = APIRouter(tags=["products"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/products", response_class=HTMLResponse)
def list_products(request: Request, service: ProductService = Depends(get_product_service)) -> HTMLResponse:
    products = service.list_products(active_only=True)
    return templates.TemplateResponse(
        request,
        "products.html",
        {
            "products": products,
            "title": "Catalog",
            "page_type": "product_list",
        },
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, service: ProductService = Depends(get_product_service)) -> HTMLResponse:
    product = service.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {
            "product": product,
            "title": product.title,
            "page_type": "product_detail",
            "page_product_id": product.id,
            "page_category": product.category,
        },
    )
