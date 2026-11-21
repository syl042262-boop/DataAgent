# DTO、实体及响应字段基线

完整字段类型、约束、默认值、JSON 日期/忽略注解及 Map 构造见下方。无显式初值的引用字段为 null；Java primitive 为 0/false。Map 请求字段见对应 controller 方法。保留源码作为逐字段核对证据，不代表未来 Python ORM 必须照搬类层次。


## ChatMessageDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/ChatMessageDTO.java`

```java
@Data
public class ChatMessageDTO {

	private String role;

	private String content;

	private String messageType;

	private String metadata;


	private boolean titleNeeded;

}
```


## DatasourceTypeDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/datasource/DatasourceTypeDTO.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DatasourceTypeDTO {


	private Integer code;


	private String typeName;


	private String dialect;


	private String protocol;


	private String displayName;

}
```


## SchemaInitRequest

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/datasource/SchemaInitRequest.java`

```java
public class SchemaInitRequest implements Serializable {

	private DbConfigBO dbConfig;

	private List<String> tables;

	public DbConfigBO getDbConfig() {
		return dbConfig;
	}

	public void setDbConfig(DbConfigBO dbConfig) {
		this.dbConfig = dbConfig;
	}

	public List<String> getTables() {
		return tables;
	}

	public void setTables(List<String> tables) {
		this.tables = tables;
	}

	@Override
	public String toString() {
		return "SchemaInitRequest{" + "dbConfig=" + dbConfig + ", tables=" + tables + '}';
	}

	@Override
	public boolean equals(Object o) {
		if (this == o)
			return true;
		if (o == null || getClass() != o.getClass())
			return false;
		SchemaInitRequest that = (SchemaInitRequest) o;
		return Objects.equals(dbConfig, that.dbConfig) && Objects.equals(tables, that.tables);
	}

	@Override
	public int hashCode() {
		return Objects.hash(dbConfig, tables);
	}

}
```


## SqlRetryDto

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/datasource/SqlRetryDto.java`

```java
public record SqlRetryDto(String reason, boolean semanticFail, boolean sqlExecuteFail) {

	public static SqlRetryDto semantic(String reason) {
		return new SqlRetryDto(reason, true, false);
	}

	public static SqlRetryDto sqlExecute(String reason) {
		return new SqlRetryDto(reason, false, true);
	}

	public static SqlRetryDto empty() {
		return new SqlRetryDto("", false, false);
	}

}
```


## ToggleDatasourceDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/datasource/ToggleDatasourceDTO.java`

```java
@Data
public class ToggleDatasourceDTO {

	private Integer datasourceId;

	private Boolean isActive;

}
```


## UpdateDatasourceTablesDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/datasource/UpdateDatasourceTablesDTO.java`

```java
@Data
public class UpdateDatasourceTablesDTO {

	@NotNull(message = "datasourceId cannot be null")
	private Integer datasourceId;

	private List<String> tables;

}
```


## GraphRequest

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/GraphRequest.java`

```java
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class GraphRequest {

	private String agentId;


	private String conversationId;


	private String threadId;

	private String query;

	private boolean humanFeedback;

	private String humanFeedbackContent;

	private boolean rejectedPlan;

	private boolean nl2sqlOnly;

}
```


## AgentKnowledgeQueryDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/knowledge/agentknowledge/AgentKnowledgeQueryDTO.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentKnowledgeQueryDTO {


	@NotNull(message = "agentId不能为空")
	private Integer agentId;


	private String title;


	@InEnum(value = KnowledgeType.class, message = "type只能是DOCUMENT/QA/FAQ 之一")
	private String type;


	@InEnum(value = EmbeddingStatus.class, message = "embeddingStatus只能是PENDING/PROCESSING/COMPLETED/FAILED之一")
	private String embeddingStatus;


	@NotNull(message = "pageNum不能为空")
	@Min(value = 1, message = "pageNum不能小于1")
	private Integer pageNum = 1;


	@NotNull(message = "pageSize不能为空")
	@Min(value = 1, message = "pageSize不能小于1")
	private Integer pageSize = 10;

}
```


## CreateKnowledgeDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/knowledge/agentknowledge/CreateKnowledgeDTO.java`

```java
@Data
public class CreateKnowledgeDTO {


	@NotNull(message = "智能体ID不能为空")
	private Integer agentId;


	@NotBlank(message = "知识标题不能为空")
	private String title;


	@NotBlank(message = "知识类型不能为空")
	@InEnum(value = KnowledgeType.class, message = "type只能是DOCUMENT/QA/FAQ 之一")
	private String type;


	private String question;


	private String content;


	private MultipartFile file;


	private String splitterType;

}
```


## UpdateKnowledgeDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/knowledge/agentknowledge/UpdateKnowledgeDTO.java`

```java
@Data
public class UpdateKnowledgeDTO {


	private String title;

	// 不更新question，只更新title和content。question要更新直接创建新的知识

	private String content;

}
```


## CreateBusinessKnowledgeDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/knowledge/businessknowledge/CreateBusinessKnowledgeDTO.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CreateBusinessKnowledgeDTO {

	@NotBlank(message = "Business term cannot be empty")
	private String businessTerm; // Business term

	@NotBlank(message = "Description cannot be empty")
	private String description; // Description

	private String synonyms; // Synonyms, comma separated

	@Builder.Default
	private Boolean isRecall = true; // Whether to recall

	@NotNull(message = "Agent ID cannot be Null")
	private Long agentId; // Associated agent ID

}
```


## UpdateBusinessKnowledgeDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/knowledge/businessknowledge/UpdateBusinessKnowledgeDTO.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UpdateBusinessKnowledgeDTO {

	@NotBlank(message = "Business term cannot be empty")
	private String businessTerm;

	@NotBlank(message = "Description cannot be empty")
	private String description;

	// Synonyms, comma separated
	private String synonyms;

	@NotNull(message = "Agent ID cannot be Null")
	private Long agentId;

}
```


## ModelConfigDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/ModelConfigDTO.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ModelConfigDTO {

	private Integer id;

	@NotBlank(message = "provider must not be empty")
	private String provider; // e.g. "openai", "deepseek"

	private String apiKey; // e.g. "https://api.openai.com"

	@NotBlank(message = "baseUrl must not be empty")
	private String baseUrl;

	@NotBlank(message = "modelName must not be empty")
	private String modelName;

	@NotBlank(message = "modelType must not be empty")
	@InEnum(value = ModelType.class, message = "CHAT/EMBEDDING 之一")
	private String modelType;

	// 仅当厂商路径非标准时填写，例如 "/custom/chat"
	private String completionsPath;

	// 仅当厂商路径非标准时填写
	private String embeddingsPath;

	@Builder.Default
	private Double temperature = 0.0;

	@Builder.Default
	private Integer maxTokens = 2000;

	@Builder.Default
	private Boolean isActive = true;

	// 模型代理配置，默认关闭（使用直连）
	@Builder.Default
	private Boolean proxyEnabled = false;

	private String proxyHost;

	private Integer proxyPort;

	private String proxyUsername;

	private String proxyPassword;

}
```


## ExecutionStep

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/planner/ExecutionStep.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ExecutionStep {

	@JsonProperty("step")
	@JsonPropertyDescription("步骤顺序号")
	private int step;

	@JsonProperty("tool_to_use")
	@JsonPropertyDescription("工具名称")
	private String toolToUse;

	@JsonProperty("tool_parameters")
	@JsonPropertyDescription("工具参数")
	private ToolParameters toolParameters;

	@Data
	@NoArgsConstructor
	@AllArgsConstructor
	// 序列化时忽略 null 值，让生成的 JSON 更干净
	@JsonInclude(JsonInclude.Include.NON_NULL)
	public static class ToolParameters {

		// 统一指令字段：
		// 1. SQL_GENERATE_NODE -> 存当前步骤要做的详细的 SQL 需求
		// 2. PYTHON_GENERATE_NODE -> 存当前步骤要做的详细的编程需求
		@JsonProperty("instruction")
		@JsonPropertyDescription("当工具名称tool_to_use是SQL_GENERATE_NODE时这里的值为 当前步骤要做的详细的 SQL 需求，是PYTHON_GENERATE_NODE时填当前步骤要做的详细的编程需求")
		private String instruction;

		// REPORT_GENERATOR_NODE专用。报告的大纲、需要回答的关键问题和建议方向。
		@JsonProperty("summary_and_recommendations")
		@JsonPropertyDescription("REPORT_GENERATOR_NODE节点专用,仅 REPORT 节点需要此字段，报告的大纲")
		private String summaryAndRecommendations;

		// --- 运行态字段 ---
		// Planner 永远不填这个字段（Prompt里根本不提它）
		// 但是 SQL_GENERATE_NODE 运行完后，会把生成的 SQL 塞进来
		@JsonProperty("sql_query")
		@JsonPropertyDescription("SQL_GENERATE_NODE 运行完后，会把生成的 SQL 塞进来")
		private String sqlQuery;

	}

	@Override
	public String toString() {
		return "ExecutionStep{" + "step=" + step + ", toolToUse='" + toolToUse + '\'' + ", toolParameters="
				+ toolParameters + '}';
	}

}
```


