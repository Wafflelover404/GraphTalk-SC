# Product Data Export Module - Visual Guide

## 📊 Module Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                  PRODUCT DATA EXPORT MODULE                          │
│                    (product_data_export)                             │
└─────────────────────────────────────────────────────────────────────┘

                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
            ┌─────────┐   ┌─────────┐   ┌─────────┐
            │  ADMIN  │   │   API   │   │  PUBLIC │
            │ PANEL   │   │ ENDPOINTS   │  ACCESS │
            └─────────┘   └─────────┘   └─────────┘
                │             │             │
                └─────────────┼─────────────┘
                              ▼
                    ┌──────────────────┐
                    │  OpenCart Model  │
                    │  & Database      │
                    └──────────────────┘
```

---

## 🔄 Data Flow Diagram

### Admin Export Flow
```
User Opens Admin Panel
        │
        ▼
User Clicks "Preview" or "Export" Button
        │
        ▼
JavaScript (jQuery) Captures Settings
  - Export format (JSON/CSV)
  - Batch size
  - Offset (page number)
        │
        ▼
AJAX Request to Controller
        │
        ▼
Controller Receives Request
        │
        ├─► Validates Parameters
        │
        ├─► Loads Model
        │
        └─► Calls Model::getProductsWithData()
                    │
                    ▼
              SQL Query to Database
              ┌──────────────────────────┐
              │ SELECT p.*, pd.*, rating │
              │ FROM product p           │
              │ LEFT JOIN descriptions   │
              │ AND special prices       │
              │ AND ratings              │
              └──────────────────────────┘
                    │
                    ▼
              Database Returns Rows
                    │
                    ▼
              Model Formats Data
              ┌──────────────────────────┐
              │ - Build URLs             │
              │ - Format prices          │
              │ - Get images             │
              │ - Calculate averages     │
              └──────────────────────────┘
                    │
                    ▼
              Controller Formats Response
              ┌──────────────────────────┐
              │ JSON or CSV format       │
              └──────────────────────────┘
                    │
                    ▼
              JavaScript Receives Data
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
    Display    Download    Show Summary
    Preview    CSV File    Statistics
```

### API Request Flow
```
External System Requests API
  GET /index.php?route=extension/module/product_data_export/export
        │
        ▼
OpenCart Router Matches Route
        │
        ▼
Catalog Controller Called
  product_data_export.php (catalog)
        │
        ▼
extract() Parameters:
  - limit: 100
  - offset: 0
        │
        ▼
Load Model:
  ModelExtensionModuleProductDataExport
        │
        ▼
Query Database
        │
        ▼
Format Results (JSON)
        │
        ▼
Set Headers:
  Content-Type: application/json
        │
        ▼
Return JSON to Client
```

---

## 🗄️ Database Schema Diagram

```
                    ┌─────────────────┐
                    │   oc_product    │
                    ├─────────────────┤
                    │ product_id (PK) │
                    │ sku             │
                    │ quantity        │
                    │ price           │
                    │ status          │
                    │ image           │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  PRODUCT     │  │  PRODUCT_    │  │  PRODUCT_    │
    │DESCRIPTION  │  │   DISCOUNT   │  │    IMAGE     │
    ├──────────────┤  ├──────────────┤  ├──────────────┤
    │ product_id  │  │ product_id   │  │ product_id   │
    │ language_id │  │ cust_grp_id  │  │ image        │
    │ name        │  │ price        │  │ sort_order   │
    │ description │  │ date_start   │  │              │
    │ | text:    │  │ date_end     │  │              │
    │ "Full prod │  │              │  │              │
    │  descript. │  │              │  │              │
    │ ..."       │  │              │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     oc_review   │
                    ├─────────────────┤
                    │ product_id      │
                    │ rating (1-5)    │
                    │ status          │
                    │ (Used for AVG)  │
                    └─────────────────┘
```

---

## 📁 File Dependencies Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCart Installation                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ADMIN SIDE                        CATALOG/FRONTEND SIDE    │
│  ═════════════════════════════════════════════════════════  │
│                                                              │
│  controller/                       controller/              │
│  └─ product_data_export.php        └─ product_data_export   │
│         │                                   │               │
│         ├─ Loads Model          ├─ Loads Model             │
│         │  (admin model)        │  (catalog model)         │
│         │                       │                          │
│         ├─ Loads View           └─ Returns JSON            │
│         │  (Twig template)         (no template)           │
│         │                                                   │
│         └─ Loads Language        Loads Language            │
│            (en-gb/admin)         (en-gb/catalog)           │
│                                                            │
│  model/                           model/                   │
│  └─ product_data_export.php       └─ product_data_export   │
│         │                              │                   │
│         ├─ getProductsWithData()       ├─ getProductsWithData()
│         ├─ getTotalProducts()          ├─ getTotalProducts()
│         └─ getProductsByCategory()     └─ getProductsByCategory()
│                  │                            │            │
│                  └────────────────┬───────────┘            │
│                                   │                        │
│                                   ▼                        │
│                        Database Tables:                    │
│                        - oc_product                        │
│                        - oc_product_description            │
│                        - oc_product_image                  │
│                        - oc_product_discount               │
│                        - oc_product_to_category            │
│                        - oc_review                         │
│                                                            │
│  view/                                                     │
│  └─ product_data_export.twig                              │
│         │                                                  │
│         ├─ Display Settings Form                          │
│         ├─ Preview Button (AJAX)                          │
│         ├─ Export Button (AJAX/Download)                  │
│         └─ Results Display                                │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 URL Routing Diagram

```
OpenCart Request
        │
        ├─ route=extension/module/product_data_export
        │   (Admin: Configuration page)
        │   (Admin: Export endpoints: /export, /exportcsv)
        │
        └─ route=extension/module/product_data_export
            (Catalog: API endpoints: /export, /category)

