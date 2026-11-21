CREATE TABLE IF NOT EXISTS python_datasource_options (
  datasource_id INT PRIMARY KEY,
  schema_name VARCHAR(255),
  FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS python_agent_schema (
  agent_datasource_id INT PRIMARY KEY,
  schema_snapshot JSON NOT NULL,
  initialized_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  FOREIGN KEY (agent_datasource_id) REFERENCES agent_datasource(id) ON DELETE CASCADE
);