## Plan

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/planner/Plan.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Plan {

	@JsonProperty("thought_process")
	@JsonPropertyDescription("简要描述你的分析思路。必须明确提到你检查了哪些表和字段")
	private String thoughtProcess;

	@JsonProperty("execution_plan")
	@JsonPropertyDescription("执行计划的步骤列表")
	private List<ExecutionStep> executionPlan;

	@Override
	public String toString() {
		return "Plan{" + "thoughtProcess='" + thoughtProcess + '\'' + ", executionPlan=" + executionPlan + '}';
	}

	// 为NL2SQL模式准备的Plan，只走SQL生成，并将实际问题作为步骤指令传给下游。
	public static String nl2SqlPlan(String instruction) {
		if (instruction == null || instruction.isBlank()) {
			throw new IllegalArgumentException("NL2SQL instruction must not be blank");
		}
		ExecutionStep step = new ExecutionStep();
		ExecutionStep.ToolParameters parameters = new ExecutionStep.ToolParameters();
		parameters.setInstruction(instruction);
		step.setStep(1);
		step.setToolToUse(Constant.SQL_GENERATE_NODE);
		step.setToolParameters(parameters);
		Plan plan = new Plan();
		plan.setThoughtProcess("根据问题生成SQL");
		plan.setExecutionPlan(List.of(step));
		try {
			return JsonUtil.getObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(plan);
		}
		catch (JsonProcessingException e) {
			throw new IllegalStateException("Failed to serialize NL2SQL plan", e);
		}
	}

}
```


## EvidenceQueryRewriteDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/EvidenceQueryRewriteDTO.java`

```java
@NoArgsConstructor
@Setter
@Getter
public class EvidenceQueryRewriteDTO {


	@JsonProperty("standalone_query")
	@JsonPropertyDescription("重写后的完整句子")
	private String standaloneQuery;

}
```


## FeasibilityAssessmentOutputDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/FeasibilityAssessmentOutputDTO.java`

```java
@Data
@NoArgsConstructor
public class FeasibilityAssessmentOutputDTO {

	@JsonProperty("requirementType")
	@JsonPropertyDescription("Requirement type: DATA_ANALYSIS, NEED_CLARIFICATION, or FREE_CHAT")
	private RequirementType requirementType;

	@JsonProperty("language")
	@JsonPropertyDescription("Language used for the response, for example zh-CN or en-US")
	private String language;

	@JsonProperty("content")
	@JsonPropertyDescription("Normalized analysis requirement, clarification question, or chat response")
	private String content;

	public enum RequirementType {

		DATA_ANALYSIS,

		NEED_CLARIFICATION,

		FREE_CHAT

	}

}
```


## IntentRecognitionOutputDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/IntentRecognitionOutputDTO.java`

```java
// 对应 模板intent-recognition.txt的输出
@Data
@NoArgsConstructor
public class IntentRecognitionOutputDTO {

	// 意图分类结果，值为"《闲聊或无关指令》"或"《可能的数据分析请求》"
	@JsonProperty("classification")
	@JsonPropertyDescription("意图分类结果，值为：《闲聊或无关指令》或《可能的数据分析请求》")
	private String classification;

	@JsonProperty("response")
	@JsonPropertyDescription("当分类为《闲聊或无关指令》时，直接返回给用户的简短友好答复；数据分析请求返回空字符串")
	private String response;

}
```


## PromptConfigDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/PromptConfigDTO.java`

```java
public record PromptConfigDTO(String id, // Configuration ID (required for update)
		String name, // Configuration name
		String promptType, // Prompt type
		Long agentId, // Associated agent ID, null means global
		String optimizationPrompt, // User-defined system prompt content
		Boolean enabled, // Whether to enable this configuration
		String description, // Configuration description
		String creator, // Creator
		Integer priority, // Configuration priority
		Integer displayOrder // Configuration display order
) {

}
```


## QueryEnhanceOutputDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/QueryEnhanceOutputDTO.java`