Admin Routes:
  /index.php?route=extension/module/product_data_export
    └─ ControllerExtensionModuleProductDataExport::index()
    └─ ControllerExtensionModuleProductDataExport::export()
    └─ ControllerExtensionModuleProductDataExport::exportcsv()

Catalog Routes:
  /index.php?route=extension/module/product_data_export/export
    └─ Parameters: limit, offset
    └─ Returns: JSON
    └─ ControllerExtensionModuleProductDataExport::export()

  /index.php?route=extension/module/product_data_export/category
    └─ Parameters: category_id, limit, offset
    └─ Returns: JSON
    └─ ControllerExtensionModuleProductDataExport::category()
```

---

## 💾 Configuration Storage Diagram

```
OpenCart Configuration
        │
        ▼
oc_setting Table
        │
        ├─ module_product_data_export_status
        │  └─ Value: 0 or 1 (enabled/disabled)
        │
        ├─ module_product_data_export_limit
        │  └─ Value: 100 (default batch size)
        │
        └─ module_product_data_export_format
           └─ Value: "json" or "csv"
```

---

## 📊 Response Format Diagram

### JSON Response Structure
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
      "description": "Product description...",
      "url": "http://shop.com/?product_id=1",
      "image": "http://shop.com/image/product.jpg",
      "quantity": 100,
      "status": 1,
      "rating": 4.5
    },
    { ... more products ... }
  ]
}
```

### CSV Response Structure
```
Product ID,Name,SKU,Price,Special Price,Description,URL,Image,Stock,Rating
1,"Product Name","PROD001","$99.99","$79.99","Description...","http://...","http://...",100,4.5
2,"Another Product","PROD002","$149.99","","Description...","http://...","http://...",50,4.2
```

---

## 🎯 Feature Matrix Diagram

```
PRODUCT DATA FIELDS EXPORTED:

Core Information:
  ├─ product_id ✅
  ├─ name ✅
  └─ sku ✅

Pricing:
  ├─ price (regular) ✅
  ├─ special (discount) ✅
  └─ considers customer groups ✅

Content:
  ├─ description ✅
  ├─ image ✅
  └─ direct URL ✅

Inventory:
  ├─ quantity (stock) ✅
  └─ status (active/inactive) ✅

Engagement:
  ├─ rating (average) ✅
  └─ based on reviews ✅

EXPORT OPTIONS:

Formats:
  ├─ JSON ✅
  │  └─ API integration friendly
  ├─ CSV ✅
  │  └─ Excel/Spreadsheet friendly
  └─ Pagination ✅
     └─ limit/offset parameters

Filtering:
  ├─ All products ✅
  ├─ By category ✅
  └─ Custom batch sizes ✅

ADMIN FEATURES:

Interface:
  ├─ Configuration page ✅
  ├─ Preview button ✅
  ├─ Export button ✅
  ├─ Format selector ✅
  ├─ Batch size config ✅
  ├─ Results display ✅
  └─ Download option ✅
```

---

## ⚙️ Class Hierarchy Diagram

```
OpenCart Base Controller
        ▲
        │
        ├─ ControllerExtensionModuleProductDataExport (Admin)
        │  ├─ index() → Admin panel
        │  ├─ export() → JSON export
        │  ├─ exportcsv() → CSV export
        │  ├─ validate() → Settings validation
        │  ├─ install() → Module install
        │  └─ uninstall() → Module uninstall
        │
        └─ ControllerExtensionModuleProductDataExport (Catalog)
           ├─ export() → API endpoint
           └─ category() → Category endpoint

OpenCart Base Model
        ▲
        │
        └─ ModelExtensionModuleProductDataExport (Shared)
           ├─ getProductsWithData() → Fetch all products
           ├─ getTotalProducts() → Count total
           └─ getProductsByCategory() → Fetch by category
```

---

## 📈 Performance Flowchart

```
Request Received
        │
        ▼
Parse Parameters
  ├─ limit (validated)
  ├─ offset (validated)
  └─ category_id (validated)
        │
        ▼
Execute SQL Query
  (with indexes optimized)
        │
        ▼
Build Result Set
  ├─ Format prices
  ├─ Generate URLs
  ├─ Get images
  ├─ Aggregate ratings
  └─ Convert data types
        │
        ▼
Encode Response
  ├─ JSON.stringify()
  │  (for JSON export)
  │
  └─ CSV formatter()
     (for CSV export)
        │
        ▼
Send Response
  ├─ Set headers
  └─ Output data
        │
        ▼
Complete (~100-500ms)
```

---

## 🔐 Security Diagram

```
REQUEST SECURITY:

User Input Parameters:
  limit, offset, category_id
        │
        ├─ Type Casting: (int)
        │
        ├─ Range Validation: min/max
        │
        └─ Database Query: Prepared Statements
              (SQL Injection Protection ✅)

OUTPUT SECURITY:

Response Data:
        │
        ├─ JSON Encoding: json_encode()
        │     (XSS Protection ✅)
        │
        ├─ CSV Escaping: addslashes()
        │     (CSV Injection Prevention ✅)
        │
        └─ Headers: Content-Type set explicitly
              (MIME Type Protection ✅)
```

---

These visual diagrams provide a quick reference for understanding the module's architecture, data flow, and structure.

---

**Module**: Product Data Export  
**Version**: 1.0.0  
**Created**: December 2025
