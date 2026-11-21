# DTO、实体及响应字段基线

下表记录上游类型声明中的字段名，便于核对接口兼容。请求与响应约定见 [接口契约矩阵](http-contracts.md)。

| 类型 | 字段 |
| --- | --- |
| `ChatMessageDTO` | `role`, `content`, `messageType`, `metadata`, `titleNeeded` |
| `DatasourceTypeDTO` | `code`, `typeName`, `dialect`, `protocol`, `displayName` |
| `SchemaInitRequest` | `dbConfig`, `tables` |
| `SqlRetryDto` | — |
| `ToggleDatasourceDTO` | `datasourceId`, `isActive` |
| `UpdateDatasourceTablesDTO` | `datasourceId`, `tables` |
| `GraphRequest` | `agentId`, `conversationId`, `threadId`, `query`, `humanFeedback`, `humanFeedbackContent`, `rejectedPlan`, `nl2sqlOnly` |
| `AgentKnowledgeQueryDTO` | `agentId`, `title`, `type`, `embeddingStatus`, `pageNum`, `pageSize` |
| `CreateKnowledgeDTO` | `agentId`, `title`, `type`, `question`, `content`, `file`, `splitterType` |
| `UpdateKnowledgeDTO` | `title`, `content` |
| `CreateBusinessKnowledgeDTO` | `businessTerm`, `description`, `synonyms`, `isRecall`, `agentId` |
| `UpdateBusinessKnowledgeDTO` | `businessTerm`, `description`, `synonyms`, `agentId` |
| `ModelConfigDTO` | `id`, `provider`, `apiKey`, `baseUrl`, `modelName`, `modelType`, `completionsPath`, `embeddingsPath`, `temperature`, `maxTokens`, `isActive`, `proxyEnabled`, `proxyHost`, `proxyPort`, `proxyUsername`, `proxyPassword` |
| `ExecutionStep` | `step`, `toolToUse`, `toolParameters`, `instruction`, `summaryAndRecommendations`, `sqlQuery` |
| `Plan` | `thoughtProcess`, `executionPlan` |
| `EvidenceQueryRewriteDTO` | `standaloneQuery` |
| `FeasibilityAssessmentOutputDTO` | `requirementType`, `language`, `content` |
| `IntentRecognitionOutputDTO` | `classification`, `response` |
| `PromptConfigDTO` | — |
| `QueryEnhanceOutputDTO` | `canonicalQuery`, `expandedQueries` |
| `SemanticConsistencyDTO` | `dialect`, `sql`, `executionDescription`, `schemaInfo`, `userQuery`, `evidence` |
| `SemanticConsistencyOutputDTO` | `passed`, `reason` |
| `SqlGenerationDTO` | `evidence`, `query`, `schemaDTO`, `previousStepResults`, `sql`, `exceptionMessage`, `executionDescription`, `dialect` |
| `ColumnDTO` | `name`, `description`, `enumeration`, `range`, `type`, `data`, `mapping` |
| `CreateLogicalRelationDTO` | `sourceTableName`, `sourceColumnName`, `targetTableName`, `targetColumnName`, `relationType`, `description` |
| `SchemaDTO` | `name`, `description`, `tableCount`, `table`, `foreignKeys` |
| `SemanticModelAddDTO` | `agentId`, `tableName`, `columnName`, `businessName`, `synonyms`, `businessDescription`, `columnComment`, `dataType` |
| `SemanticModelBatchImportDTO` | `agentId`, `items` |
| `SemanticModelImportItem` | `tableName`, `columnName`, `businessName`, `synonyms`, `businessDescription`, `columnComment`, `dataType`, `createTime` |
| `TableDTO` | `name`, `description`, `column`, `primaryKeys` |
| `UpdateLogicalRelationDTO` | `sourceTableName`, `sourceColumnName`, `targetTableName`, `targetColumnName`, `relationType`, `description` |
| `AgentSearchRequest` | `agentId`, `docVectorType`, `similarityThreshold`, `query`, `topK` |
| `HybridSearchRequest` | `query`, `topK`, `similarityThreshold`, `filterExpression`, `vectorWeight`, `keywordWeight`, `useRerank`, `extraParams` |
| `Agent` | `id`, `name`, `description`, `avatar`, `status`, `apiKey`, `apiKeyEnabled`, `prompt`, `category`, `adminId`, `tags`, `createTime`, `updateTime` |
| `AgentDatasource` | `id`, `agentId`, `datasourceId`, `isActive`, `createTime`, `updateTime`, `datasource`, `selectTables` |
| `AgentKnowledge` | `id`, `agentId`, `title`, `type`, `question`, `content`, `isRecall`, `embeddingStatus`, `errorMsg`, `sourceFilename`, `filePath`, `fileSize`, `fileType`, `splitterType`, `createdTime`, `updatedTime`, `isDeleted`, `isResourceCleaned` |
| `AgentPresetQuestion` | `id`, `agentId`, `question`, `sortOrder`, `isActive`, `createTime`, `updateTime` |
| `BusinessKnowledge` | `id`, `businessTerm`, `description`, `synonyms`, `isRecall`, `agentId`, `createdTime`, `updatedTime`, `embeddingStatus`, `errorMsg`, `isDeleted` |
| `ChatMessage` | `id`, `sessionId`, `role`, `content`, `messageType`, `metadata`, `createTime` |
| `ChatSession` | `id`, `agentId`, `title`, `status`, `isPinned`, `userId`, `createTime`, `updateTime` |
| `Datasource` | `id`, `name`, `type`, `host`, `port`, `databaseName`, `username`, `password`, `connectionUrl`, `status`, `testStatus`, `description`, `creatorId`, `createTime`, `updateTime` |
| `LogicalRelation` | `id`, `datasourceId`, `sourceTableName`, `sourceColumnName`, `targetTableName`, `targetColumnName`, `relationType`, `description`, `isDeleted`, `createdTime`, `updatedTime` |
| `ModelConfig` | `id`, `provider`, `baseUrl`, `apiKey`, `modelName`, `temperature`, `isActive`, `maxTokens`, `modelType`, `completionsPath`, `embeddingsPath`, `createdTime`, `updatedTime`, `isDeleted`, `proxyEnabled`, `proxyHost`, `proxyPort`, `proxyUsername`, `proxyPassword` |
| `SemanticModel` | `id`, `agentId`, `datasourceId`, `tableName`, `columnName`, `businessName`, `synonyms`, `businessDescription`, `columnComment`, `dataType`, `status`, `createdTime`, `updateTime` |
| `UserPromptConfig` | `id`, `name`, `promptType`, `agentId`, `systemPrompt`, `enabled`, `description`, `priority`, `displayOrder`, `createTime`, `updateTime`, `creator` |
| `AgentKnowledgeVO` | `id`, `agentId`, `title`, `type`, `question`, `content`, `isRecall`, `embeddingStatus`, `errorMsg`, `splitterType`, `createdTime`, `updatedTime` |
| `ApiKeyResponse` | `apiKey`, `apiKeyEnabled` |
| `ApiResponse` | `success`, `message`, `data` |
| `BatchImportResult` | `total`, `successCount`, `failCount`, `errors` |
| `BusinessKnowledgeVO` | `id`, `businessTerm`, `description`, `synonyms`, `isRecall`, `agentId`, `createdTime`, `updatedTime`, `embeddingStatus`, `errorMsg` |
| `ChatResponse` | `sessionId`, `message`, `messageType`, `sql`, `result`, `error` |
| `GraphNodeResponse` | `agentId`, `threadId`, `eventType`, `stepId`, `attempt`, `nodeName`, `textType`, `text`, `error`, `complete` |
| `ModelCheckVo` | — |
| `PageResponse` | `total`, `pageNum`, `pageSize`, `totalPages` |
| `PageResult` | `data`, `total`, `pageNum`, `pageSize`, `totalPages` |
| `SessionUpdateEvent` | — |
| `UploadResponse` | `success`, `message`, `url`, `filename` |