```java
// 对应 模板query-enhancement.txt的输出
@Data
@NoArgsConstructor
public class QueryEnhanceOutputDTO {

	// 经LLM重写后的 规范化查询
	@JsonProperty("canonical_query")
	@JsonPropertyDescription("对用户最终意图的单一、清晰的重写，包含绝对时间和解析后的业务术语")
	private String canonicalQuery;

	// 基于canonicalQuery的扩展查询
	@JsonProperty("expanded_queries")
	@JsonPropertyDescription("基于完整信息的扩展问题表述")
	private List<String> expandedQueries;

}
```


## SemanticConsistencyDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/SemanticConsistencyDTO.java`

```java
@AllArgsConstructor
@Builder
@Data
public class SemanticConsistencyDTO {

	private String dialect;

	private String sql;

	private String executionDescription;

	private String schemaInfo;

	private String userQuery;

	private String evidence;

}
```


## SemanticConsistencyOutputDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/SemanticConsistencyOutputDTO.java`

```java
@Data
@NoArgsConstructor
public class SemanticConsistencyOutputDTO {

	@JsonProperty("passed")
	@JsonPropertyDescription("Whether the SQL is semantically consistent with the current execution step")
	private boolean passed;

	@JsonProperty("reason")
	@JsonPropertyDescription("Concise validation result or failure reason")
	private String reason;

}
```


## SqlGenerationDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/prompt/SqlGenerationDTO.java`

```java
@AllArgsConstructor
@Builder
@Data
public class SqlGenerationDTO {

	private String evidence;

	private String query;

	private SchemaDTO schemaDTO;

	private String previousStepResults;

	private String sql;

	private String exceptionMessage;

	private String executionDescription;

	private String dialect;

}
```


## ColumnDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/ColumnDTO.java`

```java
@Data
@NoArgsConstructor
public class ColumnDTO {

	private String name;

	private String description;

	private int enumeration;

	private String range;

	private String type;

	private List<String> data;

	private Map<String, String> mapping;

	@Override
	public String toString() {
		ObjectMapper objectMapper = JsonUtil.getObjectMapper();
		try {
			return objectMapper.writeValueAsString(this);
		}
		catch (JsonProcessingException e) {
			throw new RuntimeException("Failed to convert object to JSON string", e);
		}
	}

}
```


## CreateLogicalRelationDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/CreateLogicalRelationDTO.java`

```java
@Data
public class CreateLogicalRelationDTO {


	@NotBlank(message = "主表名不能为空")
	private String sourceTableName;


	@NotBlank(message = "主表字段名不能为空")
	private String sourceColumnName;


	@NotBlank(message = "关联表名不能为空")
	private String targetTableName;


	@NotBlank(message = "关联表字段名不能为空")
	private String targetColumnName;


	private String relationType;


	private String description;

}
```


## SchemaDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/SchemaDTO.java`

```java
@Data
@NoArgsConstructor
public class SchemaDTO {

	private String name;

	private String description;

	private Integer tableCount;

	private List<TableDTO> table;

	private List<String> foreignKeys;

	@Override
	public String toString() {
		return "SchemaDTO{" + "name='" + name + '\'' + ", description='" + description + '\'' + ", tableCount="
				+ tableCount + ", table=" + table + ", foreignKeys=" + foreignKeys + '}';
	}

}
```


## SemanticModelAddDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/SemanticModelAddDTO.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SemanticModelAddDTO {


	@NotNull(message = "智能体ID不能为空")
	private Long agentId;


	@NotBlank(message = "表名不能为空")
	private String tableName;


	@NotBlank(message = "数据库字段名不能为空")
	private String columnName;


	@NotBlank(message = "业务名称不能为空")
	private String businessName;


	private String synonyms;


	private String businessDescription;


	private String columnComment;


	@NotBlank(message = "数据类型不能为空")
	private String dataType;

}
```


## SemanticModelBatchImportDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/SemanticModelBatchImportDTO.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SemanticModelBatchImportDTO {

	@NotNull(message = "智能体ID不能为空")
	private Long agentId;

	@NotEmpty(message = "导入数据不能为空")
	@Valid
	private List<SemanticModelImportItem> items;

}
```


