<?php
/**
 * Product Data Export Module - WikiAI Integration
 * Catalog Controller - For frontend/API access with automatic WikiAI import
 * 
 * This controller exports products from OpenCart and can automatically
 * push them to WikiAI catalog system for indexing and semantic search.
 */
class ControllerExtensionModuleProductDataExportWikiai extends Controller {

    private $wikiai_api_url = 'http://localhost:8000'; // Will be configurable
    private $wikiai_token = ''; // Will be loaded from config

    public function __construct($registry) {
        parent::__construct($registry);
        
        // Load WikiAI configuration
        $this->load->model('setting/setting');
        $wikiai_settings = $this->model_setting_setting->getSetting('product_data_export');
        
        if (!empty($wikiai_settings['product_data_export_wikiai_api_url'])) {
            $this->wikiai_api_url = $wikiai_settings['product_data_export_wikiai_api_url'];
        }
        if (!empty($wikiai_settings['product_data_export_wikiai_token'])) {
            $this->wikiai_token = $wikiai_settings['product_data_export_wikiai_token'];
        }
    }

    /**
     * Export products in JSON format
     * Can optionally push to WikiAI
     */
    public function export() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');

        $json = array();

        // Get export parameters
        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 100;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;
        $push_to_wikiai = isset($this->request->get['push_wikiai']) ? (bool)$this->request->get['push_wikiai'] : false;
        $catalog_id = isset($this->request->get['catalog_id']) ? $this->request->get['catalog_id'] : null;

