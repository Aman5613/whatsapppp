"""Products API router."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.services.csv_import import import_products_csv

router = APIRouter(prefix="/api/products", tags=["Products"])


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    category: str | None = None
    price: Decimal = Field(..., ge=0)
    stock: int = Field(default=0, ge=0)
    active: bool = True


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    price: float
    stock: int
    active: bool


@router.get("", response_model=list[ProductOut])
async def list_products(
    business_id: uuid.UUID = Query(..., description="Business tenant ID"),
    query: str | None = Query(None),
    category: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List products scoped by business_id with optional search and category filters."""
    repo = ProductRepository(session, business_id)
    products = await repo.search(query=query, category=category, limit=100)
    return [
        ProductOut(
            id=p.id,
            name=p.name,
            description=p.description,
            category=p.category,
            price=float(p.price),
            stock=p.stock,
            active=p.active,
        )
        for p in products
    ]


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    data: ProductCreate,
    business_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Create a new product within business catalog."""
    repo = ProductRepository(session, business_id)
    product = Product(
        business_id=business_id,
        name=data.name,
        description=data.description,
        category=data.category,
        price=data.price,
        stock=data.stock,
        active=data.active,
    )
    saved = await repo.create(product)
    await session.commit()
    return ProductOut(
        id=saved.id,
        name=saved.name,
        description=saved.description,
        category=saved.category,
        price=float(saved.price),
        stock=saved.stock,
        active=saved.active,
    )


@router.post("/import")
async def import_products(
    business_id: uuid.UUID = Query(...),
    dry_run: bool = Query(False, description="Simulate import and return validation report"),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Import products from CSV with dry_run validation and error reporting."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content_bytes = await file.read()
    try:
        csv_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = content_bytes.decode("latin-1")

    return await import_products_csv(
        csv_text=csv_text,
        business_id=business_id,
        session=session,
        dry_run=dry_run,
    )
