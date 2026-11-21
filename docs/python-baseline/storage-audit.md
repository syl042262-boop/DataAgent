# 业务表、实体及 Mapper 对账

不区分建表关键字大小写：MySQL 13 张、H2 13 张，表名集合一致。`001_business.sql` 保留 MySQL DDL 的所有列、索引、外键、默认值和 ON DELETE/UPDATE；H2 仅作对照，Python 不运行 H2。以下每表并列两套完整 DDL 和实际 Mapper，实体字段在 schemas.md。Mapper 不存在独立类时保留实际匹配文件。

原 data.sql 为演示 Agent/知识/语义数据，不含可用模型或用户凭据，默认不复制，以免假配置被误认为就绪；空库必要初始数据只有 migration 版本和模型类型互斥行（002）。存量业务复制、密文验证、ID/文件重写由 Ticket 09 执行，不运行破坏性覆盖。


## agent

实体 `Agent`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS agent (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL COMMENT '智能体名称',
    description TEXT COMMENT '智能体描述',
    avatar TEXT COMMENT '头像URL',
    status VARCHAR(50) DEFAULT 'draft' COMMENT '状态：draft-待发布，published-已发布，offline-已下线',
    api_key VARCHAR(255) DEFAULT NULL COMMENT '访问 API Key，格式 sk-xxx',
    api_key_enabled TINYINT DEFAULT 0 COMMENT 'API Key 是否启用：0-禁用，1-启用',
    prompt TEXT COMMENT '自定义Prompt配置',
    category VARCHAR(100) COMMENT '分类',
    admin_id BIGINT COMMENT '管理员ID',
    tags TEXT COMMENT '标签，逗号分隔',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_name (name),
    INDEX idx_status (status),
    INDEX idx_category (category),
    INDEX idx_admin_id (admin_id)
    ) ENGINE = InnoDB COMMENT = '智能体表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS agent (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL COMMENT '智能体名称',
    description TEXT COMMENT '智能体描述',
    avatar TEXT COMMENT '头像URL',
    status VARCHAR(50) DEFAULT 'draft' COMMENT '状态：draft-待发布，published-已发布，offline-已下线',
    api_key VARCHAR(255) DEFAULT NULL COMMENT '访问 API Key，格式 sk-xxx',
    api_key_enabled TINYINT DEFAULT 0 COMMENT 'API Key 是否启用：0-禁用，1-启用',
    prompt TEXT COMMENT '自定义Prompt配置',
    category VARCHAR(100) COMMENT '分类',
    admin_id BIGINT COMMENT '管理员ID',
    tags TEXT COMMENT '标签，逗号分隔',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_agent_name (name),
    INDEX idx_agent_status (status),
    INDEX idx_agent_category (category),
    INDEX idx_agent_admin_id (admin_id)
    ) ENGINE = InnoDB COMMENT = '智能体表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentDatasourceMapper.java`

```java
@Mapper
public interface AgentDatasourceMapper {


	@Select("SELECT ad.*, d.name, d.type, d.host, d.port, d.database_name, "
			+ "d.connection_url, d.username, d.password, d.status, d.test_status, d.description "
			+ "FROM agent_datasource ad " + "LEFT JOIN datasource d ON ad.datasource_id = d.id "
			+ "WHERE ad.agent_id = #{agentId} " + "ORDER BY ad.create_time DESC")
	List<AgentDatasource> selectByAgentIdWithDatasource(@Param("agentId") Long agentId);


	@Select("SELECT * FROM agent_datasource WHERE agent_id = #{agentId} ORDER BY create_time DESC")
	List<AgentDatasource> selectByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT datasource_id FROM agent_datasource WHERE agent_id = #{agentId} AND is_active = 1")
	Integer selectActiveDatasourceIdByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT * FROM agent_datasource WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	AgentDatasource selectByAgentIdAndDatasourceId(@Param("agentId") Long agentId,
			@Param("datasourceId") Integer datasourceId);


	@Update("UPDATE agent_datasource SET is_active = 0 WHERE agent_id = #{agentId}")
	int disableAllByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT COUNT(*) FROM agent_datasource WHERE agent_id = #{agentId} AND is_active = 1 AND datasource_id != #{excludeDatasourceId}")
	int countActiveByAgentIdExcluding(@Param("agentId") Long agentId,
			@Param("excludeDatasourceId") Integer excludeDatasourceId);

	@Delete("DELETE FROM agent_datasource WHERE datasource_id = #{datasourceId}")
	int deleteAllByDatasourceId(@Param("datasourceId") Integer datasourceId);

	@Insert("INSERT INTO agent_datasource (agent_id, datasource_id, is_active) VALUES (#{agentId}, #{datasourceId}, 1)")
	int createNewRelationEnabled(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId);

	@Update("UPDATE agent_datasource SET is_active = #{isActive} WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	int updateRelation(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId,
			@Param("isActive") Integer isActive);

	default int enableRelation(Long agentId, Integer datasourceId) {
		return updateRelation(agentId, datasourceId, 1);
	}

	@Delete("DELETE FROM agent_datasource WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	int removeRelation(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId);

}
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentDatasourceTablesMapper.java`

```java
@Mapper
public interface AgentDatasourceTablesMapper {

	// 选择当前智能体数据源所有表
	@Select("select table_name from agent_datasource_tables where agent_datasource_id = #{agentDatasourceId}")
	List<String> getAgentDatasourceTables(@Param("agentDatasourceId") int agentDatasourceId);


	@Select("""
			SELECT DISTINCT adt.table_name
			FROM agent_datasource_tables adt
			JOIN agent_datasource ad ON ad.id = adt.agent_datasource_id
			WHERE ad.datasource_id = #{datasourceId}
			ORDER BY adt.table_name
			""")
	List<String> getSelectedTablesByDatasourceId(@Param("datasourceId") int datasourceId);

	// 删除当前列表中不存在的表
	@Delete("<script>" + "DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}"
			+ "<if test='tables != null and tables.size() > 0'>" + " AND table_name NOT IN ("
			+ "<foreach collection='tables' item='table' separator=','>#{table}</foreach>" + ")" + "</if>"
			+ "</script>")
	int removeExpireTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 删除当前智能体数据源所有表
	@Delete("DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}")
	int removeAllTables(@Param("agentDatasourceId") int agentDatasourceId);

	// 插入用户选择的列表
	@Insert("<script>" + "INSERT IGNORE INTO agent_datasource_tables (agent_datasource_id, table_name) VALUES "
			+ "<if test='tables != null and tables.size() > 0'>"
			+ "<foreach collection='tables' item='table' separator=','>" + "(#{agentDatasourceId}, #{table})"
			+ "</foreach>" + "</if>" + "</script>")
	int insertNewTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 更新用户的选择（tables不能为空）
	default int updateAgentDatasourceTables(int agentDatasourceId, List<String> tables) {
		if (tables.isEmpty()) {
			throw new IllegalArgumentException("tables cannot be empty");
		}
		int deleteCount = removeExpireTables(agentDatasourceId, tables);
		int insertCount = insertNewTables(agentDatasourceId, tables);
		return deleteCount + insertCount;
	}

}
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentKnowledgeMapper.java`

```java
@Mapper
public interface AgentKnowledgeMapper {

	@Select("""
			SELECT * FROM agent_knowledge WHERE id = #{id} AND is_deleted = 0
			""")
	AgentKnowledge selectById(@Param("id") Integer id);

	@Select("""
			    SELECT * FROM agent_knowledge WHERE id = #{id}
			""")
	AgentKnowledge selectByIdIncludeDeleted(@Param("id") Integer id);

	@Select("""
			SELECT * FROM agent_knowledge WHERE agent_id = #{agentId} ORDER BY id
			""")
	List<AgentKnowledge> selectByAgentIdIncludeDeleted(@Param("agentId") Integer agentId);

	@Insert("""

			INSERT INTO agent_knowledge (agent_id, title, content, type, question, is_recall, embedding_status, source_filename, file_path, file_size, file_type, splitter_type, is_deleted, is_resource_cleaned, created_time, updated_time)
			VALUES (#{agentId}, #{title}, #{content}, #{type}, #{question}, #{isRecall}, #{embeddingStatus}, #{sourceFilename}, #{filePath}, #{fileSize}, #{fileType}, #{splitterType}, #{isDeleted}, #{isResourceCleaned}, #{createdTime}, #{updatedTime})

			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(AgentKnowledge knowledge);

	@Update("""
			<script>
			UPDATE agent_knowledge
			<set>
				<if test="title != null">title = #{title},</if>
				<if test="content != null">content = #{content},</if>
				<if test="type != null">type = #{type},</if>
				<if test="question != null">question = #{question},</if>
				<if test="isRecall != null">is_recall = #{isRecall},</if>
				<if test="embeddingStatus != null">embedding_status = #{embeddingStatus},</if>
				<if test="errorMsg != null">error_msg = #{errorMsg},</if>
				<if test="sourceFilename != null">source_filename = #{sourceFilename},</if>
				<if test="filePath != null">file_path = #{filePath},</if>
				<if test="fileSize != null">file_size = #{fileSize},</if>
				<if test="fileType != null">file_type = #{fileType},</if>
				<if test="splitterType != null">splitter_type = #{splitterType},</if>
				<if test="isDeleted != null">is_deleted = #{isDeleted},</if>
				<if test="isResourceCleaned != null">is_resource_cleaned = #{isResourceCleaned},</if>
				updated_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int update(AgentKnowledge knowledge);

	@Select("""
			<script>
			SELECT * FROM agent_knowledge
			WHERE agent_id = #{queryDTO.agentId}
			<if test="queryDTO.title != null and queryDTO.title != ''">
				AND title LIKE CONCAT('%', #{queryDTO.title}, '%')
			</if>
			<if test="queryDTO.type != null and queryDTO.type != ''">
				AND type = #{queryDTO.type}
			</if>
			<if test="queryDTO.embeddingStatus != null and queryDTO.embeddingStatus != ''">
				AND embedding_status = #{queryDTO.embeddingStatus}
			</if>
			AND is_deleted = 0
			LIMIT #{offset}, #{queryDTO.pageSize}
			</script>
			""")
	List<AgentKnowledge> selectByConditionsWithPage(@Param("queryDTO") AgentKnowledgeQueryDTO queryDTO,
			@Param("offset") Integer offset);

	@Select("""
			<script>
			SELECT COUNT(*) FROM agent_knowledge
			WHERE agent_id = #{queryDTO.agentId}
			<if test="queryDTO.title != null and queryDTO.title != ''">
				AND title LIKE CONCAT('%', #{queryDTO.title}, '%')
			</if>
			<if test="queryDTO.type != null and queryDTO.type != ''">
				AND type = #{queryDTO.type}
			</if>
			<if test="queryDTO.embeddingStatus != null and queryDTO.embeddingStatus != ''">
				AND embedding_status = #{queryDTO.embeddingStatus}
			</if>
			AND is_deleted = 0
			</script>
			""")
	Long countByConditions(@Param("queryDTO") AgentKnowledgeQueryDTO queryDTO);

	@Select("""
			SELECT id FROM agent_knowledge WHERE agent_id = #{agentId} AND is_recall = 1 AND is_deleted = 0
			""")
	List<Integer> selectRecalledKnowledgeIds(@Param("agentId") Integer agentId);


	@Select("""
			SELECT * FROM agent_knowledge
			WHERE embedding_status = 'PENDING'
			  AND is_recall = 1
			  AND is_deleted = 0
			ORDER BY id
			""")
	List<AgentKnowledge> selectPendingAndRecalled();

	@Update("""
			UPDATE agent_knowledge
			SET embedding_status = 'PENDING', error_msg = 'Recovered stale PROCESSING job', updated_time = NOW()
			WHERE embedding_status = 'PROCESSING'
			  AND is_deleted = 0
			  AND updated_time < #{beforeTime}
			""")
	int resetStaleProcessing(@Param("beforeTime") LocalDateTime beforeTime);


	@Select("""
			    SELECT * FROM agent_knowledge
			    WHERE is_deleted = 1
			      AND is_resource_cleaned = 0
			      AND updated_time < #{beforeTime}
			    LIMIT #{limit}
			""")
	List<AgentKnowledge> selectDirtyRecords(@Param("beforeTime") LocalDateTime beforeTime, @Param("limit") int limit);

	@Delete("""
			DELETE FROM agent_knowledge WHERE agent_id = #{agentId}
			""")
	int deleteByAgentId(@Param("agentId") Integer agentId);

}
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentMapper.java`

