from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.sessions import require_admin
from app.db.models import User
from app.db.schemas import ProductCreate
from app.services.product_service import ProductService, ProductSyncError, get_product_service


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


def _parse_tags(tags: str | None) -> list[str] | None:
    if not tags:
        return []
    values = [item.strip() for item in tags.split(",")]
    return [item for item in values if item]


@router.get("/products", response_class=HTMLResponse)
def admin_products(request: Request, _: User = Depends(require_admin), service: ProductService = Depends(get_product_service)) -> HTMLResponse:
    products = service.list_products(active_only=False)
    return templates.TemplateResponse(request, "admin/products.html", {"products": products, "title": "Admin Products"})


@router.get("/products/new", response_class=HTMLResponse)
def new_product_form(request: Request, _: User = Depends(require_admin)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/product_form.html",
        {"product": None, "title": "New Product", "form_action": "/admin/products"},
    )


@router.post("/products")
def create_product(
    _: User = Depends(require_admin),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    subcategory: str = Form(""),
    price: float = Form(0.0),
    difficulty: str = Form(""),
    tags: str = Form(""),
    duration: str = Form(""),
    instructor: str = Form(""),
    active: str | None = Form(None),
    service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    try:
        product = service.create_product(
            ProductCreate(
                title=title,
                description=description,
                category=category,
                subcategory=subcategory or None,
                price=price,
                difficulty=difficulty or None,
                tags=_parse_tags(tags),
                duration=duration or None,
                instructor=instructor or None,
                active=active is not None,
            )
        )
    except ProductSyncError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RedirectResponse(url=f"/admin/products/{product.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_form(
    request: Request,
    product_id: int,
    _: User = Depends(require_admin),
    service: ProductService = Depends(get_product_service),
) -> HTMLResponse:
    product = service.get_product(product_id, include_inactive=True)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return templates.TemplateResponse(
        request,
        "admin/product_form.html",
        {"product": product, "title": f"Edit {product.title}", "form_action": f"/admin/products/{product.id}/update"},
    )


@router.post("/products/{product_id}/update")
def update_product(
    product_id: int,
    _: User = Depends(require_admin),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    subcategory: str = Form(""),
    price: float = Form(0.0),
    difficulty: str = Form(""),
    tags: str = Form(""),
    duration: str = Form(""),
    instructor: str = Form(""),
    active: str | None = Form(None),
    service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    try:
        service.update_product(
            product_id,
            ProductCreate(
                title=title,
                description=description,
                category=category,
                subcategory=subcategory or None,
                price=price,
                difficulty=difficulty or None,
                tags=_parse_tags(tags),
                duration=duration or None,
                instructor=instructor or None,
                active=active is not None,
            ),
        )
    except ProductSyncError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RedirectResponse(url=f"/admin/products/{product_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/deactivate")
def deactivate_product(
    product_id: int,
    _: User = Depends(require_admin),
    service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    try:
        service.deactivate_product(product_id)
    except ProductSyncError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RedirectResponse(url=f"/admin/products/{product_id}/edit", status_code=status.HTTP_303_SEE_OTHER)
