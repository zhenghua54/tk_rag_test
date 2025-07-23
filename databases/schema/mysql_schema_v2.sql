-- 创建数据库
CREATE DATABASE IF NOT EXISTS {{DB_NAME}};

-- 使用数据库
USE {{DB_NAME}};

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS doc_info
(
    fid              INT AUTO_INCREMENT PRIMARY KEY COMMENT '文档记录ID',
    doc_id           VARCHAR(64)   NOT NULL COMMENT '文档ID',
    doc_name         VARCHAR(512)  NOT NULL COMMENT '文档名称(无后缀)',
    doc_ext          VARCHAR(100)  NOT NULL COMMENT '文档后缀',
    doc_path         VARCHAR(1024) NOT NULL COMMENT '本地源文件路径',
    doc_size         VARCHAR(100) COMMENT '源文档大小',
    doc_http_url     VARCHAR(1024) COMMENT '网络源文档路径',
    doc_output_dir   VARCHAR(1024) COMMENT '输出目录(存储解析和处理后的所有文件)',
    doc_pdf_path     VARCHAR(1024) COMMENT '文档的 PDF 路径',
    doc_json_path    VARCHAR(1024) COMMENT 'MinerU 输出的json文件路径(无坐标)',
    doc_spans_path   VARCHAR(1024) COMMENT 'MinerU 输出的版面效果文件路径(校验用)',
    doc_layout_path  VARCHAR(1024) COMMENT 'MinerU 输出的版面解析文件路径',
    doc_images_path  VARCHAR(1024) COMMENT 'json文件中的图片源文件',
    doc_process_path VARCHAR(1024) COMMENT '合并处理后的文档路径',
    process_status   VARCHAR(20) COMMENT '文档的处理状态',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间', -- 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE uk_doc_id (doc_id),
    INDEX idx_doc_id (doc_id),
    INDEX idx_process_status (process_status),
    INDEX idx_created_at (created_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT ='文档信息表';


-- 创建文件分块表
CREATE TABLE IF NOT EXISTS segment_info
(
    cid            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '分块记录的唯一ID',
    seg_id         VARCHAR(64) NOT NULL COMMENT '分块的唯一ID',
    seg_content    LONGTEXT COMMENT '分块的元内容（表格 HTML、图片标题、文本内容)',
    seg_image_path VARCHAR(255) COMMENT '分块对应的图片路径',
    seg_caption    TEXT COMMENT '分块的标题(表格标题、图片标题)',
    seg_footnote   TEXT COMMENT '分块的脚注(表格脚注、图片脚注)',
    seg_len        INT COMMENT '分块字符长度',
    seg_type       VARCHAR(20) COMMENT '分块元素类型',
    seg_page_idx   INT         NOT NULL COMMENT '所属页码',
    doc_id         VARCHAR(64) NOT NULL COMMENT '所属文档ID',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间', -- 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_seg_id (seg_id),
    INDEX idx_doc_id (doc_id),
    INDEX idx_seg_type (seg_type),
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT ='文档分块表';


-- 创建权限表_v2: 支持接收不同类型
CREATE TABLE IF NOT EXISTS permission_doc_link (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    permission_type VARCHAR(32) NOT NULL COMMENT '权限类型：department、role、user等',
    subject_id VARCHAR(64) NOT NULL COMMENT '如部门ID、角色ID等',
    doc_id VARCHAR(64) NOT NULL COMMENT '单个文档ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (doc_id) REFERENCES doc_info(doc_id) ON DELETE CASCADE,
    UNIQUE KEY uniq_permission (permission_type, subject_id, doc_id),
    INDEX idx_permission_type (permission_type),
    INDEX idx_subject_id (subject_id),
    INDEX idx_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='权限文档映射表';


-- 创建文档分页内容表
CREATE TABLE IF NOT EXISTS doc_page_info
(
    pid           INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    doc_id        VARCHAR(64) NOT NULL COMMENT '文档ID',
    page_idx      INT         NOT NULL COMMENT '页码',
    page_png_path VARCHAR(1024) COMMENT '分页图片存储路径',
    UNIQUE KEY uniq_doc_page (doc_id, page_idx), -- 防止重复页
    INDEX idx_doc_id (doc_id),
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT ='文档分页信息表';


-- 创建聊天会话表
CREATE TABLE IF NOT EXISTS chat_sessions
(
    id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '会话记录ID',
    session_id VARCHAR(64) NOT NULL UNIQUE COMMENT '会话ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT ='聊天会话表';

-- 创建聊天消息表
CREATE TABLE IF NOT EXISTS chat_messages
(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '消息记录ID',
    session_id   VARCHAR(64)          NOT NULL COMMENT '会话ID',
    message_type ENUM ('human', 'ai') NOT NULL COMMENT '消息类型',
    content      TEXT                 NOT NULL COMMENT '消息内容',
    metadata     JSON      DEFAULT NULL COMMENT '元数据(文档信息、改写查询、token数量、模型名称、处理时间、错误信息等)',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_session_id (session_id),
    INDEX idx_message_type (message_type),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT ='聊天消息表';