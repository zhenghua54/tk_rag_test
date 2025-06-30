-- 创建数据库
CREATE DATABASE IF NOT EXISTS {{DB_NAME}};

-- 使用数据库
USE {{DB_NAME}};

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS doc_info
(
    fid              INT AUTO_INCREMENT PRIMARY KEY,                                     -- 文件记录唯一ID
    doc_id           VARCHAR(64)   NOT NULL,                                             -- 文档ID，确保每个文件唯一
    doc_name         VARCHAR(512)  NOT NULL,                                             -- 文档名称
    doc_ext          VARCHAR(100),                                                       -- 文档类型
    doc_path         VARCHAR(1024) NOT NULL,                                             -- 文档路径
    doc_size         VARCHAR(100),                                                       -- 文档大小
    doc_http_url     VARCHAR(1024),                                                      -- 文档的源 HTTP 地址
    doc_output_dir   VARCHAR(1024),                                                      -- 处理后文档的保存目录
    doc_pdf_path     VARCHAR(1024),                                                      -- PDF路径
    doc_json_path    VARCHAR(1024),                                                      -- JSON路径
    doc_spans_path  VARCHAR(1024),                                                       -- spans 可视化路径
    doc_layout_path VARCHAR(1024),                                                       -- layout 可视化路径
    doc_images_path  VARCHAR(1024),                                                      -- 图片路径
    doc_process_path VARCHAR(1024),                                                      -- 合并后的文档路径
    process_status   VARCHAR(20),                                                        -- 文档处理状态：见配置文件中的 FILE_STATUS 定义
    error_message    VARCHAR(255) DEFAULT NULL,                                          -- 处理错误信息
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,                             -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 更新时间
    UNIQUE (doc_id),                                                                     -- 唯一的文档ID
    INDEX idx_doc_id (doc_id)                                                            -- 为doc_id增加索引以优化查询
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;


-- 创建文件分块表
CREATE TABLE IF NOT EXISTS segment_info
(
    cid            BIGINT AUTO_INCREMENT PRIMARY KEY,                               -- 分块记录的唯一ID
    seg_id         VARCHAR(64) NOT NULL,                                            -- 分块的唯一ID
    seg_parent_id  VARCHAR(64),                                                     -- 分块的父表 seg_id
    seg_content    LONGTEXT,                                                        -- 分块的元内容，表格 html，图片标题（暂时，增加标识），文本内容, 使用 LONGTEXT 避免超长报错
    seg_image_path VARCHAR(255),                                                    -- 分块对应的图片路径
    seg_caption    TEXT,                                                            -- 分块的标题，表格标题、图片标题
    seg_footnote   TEXT,                                                            -- 分块的脚注，表格脚注、图片脚注
    seg_len        VARCHAR(10),                                                     -- 分块字符长度
    seg_type       VARCHAR(20),                                                     -- 分块源元素类型
    seg_page_idx   INT         NOT NULL,                                            -- 分块所在页码
    doc_id         VARCHAR(64) NOT NULL,                                            -- 与文件关联的文档ID
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 更新时间
    INDEX idx_doc_id (doc_id),                                                      -- 针对 doc_id 的索引
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE,            -- 外键约束
    INDEX idx_seg_id (seg_id)                                                       -- 为 seg_id 增加索引以优化查询
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;


-- 创建权限表
CREATE TABLE IF NOT EXISTS permission_info
(
    pid            INT AUTO_INCREMENT PRIMARY KEY,                                  -- 权限记录唯一ID
    permission_ids VARCHAR(64),                                                     -- 部门ID, 允许为空，为空代表不限制
    doc_id         VARCHAR(64) NOT NULL,                                            -- 文档ID
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 权限创建时间
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 权限更新时间
    INDEX idx_department_doc (permission_ids, doc_id),                              -- 针对部门ID和文档ID建立索引
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

-- 创建文档分页内容
CREATE TABLE IF NOT EXISTS doc_page_info
(
    pid             INT AUTO_INCREMENT PRIMARY KEY, -- 记录唯一ID
    doc_id          VARCHAR(64) NOT NULL,           -- 文档ID
    page_idx        INT         NOT NULL,           -- 页码
    page_pdf_path   VARCHAR(1024),                  -- 每页的存储路径
    page_static_url VARCHAR(1024),                  -- 页面的图片/HTML链接
    UNIQUE KEY uniq_doc_page (doc_id, page_idx),    -- 防止重复页
    INDEX idx_doc_id (doc_id),
    FOREIGN KEY (doc_id) REFERENCES doc_info (doc_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;


-- 会话表
CREATE TABLE IF NOT EXISTS chat_sessions
(
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL UNIQUE COMMENT '会话ID',
    user_id    VARCHAR(64)  DEFAULT NULL COMMENT '用户ID（可选）',
    title      VARCHAR(255) DEFAULT NULL COMMENT '会话标题（可选）',
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='聊天会话表';

-- 消息表
CREATE TABLE IF NOT EXISTS chat_messages
(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id   VARCHAR(64)          NOT NULL COMMENT '会话ID',
    message_type ENUM ('human', 'ai') NOT NULL COMMENT '消息类型',
    content      TEXT                 NOT NULL COMMENT '消息内容',
    metadata     JSON      DEFAULT NULL COMMENT '元数据(文档信息等)',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_session_id (session_id),
    INDEX idx_message_type (message_type),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='聊天消息表';