<?php
/**
 * Product Data Export Module - WikiAI Integration
 * Admin Controller
 * Compatible with OpenCart 3.x
 * 
 * Allows configuration of WikiAI integration and catalog syncing
 */
class ControllerExtensionModuleProductDataExportWikiai extends Controller {
    private $error = array();

    public function index() {
        $this->load->language('extension/module/product_data_export');
        $this->document->setTitle($this->language->get('heading_title') . ' - WikiAI Integration');
        $this->load->model('setting/setting');

        if (($this->request->server['REQUEST_METHOD'] == 'POST') && $this->validate()) {
            // Save regular settings
            $this->model_setting_setting->editSetting('module_product_data_export', $this->request->post);
            
            // Save WikiAI-specific settings
            $wikiai_settings = array(
                'product_data_export_wikiai_enabled' => isset($this->request->post['product_data_export_wikiai_enabled']) ? 1 : 0,
                'product_data_export_wikiai_api_url' => isset($this->request->post['product_data_export_wikiai_api_url']) ? $this->request->post['product_data_export_wikiai_api_url'] : '',
                'product_data_export_wikiai_token' => isset($this->request->post['product_data_export_wikiai_token']) ? $this->request->post['product_data_export_wikiai_token'] : '',
                'product_data_export_wikiai_catalog_id' => isset($this->request->post['product_data_export_wikiai_catalog_id']) ? $this->request->post['product_data_export_wikiai_catalog_id'] : '',
                'product_data_export_wikiai_auto_sync' => isset($this->request->post['product_data_export_wikiai_auto_sync']) ? 1 : 0,
                'product_data_export_wikiai_sync_interval' => isset($this->request->post['product_data_export_wikiai_sync_interval']) ? (int)$this->request->post['product_data_export_wikiai_sync_interval'] : 3600,
            );
            $this->model_setting_setting->editSetting('product_data_export_wikiai', $wikiai_settings);
            
            $this->session->data['success'] = $this->language->get('text_success');
            $this->response->redirect($this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module', true));
        }

        // Prepare data
        $data = array();
        $data['error_warning'] = isset($this->error['warning']) ? $this->error['warning'] : '';

        $data['breadcrumbs'] = array();
        $data['breadcrumbs'][] = array(
            'text' => $this->language->get('text_home'),
            'href' => $this->url->link('common/dashboard', 'user_token=' . $this->session->data['user_token'], true)
        );
        $data['breadcrumbs'][] = array(
            'text' => $this->language->get('text_extension'),
            'href' => $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module', true)
        );
        $data['breadcrumbs'][] = array(
            'text' => $this->language->get('heading_title') . ' - WikiAI Integration',
            'href' => $this->url->link('extension/module/product_data_export_wikiai', 'user_token=' . $this->session->data['user_token'], true)
        );

        $data['action'] = $this->url->link('extension/module/product_data_export_wikiai', 'user_token=' . $this->session->data['user_token'], true);
        $data['cancel'] = $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module', true);

        // Get WikiAI settings
        $wikiai_settings = $this->model_setting_setting->getSetting('product_data_export_wikiai');
        
        $data['product_data_export_wikiai_enabled'] = $wikiai_settings['product_data_export_wikiai_enabled'] ?? 0;
        $data['product_data_export_wikiai_api_url'] = $wikiai_settings['product_data_export_wikiai_api_url'] ?? 'http://localhost:8000';
        $data['product_data_export_wikiai_token'] = $wikiai_settings['product_data_export_wikiai_token'] ?? '';
        $data['product_data_export_wikiai_catalog_id'] = $wikiai_settings['product_data_export_wikiai_catalog_id'] ?? '';
        $data['product_data_export_wikiai_auto_sync'] = $wikiai_settings['product_data_export_wikiai_auto_sync'] ?? 0;
        $data['product_data_export_wikiai_sync_interval'] = $wikiai_settings['product_data_export_wikiai_sync_interval'] ?? 3600;

        // Get regular module settings
        $module_settings = $this->model_setting_setting->getSetting('module_product_data_export');
        
        $data['module_product_data_export_status'] = $module_settings['module_product_data_export_status'] ?? 1;
        $data['module_product_data_export_limit'] = $module_settings['module_product_data_export_limit'] ?? 100;
        $data['module_product_data_export_format'] = $module_settings['module_product_data_export_format'] ?? 'json';

        // Add actions for testing
        $data['test_connection_url'] = $this->url->link('extension/module/product_data_export_wikiai/testConnection', 'user_token=' . $this->session->data['user_token'], true);
        $data['sync_products_url'] = $this->url->link('extension/module/product_data_export_wikiai/syncProducts', 'user_token=' . $this->session->data['user_token'], true);
        $data['check_status_url'] = $this->url->link('extension/module/product_data_export_wikiai/checkStatus', 'user_token=' . $this->session->data['user_token'], true);

        $data['header'] = $this->load->controller('common/header');
        $data['column_left'] = $this->load->controller('common/column_left');
        $data['footer'] = $this->load->controller('common/footer');

        $this->response->setOutput($this->load->view('extension/module/product_data_export_wikiai', $data));
    }

    /**
     * Test connection to WikiAI API
     */
    public function testConnection() {
        $this->load->model('setting/setting');
        $wikiai_settings = $this->model_setting_setting->getSetting('product_data_export_wikiai');
        
        $json = array('success' => false);
        
        $api_url = $wikiai_settings['product_data_export_wikiai_api_url'] ?? '';
        $token = $wikiai_settings['product_data_export_wikiai_token'] ?? '';

        if (!$api_url || !$token) {
            $json['error'] = 'WikiAI API URL and token are required';
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        // Test connection to /catalogs endpoint
        $ch = curl_init();
        curl_setopt_array($ch, array(
            CURLOPT_URL => rtrim($api_url, '/') . '/catalogs',
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => array(
                'Authorization: Bearer ' . $token
            ),
            CURLOPT_TIMEOUT => 10,
            CURLOPT_SSL_VERIFYPEER => false
        ));

        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($error) {
            $json['error'] = 'Connection error: ' . $error;
        } else if ($http_code == 200) {
            $json['success'] = true;
            $json['message'] = 'Successfully connected to WikiAI API';
            $response_data = json_decode($response, true);
            if (isset($response_data['response']['count'])) {
                $json['catalogs_count'] = $response_data['response']['count'];
            }
        } else {
            $json['error'] = 'HTTP ' . $http_code . ': Unable to connect to WikiAI API';
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Sync products to WikiAI catalog
     */
    public function syncProducts() {
        $this->load->model('setting/setting');
        $this->load->model('extension/module/product_data_export');
        
        $wikiai_settings = $this->model_setting_setting->getSetting('product_data_export_wikiai');
        
        $json = array('success' => false);
        
        $api_url = $wikiai_settings['product_data_export_wikiai_api_url'] ?? '';
        $token = $wikiai_settings['product_data_export_wikiai_token'] ?? '';
        $catalog_id = $wikiai_settings['product_data_export_wikiai_catalog_id'] ?? '';

        if (!$api_url || !$token || !$catalog_id) {
            $json['error'] = 'WikiAI configuration incomplete. Please configure API URL, token, and catalog ID.';
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        try {
            // Get products from OpenCart
            $products = $this->model_extension_module_product_data_export->getProductsWithData(500, 0);

            if (empty($products)) {
                $json['error'] = 'No products found to sync';
                $this->response->addHeader('Content-Type: application/json');
                $this->response->setOutput(json_encode($json));
                return;
            }

            // Convert to WikiAI format
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

            // Send to WikiAI
            $ch = curl_init();
            curl_setopt_array($ch, array(
                CURLOPT_URL => rtrim($api_url, '/') . '/catalogs/' . urlencode($catalog_id) . '/products/import',
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_POST => true,
                CURLOPT_HTTPHEADER => array(
                    'Content-Type: application/json',
                    'Authorization: Bearer ' . $token
                ),
                CURLOPT_POSTFIELDS => json_encode($wikiai_products),
                CURLOPT_TIMEOUT => 30,
                CURLOPT_SSL_VERIFYPEER => false
            ));

            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            $response_data = json_decode($response, true);

            if ($http_code == 200 && isset($response_data['status']) && $response_data['status'] == 'success') {
                $json['success'] = true;
                $json['message'] = 'Products synced successfully';
                $json['inserted'] = $response_data['response']['inserted'] ?? 0;
                $json['updated'] = $response_data['response']['updated'] ?? 0;
                $json['total'] = count($wikiai_products);
            } else {
                $json['error'] = $response_data['message'] ?? 'Failed to sync products (HTTP ' . $http_code . ')';
            }

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    /**
     * Check sync status with WikiAI
     */
    public function checkStatus() {
        $this->load->model('setting/setting');
        $this->load->model('extension/module/product_data_export');
        
        $wikiai_settings = $this->model_setting_setting->getSetting('product_data_export_wikiai');
        
        $json = array('success' => false);
        
        $api_url = $wikiai_settings['product_data_export_wikiai_api_url'] ?? '';
        $token = $wikiai_settings['product_data_export_wikiai_token'] ?? '';
        $catalog_id = $wikiai_settings['product_data_export_wikiai_catalog_id'] ?? '';

        if (!$catalog_id) {
            $json['error'] = 'Catalog ID not configured';
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        try {
            // Get OpenCart product count
            $opencart_total = $this->model_extension_module_product_data_export->getTotalProducts();
            
            $json['opencart_products'] = $opencart_total;
            $json['catalog_id'] = $catalog_id;

            // Get WikiAI status if configured
            if ($api_url && $token) {
                $ch = curl_init();
                curl_setopt_array($ch, array(
                    CURLOPT_URL => rtrim($api_url, '/') . '/catalogs/' . urlencode($catalog_id),
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_HTTPHEADER => array(
                        'Authorization: Bearer ' . $token
                    ),
                    CURLOPT_TIMEOUT => 10,
                    CURLOPT_SSL_VERIFYPEER => false
                ));

                $response = curl_exec($ch);
                $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                curl_close($ch);

                if ($http_code == 200) {
                    $response_data = json_decode($response, true);
                    if (isset($response_data['response'])) {
                        $json['success'] = true;
                        $json['wikiai_catalog'] = $response_data['response'];
                        $json['sync_percentage'] = $opencart_total > 0 
                            ? round(($response_data['response']['total_products'] / $opencart_total) * 100, 2)
                            : 0;
                    }
                }
            }

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    protected function validate() {
        if (!$this->user->hasPermission('modify', 'extension/module/product_data_export')) {
            $this->error['warning'] = $this->language->get('error_permission');
        }

        return !$this->error;
    }
}
?>
