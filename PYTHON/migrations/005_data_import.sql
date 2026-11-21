-- Business import evidence only; Java memory and checkpoints are never copied.
CREATE TABLE IF NOT EXISTS python_data_import (
 import_id CHAR(64) PRIMARY KEY,
 report JSON NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
