<?php
/**
 * Product Data Export Module
 * Admin Controller
 * Compatible with OpenCart 3.x
 */
class ControllerExtensionModuleProductDataExport extends Controller {
    private $error = array();

    public function index() {
        $this->load->language('extension/module/product_data_export');
        $this->document->setTitle($this->language->get('heading_title'));
        $this->load->model('setting/setting');

        if (($this->request->server['REQUEST_METHOD'] == 'POST') && $this->validate()) {
            $this->model_setting_setting->editSetting('module_product_data_export', $this->request->post);
            $this->session->data['success'] = $this->language->get('text_success');
            $this->response->redirect($this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module', true));
        }

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
            'text' => $this->language->get('heading_title'),
            'href' => $this->url->link('extension/module/product_data_export', 'user_token=' . $this->session->data['user_token'], true)
        );

        $data['action'] = $this->url->link('extension/module/product_data_export', 'user_token=' . $this->session->data['user_token'], true);
        $data['cancel'] = $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module', true);

        $data['module_product_data_export_status'] = $this->config->get('module_product_data_export_status');
        $data['module_product_data_export_limit'] = $this->config->get('module_product_data_export_limit') ?: 100;
        $data['module_product_data_export_format'] = $this->config->get('module_product_data_export_format') ?: 'json';

        $data['header'] = $this->load->controller('common/header');
        $data['column_left'] = $this->load->controller('common/column_left');
        $data['footer'] = $this->load->controller('common/footer');

        $this->response->setOutput($this->load->view('extension/module/product_data_export', $data));
    }

    public function export() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');
        $this->load->model('catalog/product');

        $json = array();

        // Get export parameters
        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 100;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;
        $format = isset($this->request->get['format']) ? $this->request->get['format'] : 'json';

        try {
            $products = $this->model_extension_module_product_data_export->getProductsWithData($limit, $offset);
            
            $json['success'] = true;
            $json['total_products'] = $this->model_extension_module_product_data_export->getTotalProducts();
            $json['limit'] = $limit;
            $json['offset'] = $offset;
            $json['products'] = $products;
            $json['count'] = count($products);

        } catch (Exception $e) {
            $json['error'] = $e->getMessage();
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }

    public function exportcsv() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');

        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 10000;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;

        $products = $this->model_extension_module_product_data_export->getProductsWithData($limit, $offset);

        // Generate CSV
        $csv_output = "Product ID,Name,SKU,Price,Special Price,Description,URL,Image,Stock,Rating\n";
        
        foreach ($products as $product) {
            $csv_output .= sprintf(
                '"%s","%s","%s","%s","%s","%s","%s","%s","%s","%s"' . "\n",
                $product['product_id'],
                addslashes($product['name']),
                $product['sku'],
                $product['price'],
                $product['special'],
                substr(addslashes($product['description']), 0, 100),
                $product['url'],
                $product['image'],
                $product['quantity'],
                $product['rating']
            );
        }

        $this->response->addHeader('Content-Type: text/csv; charset=utf-8');
        $this->response->addHeader('Content-Disposition: attachment; filename="products_' . date('Y-m-d') . '.csv"');
        $this->response->setOutput($csv_output);
    }

    protected function validate() {
        if (!$this->user->hasPermission('modify', 'extension/module/product_data_export')) {
            $this->error['warning'] = $this->language->get('error_permission');
        }

        return !$this->error;
    }

    public function install() {
        $this->load->model('setting/setting');
        
        $defaults = array(
            'module_product_data_export_status' => 1,
            'module_product_data_export_limit' => 100,
            'module_product_data_export_format' => 'json'
        );
        
        $this->model_setting_setting->editSetting('module_product_data_export', $defaults);
    }

    public function uninstall() {
        $this->load->model('setting/setting');
        $this->model_setting_setting->deleteSetting('module_product_data_export');
    }
}
