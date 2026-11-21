CREATE TABLE IF NOT EXISTS python_model_type_lock (
  model_type VARCHAR(20) PRIMARY KEY
);
INSERT IGNORE INTO python_model_type_lock VALUES ('CHAT'), ('EMBEDDING');

CREATE TABLE IF NOT EXISTS agent_run (
  thread_id CHAR(36) PRIMARY KEY,
  agent_id INT NOT NULL,
  conversation_id VARCHAR(36) NOT NULL,
  request JSON NOT NULL,
  status VARCHAR(32) NOT NULL,
  plan JSON,
  plan_revision INT NOT NULL DEFAULT 0,
  checkpoint_id VARCHAR(128),
  version BIGINT NOT NULL DEFAULT 0,
  owner VARCHAR(128),
  config_snapshot JSON,
  config_fingerprint CHAR(64),
  result_version INT,
  error TEXT,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at DATETIME(6),
  INDEX idx_run_session (agent_id, conversation_id, created_at, thread_id)
);
CREATE TABLE IF NOT EXISTS agent_session_runtime (
  agent_id INT NOT NULL,
  conversation_id VARCHAR(36) NOT NULL,
  active_thread_id CHAR(36),
  lifecycle VARCHAR(20) NOT NULL DEFAULT 'OPEN',
  version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (agent_id, conversation_id),
  UNIQUE KEY uk_active_thread (active_thread_id)
);
CREATE TABLE IF NOT EXISTS agent_conversation_turn (
  agent_id INT NOT NULL,
  conversation_id VARCHAR(36) NOT NULL,
  thread_id CHAR(36) NOT NULL,
  question MEDIUMTEXT NOT NULL,
  plan JSON,
  plan_revision INT NOT NULL DEFAULT 0,
  memory_status VARCHAR(20) NOT NULL DEFAULT 'STAGED',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (agent_id, conversation_id, thread_id)
);
CREATE TABLE IF NOT EXISTS graph_effect (
  thread_id CHAR(36) NOT NULL,
  effect_key VARCHAR(191) NOT NULL,
  status VARCHAR(20) NOT NULL,
  result_ref JSON,
  query_id VARCHAR(255),
  owner VARCHAR(128),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (thread_id, effect_key)
);
CREATE TABLE IF NOT EXISTS agent_run_result (
  thread_id CHAR(36) PRIMARY KEY,
  result_version INT NOT NULL,
  outcome VARCHAR(32) NOT NULL,
  final_answer MEDIUMTEXT,
  artifacts JSON,
  messages JSON NOT NULL,
  reason TEXT,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS agent_lifecycle (
  agent_id INT PRIMARY KEY,
  lifecycle VARCHAR(20) NOT NULL DEFAULT 'OPEN',
  version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS agent_cleanup_job (
  id CHAR(36) PRIMARY KEY,
  agent_id INT NOT NULL,
  conversation_id VARCHAR(36),
  target_ref JSON NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  attempts INT NOT NULL DEFAULT 0,
  error TEXT,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS agent_operation_audit (
  operation_id CHAR(36) PRIMARY KEY,
  thread_id CHAR(36),
  expected_version BIGINT,
  operator VARCHAR(255) NOT NULL,
  reason TEXT NOT NULL,
  evidence JSON,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);
CREATE TABLE IF NOT EXISTS chat_message_key (
  session_id VARCHAR(36) NOT NULL,
  message_key VARCHAR(191) NOT NULL,
  message_id BIGINT NOT NULL,
  PRIMARY KEY (session_id, message_key),
  FOREIGN KEY (message_id) REFERENCES chat_message(id) ON DELETE CASCADE
);
