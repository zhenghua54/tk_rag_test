-- 创建数据库
CREATE DATABASE IF NOT EXISTS rag_db;

-- 使用数据库
USE rag_db;

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS file_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id VARCHAR(64) NOT NULL,
    source_document_name VARCHAR(255),
    source_document_type VARCHAR(100),
    source_document_path VARCHAR(512),
    source_document_pdf_path VARCHAR(512),
    source_document_json_path VARCHAR(512),
    source_document_markdown_path VARCHAR(512),
    source_document_images_path VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE(doc_id)
); 