```java
@Mapper
public interface AgentMapper {

	@Select("""
			SELECT * FROM agent ORDER BY create_time DESC
			""")
	List<Agent> findAll();

	@Select("""
			SELECT * FROM agent WHERE id = #{id}
			""")
	Agent findById(Long id);

	@Select("""
			SELECT * FROM agent WHERE status = #{status} ORDER BY create_time DESC
			""")
	List<Agent> findByStatus(String status);

	@Select("""
			SELECT * FROM agent
			WHERE (name LIKE CONCAT('%', #{keyword}, '%')
				   OR description LIKE CONCAT('%', #{keyword}, '%')
				   OR tags LIKE CONCAT('%', #{keyword}, '%'))
			ORDER BY create_time DESC
			""")
	List<Agent> searchByKeyword(@Param("keyword") String keyword);

	@Select("""
			<script>
				SELECT * FROM agent
				<where>
					<if test='status != null and status != ""'>
						AND status = #{status}
					</if>
					<if test='keyword != null and keyword != ""'>
						AND (name LIKE CONCAT('%', #{keyword}, '%')
							 OR description LIKE CONCAT('%', #{keyword}, '%')
							 OR tags LIKE CONCAT('%', #{keyword}, '%'))
					</if>
				</where>
				ORDER BY create_time DESC
			</script>
			""")
	List<Agent> findByConditions(@Param("status") String status, @Param("keyword") String keyword);

	@Insert("""
			INSERT INTO agent (name, description, avatar, status, api_key, api_key_enabled, prompt, category, admin_id, tags, create_time, update_time)
			VALUES (#{name}, #{description}, #{avatar}, #{status}, #{apiKey}, #{apiKeyEnabled}, #{prompt}, #{category}, #{adminId}, #{tags}, #{createTime}, #{updateTime})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(Agent agent);

	@Update("""
			<script>
			          UPDATE agent
			          <trim prefix="SET" suffixOverrides=",">
			            <if test='name != null'>name = #{name},</if>
			            <if test='description != null'>description = #{description},</if>
			            <if test='avatar != null'>avatar = #{avatar},</if>
			            <if test='status != null'>status = #{status},</if>
			            <if test='apiKey != null'>api_key = #{apiKey},</if>
			            <if test='apiKeyEnabled != null'>api_key_enabled = #{apiKeyEnabled},</if>
			            <if test='prompt != null'>prompt = #{prompt},</if>
			            <if test='category != null'>category = #{category},</if>
			            <if test='adminId != null'>admin_id = #{adminId},</if>
			            <if test='tags != null'>tags = #{tags},</if>
			            update_time = NOW()
			          </trim>
			          WHERE id = #{id}
			</script>
			""")
	int updateById(Agent agent);

	@Update("""
			UPDATE agent
			SET api_key = #{apiKey}, api_key_enabled = #{apiKeyEnabled}, update_time = NOW()
			WHERE id = #{id}
			""")
	int updateApiKey(@Param("id") Long id, @Param("apiKey") String apiKey,
			@Param("apiKeyEnabled") Integer apiKeyEnabled);

	@Update("""
			UPDATE agent
			SET api_key_enabled = #{enabled}, update_time = NOW()
			WHERE id = #{id}
			""")
	int toggleApiKey(@Param("id") Long id, @Param("enabled") Integer enabled);

	@Delete("""
			DELETE FROM agent WHERE id = #{id}
			""")
	int deleteById(Long id);

}
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentPresetQuestionMapper.java`

```java
@Mapper
public interface AgentPresetQuestionMapper {

	@Select("""
			SELECT * FROM agent_preset_question
			         WHERE agent_id = #{agentId} AND is_active = 1
			ORDER BY sort_order ASC, id ASC
			""")
	List<AgentPresetQuestion> selectByAgentId(@Param("agentId") Long agentId);

	@Select("""
			SELECT * FROM agent_preset_question
			         WHERE agent_id = #{agentId}
			ORDER BY sort_order ASC, id ASC
			""")
	List<AgentPresetQuestion> selectAllByAgentId(@Param("agentId") Long agentId);


	@Select("""
			SELECT * FROM agent_preset_question WHERE id = #{id}
			""")
	AgentPresetQuestion selectById(@Param("id") Long id);

	@Insert("""
			INSERT INTO agent_preset_question (agent_id, question, sort_order, is_active, create_time, update_time)
			VALUES (#{agentId}, #{question}, #{sortOrder}, #{isActive}, NOW(), NOW())
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(AgentPresetQuestion question);

	@Update("""
			<script>
			UPDATE agent_preset_question
			<set>
				<if test="question != null">question = #{question},</if>
				<if test="sortOrder != null">sort_order = #{sortOrder},</if>
				<if test="isActive != null">is_active = #{isActive},</if>
				update_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int update(AgentPresetQuestion question);

	@Delete("""
			DELETE FROM agent_preset_question WHERE id = #{id}
			""")
	int deleteById(@Param("id") Long id);

	@Delete("""
			DELETE FROM agent_preset_question WHERE agent_id = #{agentId}
			""")
	int deleteByAgentId(@Param("agentId") Long agentId);

}
```


## business_knowledge

