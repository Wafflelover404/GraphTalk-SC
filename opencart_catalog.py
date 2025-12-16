# opencart_catalog.py - Enhanced OpenCart catalog management with indexing
import os
import datetime
import aiosqlite
import logging
from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel
import uuid

logger = logging.getLogger(__name__)

# Database paths
CATALOG_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "catalogs.db")
os.makedirs(os.path.dirname(CATALOG_DB_PATH), exist_ok=True)


class CatalogMetadata(BaseModel):
    """Metadata for an OpenCart catalog"""
    catalog_id: str
    shop_name: str
    shop_url: Optional[str] = None
    user_id: int
    organization_id: Optional[str] = None
    total_products: int = 0
    indexed_products: int = 0
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_indexed_at: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.catalog_id:
            self.catalog_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.datetime.utcnow().isoformat()


class CatalogProduct(BaseModel):
    """Product record in a catalog"""
    product_id: str
    catalog_id: str
    name: str
    sku: Optional[str] = None
    price: float
    special: Optional[str] = None
    description: Optional[str] = None
    url: str
    image: Optional[str] = None
    quantity: int = 0
    status: int = 1
    rating: Optional[int] = None
    indexed: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.datetime.utcnow().isoformat()


async def init_catalog_db():
    """Initialize the catalog database with required tables."""
    os.makedirs(os.path.dirname(CATALOG_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        # Catalogs table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalogs (
                catalog_id TEXT PRIMARY KEY,
                shop_name TEXT NOT NULL,
                shop_url TEXT,
                user_id INTEGER NOT NULL,
                organization_id TEXT,
                total_products INTEGER DEFAULT 0,
                indexed_products INTEGER DEFAULT 0,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_indexed_at TEXT
            )
            """
        )
        
        # Products in catalogs table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog_products (
                product_id TEXT NOT NULL,
                catalog_id TEXT NOT NULL,
                name TEXT NOT NULL,
                sku TEXT,
                price REAL NOT NULL,
                special TEXT,
                description TEXT,
                url TEXT NOT NULL,
                image TEXT,
                quantity INTEGER DEFAULT 0,
                status INTEGER DEFAULT 1,
                rating INTEGER,
                indexed BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (product_id, catalog_id),
                FOREIGN KEY (catalog_id) REFERENCES catalogs(catalog_id)
            )
            """
        )
        
        # Indexing metadata table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog_indexing_log (
                log_id TEXT PRIMARY KEY,
                catalog_id TEXT NOT NULL,
                product_ids TEXT,
                indexed_count INTEGER,
                failed_count INTEGER,
                status TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (catalog_id) REFERENCES catalogs(catalog_id)
            )
            """
        )
        
        # Create indexes for faster queries
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON catalogs(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_org_id ON catalogs(organization_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_id ON catalog_products(catalog_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_indexed ON catalog_products(indexed)")
        
        await conn.commit()


async def create_catalog(
    shop_name: str,
    shop_url: Optional[str],
    user_id: int,
    organization_id: Optional[str],
    description: Optional[str] = None
) -> str:
    """Create a new catalog entry. Returns catalog_id."""
    catalog_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO catalogs (
                catalog_id, shop_name, shop_url, user_id, organization_id,
                description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (catalog_id, shop_name, shop_url, user_id, organization_id, description, now, now)
        )
        await conn.commit()
    
    logger.info(f"Created catalog {catalog_id} for shop {shop_name}")
    return catalog_id


async def get_catalog(catalog_id: str) -> Optional[Dict]:
    """Retrieve catalog metadata."""
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM catalogs WHERE catalog_id = ?",
            (catalog_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_catalogs_by_user(user_id: int, organization_id: Optional[str] = None) -> List[Dict]:
    """List all catalogs for a user, optionally filtered by organization."""
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if organization_id:
            cursor = await conn.execute(
                "SELECT * FROM catalogs WHERE user_id = ? AND organization_id = ? ORDER BY created_at DESC",
                (user_id, organization_id)
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM catalogs WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def list_catalogs_by_org(organization_id: str) -> List[Dict]:
    """List all catalogs in an organization."""
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM catalogs WHERE organization_id = ? ORDER BY created_at DESC",
            (organization_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_catalog_metadata(catalog_id: str, **kwargs) -> bool:
    """Update catalog metadata (shop_name, description, is_active, organization_id, etc.)."""
    allowed_fields = ["shop_name", "shop_url", "description", "is_active", "organization_id"]
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not updates:
        return False
    
    updates["updated_at"] = datetime.datetime.utcnow().isoformat()
    
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [catalog_id]
    
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        cursor = await conn.execute(
            f"UPDATE catalogs SET {set_clause} WHERE catalog_id = ?",
            values
        )
        await conn.commit()
        return cursor.rowcount > 0


async def delete_catalog(catalog_id: str) -> bool:
    """Delete a catalog and all its products."""
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        # Delete products
        await conn.execute("DELETE FROM catalog_products WHERE catalog_id = ?", (catalog_id,))
        # Delete indexing logs
        await conn.execute("DELETE FROM catalog_indexing_log WHERE catalog_id = ?", (catalog_id,))
        # Delete catalog
        cursor = await conn.execute("DELETE FROM catalogs WHERE catalog_id = ?", (catalog_id,))
        await conn.commit()
        return cursor.rowcount > 0


async def upsert_catalog_products(
    catalog_id: str,
    products: List[Dict],
    user_id: int,
    organization_id: Optional[str] = None
) -> Tuple[int, int]:
    """
    Insert or update products in a catalog.
    Returns (inserted, updated) counts.
    """
    inserted = 0
    updated = 0
    now = datetime.datetime.utcnow().isoformat()
    
    # First ensure catalog exists
    catalog = await get_catalog(catalog_id)
    if not catalog:
        # Create new catalog
        await create_catalog(
            shop_name=f"Import-{catalog_id[:8]}",
            shop_url=None,
            user_id=user_id,
            organization_id=organization_id,
            description="Imported catalog"
        )
    
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        for product in products:
            product_id = str(product.get("product_id"))
            name = product.get("name", "")
            sku = product.get("sku")
            price = _parse_float(product.get("price", 0))
            special = product.get("special")
            description = product.get("description")
            url = product.get("url", "")
            image = product.get("image")
            quantity = _parse_int(product.get("quantity", 0))
            status = _parse_int(product.get("status", 1))
            rating = _parse_int(product.get("rating"))
            
            if not product_id or not name:
                continue
            
            # Try to update
            update_cursor = await conn.execute(
                """
                UPDATE catalog_products SET
                    name=?, sku=?, price=?, special=?, description=?, url=?, 
                    image=?, quantity=?, status=?, rating=?, updated_at=?
                WHERE product_id=? AND catalog_id=?
                """,
                (name, sku, price, special, description, url, image, quantity, status, rating, now, product_id, catalog_id)
            )
            
            if update_cursor.rowcount:
                updated += 1
            else:
                # Insert new
                await conn.execute(
                    """
                    INSERT INTO catalog_products (
                        product_id, catalog_id, name, sku, price, special, description, 
                        url, image, quantity, status, rating, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (product_id, catalog_id, name, sku, price, special, description, url, image, quantity, status, rating, now, now)
                )
                inserted += 1
        
        # Update catalog stats
        product_count_cursor = await conn.execute(
            "SELECT COUNT(*) FROM catalog_products WHERE catalog_id = ?",
            (catalog_id,)
        )
        product_count = (await product_count_cursor.fetchone())[0]
        
        indexed_count_cursor = await conn.execute(
            "SELECT COUNT(*) FROM catalog_products WHERE catalog_id = ? AND indexed = 1",
            (catalog_id,)
        )
        indexed_count = (await indexed_count_cursor.fetchone())[0]
        
        await conn.execute(
            "UPDATE catalogs SET total_products = ?, indexed_products = ?, updated_at = ? WHERE catalog_id = ?",
            (product_count, indexed_count, now, catalog_id)
        )
        
        await conn.commit()
    
    return inserted, updated