        try {
            $products = $this->model_extension_module_product_data_export->getProductsWithData($limit, $offset);
            
            $json['success'] = true;
            $json['total_products'] = $this->model_extension_module_product_data_export->getTotalProducts();
            $json['limit'] = $limit;
            $json['offset'] = $offset;
            $json['products'] = $products;
            $json['count'] = count($products);

            // Push to WikiAI if requested and token is configured
            if ($push_to_wikiai && $this->wikiai_token && $catalog_id) {
                $import_result = $this->pushToWikiAI($products, $catalog_id);
                $json['wikiai_import'] = $import_result;
            }

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
            $json['success'] = false;
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Export products by category
     */
    public function category() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');

        $json = array();

        $category_id = isset($this->request->get['category_id']) ? (int)$this->request->get['category_id'] : 0;
        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 100;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;
        $push_to_wikiai = isset($this->request->get['push_wikiai']) ? (bool)$this->request->get['push_wikiai'] : false;
        $catalog_id = isset($this->request->get['catalog_id']) ? $this->request->get['catalog_id'] : null;

        if (!$category_id) {
            $json['error'] = 'Category ID is required';
            $json['success'] = false;
        } else {
            try {
                $products = $this->model_extension_module_product_data_export->getProductsByCategory($category_id, $limit, $offset);
                
                $json['success'] = true;
                $json['category_id'] = $category_id;
                $json['limit'] = $limit;
                $json['offset'] = $offset;
                $json['products'] = $products;
                $json['count'] = count($products);

                // Push to WikiAI if requested
                if ($push_to_wikiai && $this->wikiai_token && $catalog_id) {
                    $import_result = $this->pushToWikiAI($products, $catalog_id);
                    $json['wikiai_import'] = $import_result;
                }

            } catch (Exception $e) {
                $json['error'] = $e->getMessage();
                $json['success'] = false;
            }
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Sync products to WikiAI catalog
     * This is a dedicated endpoint for syncing operations
     */
    public function syncWikiai() {
        $this->load->model('extension/module/product_data_export');

        $json = array('success' => false);
        
        if (!$this->wikiai_token) {
            $json['error'] = 'WikiAI not configured. Please set API token in module settings.';
            $this->response->addHeader('Content-Type: application/json; charset=utf-8');
            $this->response->setOutput(json_encode($json));
            return;
        }

        $catalog_id = isset($this->request->post['catalog_id']) ? $this->request->post['catalog_id'] : null;
        $limit = isset($this->request->post['limit']) ? (int)$this->request->post['limit'] : 500;
        $offset = isset($this->request->post['offset']) ? (int)$this->request->post['offset'] : 0;

        if (!$catalog_id) {
            $json['error'] = 'Catalog ID is required';
            $this->response->addHeader('Content-Type: application/json; charset=utf-8');
            $this->response->setOutput(json_encode($json));
            return;
        }

        try {
            // Get all products
            $all_products = $this->model_extension_module_product_data_export->getProductsWithData($limit, $offset);
            
            if (empty($all_products)) {
                $json['error'] = 'No products found to sync';
                $this->response->addHeader('Content-Type: application/json; charset=utf-8');
                $this->response->setOutput(json_encode($json));
                return;
            }

            // Push to WikiAI
            $import_result = $this->pushToWikiAI($all_products, $catalog_id);
            
            if ($import_result['success']) {
                $json['success'] = true;
                $json['message'] = 'Products synced to WikiAI successfully';
                $json['synced_count'] = $import_result['imported'];
                $json['updated_count'] = $import_result['updated'];
                $json['total'] = count($all_products);
            } else {
                $json['error'] = $import_result['error'] ?? 'Failed to sync products';
            }

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Get sync status between OpenCart and WikiAI
     */
    public function getSyncStatus() {
        $catalog_id = isset($this->request->get['catalog_id']) ? $this->request->get['catalog_id'] : null;
        
        $json = array('success' => false);

        if (!$catalog_id) {
            $json['error'] = 'Catalog ID is required';
            $this->response->addHeader('Content-Type: application/json; charset=utf-8');
            $this->response->setOutput(json_encode($json));
            return;
        }

        try {
            // Get total OpenCart products
            $this->load->model('extension/module/product_data_export');
            $opencart_total = $this->model_extension_module_product_data_export->getTotalProducts();

            // Get status from WikiAI
            $status = $this->getWikiAISyncStatus($catalog_id);
            
            $json['success'] = true;
            $json['opencart_products'] = $opencart_total;
            $json['wikiai_catalog'] = $status;

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Push products to WikiAI catalog
     * 
     * @param array $products Array of product data
     * @param string $catalog_id WikiAI catalog ID
     * @return array Result of import operation
     */
    private function pushToWikiAI($products, $catalog_id) {
        if (empty($this->wikiai_token)) {
            return array(
                'success' => false,
                'error' => 'WikiAI API token not configured'
            );
        }

        // Convert OpenCart product format to WikiAI format
        $wikiai_products = array();
        foreach ($products as $product) {
            $wikiai_products[] = array(
                'product_id' => (string)$product['product_id'],
                'name' => $product['name'],
                'sku' => $product['sku'],
                'description' => $product['description'],
                'price' => (float)$product['price'],
                'special_price' => $product['special'] ? (float)$product['special'] : null,
                'url' => $product['url'],
                'image' => $product['image'],
                'quantity' => (int)$product['quantity'],
                'rating' => $product['rating'] ? (float)$product['rating'] : 0,
                'status' => (int)$product['status']
            );
        }

        // Prepare API request
        $url = $this->wikiai_api_url . '/catalogs/' . urlencode($catalog_id) . '/products/import';
        
        $ch = curl_init();
        curl_setopt_array($ch, array(
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_HTTPHEADER => array(
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->wikiai_token
            ),
            CURLOPT_POSTFIELDS => json_encode($wikiai_products),
            CURLOPT_TIMEOUT => 30,
            CURLOPT_SSL_VERIFYPEER => false // Use with caution in production
        ));

        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($error) {
            return array(
                'success' => false,
                'error' => 'CURL Error: ' . $error
            );
        }

        $response_data = json_decode($response, true);

        if ($http_code == 200 && isset($response_data['status']) && $response_data['status'] == 'success') {
            return array(
                'success' => true,
                'imported' => $response_data['response']['inserted'] ?? 0,
                'updated' => $response_data['response']['updated'] ?? 0,
                'total' => $response_data['response']['total'] ?? count($wikiai_products)
            );
        } else {
            return array(
                'success' => false,
                'error' => $response_data['message'] ?? 'WikiAI API error (HTTP ' . $http_code . ')',
                'http_code' => $http_code
            );
        }
    }

    /**
     * Get sync status from WikiAI
     * 
     * @param string $catalog_id WikiAI catalog ID
     * @return array Catalog details from WikiAI
     */
    private function getWikiAISyncStatus($catalog_id) {
        if (empty($this->wikiai_token)) {
            return array(
                'error' => 'WikiAI not configured'
            );
        }

        $url = $this->wikiai_api_url . '/catalogs/' . urlencode($catalog_id);
        
        $ch = curl_init();
        curl_setopt_array($ch, array(
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => array(
                'Authorization: Bearer ' . $this->wikiai_token
            ),
            CURLOPT_TIMEOUT => 10,
            CURLOPT_SSL_VERIFYPEER => false
        ));

        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $response_data = json_decode($response, true);

        if ($http_code == 200 && isset($response_data['response'])) {
            return array(
                'id' => $response_data['response']['id'] ?? $catalog_id,
                'total_products' => $response_data['response']['total_products'] ?? 0,
                'indexed_products' => $response_data['response']['indexed_products'] ?? 0,
                'last_updated' => $response_data['response']['updated_at'] ?? null
            );
        }

        return array('error' => 'Unable to fetch catalog status');
    }
}
?>
