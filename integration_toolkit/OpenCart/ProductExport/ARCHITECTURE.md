# Product Data Export Module - Technical Architecture

## Module Overview

**Name**: Product Data Export  
**Code**: `product_data_export`  
**Version**: 1.0.0  
**OpenCart Compatibility**: 3.0+  
**Language**: PHP 7.2+

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCart 3.x Store                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            Product Data Export Module                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ADMIN INTERFACE (Dashboard)                                │
│  ├─ Controller: product_data_export.php (admin)            │
│  ├─ Model: product_data_export.php (admin)                 │
│  ├─ View: product_data_export.twig                         │
│  └─ Language: product_data_export.php (admin)              │
│                                                              │
│  PUBLIC API (Frontend/Catalog)                              │
│  ├─ Controller: product_data_export.php (catalog)          │
│  ├─ Model: product_data_export.php (catalog)               │
│  └─ Language: product_data_export.php (catalog)            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              OpenCart Database                               │
├─────────────────────────────────────────────────────────────┤
│  - oc_product (core product data)                           │
│  - oc_product_description (localized info)                  │
│  - oc_product_image (images)                                │
│  - oc_product_discount (special prices)                     │
│  - oc_product_to_category (categories)                      │
│  - oc_review (ratings/reviews)                              │
└─────────────────────────────────────────────────────────────┘
```

## Class Structure

### Admin Controller
**File**: `upload/admin/controller/extension/module/product_data_export.php`  
**Class**: `ControllerExtensionModuleProductDataExport`

**Methods**:
- `index()` - Admin configuration page
- `export()` - Export products as JSON
- `exportcsv()` - Export products as CSV
- `validate()` - Validate settings
- `install()` - Initialize module settings
- `uninstall()` - Remove module settings

### Admin Model
**File**: `upload/admin/model/extension/module/product_data_export.php`  
**Class**: `ModelExtensionModuleProductDataExport`

**Methods**:
- `getProductsWithData($limit, $offset)` - Fetch products with all data
- `getTotalProducts()` - Count total products
- `getProductsByCategory($category_id, $limit, $offset)` - Get category products

### Catalog Controller
**File**: `upload/catalog/controller/extension/module/product_data_export.php`  
**Class**: `ControllerExtensionModuleProductDataExport`

**Methods**:
- `export()` - API endpoint for product export
- `category()` - API endpoint for category-specific export

### Catalog Model
**File**: `upload/catalog/model/extension/module/product_data_export.php`  
**Class**: `ModelExtensionModuleProductDataExport`

**Methods**:
- `getProductsWithData($limit, $offset)` - Fetch products
- `getTotalProducts()` - Total product count
- `getProductsByCategory($category_id, $limit, $offset)` - Category products

## Database Schema

### Primary Tables Used

#### oc_product
```
Columns:
- product_id (INT, PRIMARY KEY)
- sku (VARCHAR 64)
- quantity (INT)
- status (TINYINT)
- image (VARCHAR 255)
- price (DECIMAL 15,4)
```

#### oc_product_description
```
Columns:
- product_id (INT)
- language_id (INT)
- name (VARCHAR 255)
- description (TEXT)
```

#### oc_product_image
```
Columns:
- product_id (INT)
- image (VARCHAR 255)
- sort_order (INT)
```

#### oc_product_discount
```
Columns:
- product_id (INT)
- customer_group_id (INT)
- price (DECIMAL 15,4)
- date_start (DATE)
- date_end (DATE)
```

#### oc_product_to_category
```
Columns:
- product_id (INT)
- category_id (INT)
```

#### oc_review
```
Columns:
- product_id (INT)
- rating (INT 0-5)
- status (TINYINT)
```

## Data Model

### Product Object Structure
```php
[
  'product_id'    => (int),           // Unique product identifier
  'name'          => (string),        // Product name
  'sku'           => (string),        // Stock keeping unit
  'price'         => (string/float),  // Regular price
  'special'       => (string/float),  // Discounted price
  'description'   => (string),        // Full description
  'url'           => (string),        // Direct product URL
  'image'         => (string),        // Product image URL
  'quantity'      => (int),           // Stock level
  'status'        => (int),           // 1=active, 0=inactive
  'rating'        => (float)          // 0-5 star rating
]
```

## API Endpoints

### Endpoint 1: Get All Products
```
Route: /index.php?route=extension/module/product_data_export/export
Method: GET
Parameters:
  - limit (int): Products per request (1-10000, default: 100)
  - offset (int): Skip N products (default: 0)

Response: JSON
{
  "success": true,
  "total_products": (int),
  "count": (int),
  "limit": (int),
  "offset": (int),
  "products": [...]
}
```

### Endpoint 2: Get Category Products
```
Route: /index.php?route=extension/module/product_data_export/category
Method: GET
Parameters:
  - category_id (int): Required category ID
  - limit (int): Products per request (default: 100)
  - offset (int): Skip N products (default: 0)

Response: JSON (same structure as Endpoint 1)
```

### Endpoint 3: Export CSV
```
Route: /index.php?route=extension/module/product_data_export/exportcsv
Method: GET
Parameters:
  - limit (int): Max products to export (default: 10000)
  - offset (int): Skip N products (default: 0)

Response: CSV file download
Headers:
  Content-Type: text/csv; charset=utf-8
  Content-Disposition: attachment; filename="products_YYYY-MM-DD.csv"
```

## Request/Response Flow

### Admin Export Flow
```
1. User clicks "Export" button in admin panel
   ↓
2. JavaScript captures limit and format from form
   ↓
3. AJAX request → Admin Controller::export()
   ↓
4. Controller loads Model
   ↓
5. Model executes SQL query with limit/offset
   ↓
6. Model formats response with products
   ↓
7. Controller returns JSON
   ↓
