-- 创建数据库
CREATE DATABASE IF NOT EXISTS {{DB_NAME}};

-- 使用数据库
USE {{DB_NAME}};

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS doc_info
(
    fid              INT AUTO_INCREMENT PRIMARY KEY,                                  -- 文件记录唯一ID
    doc_id           VARCHAR(64)   NOT NULL,                                          -- 文档ID，确保每个文件唯一
    doc_name         VARCHAR(255)  NOT NULL,                                          -- 文档名称
    doc_ext          VARCHAR(100),                                                    -- 文档类型
    doc_path         VARCHAR(1024) NOT NULL,                                          -- 文档路径
    doc_size         VARCHAR(100),                                                    -- 文档大小
    doc_pdf_path     VARCHAR(1024),                                                   -- PDF路径
    doc_json_path    VARCHAR(1024),                                                   -- JSON路径
    doc_images_path  VARCHAR(1024),                                                   -- 图片路径
    doc_process_path VARCHAR(1024),                                                   -- 合并后的文档路径
    is_soft_deleted  BOOL      DEFAULT FALSE,                                         -- 是否软删除，默认为 false
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 更新时间
    UNIQUE (doc_id),                                                                  -- 唯一的文档ID
    INDEX idx_doc_id (doc_id)                                                         -- 为doc_id增加索引以优化查询
);


-- 创建文件分块表
CREATE TABLE IF NOT EXISTS segment_info
(
    cid             INT AUTO_INCREMENT PRIMARY KEY,                                  -- 分块记录的唯一ID
    seg_id          VARCHAR(64) NOT NULL,                                            -- 分块的唯一ID
    seg_parent_id   VARCHAR(64),                                                     -- 分块的父表 segment_ID
    seg_content     TEXT        NOT NULL,                                            -- 分块的元内容，表格 html，图片标题（暂时，增加标识），文本内容
    seg_image_path  VARCHAR(1024),                                                   -- 分块对应的图片路径
    seg_caption     TEXT,                                                            -- 分块的标题，表格标题、图片标题
    seg_footnote    TEXT,                                                            -- 分块的脚注，表格脚注、图片脚注
    seg_len         VARCHAR(100),                                                    -- 分块字符长度
    seg_type        VARCHAR(100),                                                    -- 分块源元素类型
    seg_page_idx    VARCHAR(100),                                                    -- 分块所在页码
    doc_id          VARCHAR(64) NOT NULL,                                            -- 与文件关联的文档ID
    is_soft_deleted BOOL      DEFAULT FALSE,                                         -- 是否软删除，默认为 false
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 更新时间
    INDEX idx_doc_id (doc_id),                                                       -- 针对 doc_id 的索引
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE,             -- 外键约束
    INDEX idx_segment_id (seg_id)                                                    -- 为 segment_id 增加索引以优化查询
);


-- 创建权限表
CREATE TABLE IF NOT EXISTS permission_info
(
    pid             INT AUTO_INCREMENT PRIMARY KEY,                                  -- 权限记录唯一ID
    department_id   VARCHAR(64) NOT NULL,                                            -- 部门ID
    doc_id          VARCHAR(64) NOT NULL,                                            -- 文档ID
    is_soft_deleted BOOL      DEFAULT FALSE,                                         -- 是否软删除，默认为 false
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 权限创建时间
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 权限更新时间
    INDEX idx_department_doc (department_id, doc_id)                                 -- 针对部门ID和文档ID建立索引
);
