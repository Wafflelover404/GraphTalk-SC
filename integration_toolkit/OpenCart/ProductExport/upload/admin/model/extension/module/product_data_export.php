<?php
/**
 * Product Data Export Module
 * Admin Model
 */
class ModelExtensionModuleProductDataExport extends Model {
    
    public function getProductsWithData($limit = 100, $offset = 0) {
        $query = $this->db->query(
            "SELECT 
                p.product_id,
                p.sku,
                p.quantity,
                p.status,
                p.image,
                pd.name,
                pd.description,
                (SELECT price FROM " . DB_PREFIX . "product_discount pf 
                    WHERE pf.product_id = p.product_id 
                    AND pf.customer_group_id = '" . (int)$this->config->get('config_customer_group_id') . "'
                    AND ((pf.date_start = '0000-00-00' OR DATE(pf.date_start) <= NOW()) 
                    AND (pf.date_end = '0000-00-00' OR DATE(pf.date_end) >= NOW()))
                    ORDER BY pf.priority ASC, pf.price ASC LIMIT 1) AS special,
                p.price,
                (SELECT AVG(rating) FROM " . DB_PREFIX . "review WHERE product_id = p.product_id AND status = '1') AS rating,
                CONCAT('" . $this->config->get('config_url') . "index.php?route=product/product&product_id=', p.product_id) AS url
            FROM " . DB_PREFIX . "product p
            LEFT JOIN " . DB_PREFIX . "product_description pd ON p.product_id = pd.product_id
            WHERE pd.language_id = '" . (int)$this->config->get('config_language_id') . "'
            ORDER BY p.product_id DESC
            LIMIT " . (int)$offset . ", " . (int)$limit
        );

        $products = array();
        
        foreach ($query->rows as $product) {
            // Get product image
            $image_query = $this->db->query(
                "SELECT image FROM " . DB_PREFIX . "product_image 
                WHERE product_id = '" . (int)$product['product_id'] . "' 
                ORDER BY sort_order ASC LIMIT 1"
            );
            
            $image = $product['image'];
            if ($image_query->row) {
                $image = $image_query->row['image'];
            }

            // Format product data
            $products[] = array(
                'product_id' => $product['product_id'],
                'name' => $product['name'],
                'sku' => $product['sku'],
                // Use raw numeric values so downstream APIs (e.g., Graphtalk ingest) can parse reliably
                'price' => $product['price'],
                'special' => $product['special'],
                'description' => html_entity_decode(strip_tags($product['description'])),
                'url' => $product['url'],
                'image' => $image ? $this->config->get('config_url') . 'image/' . $image : '',
                'quantity' => $product['quantity'],
                'status' => $product['status'],
                'rating' => $product['rating'] ? round($product['rating'], 2) : 0
            );
        }

        return $products;
    }

    public function getTotalProducts() {
        $query = $this->db->query(
            "SELECT COUNT(*) as total FROM " . DB_PREFIX . "product"
        );
        return $query->row['total'];
    }

    public function getProductsByCategory($category_id, $limit = 100, $offset = 0) {
        $query = $this->db->query(
            "SELECT 
                p.product_id,
                p.sku,
                p.quantity,
                p.status,
                p.image,
                pd.name,
                pd.description,
                p.price,
                (SELECT AVG(rating) FROM " . DB_PREFIX . "review WHERE product_id = p.product_id AND status = '1') AS rating,
                CONCAT('" . $this->config->get('config_url') . "index.php?route=product/product&product_id=', p.product_id) AS url
            FROM " . DB_PREFIX . "product p
            LEFT JOIN " . DB_PREFIX . "product_description pd ON p.product_id = pd.product_id
            LEFT JOIN " . DB_PREFIX . "product_to_category pc ON p.product_id = pc.product_id
            WHERE pd.language_id = '" . (int)$this->config->get('config_language_id') . "'
            AND pc.category_id = '" . (int)$category_id . "'
            ORDER BY p.product_id DESC
            LIMIT " . (int)$offset . ", " . (int)$limit
        );

        return $query->rows;
    }
}