实体 `BusinessKnowledge`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS business_knowledge (
  id INT NOT NULL AUTO_INCREMENT,
  business_term VARCHAR(255) NOT NULL COMMENT '业务名词',
  description TEXT COMMENT '描述',
  synonyms TEXT COMMENT '同义词，逗号分隔',
  is_recall INT DEFAULT 1 COMMENT '是否召回：0-不召回，1-召回',
  agent_id INT NOT NULL COMMENT '关联的智能体ID',
  created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  embedding_status VARCHAR(20) DEFAULT NULL COMMENT '向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败',
  error_msg VARCHAR(255) DEFAULT NULL COMMENT '操作失败的错误信息',
  is_deleted INT DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (id),
  INDEX idx_business_term (business_term),
  INDEX idx_agent_id (agent_id),
  INDEX idx_is_recall (is_recall),
  INDEX idx_embedding_status (embedding_status),
  INDEX idx_is_deleted (is_deleted),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '业务知识表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS business_knowledge (
  id INT NOT NULL AUTO_INCREMENT,
  business_term VARCHAR(255) NOT NULL COMMENT '业务名词',
  description TEXT COMMENT '描述',
  synonyms TEXT COMMENT '同义词，逗号分隔',
  is_recall INT DEFAULT 1 COMMENT '是否召回：0-不召回，1-召回',
  agent_id INT NOT NULL COMMENT '关联的智能体ID',
  created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  embedding_status VARCHAR(20) DEFAULT NULL COMMENT '向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败',
  error_msg VARCHAR(255) DEFAULT NULL COMMENT '操作失败的错误信息',
  is_deleted INT DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (id),
  INDEX idx_business_knowledge_business_term (business_term),
  INDEX idx_business_knowledge_agent_id (agent_id),
  INDEX idx_business_knowledge_is_recall (is_recall),
  INDEX idx_business_knowledge_embedding_status (embedding_status),
  INDEX idx_business_knowledge_is_deleted (is_deleted),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '业务知识表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/BusinessKnowledgeMapper.java`

```java
@Mapper
public interface BusinessKnowledgeMapper {


	@Select("""
			SELECT * FROM business_knowledge
			WHERE agent_id = #{agentId} AND is_deleted = 0
			ORDER BY created_time DESC
			""")
	List<BusinessKnowledge> selectByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT * FROM business_knowledge WHERE is_deleted = 0 ORDER BY created_time DESC")
	List<BusinessKnowledge> selectAll();


	@Select("""
			SELECT * FROM business_knowledge
			WHERE agent_id = #{agentId} AND is_deleted = 0
			  AND (business_term LIKE CONCAT('%', #{keyword}, '%')
			    OR description LIKE CONCAT('%', #{keyword}, '%')
			    OR synonyms LIKE CONCAT('%', #{keyword}, '%'))
			ORDER BY created_time DESC
			""")
	List<BusinessKnowledge> searchInAgent(@Param("agentId") Long agentId, @Param("keyword") String keyword);

	@Insert("""
			INSERT INTO business_knowledge (business_term, description, synonyms, is_recall, agent_id, created_time, updated_time, embedding_status, is_deleted)
			VALUES (#{businessTerm}, #{description}, #{synonyms}, #{isRecall}, #{agentId}, NOW(), NOW(), #{embeddingStatus}, #{isDeleted})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(BusinessKnowledge knowledge);

	@Update("""
			<script>
			UPDATE business_knowledge
			<set>
				<if test="businessTerm != null">business_term = #{businessTerm},</if>
				<if test="description != null">description = #{description},</if>
				<if test="synonyms != null">synonyms = #{synonyms},</if>
				<if test="isRecall != null">is_recall = #{isRecall},</if>
				<if test="agentId != null">agent_id = #{agentId},</if>
				<if test="embeddingStatus != null">embedding_status = #{embeddingStatus},</if>
				<if test="errorMsg != null">error_msg = #{errorMsg},</if>
				<if test="isDeleted != null">is_deleted = #{isDeleted},</if>
				updated_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int updateById(BusinessKnowledge knowledge);

	@Delete("""
			DELETE FROM business_knowledge
			WHERE id = #{id}
			""")
	int deleteById(@Param("id") Long id);

	@Select("""
			SELECT * FROM business_knowledge
			WHERE id = #{id} AND is_deleted = 0
			""")
	BusinessKnowledge selectById(Long id);

	@Select("""
			SELECT id FROM business_knowledge
			WHERE agent_id = #{agentId} AND is_recall = 1 AND is_deleted = 0
			""")
	List<Long> selectRecalledKnowledgeIds(@Param("agentId") Long agentId);

	@Update("""
			UPDATE business_knowledge
			SET embedding_status = 'PENDING', error_msg = 'Recovered stale PROCESSING job', updated_time = NOW()
			WHERE embedding_status = 'PROCESSING'
			  AND is_deleted = 0
			  AND updated_time < #{beforeTime}
			""")
	int resetStaleProcessing(@Param("beforeTime") LocalDateTime beforeTime);

	@Update("""
			UPDATE business_knowledge
			SET is_deleted = #{isDeleted}, updated_time = NOW()
			WHERE id = #{id}
			""")
	int logicalDelete(@Param("id") Long id, @Param("isDeleted") Integer isDeleted);

}
```


## semantic_model

实体 `SemanticModel`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS `semantic_model` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agent_id` int(11) NOT NULL COMMENT '关联的智能体ID',
  `datasource_id` int(11) NOT NULL COMMENT '关联的数据源ID',
  `table_name` varchar(255) COLLATE utf8mb4_bin NOT NULL COMMENT '关联的表名',
  `column_name` varchar(255) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '数据库中的物理字段名 (例如: csat_score)',
  `business_name` varchar(255) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '业务名/别名 (例如: 客户满意度分数)',
  `synonyms` text COLLATE utf8mb4_bin COMMENT '业务名的同义词 (例如: 满意度,客户评分)',
  `business_description` text COLLATE utf8mb4_bin COMMENT '业务描述 (用于向LLM解释字段的业务含义)',
  `column_comment` varchar(255) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '数据库中的物理字段的原始注释 ',
  `data_type` varchar(255) COLLATE utf8mb4_bin NOT NULL DEFAULT '' COMMENT '物理数据类型 (例如: int, varchar(20))',
  `status` tinyint(4) NOT NULL DEFAULT '1' COMMENT '0 停用 1 启用',
  `created_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_agent_id` (`agent_id`) USING BTREE,
  KEY `idx_field_name` (`business_name`) USING BTREE,
  KEY `idx_status` (`status`) USING BTREE,
  CONSTRAINT `fk_semantic_model_agent` FOREIGN KEY (`agent_id`) REFERENCES `agent` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='语义模型表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS semantic_model (
  id INT NOT NULL AUTO_INCREMENT,
  agent_id INT NOT NULL COMMENT '关联的智能体ID',
  datasource_id INT NOT NULL COMMENT '关联的数据源ID',
  table_name VARCHAR(255) NOT NULL COMMENT '关联的表名',
  column_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '数据库中的物理字段名 (例如: csat_score)',
  business_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '业务名/别名 (例如: 客户满意度分数)',
  synonyms TEXT COMMENT '业务名的同义词 (例如: 满意度,客户评分)',
  business_description TEXT COMMENT '业务描述 (用于向LLM解释字段的业务含义)',
  column_comment VARCHAR(255) DEFAULT NULL COMMENT '数据库中的物理字段的原始注释 ',
  data_type VARCHAR(255) NOT NULL DEFAULT '' COMMENT '物理数据类型 (例如: int, varchar(20))',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0 停用 1 启用',
  created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_semantic_model_agent_id (agent_id),
  INDEX idx_semantic_model_business_name (business_name),
  INDEX idx_semantic_model_status (status),
  CONSTRAINT fk_semantic_model_agent FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '语义模型表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/SemanticModelMapper.java`

```java
@Mapper
public interface SemanticModelMapper {

	@Select("SELECT * FROM semantic_model ORDER BY created_time DESC")
	List<SemanticModel> selectAll();


	@Select("""
			SELECT * FROM semantic_model
			WHERE agent_id = #{agentId}
			ORDER BY created_time DESC
			""")
	List<SemanticModel> selectByAgentId(@Param("agentId") Long agentId);


	@Select("""
			SELECT * FROM semantic_model
			WHERE id = #{id}
			""")
	SemanticModel selectById(@Param("id") Long id);


	@Select("""
			SELECT * FROM semantic_model
			WHERE column_name LIKE CONCAT('%', #{keyword}, '%')
			   OR business_name LIKE CONCAT('%', #{keyword}, '%')
			   OR business_description LIKE CONCAT('%', #{keyword}, '%')
			   OR synonyms LIKE CONCAT('%', #{keyword}, '%')
			ORDER BY created_time DESC
			""")
	List<SemanticModel> searchByKeyword(@Param("keyword") String keyword);


	@Update("""
			UPDATE semantic_model
			SET status = 1
			WHERE id = #{id}
			""")
	int enableById(@Param("id") Long id);


	@Update("""
			UPDATE semantic_model
			SET status = 0
			WHERE id = #{id}
			""")
	int disableById(@Param("id") Long id);


	@Select("""
			SELECT * FROM semantic_model
			WHERE agent_id = #{agentId}
			  AND status != 0
			ORDER BY created_time DESC
			""")
	List<SemanticModel> selectEnabledByAgentId(@Param("agentId") Long agentId);

	@Insert("""
			INSERT INTO semantic_model
			(agent_id, datasource_id, table_name, column_name, business_name, synonyms, business_description, column_comment, data_type, created_time, updated_time, status)
			VALUES
			(#{agentId}, #{datasourceId}, #{tableName}, #{columnName}, #{businessName}, #{synonyms}, #{businessDescription}, #{columnComment}, #{dataType}, NOW(), NOW(), #{status})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(SemanticModel model);

	@Update("""
			<script>
			UPDATE semantic_model
			<set>
			    <if test="agentId != null">agent_id = #{agentId},</if>
			    <if test="datasourceId != null">datasource_id = #{datasourceId},</if>
			    <if test="tableName != null">table_name = #{tableName},</if>
				<if test="columnName != null">column_name = #{columnName},</if>
				<if test="businessName != null">business_name = #{businessName},</if>
				<if test="synonyms != null">synonyms = #{synonyms},</if>
				<if test="businessDescription != null">business_description = #{businessDescription},</if>
				<if test="columnComment != null">column_comment = #{columnComment},</if>
				<if test="dataType != null">data_type = #{dataType},</if>
				<if test="status != null">status = #{status},</if>
				updated_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int updateById(SemanticModel model);

	@Delete("""
			DELETE FROM semantic_model
			WHERE id = #{id}
			""")
	int deleteById(@Param("id") Long id);


	@Select("""
			<script>
			SELECT * FROM semantic_model
			WHERE datasource_id = #{datasourceId}
			  AND status = 1
			  AND table_name IN
			  <foreach item='tableName' index='index' collection='tableNames' open='(' separator=',' close=')'>
			    #{tableName}
			  </foreach>
			ORDER BY created_time DESC
			</script>
			""")
	List<SemanticModel> selectByDatasourceIdAndTableNames(@Param("datasourceId") Integer datasourceId,
			@Param("tableNames") List<String> tableNames);


	@Select("""
			SELECT * FROM semantic_model
			WHERE agent_id = #{agentId}
			  AND table_name = #{tableName}
			  AND column_name = #{columnName}
			LIMIT 1
			""")
	SemanticModel selectByAgentIdAndTableNameAndColumnName(@Param("agentId") Integer agentId,
			@Param("tableName") String tableName, @Param("columnName") String columnName);

}
```


## agent_knowledge

实体 `AgentKnowledge`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS `agent_knowledge` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID, 用于内部关联',
  `agent_id` int(11) NOT NULL COMMENT '关联的智能体ID',
  `title` varchar(255) COLLATE utf8mb4_bin NOT NULL COMMENT '知识的标题 (用户定义, 用于在UI上展示和识别)',
  `type` varchar(50) COLLATE utf8mb4_bin NOT NULL COMMENT '知识类型: DOCUMENT-文档, QA-问答, FAQ-常见问题',
  `question` text COLLATE utf8mb4_bin COMMENT '问题 (仅当type为QA或FAQ时使用)',
  `content` mediumtext COLLATE utf8mb4_bin COMMENT '知识内容 (对于QA/FAQ是答案; 对于DOCUMENT, 此字段通常为空)',
  `is_recall` int(11) DEFAULT 1 COMMENT '业务状态: 1=召回, 0=非召回',
  `embedding_status` varchar(20) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败',
  `error_msg` varchar(255) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '操作失败的错误信息',
  `source_filename` varchar(500) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '上传时的原始文件名',
  `file_path` varchar(500) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '文件在服务器上的物理存储路径',
  `file_size` bigint(20) DEFAULT NULL COMMENT '文件大小 (字节)',
  `file_type` varchar(255) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '文件类型（pdf,md,markdown,doc等）',
  `splitter_type` varchar(50) COLLATE utf8mb4_bin DEFAULT 'token' COMMENT '分块策略类型：token, recursive, sentence, semantic',
  `created_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `is_deleted` int(11) DEFAULT 0 COMMENT '逻辑删除字段，0=未删除, 1=已删除',
  `is_resource_cleaned` int(11) DEFAULT 0 COMMENT '0=物理资源（文件和向量）未清理, 1=物理资源已清理',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_agent_id_status` (`agent_id`,`is_recall`) USING BTREE,
  KEY `idx_embedding_status` (`embedding_status`) USING BTREE,
  KEY `idx_is_deleted` (`is_deleted`) USING BTREE,
  CONSTRAINT `fk_agent_knowledge_agent` FOREIGN KEY (`agent_id`) REFERENCES `agent` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='智能体知识源管理表 (支持文档、QA、FAQ)';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS agent_knowledge (
  id INT NOT NULL AUTO_INCREMENT COMMENT '主键ID, 用于内部关联',
  agent_id INT NOT NULL COMMENT '关联的智能体ID',
  title VARCHAR(255) NOT NULL COMMENT '知识的标题 (用户定义, 用于在UI上展示和识别)',
  type VARCHAR(50) NOT NULL COMMENT '知识类型: DOCUMENT-文档, QA-问答, FAQ-常见问题',
  question TEXT COMMENT '问题 (仅当type为QA或FAQ时使用)',
  content MEDIUMTEXT COMMENT '知识内容 (对于QA/FAQ是答案; 对于DOCUMENT, 此字段通常为空)',
  is_recall INT DEFAULT 1 COMMENT '业务状态: 1=召回, 0=非召回',
  embedding_status VARCHAR(20) DEFAULT NULL COMMENT '向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败',
  error_msg VARCHAR(255) DEFAULT NULL COMMENT '操作失败的错误信息',
  source_filename VARCHAR(500) DEFAULT NULL COMMENT '上传时的原始文件名',
  file_path VARCHAR(500) DEFAULT NULL COMMENT '文件在服务器上的物理存储路径',
  file_size BIGINT DEFAULT NULL COMMENT '文件大小 (字节)',
  file_type VARCHAR(255) DEFAULT NULL COMMENT '文件类型（pdf,md,markdown,doc等）',
  splitter_type VARCHAR(50) DEFAULT 'token' COMMENT '分块策略类型：token, recursive, sentence, semantic',
  created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  is_deleted INT DEFAULT 0 COMMENT '逻辑删除字段，0=未删除, 1=已删除',
  is_resource_cleaned INT DEFAULT 0 COMMENT '0=物理资源（文件和向量）未清理, 1=物理资源已清理',
  PRIMARY KEY (id),
  INDEX idx_agent_knowledge_agent_id_status (agent_id, is_recall),
  INDEX idx_agent_knowledge_embedding_status (embedding_status),
  INDEX idx_agent_knowledge_is_deleted (is_deleted),
  CONSTRAINT fk_agent_knowledge_agent FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '智能体知识表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentKnowledgeMapper.java`

```java
@Mapper
public interface AgentKnowledgeMapper {

	@Select("""
			SELECT * FROM agent_knowledge WHERE id = #{id} AND is_deleted = 0
			""")
	AgentKnowledge selectById(@Param("id") Integer id);

	@Select("""
			    SELECT * FROM agent_knowledge WHERE id = #{id}
			""")
	AgentKnowledge selectByIdIncludeDeleted(@Param("id") Integer id);

	@Select("""
			SELECT * FROM agent_knowledge WHERE agent_id = #{agentId} ORDER BY id
			""")
	List<AgentKnowledge> selectByAgentIdIncludeDeleted(@Param("agentId") Integer agentId);

	@Insert("""

			INSERT INTO agent_knowledge (agent_id, title, content, type, question, is_recall, embedding_status, source_filename, file_path, file_size, file_type, splitter_type, is_deleted, is_resource_cleaned, created_time, updated_time)
			VALUES (#{agentId}, #{title}, #{content}, #{type}, #{question}, #{isRecall}, #{embeddingStatus}, #{sourceFilename}, #{filePath}, #{fileSize}, #{fileType}, #{splitterType}, #{isDeleted}, #{isResourceCleaned}, #{createdTime}, #{updatedTime})

			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(AgentKnowledge knowledge);

	@Update("""
			<script>
			UPDATE agent_knowledge
			<set>
				<if test="title != null">title = #{title},</if>
				<if test="content != null">content = #{content},</if>
				<if test="type != null">type = #{type},</if>
				<if test="question != null">question = #{question},</if>
				<if test="isRecall != null">is_recall = #{isRecall},</if>
				<if test="embeddingStatus != null">embedding_status = #{embeddingStatus},</if>
				<if test="errorMsg != null">error_msg = #{errorMsg},</if>
				<if test="sourceFilename != null">source_filename = #{sourceFilename},</if>
				<if test="filePath != null">file_path = #{filePath},</if>
				<if test="fileSize != null">file_size = #{fileSize},</if>
				<if test="fileType != null">file_type = #{fileType},</if>
				<if test="splitterType != null">splitter_type = #{splitterType},</if>
				<if test="isDeleted != null">is_deleted = #{isDeleted},</if>
				<if test="isResourceCleaned != null">is_resource_cleaned = #{isResourceCleaned},</if>
				updated_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int update(AgentKnowledge knowledge);

	@Select("""
			<script>
			SELECT * FROM agent_knowledge
			WHERE agent_id = #{queryDTO.agentId}
			<if test="queryDTO.title != null and queryDTO.title != ''">
				AND title LIKE CONCAT('%', #{queryDTO.title}, '%')
			</if>
			<if test="queryDTO.type != null and queryDTO.type != ''">
				AND type = #{queryDTO.type}
			</if>
			<if test="queryDTO.embeddingStatus != null and queryDTO.embeddingStatus != ''">
				AND embedding_status = #{queryDTO.embeddingStatus}
			</if>
			AND is_deleted = 0
			LIMIT #{offset}, #{queryDTO.pageSize}
			</script>
			""")
	List<AgentKnowledge> selectByConditionsWithPage(@Param("queryDTO") AgentKnowledgeQueryDTO queryDTO,
			@Param("offset") Integer offset);

	@Select("""
			<script>
			SELECT COUNT(*) FROM agent_knowledge
			WHERE agent_id = #{queryDTO.agentId}
			<if test="queryDTO.title != null and queryDTO.title != ''">
				AND title LIKE CONCAT('%', #{queryDTO.title}, '%')
			</if>
			<if test="queryDTO.type != null and queryDTO.type != ''">
				AND type = #{queryDTO.type}
			</if>
			<if test="queryDTO.embeddingStatus != null and queryDTO.embeddingStatus != ''">
				AND embedding_status = #{queryDTO.embeddingStatus}
			</if>
			AND is_deleted = 0
			</script>
			""")
	Long countByConditions(@Param("queryDTO") AgentKnowledgeQueryDTO queryDTO);

	@Select("""
			SELECT id FROM agent_knowledge WHERE agent_id = #{agentId} AND is_recall = 1 AND is_deleted = 0
			""")
	List<Integer> selectRecalledKnowledgeIds(@Param("agentId") Integer agentId);


	@Select("""
			SELECT * FROM agent_knowledge
			WHERE embedding_status = 'PENDING'
			  AND is_recall = 1
			  AND is_deleted = 0
			ORDER BY id
			""")
	List<AgentKnowledge> selectPendingAndRecalled();

	@Update("""
			UPDATE agent_knowledge
			SET embedding_status = 'PENDING', error_msg = 'Recovered stale PROCESSING job', updated_time = NOW()
			WHERE embedding_status = 'PROCESSING'
			  AND is_deleted = 0
			  AND updated_time < #{beforeTime}
			""")
	int resetStaleProcessing(@Param("beforeTime") LocalDateTime beforeTime);


	@Select("""
			    SELECT * FROM agent_knowledge
			    WHERE is_deleted = 1
			      AND is_resource_cleaned = 0
			      AND updated_time < #{beforeTime}
			    LIMIT #{limit}
			""")
	List<AgentKnowledge> selectDirtyRecords(@Param("beforeTime") LocalDateTime beforeTime, @Param("limit") int limit);

	@Delete("""
			DELETE FROM agent_knowledge WHERE agent_id = #{agentId}
			""")
	int deleteByAgentId(@Param("agentId") Integer agentId);

}
```


## datasource

实体 `Datasource`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS datasource (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL COMMENT '数据源名称',
  type VARCHAR(50) NOT NULL COMMENT '数据源类型：mysql, postgresql',
  host VARCHAR(255) NOT NULL COMMENT '主机地址',
  port INT NOT NULL COMMENT '端口号',
  database_name VARCHAR(255) NOT NULL COMMENT '数据库名称',
  username VARCHAR(255) NOT NULL COMMENT '用户名',
  password VARCHAR(255) NOT NULL COMMENT '密码（加密存储）',
  connection_url VARCHAR(1000) COMMENT '完整连接URL',
  status VARCHAR(50) DEFAULT 'inactive' COMMENT '状态：active-启用，inactive-禁用',
  test_status VARCHAR(50) DEFAULT 'unknown' COMMENT '连接测试状态：success-成功，failed-失败，unknown-未知',
  description TEXT COMMENT '描述',
  creator_id BIGINT COMMENT '创建者ID',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_name (name),
  INDEX idx_type (type),
  INDEX idx_status (status),
  INDEX idx_creator_id (creator_id)
) ENGINE = InnoDB COMMENT = '数据源表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS datasource (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL COMMENT '数据源名称',
  type VARCHAR(50) NOT NULL COMMENT '数据源类型：mysql, postgresql',
  host VARCHAR(255) NOT NULL COMMENT '主机地址',
  port INT NOT NULL COMMENT '端口号',
  database_name VARCHAR(255) NOT NULL COMMENT '数据库名称',
  username VARCHAR(255) NOT NULL COMMENT '用户名',
  password VARCHAR(255) NOT NULL COMMENT '密码（加密存储）',
  connection_url VARCHAR(1000) COMMENT '完整连接URL',
  status VARCHAR(50) DEFAULT 'inactive' COMMENT '状态：active-启用，inactive-禁用',
  test_status VARCHAR(50) DEFAULT 'unknown' COMMENT '连接测试状态：success-成功，failed-失败，unknown-未知',
  description TEXT COMMENT '描述',
  creator_id BIGINT COMMENT '创建者ID',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_datasource_name (name),
  INDEX idx_datasource_type (type),
  INDEX idx_datasource_status (status),
  INDEX idx_datasource_creator_id (creator_id)
) ENGINE = InnoDB COMMENT = '数据源表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/DatasourceMapper.java`

```java
@Mapper
public interface DatasourceMapper {

	@Select("SELECT * FROM datasource WHERE id = #{id}")
	Datasource selectById(@Param("id") Integer id);

	@Select("SELECT * FROM datasource ORDER BY create_time DESC")
	List<Datasource> selectAll();

	@Insert("""
			INSERT INTO datasource
			    (name, type, host, port, database_name, username, password, connection_url, status, test_status, description, creator_id, create_time, update_time)
			VALUES (#{name}, #{type}, #{host}, #{port}, #{databaseName}, #{username}, #{password}, #{connectionUrl}, #{status}, #{testStatus}, #{description}, #{creatorId}, NOW(), NOW())
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(Datasource datasource);


	@Update("""
			<script>
			UPDATE datasource
			<set>
			    <if test="name != null">name = #{name},</if>
			    <if test="type != null">type = #{type},</if>
			    <if test="host != null">host = #{host},</if>
			    <if test="port != null">port = #{port},</if>
			    <if test="databaseName != null">database_name = #{databaseName},</if>
			    <if test="username != null">username = #{username},</if>
			    <if test="password != null">password = #{password},</if>
			    <if test="connectionUrl != null">connection_url = #{connectionUrl},</if>
			    <if test="status != null">status = #{status},</if>
			    <if test="testStatus != null">test_status = #{testStatus},</if>
			    <if test="description != null">description = #{description},</if>
			    <if test="creatorId != null">creator_id = #{creatorId},</if>
			    update_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int updateById(Datasource datasource);

	@Update("UPDATE datasource SET test_status = #{testStatus} WHERE id = #{id}")
	int updateTestStatusById(@Param("id") Integer id, @Param("testStatus") String testStatus);


	@Select("SELECT * FROM datasource WHERE status = #{status} ORDER BY create_time DESC")
	List<Datasource> selectByStatus(@Param("status") String status);


	@Select("SELECT * FROM datasource WHERE type = #{type} ORDER BY create_time DESC")
	List<Datasource> selectByType(@Param("type") String type);


	@Select("SELECT status, COUNT(*) as count FROM datasource GROUP BY status")
	List<Map<String, Object>> selectStatusStats();


	@Select("SELECT type, COUNT(*) as count FROM datasource GROUP BY type")
	List<Map<String, Object>> selectTypeStats();


	@Select("SELECT test_status, COUNT(*) as count FROM datasource GROUP BY test_status")
	List<Map<String, Object>> selectTestStatusStats();

	@Select("SELECT COUNT(*) FROM datasource")
	Long selectCount();

	@Delete("DELETE FROM datasource WHERE id = #{id}")
	int deleteById(Integer id);

}
```


## logical_relation

实体 `LogicalRelation`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS logical_relation (
  id INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  datasource_id INT NOT NULL COMMENT '关联的数据源ID',
  source_table_name VARCHAR(100) NOT NULL COMMENT '主表名 (例如 t_order)',
  source_column_name VARCHAR(100) NOT NULL COMMENT '主表字段名 (例如 buyer_uid)',
  target_table_name VARCHAR(100) NOT NULL COMMENT '关联表名 (例如 t_user)',
  target_column_name VARCHAR(100) NOT NULL COMMENT '关联表字段名 (例如 id)',
  relation_type VARCHAR(20) DEFAULT NULL COMMENT '关系类型: 1:1, 1:N, N:1 (辅助LLM理解数据基数，可选)',
  description VARCHAR(500) DEFAULT NULL COMMENT '业务描述: 存入Prompt中帮助LLM理解 (例如: 订单表通过buyer_uid关联用户表id)',
  is_deleted TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除, 1-已删除',
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_datasource_id (datasource_id) COMMENT '加速根据数据源查找关系的查询',
  INDEX idx_source_table (datasource_id, source_table_name) COMMENT '加速根据表名查找关系的查询',
  FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '逻辑外键配置表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS logical_relation (
  id INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  datasource_id INT NOT NULL COMMENT '关联的数据源ID',
  source_table_name VARCHAR(100) NOT NULL COMMENT '主表名 (例如 t_order)',
  source_column_name VARCHAR(100) NOT NULL COMMENT '主表字段名 (例如 buyer_uid)',
  target_table_name VARCHAR(100) NOT NULL COMMENT '关联表名 (例如 t_user)',
  target_column_name VARCHAR(100) NOT NULL COMMENT '关联表字段名 (例如 id)',
  relation_type VARCHAR(20) DEFAULT NULL COMMENT '关系类型: 1:1, 1:N, N:1 (辅助LLM理解数据基数，可选)',
  description VARCHAR(500) DEFAULT NULL COMMENT '业务描述: 存入Prompt中帮助LLM理解 (例如: 订单表通过buyer_uid关联用户表id)',
  is_deleted TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除, 1-已删除',
  created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_logical_relation_datasource_id (datasource_id),
  INDEX idx_logical_relation_source_table (datasource_id, source_table_name),
  FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '逻辑外键配置表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/LogicalRelationMapper.java`

```java
@Mapper
public interface LogicalRelationMapper {


	@Select("SELECT * FROM logical_relation WHERE id = #{id} AND is_deleted = 0")
	LogicalRelation selectById(@Param("id") Integer id);


	@Select("SELECT * FROM logical_relation WHERE datasource_id = #{datasourceId} AND is_deleted = 0 ORDER BY created_time DESC")
	List<LogicalRelation> selectByDatasourceId(@Param("datasourceId") Integer datasourceId);


	@Insert("""
			INSERT INTO logical_relation
			    (datasource_id, source_table_name, source_column_name, target_table_name, target_column_name,
			     relation_type, description, is_deleted, created_time, updated_time)
			VALUES (#{datasourceId}, #{sourceTableName}, #{sourceColumnName}, #{targetTableName}, #{targetColumnName},
			        #{relationType}, #{description}, 0, NOW(), NOW())
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(LogicalRelation logicalRelation);


	@Update("""
			<script>
			UPDATE logical_relation
			<set>
			    <if test="sourceTableName != null">source_table_name = #{sourceTableName},</if>
			    <if test="sourceColumnName != null">source_column_name = #{sourceColumnName},</if>
			    <if test="targetTableName != null">target_table_name = #{targetTableName},</if>
			    <if test="targetColumnName != null">target_column_name = #{targetColumnName},</if>
			    <if test="relationType != null">relation_type = #{relationType},</if>
			    <if test="description != null">description = #{description},</if>
			    updated_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int updateById(LogicalRelation logicalRelation);


	@Update("UPDATE logical_relation SET is_deleted = 1, updated_time = NOW() WHERE id = #{id}")
	int deleteById(@Param("id") Integer id);


	@Update("UPDATE logical_relation SET is_deleted = 1, updated_time = NOW() WHERE datasource_id = #{datasourceId}")
	int deleteByDatasourceId(@Param("datasourceId") Integer datasourceId);


	@Select("""
			SELECT COUNT(*) FROM logical_relation
			WHERE datasource_id = #{datasourceId}
			  AND source_table_name = #{sourceTableName}
			  AND source_column_name = #{sourceColumnName}
			  AND target_table_name = #{targetTableName}
			  AND target_column_name = #{targetColumnName}
			  AND is_deleted = 0
			""")
	int checkExists(@Param("datasourceId") Integer datasourceId, @Param("sourceTableName") String sourceTableName,
			@Param("sourceColumnName") String sourceColumnName, @Param("targetTableName") String targetTableName,
			@Param("targetColumnName") String targetColumnName);

}
```


## agent_datasource

实体 `AgentDatasource`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS agent_datasource (
  id INT NOT NULL AUTO_INCREMENT,
  agent_id INT NOT NULL COMMENT '智能体ID',
  datasource_id INT NOT NULL COMMENT '数据源ID',
  is_active TINYINT DEFAULT 0 COMMENT '是否启用：0-禁用，1-启用',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_datasource (agent_id, datasource_id),
  INDEX idx_agent_id (agent_id),
  INDEX idx_datasource_id (datasource_id),
  INDEX idx_is_active (is_active),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
  FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '智能体数据源关联表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS agent_datasource (
  id INT NOT NULL AUTO_INCREMENT,
  agent_id INT NOT NULL COMMENT '智能体ID',
  datasource_id INT NOT NULL COMMENT '数据源ID',
  is_active TINYINT DEFAULT 0 COMMENT '是否启用：0-禁用，1-启用',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_datasource (agent_id, datasource_id),
  INDEX idx_agent_datasource_agent_id (agent_id),
  INDEX idx_agent_datasource_datasource_id (datasource_id),
  INDEX idx_agent_datasource_is_active (is_active),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
  FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '智能体数据源关联表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentDatasourceMapper.java`

```java
@Mapper
public interface AgentDatasourceMapper {


	@Select("SELECT ad.*, d.name, d.type, d.host, d.port, d.database_name, "
			+ "d.connection_url, d.username, d.password, d.status, d.test_status, d.description "
			+ "FROM agent_datasource ad " + "LEFT JOIN datasource d ON ad.datasource_id = d.id "
			+ "WHERE ad.agent_id = #{agentId} " + "ORDER BY ad.create_time DESC")
	List<AgentDatasource> selectByAgentIdWithDatasource(@Param("agentId") Long agentId);


	@Select("SELECT * FROM agent_datasource WHERE agent_id = #{agentId} ORDER BY create_time DESC")
	List<AgentDatasource> selectByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT datasource_id FROM agent_datasource WHERE agent_id = #{agentId} AND is_active = 1")
	Integer selectActiveDatasourceIdByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT * FROM agent_datasource WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	AgentDatasource selectByAgentIdAndDatasourceId(@Param("agentId") Long agentId,
			@Param("datasourceId") Integer datasourceId);


	@Update("UPDATE agent_datasource SET is_active = 0 WHERE agent_id = #{agentId}")
	int disableAllByAgentId(@Param("agentId") Long agentId);


	@Select("SELECT COUNT(*) FROM agent_datasource WHERE agent_id = #{agentId} AND is_active = 1 AND datasource_id != #{excludeDatasourceId}")
	int countActiveByAgentIdExcluding(@Param("agentId") Long agentId,
			@Param("excludeDatasourceId") Integer excludeDatasourceId);

	@Delete("DELETE FROM agent_datasource WHERE datasource_id = #{datasourceId}")
	int deleteAllByDatasourceId(@Param("datasourceId") Integer datasourceId);

	@Insert("INSERT INTO agent_datasource (agent_id, datasource_id, is_active) VALUES (#{agentId}, #{datasourceId}, 1)")
	int createNewRelationEnabled(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId);

	@Update("UPDATE agent_datasource SET is_active = #{isActive} WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	int updateRelation(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId,
			@Param("isActive") Integer isActive);

	default int enableRelation(Long agentId, Integer datasourceId) {
		return updateRelation(agentId, datasourceId, 1);
	}

	@Delete("DELETE FROM agent_datasource WHERE agent_id = #{agentId} AND datasource_id = #{datasourceId}")
	int removeRelation(@Param("agentId") Long agentId, @Param("datasourceId") Integer datasourceId);

}
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentDatasourceTablesMapper.java`

```java
@Mapper
public interface AgentDatasourceTablesMapper {

	// 选择当前智能体数据源所有表
	@Select("select table_name from agent_datasource_tables where agent_datasource_id = #{agentDatasourceId}")
	List<String> getAgentDatasourceTables(@Param("agentDatasourceId") int agentDatasourceId);


	@Select("""
			SELECT DISTINCT adt.table_name
			FROM agent_datasource_tables adt
			JOIN agent_datasource ad ON ad.id = adt.agent_datasource_id
			WHERE ad.datasource_id = #{datasourceId}
			ORDER BY adt.table_name
			""")
	List<String> getSelectedTablesByDatasourceId(@Param("datasourceId") int datasourceId);

	// 删除当前列表中不存在的表
	@Delete("<script>" + "DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}"
			+ "<if test='tables != null and tables.size() > 0'>" + " AND table_name NOT IN ("
			+ "<foreach collection='tables' item='table' separator=','>#{table}</foreach>" + ")" + "</if>"
			+ "</script>")
	int removeExpireTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 删除当前智能体数据源所有表
	@Delete("DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}")
	int removeAllTables(@Param("agentDatasourceId") int agentDatasourceId);

	// 插入用户选择的列表
	@Insert("<script>" + "INSERT IGNORE INTO agent_datasource_tables (agent_datasource_id, table_name) VALUES "
			+ "<if test='tables != null and tables.size() > 0'>"
			+ "<foreach collection='tables' item='table' separator=','>" + "(#{agentDatasourceId}, #{table})"
			+ "</foreach>" + "</if>" + "</script>")
	int insertNewTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 更新用户的选择（tables不能为空）
	default int updateAgentDatasourceTables(int agentDatasourceId, List<String> tables) {
		if (tables.isEmpty()) {
			throw new IllegalArgumentException("tables cannot be empty");
		}
		int deleteCount = removeExpireTables(agentDatasourceId, tables);
		int insertCount = insertNewTables(agentDatasourceId, tables);
		return deleteCount + insertCount;
	}

}
```


## agent_datasource_tables

实体 `AgentDatasourceTables`，字段见 [catalog](schemas.md)。


### mysql

```sql
create table if not exists agent_datasource_tables
(
    id                  int auto_increment primary key,
    agent_datasource_id int                                 not null comment '智能体数据源ID',
    table_name          varchar(255)                        not null comment '数据表名',
    create_time         timestamp default CURRENT_TIMESTAMP null comment '创建时间',
    update_time         timestamp default CURRENT_TIMESTAMP null comment '更新时间',
    constraint agent_datasource_tables_agent_datasource_id_table_name_uindex
        unique (agent_datasource_id, table_name),
    constraint agent_datasource_tables_agent_datasource_id_fk
        foreign key (agent_datasource_id) references agent_datasource (id)
            on update cascade on delete cascade
)
    comment '某个智能体某个数据源所选中的数据表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS agent_datasource_tables
(
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    agent_datasource_id INT                                 NOT NULL COMMENT '智能体数据源ID',
    table_name          VARCHAR(255)                        NOT NULL COMMENT '数据表名',
    create_time         TIMESTAMP DEFAULT CURRENT_TIMESTAMP NULL COMMENT '创建时间',
    update_time         TIMESTAMP DEFAULT CURRENT_TIMESTAMP NULL COMMENT '更新时间',
    CONSTRAINT uk_agent_datasource_tables_agent_datasource_id_table_name
        UNIQUE (agent_datasource_id, table_name),
    CONSTRAINT fk_agent_datasource_tables_agent_datasource_id
        FOREIGN KEY (agent_datasource_id) REFERENCES agent_datasource (id)
            ON UPDATE CASCADE ON DELETE CASCADE
    ) ENGINE = InnoDB COMMENT = '某个智能体某个数据源所选中的数据表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentDatasourceTablesMapper.java`

```java
@Mapper
public interface AgentDatasourceTablesMapper {

	// 选择当前智能体数据源所有表
	@Select("select table_name from agent_datasource_tables where agent_datasource_id = #{agentDatasourceId}")
	List<String> getAgentDatasourceTables(@Param("agentDatasourceId") int agentDatasourceId);


	@Select("""
			SELECT DISTINCT adt.table_name
			FROM agent_datasource_tables adt
			JOIN agent_datasource ad ON ad.id = adt.agent_datasource_id
			WHERE ad.datasource_id = #{datasourceId}
			ORDER BY adt.table_name
			""")
	List<String> getSelectedTablesByDatasourceId(@Param("datasourceId") int datasourceId);

	// 删除当前列表中不存在的表
	@Delete("<script>" + "DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}"
			+ "<if test='tables != null and tables.size() > 0'>" + " AND table_name NOT IN ("
			+ "<foreach collection='tables' item='table' separator=','>#{table}</foreach>" + ")" + "</if>"
			+ "</script>")
	int removeExpireTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 删除当前智能体数据源所有表
	@Delete("DELETE FROM agent_datasource_tables WHERE agent_datasource_id = #{agentDatasourceId}")
	int removeAllTables(@Param("agentDatasourceId") int agentDatasourceId);

	// 插入用户选择的列表
	@Insert("<script>" + "INSERT IGNORE INTO agent_datasource_tables (agent_datasource_id, table_name) VALUES "
			+ "<if test='tables != null and tables.size() > 0'>"
			+ "<foreach collection='tables' item='table' separator=','>" + "(#{agentDatasourceId}, #{table})"
			+ "</foreach>" + "</if>" + "</script>")
	int insertNewTables(@Param("agentDatasourceId") int agentDatasourceId, @Param("tables") List<String> tables);

	// 更新用户的选择（tables不能为空）
	default int updateAgentDatasourceTables(int agentDatasourceId, List<String> tables) {
		if (tables.isEmpty()) {
			throw new IllegalArgumentException("tables cannot be empty");
		}
		int deleteCount = removeExpireTables(agentDatasourceId, tables);
		int insertCount = insertNewTables(agentDatasourceId, tables);
		return deleteCount + insertCount;
	}

}
```


## agent_preset_question

实体 `AgentPresetQuestion`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS agent_preset_question (
  id INT NOT NULL AUTO_INCREMENT,
  agent_id INT NOT NULL COMMENT '智能体ID',
  question TEXT NOT NULL COMMENT '预设问题内容',
  sort_order INT DEFAULT 0 COMMENT '排序顺序',
  is_active TINYINT DEFAULT 0 COMMENT '是否启用：0-禁用，1-启用',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_agent_id (agent_id),
  INDEX idx_sort_order (sort_order),
  INDEX idx_is_active (is_active),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '智能体预设问题表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS agent_preset_question (
  id INT NOT NULL AUTO_INCREMENT,
  agent_id INT NOT NULL COMMENT '智能体ID',
  question TEXT NOT NULL COMMENT '预设问题内容',
  sort_order INT DEFAULT 0 COMMENT '排序顺序',
  is_active TINYINT DEFAULT 0 COMMENT '是否启用：0-禁用，1-启用',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_agent_preset_question_agent_id (agent_id),
  INDEX idx_agent_preset_question_sort_order (sort_order),
  INDEX idx_agent_preset_question_is_active (is_active),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '智能体预设问题表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/AgentPresetQuestionMapper.java`

```java
@Mapper
public interface AgentPresetQuestionMapper {

	@Select("""
			SELECT * FROM agent_preset_question
			         WHERE agent_id = #{agentId} AND is_active = 1
			ORDER BY sort_order ASC, id ASC
			""")
	List<AgentPresetQuestion> selectByAgentId(@Param("agentId") Long agentId);

	@Select("""
			SELECT * FROM agent_preset_question
			         WHERE agent_id = #{agentId}
			ORDER BY sort_order ASC, id ASC
			""")
	List<AgentPresetQuestion> selectAllByAgentId(@Param("agentId") Long agentId);


	@Select("""
			SELECT * FROM agent_preset_question WHERE id = #{id}
			""")
	AgentPresetQuestion selectById(@Param("id") Long id);

	@Insert("""
			INSERT INTO agent_preset_question (agent_id, question, sort_order, is_active, create_time, update_time)
			VALUES (#{agentId}, #{question}, #{sortOrder}, #{isActive}, NOW(), NOW())
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(AgentPresetQuestion question);

	@Update("""
			<script>
			UPDATE agent_preset_question
			<set>
				<if test="question != null">question = #{question},</if>
				<if test="sortOrder != null">sort_order = #{sortOrder},</if>
				<if test="isActive != null">is_active = #{isActive},</if>
				update_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int update(AgentPresetQuestion question);

	@Delete("""
			DELETE FROM agent_preset_question WHERE id = #{id}
			""")
	int deleteById(@Param("id") Long id);

	@Delete("""
			DELETE FROM agent_preset_question WHERE agent_id = #{agentId}
			""")
	int deleteByAgentId(@Param("agentId") Long agentId);

}
```


## chat_session

实体 `ChatSession`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS chat_session (
  id VARCHAR(36) NOT NULL COMMENT '会话ID（UUID）',
  agent_id INT NOT NULL COMMENT '智能体ID',
  title VARCHAR(255) DEFAULT '新对话' COMMENT '会话标题',
  status VARCHAR(50) DEFAULT 'active' COMMENT '状态：active-活跃，archived-归档，deleted-已删除',
  is_pinned TINYINT DEFAULT 0 COMMENT '是否置顶：0-否，1-是',
  user_id BIGINT COMMENT '用户ID',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_agent_id (agent_id),
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_is_pinned (is_pinned),
  INDEX idx_create_time (create_time),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '聊天会话表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS chat_session (
  id VARCHAR(36) NOT NULL COMMENT '会话ID（UUID）',
  agent_id INT NOT NULL COMMENT '智能体ID',
  title VARCHAR(255) DEFAULT '新对话' COMMENT '会话标题',
  status VARCHAR(50) DEFAULT 'active' COMMENT '状态：active-活跃，archived-归档，deleted-已删除',
  is_pinned TINYINT DEFAULT 0 COMMENT '是否置顶：0-否，1-是',
  user_id BIGINT COMMENT '用户ID',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_chat_session_agent_id (agent_id),
  INDEX idx_chat_session_user_id (user_id),
  INDEX idx_chat_session_status (status),
  INDEX idx_chat_session_is_pinned (is_pinned),
  INDEX idx_chat_session_create_time (create_time),
  FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '聊天会话表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/ChatSessionMapper.java`

```java
@Mapper
public interface ChatSessionMapper {


	@Select("""
			SELECT * FROM chat_session
			WHERE agent_id = #{agentId} AND status != 'deleted'
			ORDER BY is_pinned DESC, update_time DESC
			""")
	List<ChatSession> selectByAgentId(@Param("agentId") Integer agentId);


	@Select("""
			SELECT * FROM chat_session
			WHERE id = #{sessionId} AND status != 'deleted'
			""")
	ChatSession selectBySessionId(@Param("sessionId") String sessionId);


	@Update("""
			<script>
			UPDATE chat_session
			<set>
				<if test="title != null">title = #{title},</if>
				<if test="status != null">status = #{status},</if>
				<if test="isPinned != null">is_pinned = #{isPinned},</if>
				<if test="userId != null">user_id = #{userId},</if>
				update_time = NOW()
			</set>
			WHERE id = #{sessionId}
			</script>
			""")
	int updateById(ChatSession session);


	@Update("""
			UPDATE chat_session
			SET status = 'deleted', update_time = #{updateTime}
			WHERE agent_id = #{agentId}
			""")
	int softDeleteByAgentId(@Param("agentId") Integer agentId, @Param("updateTime") LocalDateTime updateTime);


	@Update("""
			UPDATE chat_session
			SET update_time = #{updateTime}
			WHERE id = #{sessionId}
			""")
	int updateSessionTime(@Param("sessionId") String sessionId, @Param("updateTime") LocalDateTime updateTime);


	@Update("""
			UPDATE chat_session SET
				is_pinned = #{isPinned},
				update_time = #{updateTime}
			WHERE id = #{sessionId}
			""")
	int updatePinStatus(@Param("sessionId") String sessionId, @Param("isPinned") boolean isPinned,
			@Param("updateTime") LocalDateTime updateTime);


	@Update("""
			UPDATE chat_session SET
				title = #{title},
				update_time = #{updateTime}
			WHERE id = #{sessionId}
			""")
	int updateTitle(@Param("sessionId") String sessionId, @Param("title") String title,
			@Param("updateTime") LocalDateTime updateTime);


	@Update("""
			UPDATE chat_session
			SET status = 'deleted', update_time = #{updateTime}
			WHERE id = #{sessionId}
			""")
	int softDeleteById(@Param("sessionId") String sessionId, @Param("updateTime") LocalDateTime updateTime);

	@Insert("""
			INSERT INTO chat_session (id, agent_id, title, status, is_pinned, user_id, create_time, update_time)
			VALUES (#{id}, #{agentId}, #{title}, #{status}, #{isPinned}, #{userId}, #{createTime}, #{updateTime})
			""")
	int insert(ChatSession session);

}
```


## chat_message

实体 `ChatMessage`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS chat_message (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id VARCHAR(36) NOT NULL COMMENT '会话ID',
  role VARCHAR(20) NOT NULL COMMENT '角色：user-用户，assistant-助手，system-系统',
  content MEDIUMTEXT NOT NULL COMMENT '消息内容',
  message_type VARCHAR(50) DEFAULT 'text' COMMENT '消息类型：text-文本，sql-SQL查询，result-查询结果，error-错误',
  metadata JSON COMMENT '元数据（JSON格式）',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  INDEX idx_session_id (session_id),
  INDEX idx_role (role),
  INDEX idx_message_type (message_type),
  INDEX idx_create_time (create_time),
  FOREIGN KEY (session_id) REFERENCES chat_session(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '聊天消息表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS chat_message (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id VARCHAR(36) NOT NULL COMMENT '会话ID',
  role VARCHAR(20) NOT NULL COMMENT '角色：user-用户，assistant-助手，system-系统',
  content TEXT NOT NULL COMMENT '消息内容',
  message_type VARCHAR(50) DEFAULT 'text' COMMENT '消息类型：text-文本，sql-SQL查询，result-查询结果，error-错误',
  metadata JSON COMMENT '元数据（JSON格式）',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  INDEX idx_chat_message_session_id (session_id),
  INDEX idx_chat_message_role (role),
  INDEX idx_chat_message_message_type (message_type),
  INDEX idx_chat_message_create_time (create_time),
  FOREIGN KEY (session_id) REFERENCES chat_session(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = '聊天消息表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/ChatMessageMapper.java`

```java
@Mapper
public interface ChatMessageMapper {


	@Select("""
			SELECT * FROM chat_message
			WHERE session_id = #{sessionId}
			ORDER BY create_time ASC
			""")
	List<ChatMessage> selectBySessionId(@Param("sessionId") String sessionId);


	@Select("""
			SELECT * FROM chat_message
			WHERE id = #{id}
			""")
	ChatMessage selectById(@Param("id") Long id);


	@Select("""
			SELECT COUNT(*) FROM chat_message
			WHERE session_id = #{sessionId}
			""")
	int countBySessionId(@Param("sessionId") String sessionId);


	@Select("""
			SELECT * FROM chat_message
			WHERE session_id = #{sessionId}
			AND role = #{role}
			ORDER BY create_time ASC
			""")
	List<ChatMessage> selectBySessionIdAndRole(@Param("sessionId") String sessionId, @Param("role") String role);

	@Insert("""
			INSERT INTO chat_message (session_id, role, content, message_type, metadata, create_time)
			VALUES (#{sessionId}, #{role}, #{content}, #{messageType}, #{metadata}, NOW())
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(ChatMessage message);

	@Delete("""
			DELETE FROM chat_message
			WHERE id = #{id}
			""")
	int deleteById(@Param("id") Long id);

}
```


## user_prompt_config

实体 `UserPromptConfig`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS user_prompt_config (
  id VARCHAR(36) NOT NULL COMMENT '配置ID（UUID）',
  name VARCHAR(255) NOT NULL COMMENT '配置名称',
  prompt_type VARCHAR(100) NOT NULL COMMENT 'Prompt类型（如report-generator, planner等）',
  agent_id INT COMMENT '关联的智能体ID，为空表示全局配置',
  system_prompt TEXT NOT NULL COMMENT '用户自定义系统Prompt内容',
  enabled TINYINT DEFAULT 1 COMMENT '是否启用该配置：0-禁用，1-启用',
  description TEXT COMMENT '配置描述',
  priority INT DEFAULT 0 COMMENT '配置优先级，数字越大优先级越高',
  display_order INT DEFAULT 0 COMMENT '配置显示顺序，数字越小越靠前',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  creator VARCHAR(255) COMMENT '创建者',
  PRIMARY KEY (id),
  INDEX idx_prompt_type (prompt_type),
  INDEX idx_agent_id (agent_id),
  INDEX idx_enabled (enabled),
  INDEX idx_create_time (create_time),
  INDEX idx_prompt_type_enabled_priority (prompt_type, agent_id, enabled, priority DESC),
  INDEX idx_display_order (display_order ASC)
) ENGINE = InnoDB COMMENT = '用户Prompt配置表';
```


### h2

```sql
CREATE TABLE IF NOT EXISTS user_prompt_config (
  id VARCHAR(36) NOT NULL COMMENT '配置ID（UUID）',
  name VARCHAR(255) NOT NULL COMMENT '配置名称',
  prompt_type VARCHAR(100) NOT NULL COMMENT 'Prompt类型（如report-generator, planner等）',
  agent_id INT COMMENT '关联的智能体ID，为空表示全局配置',
  system_prompt TEXT NOT NULL COMMENT '用户自定义系统Prompt内容',
  enabled TINYINT DEFAULT 1 COMMENT '是否启用该配置：0-禁用，1-启用',
  description TEXT COMMENT '配置描述',
  priority INT DEFAULT 0 COMMENT '配置优先级，数字越大优先级越高',
  display_order INT DEFAULT 0 COMMENT '配置显示顺序，数字越小越靠前',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  creator VARCHAR(255) COMMENT '创建者',
  PRIMARY KEY (id),
  INDEX idx_user_prompt_config_prompt_type (prompt_type),
  INDEX idx_user_prompt_config_agent_id (agent_id),
  INDEX idx_user_prompt_config_enabled (enabled),
  INDEX idx_user_prompt_config_create_time (create_time),
  INDEX idx_user_prompt_config_type_enabled_priority (prompt_type, agent_id, enabled, priority DESC),
  INDEX idx_user_prompt_config_display_order (display_order ASC)
) ENGINE = InnoDB COMMENT = '用户Prompt配置表';
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/UserPromptConfigMapper.java`

```java
@Mapper
public interface UserPromptConfigMapper {


	@Select("""
			<script>
			SELECT * FROM user_prompt_config
			WHERE prompt_type = #{promptType}
			<if test='agentId != null'> AND agent_id = #{agentId}</if>
			ORDER BY update_time DESC
			</script>
			""")
	List<UserPromptConfig> selectByPromptType(@Param("promptType") String promptType, @Param("agentId") Long agentId);


	@Select("""
			<script>
			SELECT * FROM user_prompt_config
			WHERE prompt_type = #{promptType}
			  AND enabled = 1
			<if test='agentId != null'> AND agent_id = #{agentId}</if>
			LIMIT 1
			</script>
			""")
	UserPromptConfig selectActiveByPromptType(@Param("promptType") String promptType, @Param("agentId") Long agentId);


	@Update("""
			<script>
			UPDATE user_prompt_config
			SET enabled = 0
			WHERE prompt_type = #{promptType}
			<if test='agentId != null'> AND agent_id = #{agentId}</if>
			</script>
			""")
	int disableAllByPromptType(@Param("promptType") String promptType, @Param("agentId") Long agentId);


	@Update("UPDATE user_prompt_config SET enabled = 1 WHERE id = #{id}")
	int enableById(@Param("id") String id);


	@Update("UPDATE user_prompt_config SET enabled = 0 WHERE id = #{id}")
	int disableById(@Param("id") String id);

	@Select("SELECT * FROM user_prompt_config WHERE id = #{id}")
	UserPromptConfig selectById(String id);

	@Update("""
			<script>
			UPDATE user_prompt_config
			<set>
			  <if test='name != null'>name = #{name},</if>
			  <if test='promptType != null'>prompt_type = #{promptType},</if>
			  <if test='agentId != null'>agent_id = #{agentId},</if>
			  <if test='systemPrompt != null'>system_prompt = #{systemPrompt},</if>
			  <if test='enabled != null'>enabled = #{enabled},</if>
			  <if test='description != null'>description = #{description},</if>
			  <if test='priority != null'>priority = #{priority},</if>
			  <if test='displayOrder != null'>display_order = #{displayOrder},</if>
			  update_time = NOW()
			</set>
			WHERE id = #{id}
			</script>
			""")
	int updateById(UserPromptConfig config);

	@Insert("""
			INSERT INTO user_prompt_config
			(id, name, prompt_type, agent_id, system_prompt, enabled, description, priority, display_order, create_time, update_time, creator)
			VALUES (#{id}, #{name}, #{promptType}, #{agentId}, #{systemPrompt}, #{enabled}, #{description}, #{priority}, #{displayOrder}, NOW(), NOW(), #{creator})
			""")
	int insert(UserPromptConfig config);

	@Select("""
			<script>
			SELECT * FROM user_prompt_config
			WHERE prompt_type = #{promptType}
			  AND enabled = true
			<if test='agentId != null'> AND agent_id = #{agentId}</if>
			ORDER BY priority DESC, display_order, update_time DESC
			</script>
			""")
	List<UserPromptConfig> getActiveConfigsByType(@Param("promptType") String promptType,
			@Param("agentId") Long agentId);

	@Select("""
			<script>
			SELECT * FROM user_prompt_config
			WHERE prompt_type = #{promptType}
			<if test='agentId != null'> AND agent_id = #{agentId}</if>
			ORDER BY priority DESC, display_order, update_time DESC
			</script>
			""")
	List<UserPromptConfig> getConfigsByType(@Param("promptType") String promptType, @Param("agentId") Long agentId);

	@Select("SELECT * FROM user_prompt_config ORDER BY priority DESC, display_order, update_time DESC")
	List<UserPromptConfig> selectAll();

	@Delete("DELETE FROM user_prompt_config WHERE id = #{id}")
	int deleteById(String id);

}
```


## model_config

实体 `ModelConfig`，字段见 [catalog](schemas.md)。


### mysql

```sql
CREATE TABLE IF NOT EXISTS `model_config` (
                                              `id` int(11) NOT NULL AUTO_INCREMENT,
    `provider` varchar(255) NOT NULL COMMENT '厂商标识 (方便前端展示回显，实际调用主要靠 baseUrl)',
    `base_url` varchar(255) NOT NULL COMMENT '关键配置',
    `api_key` varchar(255) NOT NULL COMMENT 'API密钥',
    `model_name` varchar(255) NOT NULL COMMENT '模型名称',
    `temperature` decimal(10,2) unsigned DEFAULT '0.00' COMMENT '温度参数',
    `is_active` tinyint(1) DEFAULT '0' COMMENT '是否激活',
    `max_tokens` int(11) DEFAULT '2000' COMMENT '输出响应最大令牌数',
    `model_type` varchar(20) NOT NULL DEFAULT 'CHAT' COMMENT '模型类型 (CHAT/EMBEDDING)',
    `completions_path` varchar(255) DEFAULT NULL COMMENT 'Chat模型专用。附加到 Base URL 的路径。例如OpenAi的/v1/chat/completions',
    `embeddings_path` varchar(255) DEFAULT NULL COMMENT '嵌入模型专用。附加到 Base URL 的路径。',
    `created_time` datetime DEFAULT NULL COMMENT '创建时间',
    `updated_time` datetime DEFAULT NULL COMMENT '更新时间',
    `is_deleted` int(11) DEFAULT '0' COMMENT '0=未删除, 1=已删除',
    -- 新增 AI 代理配置字段（默认关闭以确保零侵入性）
    `proxy_enabled` tinyint(1) DEFAULT '0' COMMENT '是否启用代理：0-禁用，1-启用',
    `proxy_host` varchar(255) DEFAULT NULL COMMENT '代理主机地址',
    `proxy_port` int(11) DEFAULT NULL COMMENT '代理端口',
    `proxy_username` varchar(255) DEFAULT NULL COMMENT '代理用户名（可选）',
    `proxy_password` varchar(255) DEFAULT NULL COMMENT '代理密码（可选）',
    PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```


### h2

```sql
CREATE TABLE IF NOT EXISTS `model_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `provider` varchar(255) NOT NULL COMMENT '厂商标识 (方便前端展示回显，实际调用主要靠 baseUrl)',
  `base_url` varchar(255) NOT NULL COMMENT '关键配置',
  `api_key` varchar(255) NOT NULL COMMENT 'API密钥',
  `model_name` varchar(255) NOT NULL COMMENT '模型名称',
  `temperature` decimal(10,2) DEFAULT '0.00' COMMENT '温度参数',
  `is_active` tinyint(1) DEFAULT '0' COMMENT '是否激活',
  `max_tokens` int(11) DEFAULT '2000' COMMENT '输出响应最大令牌数',
  `model_type` varchar(20) NOT NULL DEFAULT 'CHAT' COMMENT '模型类型 (CHAT/EMBEDDING)',
  `completions_path` varchar(255) DEFAULT NULL COMMENT 'Chat模型专用。附加到 Base URL 的路径。例如OpenAi的/v1/chat/completions',
  `embeddings_path` varchar(255) DEFAULT NULL COMMENT '嵌入模型专用。附加到 Base URL 的路径。',
  `created_time` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_time` datetime DEFAULT NULL COMMENT '更新时间',
  `is_deleted` int(11) DEFAULT '0' COMMENT '0=未删除, 1=已删除',
  -- 新增 AI 代理配置字段（默认关闭以确保零侵入性）
  `proxy_enabled` tinyint(1) DEFAULT '0' COMMENT '是否启用代理：0-禁用，1-启用',
  `proxy_host` varchar(255) DEFAULT NULL COMMENT '代理主机地址',
  `proxy_port` int(11) DEFAULT NULL COMMENT '代理端口',
  `proxy_username` varchar(255) DEFAULT NULL COMMENT '代理用户名（可选）',
  `proxy_password` varchar(255) DEFAULT NULL COMMENT '代理密码（可选）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
```


Mapper `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/mapper/ModelConfigMapper.java`

```java
@Mapper
public interface ModelConfigMapper {

	@Select("""
			SELECT id, provider, base_url, api_key, model_name, temperature, is_active, max_tokens,
			       model_type, completions_path, embeddings_path, created_time, updated_time, is_deleted,
			       proxy_enabled, proxy_host, proxy_port, proxy_username, proxy_password
			FROM model_config WHERE is_deleted = 0 ORDER BY created_time DESC
			""")
	List<ModelConfig> findAll();

	@Select("""
			SELECT id, provider, base_url, api_key, model_name, temperature, is_active, max_tokens,
			       model_type, completions_path, embeddings_path, created_time, updated_time, is_deleted,
			       proxy_enabled, proxy_host, proxy_port, proxy_username, proxy_password
			FROM model_config WHERE id = #{id} AND is_deleted = 0
			""")
	ModelConfig findById(Integer id);

	@Select("""
			SELECT id, provider, base_url, api_key, model_name, temperature, is_active, max_tokens,
			       model_type, completions_path, embeddings_path, created_time, updated_time, is_deleted,
			       proxy_enabled, proxy_host, proxy_port, proxy_username, proxy_password
			FROM model_config WHERE model_type = #{modelType} AND is_active = 1 AND is_deleted = 0 LIMIT 1
			""")
	ModelConfig selectActiveByType(@Param("modelType") String modelType);

	@Update("UPDATE model_config SET is_active = 0 WHERE model_type = #{modelType} AND id != #{currentId} AND is_deleted = 0")
	void deactivateOthers(@Param("modelType") String modelType, @Param("currentId") Integer currentId);

	@Select("""
			<script>
			   SELECT id, provider, base_url, api_key, model_name, temperature, is_active, max_tokens,
			          model_type, completions_path, embeddings_path, created_time, updated_time, is_deleted,
			          proxy_enabled, proxy_host, proxy_port, proxy_username, proxy_password
			   FROM model_config
			   <where>
			      is_deleted = 0
			      <if test='provider != null and provider != ""'>
			         AND provider = #{provider}
			      </if>
			      <if test='keyword != null and keyword != ""'>
			         AND (provider LIKE CONCAT('%', #{keyword}, '%')
			             OR base_url LIKE CONCAT('%', #{keyword}, '%')
			             OR model_name LIKE CONCAT('%', #{keyword}, '%'))
			      </if>
			      <if test='isActive != null'>
			         AND is_active = #{isActive}
			      </if>
			      <if test='maxTokens != null'>
			         AND max_tokens = #{maxTokens}
			      </if>
			      <if test='modelType != null'>
			         AND model_type = #{modelType}
			      </if>
			   </where>
			   ORDER BY created_time DESC
			</script>
			""")
	List<ModelConfig> findByConditions(@Param("provider") String provider, @Param("keyword") String keyword,
			@Param("isActive") Boolean isActive, @Param("maxTokens") Integer maxTokens,
			@Param("modelType") String modelType);

	@Insert("""
			INSERT INTO model_config (provider, base_url, api_key, model_name, temperature, is_active, max_tokens,
			                         model_type, completions_path, embeddings_path, created_time, updated_time, is_deleted,
			                         proxy_enabled, proxy_host, proxy_port, proxy_username, proxy_password)
			VALUES (#{provider}, #{baseUrl}, #{apiKey}, #{modelName}, #{temperature}, #{isActive}, #{maxTokens},
			        #{modelType}, #{completionsPath}, #{embeddingsPath}, NOW(), NOW(), 0,
			        #{proxyEnabled}, #{proxyHost}, #{proxyPort}, #{proxyUsername}, #{proxyPassword})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(ModelConfig modelConfig);

	@Update("""
			<script>
			          UPDATE model_config
			          <trim prefix="SET" suffixOverrides=",">
			            <if test='provider != null'>provider = #{provider},</if>
			            <if test='baseUrl != null'>base_url = #{baseUrl},</if>
			            <if test='apiKey != null'>api_key = #{apiKey},</if>
			            <if test='modelName != null'>model_name = #{modelName},</if>
			            <if test='temperature != null'>temperature = #{temperature},</if>
			            <if test='isActive != null'>is_active = #{isActive},</if>
			            <if test='maxTokens != null'>max_tokens = #{maxTokens},</if>
			            <if test='modelType != null'>model_type = #{modelType},</if>
			            <if test='completionsPath != null'>completions_path = #{completionsPath},</if>
			            <if test='embeddingsPath != null'>embeddings_path = #{embeddingsPath},</if>
			            <if test='isDeleted != null'>is_deleted = #{isDeleted},</if>
			            <if test='proxyEnabled != null'>proxy_enabled = #{proxyEnabled},</if>
			            <if test='proxyHost != null'>proxy_host = #{proxyHost},</if>
			            <if test='proxyPort != null'>proxy_port = #{proxyPort},</if>
			            <if test='proxyUsername != null'>proxy_username = #{proxyUsername},</if>
			            <if test='proxyPassword != null'>proxy_password = #{proxyPassword},</if>
			            updated_time = NOW()
			          </trim>
			          WHERE id = #{id}
			</script>
			""")
	int updateById(ModelConfig modelConfig);

	@Update("""
			UPDATE model_config SET is_deleted = 1 WHERE id = #{id}
			""")
	int deleteById(Integer id);

}
```


## 方言及约束决策

MySQL 为列/约束权威：保留 utf8mb4_bin 对表列名的大小写区分、JSON metadata、MEDIUMTEXT、unsigned temperature、自动增量和 ON UPDATE 时间；H2 的兼容语法不复制到 Python。agent_datasource 的 (agent_id,datasource_id) 唯一、agent_datasource_tables 的 (agent_datasource_id,table_name) 唯一及解绑级联均完整保留。semantic_model.datasource_id 和 user_prompt_config.agent_id 原本无外键，不擅自增加。实体展示字段 selectTables 等不当作存储列；JSON metadata 由 API 转换，不能再次字符串化。

框架表：Java MysqlSaver 自动建图表及 Spring AI ChatMemory 表与这 13 张表分开；精确版本框架表字段与索引见 [框架表清单](../python-framework-tables.md)，迁移工具显式排除，不复制其序列化字节。Java checkpoint 重建，chat memory 从成功轮次转换为 agent_conversation_turn 后重建，历史 PYTHON 文本仅读兼容。

Python 新表和唯一键见 `PYTHON/migrations/002_runtime.sql`；无隐式跨存储外键。运行/效果/结果由 runtime 服务写、展示消息由消息 API 写，所有删除通过公共生命周期闸门后先提交清理作业。SQLite saver 独立文件内由锁定版本 setup 建立 checkpoints、writes 表（实际兼容性另有重启验证），不计入业务表数。应用生命周期调用 setup，业务迁移版本记录只记录 MySQL 001/002，变更既有 SQL 校验和会阻止启动。