async def get_catalog_products(
    catalog_id: str,
    limit: int = 100,
    offset: int = 0,
    indexed_only: bool = False
) -> Tuple[List[Dict], int]:
    """
    Get products from a catalog with pagination.
    Returns (products list, total count).
    """
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        where_clause = "catalog_id = ?"
        params = [catalog_id]
        
        if indexed_only:
            where_clause += " AND indexed = 1"
        
        # Get total count
        count_cursor = await conn.execute(
            f"SELECT COUNT(*) FROM catalog_products WHERE {where_clause}",
            params
        )
        total = (await count_cursor.fetchone())[0]
        
        # Get paginated products
        cursor = await conn.execute(
            f"SELECT * FROM catalog_products WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        
        rows = await cursor.fetchall()
        products = [dict(row) for row in rows]
        
        return products, total


async def mark_products_indexed(catalog_id: str, product_ids: List[str]) -> int:
    """Mark products as indexed in Chroma. Returns count updated."""
    now = datetime.datetime.utcnow().isoformat()
    updated = 0
    
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        for product_id in product_ids:
            cursor = await conn.execute(
                "UPDATE catalog_products SET indexed = 1, updated_at = ? WHERE product_id = ? AND catalog_id = ?",
                (now, product_id, catalog_id)
            )
            updated += cursor.rowcount
        
        # Update catalog indexing timestamp
        await conn.execute(
            "UPDATE catalogs SET last_indexed_at = ? WHERE catalog_id = ?",
            (now, catalog_id)
        )
        
        await conn.commit()
    
    return updated


async def log_indexing_event(
    catalog_id: str,
    product_ids: List[str],
    indexed_count: int,
    failed_count: int,
    status: str,
    error_message: Optional[str] = None
) -> str:
    """Log an indexing event. Returns log_id."""
    log_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO catalog_indexing_log (
                log_id, catalog_id, product_ids, indexed_count, failed_count, status, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, catalog_id, ",".join(product_ids), indexed_count, failed_count, status, error_message, now)
        )
        await conn.commit()
    
    return log_id


