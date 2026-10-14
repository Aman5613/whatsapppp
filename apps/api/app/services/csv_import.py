"""CSV parsing, row validation, preview, and import service."""

import csv
import io
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem
from app.models.product import Product


async def import_products_csv(
    csv_text: str,
    business_id: uuid.UUID,
    session: AsyncSession,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Parse products CSV, validate fields, return error report or persist records.

    Expected CSV columns: name, price, stock, category (optional), description (optional).
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return {
            "total_rows": 0,
            "valid_rows": 0,
            "error_count": 1,
            "dry_run": dry_run,
            "errors": [{"row": 1, "field": "header", "error": "Empty or invalid CSV file"}],
            "preview": [],
        }

    errors: list[dict[str, Any]] = []
    valid_products: list[Product] = []
    preview: list[dict[str, Any]] = []
    row_idx = 1

    for row in reader:
        row_idx += 1
        name = (row.get("name") or "").strip()
        price_str = (row.get("price") or "").strip()
        stock_str = (row.get("stock") or "0").strip()
        category = (row.get("category") or "").strip() or None
        description = (row.get("description") or "").strip() or None

        if not name:
            errors.append({"row": row_idx, "field": "name", "error": "Product name is required"})
            continue

        try:
            price = Decimal(price_str)
            if price < 0:
                errors.append(
                    {"row": row_idx, "field": "price", "error": "Price must be non-negative"}
                )
                continue
        except Exception:
            errors.append(
                {
                    "row": row_idx,
                    "field": "price",
                    "error": f"Invalid price numeric value: '{price_str}'",
                }
            )
            continue

        try:
            stock = int(stock_str)
            if stock < 0:
                errors.append(
                    {"row": row_idx, "field": "stock", "error": "Stock must be non-negative"}
                )
                continue
        except Exception:
            errors.append(
                {
                    "row": row_idx,
                    "field": "stock",
                    "error": f"Invalid stock integer value: '{stock_str}'",
                }
            )
            continue

        prod = Product(
            business_id=business_id,
            name=name,
            description=description,
            category=category,
            price=price,
            stock=stock,
            active=True,
        )
        valid_products.append(prod)

        if len(preview) < 5:
            preview.append(
                {
                    "name": name,
                    "price": float(price),
                    "stock": stock,
                    "category": category,
                }
            )

    total_rows = row_idx - 1
    valid_count = len(valid_products)

    if not dry_run and valid_products:
        session.add_all(valid_products)
        await session.commit()

    return {
        "total_rows": total_rows,
        "valid_rows": valid_count,
        "error_count": len(errors),
        "dry_run": dry_run,
        "errors": errors,
        "preview": preview,
    }


async def import_orders_csv(
    csv_text: str,
    business_id: uuid.UUID,
    session: AsyncSession,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Parse orders CSV, validate, and persist orders with order_items.

    Expected CSV columns: customer_phone, product_name, quantity, unit_price, status (optional).
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return {
            "total_rows": 0,
            "valid_rows": 0,
            "error_count": 1,
            "dry_run": dry_run,
            "errors": [{"row": 1, "field": "header", "error": "Empty or invalid CSV file"}],
            "preview": [],
        }

    errors: list[dict[str, Any]] = []
    valid_orders: list[Order] = []
    preview: list[dict[str, Any]] = []
    row_idx = 1

    for row in reader:
        row_idx += 1
        phone = (row.get("customer_phone") or "").strip()
        product_name = (row.get("product_name") or "").strip()
        qty_str = (row.get("quantity") or "1").strip()
        price_str = (row.get("unit_price") or "0").strip()
        status = (row.get("status") or "pending").strip()

        if not phone:
            errors.append(
                {"row": row_idx, "field": "customer_phone", "error": "Customer phone is required"}
            )
            continue
        if not product_name:
            errors.append(
                {"row": row_idx, "field": "product_name", "error": "Product name is required"}
            )
            continue

        try:
            qty = int(qty_str)
            if qty <= 0:
                errors.append(
                    {
                        "row": row_idx,
                        "field": "quantity",
                        "error": "Quantity must be greater than 0",
                    }
                )
                continue
        except Exception:
            errors.append(
                {
                    "row": row_idx,
                    "field": "quantity",
                    "error": f"Invalid integer quantity: '{qty_str}'",
                }
            )
            continue

        try:
            unit_price = Decimal(price_str)
            if unit_price < 0:
                errors.append(
                    {
                        "row": row_idx,
                        "field": "unit_price",
                        "error": "Unit price cannot be negative",
                    }
                )
                continue
        except Exception:
            errors.append(
                {
                    "row": row_idx,
                    "field": "unit_price",
                    "error": f"Invalid price numeric: '{price_str}'",
                }
            )
            continue

        total = unit_price * qty
        order = Order(
            business_id=business_id,
            customer_phone=phone,
            status=status,
            total=total,
        )
        item = OrderItem(
            product_name=product_name,
            quantity=qty,
            unit_price=unit_price,
        )
        order.items.append(item)
        valid_orders.append(order)

        if len(preview) < 5:
            preview.append(
                {
                    "customer_phone": phone,
                    "product_name": product_name,
                    "quantity": qty,
                    "total": float(total),
                    "status": status,
                }
            )

    total_rows = row_idx - 1
    valid_count = len(valid_orders)

    if not dry_run and valid_orders:
        session.add_all(valid_orders)
        await session.commit()

    return {
        "total_rows": total_rows,
        "valid_rows": valid_count,
        "error_count": len(errors),
        "dry_run": dry_run,
        "errors": errors,
        "preview": preview,
    }
