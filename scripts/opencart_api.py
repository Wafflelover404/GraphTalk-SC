# opencart_api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Tuple, Dict, Any
import datetime
import aiosqlite
import os
from pydantic import BaseModel
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opencart", tags=["OpenCart"])

# Reuse the same security scheme as other APIs
security_scheme = HTTPBearer(auto_error=False)

# Database path
DB_PATH = os.path.expanduser('~/opencart_products.db')

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
    """Initialize the OpenCart products database."""
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


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """Get the current user from the authorization token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required.")
    
    # Reuse the existing user authentication
    from userdb import get_user_by_token
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
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


@router.on_event("startup")
async def on_startup():
    await init_db()


@router.post("/products/import", response_model=APIResponse)
async def import_products(payload: ProductsImport, user=Depends(get_current_user)):
    """
    Import products from OpenCart.
    
    This endpoint accepts a list of products and either inserts them as new records
    or updates existing ones based on the product_id.
    """
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


@router.get("/products", response_model=APIResponse)
async def list_products(
    q: Optional[str] = Query(None, description="Search query to filter products by name, SKU, or description"),
    limit: int = Query(50, le=100, description="Number of products per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    in_stock: Optional[bool] = Query(None, description="Filter products in stock"),
    status: Optional[int] = Query(None, description="Filter by product status"),
    user=Depends(get_current_user)
):
    """
    List and search products with filtering and pagination.
    
    Supports text search across product names, SKUs, and descriptions,
    with additional filtering by price, stock status, and product status.
    """
    try:
        query = """
            SELECT 
                product_id, name, sku, price, special, description, 
                url, image, quantity, status, rating, updated_at
            FROM products
            WHERE 1=1
        """
        params: List[Any] = []
        
        # Add search query conditions
        if q:
            query += " AND (name LIKE ? OR sku LIKE ? OR description LIKE ?)"
            search_term = f"%{q}%"
            params.extend([search_term, search_term, search_term])
        
        # Add price filters
        if min_price is not None:
            query += " AND price >= ?"
            params.append(min_price)
        if max_price is not None:
            query += " AND price <= ?"
            params.append(max_price)
        
        # Add stock filter
        if in_stock is not None:
            query += " AND quantity > 0" if in_stock else " AND quantity <= 0"
        
        # Add status filter
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        
        # Get total count with filters applied
        count_query = f"SELECT COUNT(*) FROM ({query})"
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(count_query, params)
            total = (await cursor.fetchone())[0]
            
            # Add sorting and pagination
            query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # Execute the query
            cursor = await conn.execute(query, params)
            
            products = []
            async for row in cursor:
                products.append({
                    "product_id": row[0],
                    "name": row[1],
                    "sku": row[2],
                    "price": row[3],
                    "special": row[4],
                    "description": row[5],
                    "url": row[6],
                    "image": row[7],
                    "quantity": row[8],
                    "status": row[9],
                    "rating": row[10],
                    "updated_at": row[11]
                })
        
        return APIResponse(
            status="success",
            message=f"Found {total} matching products" if q else f"Retrieved {len(products)} of {total} products",
            response={
                "total": total,
                "limit": limit,
                "offset": offset,
                "products": products,
                "filters": {
                    "query": q,
                    "min_price": min_price,
                    "max_price": max_price,
                    "in_stock": in_stock,
                    "status": status
                }
            }
        )
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))