def _parse_float(value) -> float:
    """Parse value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _parse_int(value) -> int:
    """Parse value to int."""
    if value is None:
        return 0
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


async def load_opencart_products_from_db(opencart_db_path: str, catalog_id: str, shop_url: str) -> Tuple[int, int]:
    """
    Load all products from OpenCart database and insert into catalog.
    Returns (inserted, updated) counts.
    """
    if not os.path.exists(opencart_db_path):
        logger.error(f"OpenCart database not found at {opencart_db_path}")
        return 0, 0
    
    inserted = 0
    updated = 0
    now = datetime.datetime.utcnow().isoformat()
    
    try:
        async with aiosqlite.connect(opencart_db_path) as oc_conn:
            oc_conn.row_factory = aiosqlite.Row
            # Query all products from OpenCart database
            cursor = await oc_conn.execute(
                "SELECT product_id, name, sku, price, special, description, url, image, quantity, status, rating FROM products"
            )
            rows = await cursor.fetchall()
            products = [dict(row) for row in rows]
        
        # Insert products into catalog
        if products:
            async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
                for product in products:
                    product_id = str(product.get('product_id', ''))
                    name = product.get('name', 'Unknown')
                    sku = product.get('sku', '')
                    price = _parse_float(product.get('price', 0))
                    special = product.get('special')
                    description = product.get('description', '')
                    url = product.get('url', shop_url)
                    image = product.get('image')
                    quantity = _parse_int(product.get('quantity', 0))
                    status = _parse_int(product.get('status', 1))
                    rating = _parse_int(product.get('rating'))
                    
                    # Try to insert, or update if exists
                    cursor = await conn.execute(
                        "SELECT * FROM catalog_products WHERE product_id = ? AND catalog_id = ?",
                        (product_id, catalog_id)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing:
                        # Update existing product
                        await conn.execute(
                            """
                            UPDATE catalog_products SET
                                name=?, sku=?, price=?, special=?, description=?,
                                url=?, image=?, quantity=?, status=?, rating=?, updated_at=?
                            WHERE product_id = ? AND catalog_id = ?
                            """,
                            (name, sku, price, special, description, url, image, quantity, status, rating, now, product_id, catalog_id)
                        )
                        updated += 1
                    else:
                        # Insert new product
                        await conn.execute(
                            """
                            INSERT INTO catalog_products (
                                product_id, catalog_id, name, sku, price, special, description,
                                url, image, quantity, status, rating, indexed, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (product_id, catalog_id, name, sku, price, special, description,
                             url, image, quantity, status, rating, 0, now, now)
                        )
                        inserted += 1
                
                # Update catalog stats
                await conn.execute(
                    "UPDATE catalogs SET total_products = total_products + ? WHERE catalog_id = ?",
                    (inserted, catalog_id)
                )
                await conn.commit()
        
        logger.info(f"Loaded {inserted} new products and updated {updated} existing products from OpenCart DB to catalog {catalog_id}")
    
    except Exception as e:
        logger.error(f"Error loading products from OpenCart DB: {e}")
    
    return inserted, updated
