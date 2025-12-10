<?php
/**
 * Product Data Export Module
 * Catalog Controller - For frontend/API access
 */
class ControllerExtensionModuleProductDataExport extends Controller {

    public function export() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');

        $json = array();

        // Get export parameters
        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 100;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;

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

    public function category() {
        $this->load->language('extension/module/product_data_export');
        $this->load->model('extension/module/product_data_export');

        $json = array();

        $category_id = isset($this->request->get['category_id']) ? (int)$this->request->get['category_id'] : 0;
        $limit = isset($this->request->get['limit']) ? (int)$this->request->get['limit'] : 100;
        $offset = isset($this->request->get['offset']) ? (int)$this->request->get['offset'] : 0;

        if (!$category_id) {
            $json['error'] = 'Category ID is required';
        } else {
            try {
                $products = $this->model_extension_module_product_data_export->getProductsByCategory($category_id, $limit, $offset);
                
                $json['success'] = true;
                $json['category_id'] = $category_id;
                $json['limit'] = $limit;
                $json['offset'] = $offset;
                $json['products'] = $products;
                $json['count'] = count($products);

            } catch (Exception $e) {
                $json['error'] = $e->getMessage();
            }
        }

        $this->response->addHeader('Content-Type: application/json; charset=utf-8');
        $this->response->setOutput(json_encode($json));
    }
}
