-- 创建数据库
CREATE DATABASE IF NOT EXISTS rag_db;

-- 使用数据库
USE rag_db;

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS file_info (
    fid INT AUTO_INCREMENT PRIMARY KEY,  -- 文件记录唯一ID
    doc_id VARCHAR(64) NOT NULL,  -- 文档ID，确保每个文件唯一
    source_document_name VARCHAR(255) NOT NULL,  -- 文档名称
    source_document_type VARCHAR(100),  -- 文档类型
    source_document_path VARCHAR(512) NOT NULL,  -- 文档路径
    source_document_pdf_path VARCHAR(512),  -- PDF路径
    source_document_json_path VARCHAR(512),  -- JSON路径
    source_document_images_path VARCHAR(512),  -- 图片路径
    merge_document_path VARCHAR(512),  -- 合并后的文档路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 更新时间
    UNIQUE(doc_id),  -- 唯一的文档ID
    INDEX idx_doc_id (doc_id)  -- 为doc_id增加索引以优化查询
);



-- 创建文件分块表
CREATE TABLE IF NOT EXISTS chunk_info (
    cid INT AUTO_INCREMENT PRIMARY KEY,  -- 分块记录的唯一ID
    segment_id VARCHAR(64) NOT NULL,  -- 分块的唯一ID
    parent_segment_id VARCHAR(64),  -- 分块的父表 segment_ID
    segment_text TEXT NOT NULL,  -- 分块的文本内容
    doc_id VARCHAR(64) NOT NULL,  -- 与文件关联的文档ID
    UNIQUE(segment_id),  -- 保证分块ID唯一
    INDEX idx_doc_id (doc_id),  -- 针对doc_id的索引
    FOREIGN KEY (doc_id) REFERENCES file_info(doc_id) ON DELETE CASCADE,  -- 外键约束
    INDEX idx_segment_id (segment_id)  -- 为segment_id增加索引以优化查询
);


-- 创建权限表
CREATE TABLE IF NOT EXISTS permission_info (
    pid INT AUTO_INCREMENT PRIMARY KEY,  -- 权限记录唯一ID
    department_id VARCHAR(64) NOT NULL,  -- 部门ID
    doc_id VARCHAR(64) NOT NULL,  -- 文档ID
    action_type VARCHAR(32),  -- 权限变更类型，如 'GRANT', 'REVOKE', 'UPDATE' 等
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 权限创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 权限更新时间
    INDEX idx_department_doc (department_id, doc_id)  -- 针对部门ID和文档ID建立索引
);
