# Product Data Export Module - Quick Reference

## Module Location
```
/integration_toolkit/OpenCart/ProductExport/
```

## File Structure
```
ProductExport/
├── install.xml                                          # Module manifest
├── README.md                                           # Full documentation
└── upload/
    ├── admin/
    │   ├── controller/extension/module/
    │   │   └── product_data_export.php                # Admin controller
    │   ├── model/extension/module/
    │   │   └── product_data_export.php                # Admin model
    │   ├── view/template/extension/module/
    │   │   └── product_data_export.twig               # Admin UI
    │   └── language/en-gb/extension/module/
    │       └── product_data_export.php                # Admin language
    └── catalog/
        ├── controller/extension/module/
        │   └── product_data_export.php                # Frontend controller
        ├── model/extension/module/
        │   └── product_data_export.php                # Frontend model
        └── language/en-gb/extension/module/
            └── product_data_export.php                # Frontend language
```

## API Endpoints

### 1. Export All Products
```
GET /index.php?route=extension/module/product_data_export/export
```
**Parameters:**
- `limit` (optional, default: 100) - Products per batch
- `offset` (optional, default: 0) - Skip N products

**Returns:** JSON with products list

---

### 2. Export by Category
```
GET /index.php?route=extension/module/product_data_export/category
```
**Parameters:**
- `category_id` (required) - Category ID
- `limit` (optional, default: 100) - Products per batch
- `offset` (optional, default: 0) - Skip N products

**Returns:** JSON with category products

---

### 3. CSV Download (Admin Only)
```
GET /index.php?route=extension/module/product_data_export/exportcsv
```
**Parameters:**
- `limit` (optional, default: 10000) - Max products
- `offset` (optional, default: 0) - Skip N products

**Returns:** CSV file download

---

## Response Format

```json
{
  "success": true,
  "total_products": 1250,
  "count": 50,
  "limit": 50,
  "offset": 0,
  "products": [
    {
      "product_id": 1,
      "name": "Product Name",
      "sku": "SKU123",
      "price": "$99.99",
      "special": "$79.99",
      "description": "Product description text...",
      "url": "http://shop.com/index.php?route=product/product&product_id=1",
      "image": "http://shop.com/image/cache/product/file.jpg",
      "quantity": 100,
      "status": 1,
      "rating": 4.5
    }
  ]
}
```

## Installation Steps

1. Copy `ProductExport/` folder contents to OpenCart root
2. Go to OpenCart Admin: **Extensions → Extension Installer**
3. Install the module
4. Navigate to: **Extensions → Modules → Product Data Export**
5. Click **Install** button
6. Set **Status** to "Enabled"
7. Configure **Batch Size** (default: 100)
8. Click **Save**

## Usage Examples

### Export 100 products
```
http://yourshop.com/index.php?route=extension/module/product_data_export/export?limit=100&offset=0
```

### Export next 100 products (pagination)
```
http://yourshop.com/index.php?route=extension/module/product_data_export/export?limit=100&offset=100
```

### Get category 5 products
```
http://yourshop.com/index.php?route=extension/module/product_data_export/category?category_id=5&limit=100
```

### Download CSV
```
http://yourshop.com/index.php?route=extension/module/product_data_export/exportcsv?limit=10000
```

## Features at a Glance

| Feature | Support |
|---------|---------|
| JSON Export | ✅ Yes |
| CSV Export | ✅ Yes |
| Category Filter | ✅ Yes |
| Pagination | ✅ Yes |
| Product Images | ✅ Yes |
| Prices/Discounts | ✅ Yes |
| Ratings/Reviews | ✅ Yes |
| Links | ✅ Yes |
| Descriptions | ✅ Yes |
| Stock Levels | ✅ Yes |

## Database Tables Used

- `oc_product` - Main product data
- `oc_product_description` - Localized product info
- `oc_product_image` - Product images
- `oc_product_discount` - Special prices
- `oc_product_to_category` - Category assignments
- `oc_review` - Customer ratings

## Performance Notes

- Default batch size: 100 products
- Supports pagination for large catalogs
- Optimized SQL queries with proper indexes
- Response time: ~100-500ms per request (depends on batch size)
- Max recommended batch: 1000 products

## Troubleshooting

**Issue: "Extension not found"**
- Ensure files are in correct directory structure
- Clear OpenCart cache
- Check file permissions (644 for files, 755 for directories)

**Issue: "No products showing"**
- Verify products exist in database
- Check products are marked as active
- Ensure product descriptions exist for current language

**Issue: "Slow response"**
- Reduce batch size
- Check database indexes
- Implement client-side caching
- Use offset-based pagination

## Integration Tips

- Cache results on your server
- Use batch/pagination for large catalogs
- Implement rate limiting if public API
- Add authentication for sensitive operations
- Schedule regular exports (cron jobs)

---

**Module Code**: `product_data_export`
**Version**: 1.0.0
**OpenCart**: 3.0+
