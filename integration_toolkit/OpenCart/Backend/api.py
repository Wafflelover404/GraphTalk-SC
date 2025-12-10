import os
import sys
import datetime
from typing import List, Optional, Tuple

import aiosqlite
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Allow importing the shared auth utilities from the root project
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from userdb import get_user_by_session_id, get_user_by_token  # reuse the same token/session validation

app = FastAPI(title="OpenCart Product Ingest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://wikiai.by", "https://api.wikiai.by", "https://esell.by"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security_scheme = HTTPBearer(auto_error=False)

DB_PATH = os.path.join(os.path.dirname(__file__), "opencart_products.db")


class ProductPayload(BaseModel):
    product_id: str
    name: str
    sku: Optional[str] = None
    price: str
    special: Optional[str] = None
    description: Optional[str] = None
    url: str
    image: Optional[str] = None
    quantity: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None


class ProductsImport(BaseModel):
    success: bool
    total_products: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    products: List[ProductPayload]


class APIResponse(BaseModel):
    status: str
    message: str
    response: Optional[dict] = None


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT,
                price REAL,
                special TEXT,
                description TEXT,
                url TEXT,
                image TEXT,
                quantity INTEGER,
                status INTEGER,
                rating INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.commit()


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")

    token = credentials.credentials
    user = await get_user_by_session_id(token)
    if user:
        return user

    user = await get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired session_id or token.")
    return user


async def upsert_products(products: List[ProductPayload]) -> Tuple[int, int]:
    """Insert or update products and return (inserted, updated) counts."""
    inserted = 0
    updated = 0
    now = datetime.datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as conn:
        for product in products:
            pid = _parse_int(product.product_id)
            if pid is None:
                # Skip malformed product id rows
                continue

            price = _parse_float(product.price)
            qty = _parse_int(product.quantity)
            status = _parse_int(product.status)
            rating = _parse_int(str(product.rating)) if product.rating is not None else None

            update_cursor = await conn.execute(
                """
                UPDATE products SET
                    name=?,
                    sku=?,
                    price=?,
                    special=?,
                    description=?,
                    url=?,
                    image=?,
                    quantity=?,
                    status=?,
                    rating=?,
                    updated_at=?
                WHERE product_id=?
                """,
                (
                    product.name,
                    product.sku,
                    price,
                    product.special,
                    product.description,
                    product.url,
                    product.image,
                    qty,
                    status,
                    rating,
                    now,
                    pid,
                ),
            )

            if update_cursor.rowcount:
                updated += 1
            else:
                await conn.execute(
                    """
                    INSERT INTO products (
                        product_id, name, sku, price, special, description, url,
                        image, quantity, status, rating, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        product.name,
                        product.sku,
                        price,
                        product.special,
                        product.description,
                        product.url,
                        product.image,
                        qty,
                        status,
                        rating,
                        now,
                    ),
                )
                inserted += 1
        await conn.commit()
    return inserted, updated


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.post("/opencart/products/import", response_model=APIResponse)
async def import_products(payload: ProductsImport, user=Depends(get_current_user)):
    inserted, updated = await upsert_products(payload.products)
    return APIResponse(
        status="success",
        message="Products imported",
        response={
            "inserted": inserted,
            "updated": updated,
            "received": len(payload.products),
        },
    )