## SemanticModelImportItem

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/SemanticModelImportItem.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SemanticModelImportItem {

	@NotBlank(message = "表名不能为空")
	@ExcelProperty(value = "表名*", index = 0)
	private String tableName;

	@NotBlank(message = "字段名不能为空")
	@ExcelProperty(value = "字段名*", index = 1)
	private String columnName;

	@NotBlank(message = "业务名称不能为空")
	@ExcelProperty(value = "业务名称*", index = 2)
	private String businessName;

	@ExcelProperty(value = "同义词", index = 4)
	private String synonyms;

	@JsonAlias({ "businessDesc", "description", "desc" })
	@ExcelProperty(value = "业务描述", index = 5)
	private String businessDescription;

	@ExcelProperty(value = "字段注释", index = 6)
	private String columnComment;

	@NotBlank(message = "数据类型不能为空")
	@ExcelProperty(value = "数据类型*", index = 3)
	private String dataType;


	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	@ExcelProperty(value = "创建时间", index = 7)
	private LocalDateTime createTime;

}
```


## TableDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/TableDTO.java`

```java
@Data
@NoArgsConstructor
public class TableDTO {

	private String name;

	private String description;

	private List<ColumnDTO> column = new ArrayList<ColumnDTO>();

	private List<String> primaryKeys;

	@Override
	public String toString() {
		ObjectMapper objectMapper = JsonUtil.getObjectMapper();
		try {
			return objectMapper.writeValueAsString(this);
		}
		catch (JsonProcessingException e) {
			throw new RuntimeException("Failed to convert object to JSON string", e);
		}
	}

}
```


## UpdateLogicalRelationDTO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/schema/UpdateLogicalRelationDTO.java`

```java
@Data
public class UpdateLogicalRelationDTO {


	private String sourceTableName;


	private String sourceColumnName;


	private String targetTableName;


	private String targetColumnName;


	private String relationType;


	private String description;

}
```


## AgentSearchRequest

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/search/AgentSearchRequest.java`

```java
@Data
@Builder
public class AgentSearchRequest implements java.io.Serializable {

	@java.io.Serial
	private static final long serialVersionUID = 1L;

	private String agentId;

	private String docVectorType;

	@Builder.Default
	private Double similarityThreshold = 0.2;

	private String query;

	private Integer topK;

}
```


## HybridSearchRequest

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/dto/search/HybridSearchRequest.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HybridSearchRequest implements Serializable {

	// === 基础参数 ===
	private String query;

	private Integer topK;

	@Builder.Default
	private double similarityThreshold = 0.0;

	private Filter.Expression filterExpression;

	// 向量检索权重
	@Builder.Default
	private Double vectorWeight = 0.5;

	// 关键词检索权重
	@Builder.Default
	private Double keywordWeight = 0.5;

	// 是否开启重排序模型
	@Builder.Default
	private boolean useRerank = false;

	// 扩展参数包将来某种数据库的特有参数
	@Builder.Default
	private Map<String, Object> extraParams = new HashMap<>();

	public org.springframework.ai.vectorstore.SearchRequest toVectorSearchRequest() {
		return org.springframework.ai.vectorstore.SearchRequest.builder()
			.query(this.query)
			.topK(this.topK)
			.similarityThreshold(this.similarityThreshold)
			.filterExpression(this.filterExpression)
			.build();
	}

}
```


## Agent

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/Agent.java`

```java
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Data
public class Agent {

	private Long id;

	private String name; // Agent name

	private String description; // Agent description

	private String avatar; // Avatar URL

	// todo: 改为枚举
	private String status; // Status: draft-pending publication, published-published,
							// offline-offline

	@JsonIgnore
	private String apiKey; // API Key for external access, format sk-xxx

	@Builder.Default
	private Integer apiKeyEnabled = 0; // 0/1 toggle for API access

	private String prompt; // Custom Prompt configuration

	private String category; // Category

	private Long adminId; // Admin ID

	private String tags; // Tags, comma separated

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updateTime;

}
```


## AgentDatasource

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/AgentDatasource.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentDatasource {

	private Integer id;

	private Long agentId;

	private Integer datasourceId;

	private Integer isActive;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime createTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime updateTime;

	// Associated data source object (for joint query)
	private Datasource datasource;

	// 当前数据源选中的表
	private List<String> selectTables;

	public AgentDatasource(Long agentId, Integer datasourceId) {
		this.agentId = agentId;
		this.datasourceId = datasourceId;
		this.isActive = 1;
	}

}
```


