-- 使用数据库
USE tk_rag;

-- 创建新表
CREATE TABLE IF NOT EXISTS segment_info_new
(
    cid             BIGINT AUTO_INCREMENT PRIMARY KEY,                                  -- 分块记录的唯一ID
    seg_id          VARCHAR(64) NOT NULL,                                            -- 分块的唯一ID
    seg_parent_id   VARCHAR(64),                                                     -- 分块的父表 seg_id
    seg_content     LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,        -- 分块的元内容，表格 html，图片标题（暂时，增加标识），文本内容
    seg_image_path  VARCHAR(255),                                                   -- 分块对应的图片路径
    seg_caption     LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,        -- 分块的标题，表格标题、图片标题
    seg_footnote    LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,        -- 分块的脚注，表格脚注、图片脚注
    seg_len         VARCHAR(10),                                                    -- 分块字符长度
    seg_type        VARCHAR(20),                                                    -- 分块源元素类型
    seg_page_idx    VARCHAR(10),                                                    -- 分块所在页码
    doc_id          VARCHAR(64) NOT NULL,                                            -- 与文件关联的文档ID
    is_soft_deleted BOOL      DEFAULT FALSE,                                          -- 是否软删除，默认为空
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                             -- 创建时间， 同 Python 中的 current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 更新时间
    INDEX idx_doc_id (doc_id),                                                       -- 针对 doc_id 的索引
    INDEX idx_seg_id (seg_id)                                                        -- 为 seg_id 增加索引以优化查询
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 迁移数据
INSERT INTO segment_info_new 
SELECT 
    cid,
    seg_id,
    seg_parent_id,
    CAST(seg_content AS CHAR CHARACTER SET utf8mb4),
    seg_image_path,
    CAST(seg_caption AS CHAR CHARACTER SET utf8mb4),
    CAST(seg_footnote AS CHAR CHARACTER SET utf8mb4),
    seg_len,
    seg_type,
    seg_page_idx,
    doc_id,
    COALESCE(is_soft_deleted, FALSE),
    created_at,
    updated_at
FROM segment_info;

-- 验证数据迁移
SELECT COUNT(*) as old_count FROM segment_info;
SELECT COUNT(*) as new_count FROM segment_info_new;

-- 重命名表
RENAME TABLE segment_info TO segment_info_old,
             segment_info_new TO segment_info;

-- 最终验证
SELECT COUNT(*) as final_count FROM segment_info;

-- 如果一切正常，可以删除旧表
-- DROP TABLE segment_info_old; 