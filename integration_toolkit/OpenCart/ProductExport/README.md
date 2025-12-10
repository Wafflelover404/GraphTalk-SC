# Product Data Export Module for OpenCart 3.x

A comprehensive OpenCart module that exports product data including names, descriptions, prices, images, stock levels, ratings, and direct links to products.

## Features

✅ **Product Data Export**
- Product ID, Name, SKU
- Regular price and special/discount price
- Full product description
- Direct product URLs
- Product images
- Stock quantity
- Customer ratings/reviews

✅ **Multiple Export Formats**
- JSON format for API integration
- CSV format for spreadsheet applications (Excel, Google Sheets)
- Pagination support for large catalogs

✅ **Advanced Filtering**
- Export all products
- Export by category
- Configurable batch sizes
- Offset-based pagination

✅ **Admin Interface**
- Easy configuration in OpenCart admin
- Live preview of products
- One-click export/download
- JSON and CSV export options

✅ **API Access**
- RESTful API endpoints for programmatic access
- JSON response format
- No authentication required (can be added)

## Installation

1. **Upload Files**
   - Extract the module files to your OpenCart installation
   - Copy contents of `upload/` folder to your OpenCart root directory

2. **Install in OpenCart Admin**
   - Go to: **Extensions → Extension Installer**
   - Upload the module or install via the admin panel
   - Navigate to: **Extensions → Modules → Product Data Export**
   - Click **Install**

3. **Enable Module**
   - Set **Status** to "Enabled"
   - Configure batch size (default: 100 products)
   - Click **Save**

## Usage

### Admin Interface

Access the module at: **Extensions → Modules → Product Data Export**

#### Features:
- **Preview**: See sample of products with all data fields
- **Export JSON**: Download complete product catalog as JSON file
- **Export CSV**: Download as Excel-compatible CSV format
- **Batch Size**: Control number of products per export request

### API Endpoints

#### Get All Products
```
GET /index.php?route=extension/module/product_data_export/export
Parameters:
  - limit: Number of products (default: 100)
  - offset: Skip N products (default: 0)
```

**Response:**
```json
{
  "success": true,
  "total_products": 1250,
  "count": 100,
  "limit": 100,
  "offset": 0,
  "products": [
    {
      "product_id": 1,
      "name": "Product Name",
      "sku": "PROD001",
      "price": "$99.99",
      "special": "$79.99",
      "description": "Full product description...",
      "url": "http://yourshop.com/index.php?route=product/product&product_id=1",
      "image": "http://yourshop.com/image/cache/product/image.jpg",
      "quantity": 50,
      "status": 1,
      "rating": 4.5
    }
  ]
}
```

#### Get Products by Category
```
GET /index.php?route=extension/module/product_data_export/category
Parameters:
  - category_id: Category ID (required)
  - limit: Number of products (default: 100)
  - offset: Skip N products (default: 0)
```

### Example Usage

#### JavaScript/jQuery
```javascript
// Get product list
$.ajax({
  url: '/index.php?route=extension/module/product_data_export/export',
  data: { limit: 50, offset: 0 },
  success: function(data) {
    console.log(data.products);
  }
});

// Get category products
$.ajax({
  url: '/index.php?route=extension/module/product_data_export/category',
  data: { category_id: 20, limit: 100 },
  success: function(data) {
    console.log(data.products);
  }
});
```

#### Python
```python
import requests

# Get all products
response = requests.get('http://yourshop.com/index.php?route=extension/module/product_data_export/export', 
                       params={'limit': 100, 'offset': 0})
products = response.json()['products']

# Get category products
response = requests.get('http://yourshop.com/index.php?route=extension/module/product_data_export/category',
                       params={'category_id': 20, 'limit': 100})
```

#### cURL
```bash
# Export products as JSON
curl "http://yourshop.com/index.php?route=extension/module/product_data_export/export?limit=100"

# Export specific category
curl "http://yourshop.com/index.php?route=extension/module/product_data_export/category?category_id=20&limit=100"

# Export as CSV (download)
curl "http://yourshop.com/index.php?route=extension/module/product_data_export/exportcsv" -o products.csv
```

#### Send export directly to Graphtalk ingest (FastAPI)
- In the admin UI, export products (JSON).
- Enter your Graphtalk ingest URL (e.g., `https://your-graphtalk-host/opencart/products/import`).
- Paste the Graphtalk Bearer token/session_id from `api.py` auth.
- Click **Send to Endpoint** to push the JSON with `Authorization: Bearer <token>`.

## Data Fields Included

Each product includes:

| Field | Description | Example |
|-------|-------------|---------|
| `product_id` | Unique product identifier | 1 |
| `name` | Product name | "Laptop Computer" |
| `sku` | Stock keeping unit | "PROD001" |
| `price` | Regular price | "$999.99" |
| `special` | Special/discount price | "$799.99" |
| `description` | Full product description | "High performance laptop..." |
| `url` | Direct link to product page | "http://shop.com/?product_id=1" |
| `image` | Product image URL | "http://shop.com/image/product.jpg" |
| `quantity` | Stock quantity | 50 |
| `status` | Active/inactive status | 1 |
| `rating` | Average customer rating | 4.5 |

## Configuration

### Settings (Admin Panel)

1. **Status**: Enable/disable the module
2. **Batch Size**: Default number of products per request (1-10000)
3. **Format**: Default export format (JSON/CSV)

### Performance Tips

- Use reasonable batch sizes (100-500 for large catalogs)
- Implement pagination in your application to handle large exports
- Cache results if querying frequently
- Use database indexing on `product_id`, `sku`, `name`

## Troubleshooting

### "Products not showing" in export
- Ensure products are marked as **Active** in OpenCart admin
- Check that product descriptions exist for the current language
- Verify database has product data

### CSV download not working
- Check server upload/download settings
- Ensure browser allows file downloads
- Try JSON export as alternative

### Slow export performance
- Reduce batch size in settings
- Add database indexes on product tables
- Implement pagination in API calls
- Consider using off-peak hours for large exports

## API Integration Examples

### Export to External Database
```php
<?php
// PHP example
$url = 'http://yourshop.com/index.php?route=extension/module/product_data_export/export';
$response = file_get_contents($url . '?limit=100&offset=0');
$data = json_decode($response, true);

foreach ($data['products'] as $product) {
    // Insert into your database
    insert_product($product);
}
?>
```

### Create Product Sitemap
```javascript
// Generate XML sitemap from product data
fetch('/index.php?route=extension/module/product_data_export/export?limit=10000')
  .then(r => r.json())
  .then(data => {
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset>';
    data.products.forEach(p => {
      xml += `\n<url><loc>${p.url}</loc></url>`;
    });
    xml += '\n</urlset>';
    // Save or send xml...
  });
```

## Version History

- **1.0.0** - Initial release
  - Product data export (JSON/CSV)
  - Category filtering
  - Admin interface
  - API endpoints

## Support

For issues, feature requests, or questions, please refer to the OpenCart documentation or contact support.

## License

This module is provided as-is for use with OpenCart 3.x installations.

---

**Module Code**: `product_data_export`
**Compatible With**: OpenCart 3.0+
**Last Updated**: 2025