## AgentKnowledge

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/AgentKnowledge.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentKnowledge {

	private Integer id;

	private Integer agentId;

	private String title;

	// DOCUMENT, QA, FAQ
	private KnowledgeType type;

	// FAQ QA 问题
	private String question;

	// 当type=QA, FAQ时有内容
	private String content;

	// 业务状态: 1=召回, 0=非召回
	private Integer isRecall;

	// 向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败
	private EmbeddingStatus embeddingStatus;

	// 操作失败的错误信息
	private String errorMsg;

	private String sourceFilename;

	// 文件路径
	private String filePath;

	// 文件大小（字节）
	private Long fileSize;

	// 文件类型
	private String fileType;

	// 分块策略类型：token, recursive
	// 默认值是 token
	private String splitterType;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updatedTime;

	// 0=未删除, 1=已删除
	private Integer isDeleted;

	// 0=物理资源（文件和向量）未清理, 1=物理资源已清理
	// 默认值是 0
	private Integer isResourceCleaned;

}
```


## AgentPresetQuestion

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/AgentPresetQuestion.java`

```java
@Data
@NoArgsConstructor
public class AgentPresetQuestion {

	private Long id;

	private Long agentId;

	private String question;

	private Integer sortOrder;

	private Boolean isActive;

	private LocalDateTime createTime;

	private LocalDateTime updateTime;

	public AgentPresetQuestion(Long agentId, String question, Integer sortOrder) {
		this.agentId = agentId;
		this.question = question;
		this.sortOrder = sortOrder;
		this.isActive = false;
	}

}
```


## BusinessKnowledge

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/BusinessKnowledge.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class BusinessKnowledge {

	private Long id;

	private String businessTerm; // Business term

	private String description; // Description

	private String synonyms; // Synonyms, comma-separated

	@Builder.Default
	private Integer isRecall = 1; // Whether to recall (0: not recall, 1: recall)

	private Long agentId; // Associated agent ID

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updatedTime;

	// 向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败
	private EmbeddingStatus embeddingStatus;

	// 操作失败的错误信息
	private String errorMsg;

	// 0=未删除, 1=已删除
	@Builder.Default
	private Integer isDeleted = 0;

}
```


## ChatMessage

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/ChatMessage.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatMessage {

	private Long id;

	private String sessionId;

	private String role; // user, assistant, system

	private String content;

	private String messageType; // text, sql, result, error

	private String metadata; // JSON格式的元数据

	private LocalDateTime createTime;

}
```


## ChatSession

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/ChatSession.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatSession {

	private String id; // UUID

	private Integer agentId;

	private String title;

	private String status; // active, archived, deleted

	@Builder.Default
	private Boolean isPinned = false; // Whether pinned

	private Long userId;

	private LocalDateTime createTime;

	private LocalDateTime updateTime;

	public ChatSession(String id, Integer agentId, String title, String status, Long userId) {
		this.id = id;
		this.agentId = agentId;
		this.title = title;
		this.status = status;
		this.isPinned = false;
		this.userId = userId;
	}

}
```


## Datasource

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/Datasource.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Datasource {

	private Integer id;

	private String name;

	private String type;

	private String host;

	private Integer port;

	private String databaseName;

	private String username;

	@JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
	private String password;

	@JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
	private String connectionUrl;

	private String status;

	private String testStatus;

	private String description;

	private Long creatorId;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime createTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime updateTime;

	@Override
	public String toString() {
		return "Datasource{" + "id=" + id + ", name='" + name + '\'' + ", type='" + type + '\'' + ", host='" + host
				+ '\'' + ", port=" + port + ", databaseName='" + databaseName + '\'' + ", status='" + status + '\''
				+ ", testStatus='" + testStatus + '\'' + ", createTime=" + createTime + ", updateTime=" + updateTime
				+ '}';
	}

}
```


## LogicalRelation

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/LogicalRelation.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class LogicalRelation {


	private Integer id;


	private Integer datasourceId;


	private String sourceTableName;


	private String sourceColumnName;


	private String targetTableName;


	private String targetColumnName;


	private String relationType;


	private String description;


	private Integer isDeleted;


	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime createdTime;


	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	@DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
	private LocalDateTime updatedTime;

}
```


## ModelConfig

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/ModelConfig.java`

```java
@Data
public class ModelConfig {

	private Integer id;

	// 厂商标识 (方便前端展示回显，实际调用主要靠 baseUrl)
	private String provider;

	// 关键配置
	private String baseUrl;

	private String apiKey;

	private String modelName;

	private Double temperature;

	private Boolean isActive = false;

	private Integer maxTokens;

	// 模型类型
	// 可选值："CHAT", "EMBEDDING"
	private ModelType modelType;

	private String completionsPath;

	private String embeddingsPath;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updatedTime;

	// 0=未删除, 1=已删除
	private Integer isDeleted;

	// ai-proxy设置（默认关闭，使用直连）
	private Boolean proxyEnabled;

	private String proxyHost;

	private Integer proxyPort;

	private String proxyUsername;

	private String proxyPassword;

}
```