8. JavaScript processes response
   ↓
9. Display results or trigger CSV download
```

### API Request Flow
```
1. External request to /export or /category
   ↓
2. Catalog Controller receives request
   ↓
3. Parses limit, offset, category_id parameters
   ↓
4. Loads Catalog Model
   ↓
5. Model executes optimized SQL query
   ↓
6. Returns formatted product data
   ↓
7. Controller sets JSON headers
   ↓
8. Returns JSON response to client
```

## SQL Query Optimization

### Main Query Structure
```sql
SELECT 
  p.product_id,
  p.sku,
  p.quantity,
  p.status,
  p.image,
  pd.name,
  pd.description,
  p.price,
  
  -- Subquery for special price
  (SELECT price FROM product_discount 
   WHERE product_id = p.product_id 
   AND customer_group_id = '...'
   AND date_start <= NOW() AND date_end >= NOW()
   ORDER BY priority ASC LIMIT 1) AS special,
  
  -- Subquery for rating
  (SELECT AVG(rating) FROM review 
   WHERE product_id = p.product_id 
   AND status = 1) AS rating,
  
  -- Direct URL construction
  CONCAT(config_url, '...&product_id=', p.product_id) AS url
  
FROM product p
LEFT JOIN product_description pd 
  ON p.product_id = pd.product_id
LEFT JOIN product_image pi 
  ON p.product_id = pi.product_id
WHERE pd.language_id = '...'
ORDER BY p.product_id DESC
LIMIT offset, limit
```

## Performance Characteristics

### Query Performance
- **Single product fetch**: ~5-10ms
- **100 products**: ~50-100ms
- **1000 products**: ~500-1000ms
- **10000 products**: ~5-10s (not recommended)

### Memory Usage
- **JSON response (100 products)**: ~100-200KB
- **CSV response (100 products)**: ~50-100KB
- **Streaming response**: Minimal (PHP buffering)

### Database Indexes (Recommended)
```sql
CREATE INDEX idx_product_id ON product(product_id);
CREATE INDEX idx_pd_language ON product_description(language_id);
CREATE INDEX idx_pc_product_id ON product_to_category(product_id);
CREATE INDEX idx_review_product_id ON review(product_id);
CREATE INDEX idx_discount_product ON product_discount(product_id);
```

## Security Considerations

### Current Implementation
- No authentication required (public API)
- No rate limiting
- No input validation on category_id (SQL injection safe via prepared statements)
- Output is JSON-safe (json_encode())

### Recommended Enhancements
```php
// Add authentication
if (!$this->user->hasPermission('view', 'extension/module/product_data_export')) {
    exit('Access Denied');
}

// Add rate limiting
$ip = $_SERVER['REMOTE_ADDR'];
if (cache('export_' . $ip) > 100) {
    exit(json_encode(['error' => 'Rate limit exceeded']));
}

// Add parameter validation
$limit = min((int)$this->request->get['limit'], 10000);
$offset = max(0, (int)$this->request->get['offset']);
$category_id = max(0, (int)$this->request->get['category_id']);
```

## Extension Points

### Add Authentication
```php
// In export() method
if (!empty($_SERVER['HTTP_API_KEY'])) {
    if (!$this->validateApiKey($_SERVER['HTTP_API_KEY'])) {
        $json['error'] = 'Invalid API key';
        $this->response->setOutput(json_encode($json));
        return;
    }
}
```

### Add Caching
```php
$cache_key = 'product_export_' . $limit . '_' . $offset;
if ($cached = $this->cache->get($cache_key)) {
    return json_decode($cached);
}
// ... fetch products ...
$this->cache->set($cache_key, json_encode($products), 3600);
```

### Add Filtering
```php
// Filter by price range
if ($min_price = $this->request->get['min_price'] ?? null) {
    $query .= " AND p.price >= " . (float)$min_price;
}

// Filter by stock status
if ($this->request->get['in_stock'] ?? false) {
    $query .= " AND p.quantity > 0";
}
```

## File Dependencies

### Admin Controller
- Requires: `language/`, `model/`, `view/`
- Uses: `$this->load->language()`, `$this->load->model()`, `$this->load->view()`

### Models
- Requires: OpenCart Database class
- Uses: `$this->db->query()`, `$this->config->get()`

### Views
- Requires: jQuery, Bootstrap CSS (OpenCart default)
- Uses: AJAX, jQuery UI components

## Installation/Uninstall

### Install
```php
public function install() {
    // Create module settings in database
    $this->load->model('setting/setting');
    $defaults = [
        'module_product_data_export_status' => 1,
        'module_product_data_export_limit' => 100,
        'module_product_data_export_format' => 'json'
    ];
    $this->model_setting_setting->editSetting('module_product_data_export', $defaults);
}
```

### Uninstall
```php
public function uninstall() {
    // Remove module settings from database
    $this->load->model('setting/setting');
    $this->model_setting_setting->deleteSetting('module_product_data_export');
}
```

## Configuration Storage

**OpenCart Setting Keys**:
- `module_product_data_export_status` (0/1)
- `module_product_data_export_limit` (1-10000)
- `module_product_data_export_format` (json/csv)

**Storage Location**: `oc_setting` table

## Testing Checklist

- [ ] Module installs without errors
- [ ] Admin page loads
- [ ] Export JSON works with default limit
- [ ] Export CSV downloads file
- [ ] Pagination works (offset parameter)
- [ ] Category filtering works
- [ ] Large batches (1000+) complete successfully
- [ ] All product data fields populated
- [ ] Images URLs are correct
- [ ] Product URLs are correct
- [ ] Ratings calculated correctly
- [ ] Special prices applied correctly

---

**Last Updated**: 2025  
**Module Code**: `product_data_export`  
**Version**: 1.0.0
