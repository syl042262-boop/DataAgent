-- Content and recall policy have independent revisions; local index publication uses content revision.
CREATE TABLE IF NOT EXISTS python_knowledge_state (
 kind VARCHAR(20) NOT NULL,
 record_id INT NOT NULL,
 agent_id INT NOT NULL,
 revision BIGINT NOT NULL DEFAULT 1,
 index_revision BIGINT DEFAULT NULL,
 embedding_space CHAR(64) DEFAULT NULL,
 embedding_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
 error_msg VARCHAR(255) DEFAULT NULL,
 PRIMARY KEY(kind, record_id),
 INDEX idx_knowledge_owner(agent_id),
 FOREIGN KEY(agent_id) REFERENCES agent(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS python_recall_config (
 agent_id INT PRIMARY KEY,
 revision BIGINT NOT NULL DEFAULT 1,
 top_k INT NOT NULL DEFAULT 8,
 similarity_threshold DOUBLE NOT NULL DEFAULT 0.0,
 FOREIGN KEY(agent_id) REFERENCES agent(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS python_local_file (
 path VARCHAR(255) PRIMARY KEY,
 original_name VARCHAR(255) NOT NULL,
 mime_type VARCHAR(100) NOT NULL,
 size_bytes BIGINT NOT NULL,
 created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