## SemanticModel

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/SemanticModel.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SemanticModel {


	private Long id;


	private Long agentId;


	private Integer datasourceId;


	private String tableName;


	private String columnName;


	private String businessName;


	private String synonyms;


	private String businessDescription;


	private String columnComment;


	private String dataType;


	private Integer status;


	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;


	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updateTime;


	public String getPromptInfo() {
		return String.format("业务名称: %s, 表名: %s, 数据库字段名: %s, 字段同义词: %s, 业务描述: %s, 数据类型: %s", businessName, tableName,
				columnName, synonyms, businessDescription, dataType);
	}

}
```


## UserPromptConfig

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/entity/UserPromptConfig.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserPromptConfig {


	private String id;


	private String name;


	private String promptType;


	private Long agentId;


	private String systemPrompt;


	@Builder.Default
	private Boolean enabled = true;


	private String description;


	@Builder.Default
	private Integer priority = 0;


	@Builder.Default
	private Integer displayOrder = 0;


	private LocalDateTime createTime;


	private LocalDateTime updateTime;


	private String creator;

	public String getOptimizationPrompt() {
		return this.systemPrompt;
	}

	public void setOptimizationPrompt(String optimizationPrompt) {
		this.systemPrompt = optimizationPrompt;
	}

}
```


## AgentKnowledgeVO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/AgentKnowledgeVO.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentKnowledgeVO {

	private Integer id;

	private Integer agentId;

	private String title;

	// DOCUMENT, QA, FAQ
	private String type;

	// FAQ QA 问题
	private String question;

	// 当type=QA, FAQ时有内容
	private String content;

	@JsonFormat(shape = JsonFormat.Shape.BOOLEAN)
	private Boolean isRecall;

	// 向量化状态：PENDING待处理，PROCESSING处理中，COMPLETED已完成，FAILED失败
	private EmbeddingStatus embeddingStatus;

	// 操作失败的错误信息
	private String errorMsg;

	// 分块策略类型：token, recursive
	private String splitterType;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updatedTime;

}
```


## ApiKeyResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/ApiKeyResponse.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ApiKeyResponse {

	private String apiKey;

	private Integer apiKeyEnabled;

}
```


## ApiResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/ApiResponse.java`

```java
@Data
@NoArgsConstructor
public class ApiResponse<T> {

	private boolean success;

	private String message;

	private T data;

	public ApiResponse(boolean success, String message) {
		this.success = success;
		this.message = message;
	}

	public ApiResponse(boolean success, String message, T data) {
		this.success = success;
		this.message = message;
		this.data = data;
	}

	public static <T> ApiResponse<T> success(String message) {
		return new ApiResponse<>(true, message);
	}

	public static <T> ApiResponse<T> success(String message, T data) {
		return new ApiResponse<>(true, message, data);
	}

	public static <T> ApiResponse<T> error(String message) {
		return new ApiResponse<>(false, message);
	}

	public static <T> ApiResponse<T> error(String message, T data) {
		return new ApiResponse<>(false, message, data);
	}

}
```


## BatchImportResult

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/BatchImportResult.java`

```java
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BatchImportResult {

	private int total;

	private int successCount;

	private int failCount;

	@Builder.Default
	private List<String> errors = new ArrayList<>();

	public void addError(String error) {
		if (errors == null) {
			errors = new ArrayList<>();
		}
		errors.add(error);
	}

}
```


## BusinessKnowledgeVO

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/BusinessKnowledgeVO.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class BusinessKnowledgeVO {

	private Long id;

	private String businessTerm;

	private String description;

	private String synonyms;

	@JsonFormat(shape = JsonFormat.Shape.BOOLEAN)
	private Boolean isRecall;

	private Long agentId;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime createdTime;

	@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
	private LocalDateTime updatedTime;

	private String embeddingStatus;

	// 操作失败的错误信息
	private String errorMsg;

}
```


## ChatResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/ChatResponse.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ChatResponse {

	private String sessionId;

	private String message;

	private String messageType; // text, sql, result, error

	private String sql; // Generated SQL statement

	private Object result; // Query result

	private String error; // Error message

	public ChatResponse(String sessionId, String message, String messageType) {
		this.sessionId = sessionId;
		this.message = message;
		this.messageType = messageType;
	}

}
```


## GraphNodeResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/GraphNodeResponse.java`

```java
@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class GraphNodeResponse {

	private String agentId;

	private String threadId;

	@Builder.Default
	private GraphEventType eventType = GraphEventType.NODE_OUTPUT;

	private String stepId;

	private Integer attempt;

	// 使用Constant常量
	private String nodeName;

	private TextType textType;

	private String text;

	@Builder.Default
	private boolean error = false;

	@Builder.Default
	private boolean complete = false;

	public static GraphNodeResponse error(String agentId, String threadId, String text) {
		return GraphNodeResponse.builder()
			.agentId(agentId)
			.threadId(threadId)
			.text(text)
			.error(true)
			.textType(TextType.TEXT)
			.build();
	}

	public static GraphNodeResponse complete(String agentId, String threadId) {
		return GraphNodeResponse.builder()
			.agentId(agentId)
			.threadId(threadId)
			.complete(true)
			.textType(TextType.TEXT)
			.build();
	}

	public static GraphNodeResponse finalAnswer(String agentId, String threadId, String text) {
		return GraphNodeResponse.builder()
			.agentId(agentId)
			.threadId(threadId)
			.eventType(GraphEventType.FINAL_ANSWER)
			.textType(TextType.TEXT)
			.text(text)
			.build();
	}

}
```


## ModelCheckVo

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/ModelCheckVo.java`

```java
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class ModelCheckVo {

	boolean chatModelReady;

	boolean embeddingModelReady;

	boolean ready;

}
```


## PageResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/PageResponse.java`

```java
@Data
@NoArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class PageResponse<T> extends ApiResponse<T> {


	private Long total;


	private Integer pageNum;


	private Integer pageSize;


	private Integer totalPages;

	public PageResponse(boolean success, String message) {
		super(success, message);
	}

	@SuppressWarnings("unchecked")
	public PageResponse(boolean success, String message, T data) {
		super(success, message, data);
	}

	@SuppressWarnings("unchecked")
	public PageResponse(boolean success, String message, T data, Long total, Integer pageNum, Integer pageSize,
			Integer totalPages) {
		super(success, message, data);
		this.total = total;
		this.pageNum = pageNum;
		this.pageSize = pageSize;
		this.totalPages = totalPages;
	}

	public static <T> PageResponse<T> success(T data, Long total, Integer pageNum, Integer pageSize,
			Integer totalPages) {
		return new PageResponse<>(true, "查询成功", data, total, pageNum, pageSize, totalPages);
	}

	public static <T> PageResponse<T> success(String message, T data, Long total, Integer pageNum, Integer pageSize,
			Integer totalPages) {
		return new PageResponse<>(true, message, data, total, pageNum, pageSize, totalPages);
	}

	public static <T> PageResponse<T> pageError(String message) {
		return new PageResponse<>(false, message);
	}

	public static <T> PageResponse<T> pageError(String message, T data) {
		return new PageResponse<>(false, message, data);
	}

}
```


## PageResult

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/PageResult.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PageResult<T> {


	private List<T> data;


	private Long total;


	private Integer pageNum;


	private Integer pageSize;


	private Integer totalPages;


	public void calculateTotalPages() {
		if (this.total != null && this.pageSize != null && this.pageSize > 0) {
			this.totalPages = (int) Math.ceil((double) this.total / this.pageSize);
		}
		else {
			this.totalPages = 0;
		}
	}

}
```


## SessionUpdateEvent

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/SessionUpdateEvent.java`

```java
@Value
@Builder
public class SessionUpdateEvent {

	public static final String TYPE_TITLE_UPDATED = "title-updated";

	String type;

	String sessionId;

	String title;

	public static SessionUpdateEvent titleUpdated(String sessionId, String title) {
		return SessionUpdateEvent.builder().type(TYPE_TITLE_UPDATED).sessionId(sessionId).title(title).build();
	}

}
```


## UploadResponse

来源 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/vo/UploadResponse.java`

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UploadResponse {

	private boolean success;

	private String message;

	private String url;

	private String filename;

	public static UploadResponse ok(String message, String url, String filename) {
		UploadResponse r = new UploadResponse();
		r.setSuccess(true);
		r.setMessage(message);
		r.setUrl(url);
		r.setFilename(filename);
		return r;
	}

	public static UploadResponse error(String message) {
		UploadResponse r = new UploadResponse();
		r.setSuccess(false);
		r.setMessage(message);
		return r;
	}

}
```
