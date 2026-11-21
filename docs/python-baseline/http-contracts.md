# 98 个接口契约矩阵

由 `PYTHON/tools/build_baseline.py` 从当前 JAVA 源码重建。编号对应原清单；主交付归属按当前 01–09 本地任务索引维护。01–07 已交付，08 实施中，最终逐接口/真实副作用验收由 09 汇总；本源码矩阵本身不证明运行时兼容。

参数栏保留完整绑定注解：PathVariable=路径，RequestParam=查询，RequestBody=JSON，RequestPart=multipart；required 未写默认为 true，required=false 的引用类型默认为 null、boolean 为 false。defaultValue 如实保留。DTO 字段/校验/初值见 [schema catalog](schemas.md)。返回类型中的泛型是准确响应包裹，Map 的具体字段见逐接口返回分支。

Python 绑定/验证错误约定 HTTP 400；Java GlobalExceptionHandler 的 generic Exception 分支为 500，见下方完整源码，属于显式差异。管理接口未增加鉴权（开放本机管理）；search 使用当前 Agent key，Python 的 stop/标题/运行扩展增加同样鉴权，详见 [公共协议](../python-runtime-contract.md)。全局异常分支和逐路由返回分支附后，不能把 ApiResponse.error 的 HTTP 200 当成功。日期/字段别名以 schema catalog 注解为准，null 保留，分页字段不得更名。

|编号|方法/路径|Ticket / Python状态|参数与DTO|响应类型|HTTP/错误|鉴权|业务效果入口|前端消费|
|---:|---|---|---|---|---|---|---|---|
|1|GET `/api/agent/list`|02 / 已交付；最终验收见09|`@RequestParam(value = "status", required = false) String status, @RequestParam(value = "keyword", required = false) String keyword`|`List<Agent>`|200|无（本机管理）|agentService.findAll; agentService.findByStatus; agentService.search|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|2|GET `/api/agent/{id}`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`Agent`|200/404|无（本机管理）|get|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|3|POST `/api/agent`|02 / 已交付；最终验收见09|`@RequestBody Agent agent`|`Agent`|200|无（本机管理）|agentService.save|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|4|PUT `/api/agent/{id}`|02 / 已交付；最终验收见09|`@PathVariable Long id, @RequestBody Agent agent`|`Agent`|200/404|无（本机管理）|agentService.save|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|5|DELETE `/api/agent/{id}`|08 / 实施中；待最终验收|`@PathVariable Long id`|`void`|200/404|无（本机管理）|agentService.deleteById|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|6|POST `/api/agent/{id}/publish`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`Agent`|200/404|无（本机管理）|agentService.save|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|7|POST `/api/agent/{id}/offline`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`Agent`|200/404|无（本机管理）|agentService.save|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|8|GET `/api/agent/{id}/api-key`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`ApiResponse<ApiKeyResponse>`|200/404; 200 success=false 业务错误|无（本机管理）|agentService.getApiKeyMasked|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|9|POST `/api/agent/{id}/api-key/generate`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`ApiResponse<ApiKeyResponse>`|200/404; 200 success=false 业务错误|无（本机管理）|agentService.generateApiKey|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|10|POST `/api/agent/{id}/api-key/reset`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`ApiResponse<ApiKeyResponse>`|200/404; 200 success=false 业务错误|无（本机管理）|agentService.resetApiKey|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|11|DELETE `/api/agent/{id}/api-key`|02 / 已交付；最终验收见09|`@PathVariable Long id`|`ApiResponse<ApiKeyResponse>`|200/404; 200 success=false 业务错误|无（本机管理）|agentService.deleteApiKey|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|12|POST `/api/agent/{id}/api-key/enable`|02 / 已交付；最终验收见09|`@PathVariable Long id, @RequestParam("enabled") boolean enabled`|`ApiResponse<ApiKeyResponse>`|200/404; 200 success=false 业务错误|无（本机管理）|agentService.toggleApiKey|[services/agent](../../JAVA/data-agent-frontend-nuxt/app/services/agent/index.ts)|
|13|POST `/api/agent/{agentId}/datasources/init`|02 / 已交付；最终验收见09|`@PathVariable Long agentId`|`ApiResponse<?>`|200/400/500; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.getCurrentAgentDatasource; agentDatasourceService.initializeSchemaForAgentWithDatasource|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|14|GET `/api/agent/{agentId}/datasources`|02 / 已交付；最终验收见09|`@PathVariable Long agentId`|`ApiResponse<List<AgentDatasource>>`|200/400; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.getAgentDatasource|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|15|GET `/api/agent/{agentId}/datasources/active`|02 / 已交付；最终验收见09|`@PathVariable Long agentId`|`ApiResponse<AgentDatasource>`|200/400; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.getCurrentAgentDatasource|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|16|POST `/api/agent/{agentId}/datasources/{datasourceId}`|02 / 已交付；最终验收见09|`@PathVariable Long agentId, @PathVariable Integer datasourceId`|`ApiResponse<AgentDatasource>`|200/400/500; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.addDatasourceToAgent|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|17|POST `/api/agent/{agentId}/datasources/tables`|02 / 已交付；最终验收见09|`@PathVariable Long agentId, @RequestBody @Validated UpdateDatasourceTablesDTO dto`|`ApiResponse<?>`|200/500; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.updateDatasourceTables|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|18|DELETE `/api/agent/{agentId}/datasources/{datasourceId}`|02 / 已交付；最终验收见09|`@PathVariable Long agentId, @PathVariable Integer datasourceId`|`ApiResponse<?>`|200/500; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.removeDatasourceFromAgent|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|19|PUT `/api/agent/{agentId}/datasources/toggle`|02 / 已交付；最终验收见09|`@PathVariable Long agentId, @RequestBody ToggleDatasourceDTO dto`|`ApiResponse<AgentDatasource>`|200/400/500; 200 success=false 业务错误|无（本机管理）|agentDatasourceService.toggleDatasourceForAgent|[services/agentDatasource](../../JAVA/data-agent-frontend-nuxt/app/services/agentDatasource/index.ts)|
|20|GET `/api/agent-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable("id") Integer id`|`ApiResponse<AgentKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.getKnowledgeById|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|21|POST `/api/agent-knowledge/create`|06 / 已交付；最终验收见09|`@RequestPart("agentId") String agentId, @RequestPart("title") String title, @RequestPart("type") String type, @RequestPart(value = "question", required = false) String question, @RequestPart(value = "content", required = false) String content, @RequestPart(value = "file", required = false) FilePart filePart, @RequestPart(value = "splitterType", required = false) String splitterType`|`Mono<ApiResponse<AgentKnowledgeVO>>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.createKnowledge|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|22|PUT `/api/agent-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable("id") Integer id, @RequestBody UpdateKnowledgeDTO updateKnowledgeDto`|`ApiResponse<AgentKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.updateKnowledge|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|23|PUT `/api/agent-knowledge/recall/{id}`|06 / 已交付；最终验收见09|`@PathVariable Integer id, @RequestParam(value = "isRecall") Boolean isRecall`|`ApiResponse<AgentKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.updateKnowledgeRecallStatus|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|24|DELETE `/api/agent-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable("id") Integer id`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.deleteKnowledge|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|25|POST `/api/agent-knowledge/query/page`|06 / 已交付；最终验收见09|`@Valid @RequestBody AgentKnowledgeQueryDTO queryDTO`|`PageResponse<List<AgentKnowledgeVO>>`|200|无（本机管理）|agentKnowledgeService.queryByConditionsWithPage|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|26|POST `/api/agent-knowledge/retry-embedding/{id}`|06 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse<AgentKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|agentKnowledgeService.retryEmbedding|[services/agentKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/agentKnowledge/index.ts)|
|27|GET `/api/agent/{agentId}/preset-questions`|02 / 已交付；最终验收见09|`@PathVariable(value = "agentId") Long agentId`|`ResponseEntity<List<AgentPresetQuestion>>`|200/500|无（本机管理）|presetQuestionService.findAllByAgentId|[services/presetQuestion](../../JAVA/data-agent-frontend-nuxt/app/services/presetQuestion/index.ts)|
|28|POST `/api/agent/{agentId}/preset-questions`|02 / 已交付；最终验收见09|`@PathVariable(value = "agentId") Long agentId, @RequestBody List<Map<String, Object>> questionsData`|`ResponseEntity<Map<String, String>>`|200/500; 200 success=false 业务错误|无（本机管理）|presetQuestionService.batchSave|[services/presetQuestion](../../JAVA/data-agent-frontend-nuxt/app/services/presetQuestion/index.ts)|
|29|DELETE `/api/agent/{agentId}/preset-questions/{questionId}`|02 / 已交付；最终验收见09|`@PathVariable(value = "agentId") Long agentId, @PathVariable Long questionId`|`ResponseEntity<Map<String, String>>`|200/500; 200 success=false 业务错误|无（本机管理）|presetQuestionService.deleteById|[services/presetQuestion](../../JAVA/data-agent-frontend-nuxt/app/services/presetQuestion/index.ts)|
|30|GET `/api/business-knowledge`|06 / 已交付；最终验收见09|`@RequestParam(value = "agentId") String agentIdStr, @RequestParam(value = "keyword", required = false) String keyword`|`ApiResponse<List<BusinessKnowledgeVO>>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.getKnowledge; businessKnowledgeService.searchKnowledge|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|31|GET `/api/business-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id`|`ApiResponse<BusinessKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.getKnowledgeById|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|32|POST `/api/business-knowledge`|06 / 已交付；最终验收见09|`@RequestBody @Validated CreateBusinessKnowledgeDTO knowledge`|`ApiResponse<BusinessKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.addKnowledge|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|33|PUT `/api/business-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id, @RequestBody UpdateBusinessKnowledgeDTO knowledge`|`ApiResponse<BusinessKnowledgeVO>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.updateKnowledge|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|34|DELETE `/api/business-knowledge/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.deleteKnowledge; businessKnowledgeService.getKnowledgeById|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|35|POST `/api/business-knowledge/recall/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id, @RequestParam(value = "isRecall") Boolean isRecall`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.recallKnowledge|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|36|POST `/api/business-knowledge/refresh-vector-store`|06 / 已交付；最终验收见09|`@RequestParam(value = "agentId") String agentId`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.refreshAllKnowledgeToVectorStore|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|37|POST `/api/business-knowledge/retry-embedding/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|businessKnowledgeService.retryEmbedding|[services/businessKnowledge](../../JAVA/data-agent-frontend-nuxt/app/services/businessKnowledge/index.ts)|
|38|GET `/api/agent/{id}/sessions`|03 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer id`|`ResponseEntity<List<ChatSession>>`|200|无（本机管理）|chatSessionService.findByAgentId|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|39|POST `/api/agent/{id}/sessions`|03 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer id, @RequestBody(required = false) Map<String, Object> request`|`ResponseEntity<ChatSession>`|200|无（本机管理）|chatSessionService.createSession|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|40|DELETE `/api/agent/{id}/sessions`|08 / 实施中；待最终验收|`@PathVariable(value = "id") Integer id`|`ResponseEntity<ApiResponse>`|200; 200 success=false 业务错误|Java 无；Python 增加 Agent key/401|chatSessionService.clearSessionsByAgentId|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|41|GET `/api/sessions/{sessionId}/messages`|05 / 已交付；最终验收见09|`@PathVariable(value = "sessionId") String sessionId`|`ResponseEntity<List<ChatMessage>>`|200|Java 无；Python 增加 Agent key/401|chatMessageService.findBySessionId|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|42|POST `/api/sessions/{sessionId}/messages`|05 / 已交付；最终验收见09|`@PathVariable(value = "sessionId") String sessionId, @RequestBody ChatMessageDTO request`|`ResponseEntity<ChatMessage>`|200/400/500|Java 无；Python 增加 Agent key/401|chatMessageService.saveMessage; chatSessionService.updateSessionTime; sessionTitleService.scheduleTitleGeneration|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|43|PUT `/api/sessions/{sessionId}/pin`|05 / 已交付；最终验收见09|`@PathVariable(value = "sessionId") String sessionId, @RequestParam(value = "isPinned") Boolean isPinned`|`ResponseEntity<ApiResponse>`|200/500; 200 success=false 业务错误|Java 无；Python 增加 Agent key/401|chatSessionService.pinSession|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|44|PUT `/api/sessions/{sessionId}/rename`|05 / 已交付；最终验收见09|`@PathVariable(value = "sessionId") String sessionId, @RequestParam(value = "title") String title`|`ResponseEntity<ApiResponse>`|200/400/500; 200 success=false 业务错误|Java 无；Python 增加 Agent key/401|chatSessionService.renameSession|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|45|DELETE `/api/sessions/{sessionId}`|08 / 实施中；待最终验收|`@PathVariable(value = "sessionId") String sessionId`|`ResponseEntity<ApiResponse>`|200/500; 200 success=false 业务错误|Java 无；Python 增加 Agent key/401|chatSessionService.deleteSession|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|46|POST `/api/sessions/{sessionId}/reports/html`|07 / 已交付；最终验收见09|`@PathVariable(value = "sessionId") String sessionId, @RequestBody String content`|`ResponseEntity<byte[]>`|200/400/500|Java 无；Python 增加 Agent key/401|reportTemplateUtil.getFooter; reportTemplateUtil.getHeader|[services/chat](../../JAVA/data-agent-frontend-nuxt/app/services/chat/index.ts)|
|47|GET `/api/datasource/types`|02 / 已交付；最终验收见09|`无`|`ApiResponse<List<DatasourceTypeDTO>>`|200; 200 success=false 业务错误|无（本机管理）|getDatasourceTypes|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|48|GET `/api/datasource`|02 / 已交付；最终验收见09|`@RequestParam(value = "status", required = false) String status, @RequestParam(value = "type", required = false) String type`|`List<Datasource>`|200|无（本机管理）|datasourceService.getAllDatasource; datasourceService.getDatasourceByStatus; datasourceService.getDatasourceByType|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|49|GET `/api/datasource/{id}`|02 / 已交付；最终验收见09|`@PathVariable Integer id`|`Datasource`|200/404|无（本机管理）|getDatasourceById|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|50|GET `/api/datasource/{id}/tables`|02 / 已交付；最终验收见09|`@PathVariable Integer id`|`List<String>`|200/404/500|无（本机管理）|datasourceService.getDatasourceTables|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|51|POST `/api/datasource`|02 / 已交付；最终验收见09|`@RequestBody Datasource datasource`|`Datasource`|200/500|无（本机管理）|datasourceService.createDatasource|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|52|PUT `/api/datasource/{id}`|02 / 已交付；最终验收见09|`@PathVariable Integer id, @RequestBody Datasource datasource`|`Datasource`|200/404/500|无（本机管理）|datasourceService.updateDatasource|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|53|DELETE `/api/datasource/{id}`|02 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse`|200/400/404/500; 200 success=false 业务错误|无（本机管理）|datasourceService.deleteDatasource|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|54|POST `/api/datasource/{id}/test`|02 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.testConnection|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|55|GET `/api/datasource/{id}/tables/{tableName}/columns`|02 / 已交付；最终验收见09|`@PathVariable Integer id, @PathVariable String tableName`|`ApiResponse<List<String>>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.getTableColumns|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|56|GET `/api/datasource/{id}/logical-relations`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer datasourceId`|`ApiResponse<List<LogicalRelation>>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.getLogicalRelations|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|57|POST `/api/datasource/{id}/logical-relations`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer datasourceId, @Valid @RequestBody CreateLogicalRelationDTO dto`|`ApiResponse<LogicalRelation>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.addLogicalRelation|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|58|PUT `/api/datasource/{id}/logical-relations/{relationId}`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer datasourceId, @PathVariable Integer relationId, @RequestBody UpdateLogicalRelationDTO dto`|`ApiResponse<LogicalRelation>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.updateLogicalRelation|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|59|DELETE `/api/datasource/{id}/logical-relations/{relationId}`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer datasourceId, @PathVariable Integer relationId`|`ApiResponse<Void>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.deleteLogicalRelation|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|60|PUT `/api/datasource/{id}/logical-relations`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") Integer datasourceId, @RequestBody List<LogicalRelation> logicalRelations`|`ApiResponse<List<LogicalRelation>>`|200/500; 200 success=false 业务错误|无（本机管理）|datasourceService.saveLogicalRelations|[services/datasource](../../JAVA/data-agent-frontend-nuxt/app/services/datasource/index.ts)|
|61|GET `/echo/ok`|01 / 已交付；最终验收见09|`无`|`String`|200|无（本机管理）|只读健康检查|无（运维探活）|
|62|POST `/api/upload/avatar`|06 / 已交付；最终验收见09|`@RequestPart("file") FilePart file`|`Mono<ResponseEntity<UploadResponse>>`|200/400/500|无（本机管理）|fileStorageService.getFileUrl; fileStorageService.storeFile|[services/fileUpload](../../JAVA/data-agent-frontend-nuxt/app/services/fileUpload/index.ts)|
|63|GET `/api/upload/**`|06 / 已交付；最终验收见09|`ServerHttpRequest request`|`ResponseEntity<byte[]>`|200/400/403/404/500|无（本机管理）|getFile|[services/fileUpload](../../JAVA/data-agent-frontend-nuxt/app/services/fileUpload/index.ts)|
|64|GET `/api/stream/search`|03 / 已交付；最终验收见09|`@RequestParam("agentId") String agentId, @RequestParam(value = "conversationId", required = false) String conversationId, @RequestParam(value = "threadId", required = false) String threadId, @RequestParam("query") String query, @RequestParam(value = "humanFeedback", required = false) boolean humanFeedback, @RequestParam(value = "humanFeedbackContent", required = false) String humanFeedbackContent, @RequestParam(value = "rejectedPlan", required = false) boolean rejectedPlan, @RequestParam(value = "nl2sqlOnly", required = false) boolean nl2sqlOnly, ServerHttpResponse response`|`Flux<ServerSentEvent<GraphNodeResponse>>`|200|Java Agent key；401|graphService.graphStreamProcess; graphService.stopStreamProcessing|[services/graph](../../JAVA/data-agent-frontend-nuxt/app/services/graph/index.ts)|
|65|POST `/api/stream/stop`|08 / 实施中；待最终验收|`@RequestParam("conversationId") String conversationId, @RequestParam(value = "threadId", required = false) String threadId`|`ResponseEntity<Void>`|204|Java 无；Python 增加 Agent key/401|graphService.stopStreamProcessing; graphService.stopStreamProcessingByConversationId|[services/graph](../../JAVA/data-agent-frontend-nuxt/app/services/graph/index.ts)|
|66|GET `/api/model-config/list`|01 / 已交付；最终验收见09|`无`|`ApiResponse<List<ModelConfigDTO>>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigDataService.listConfigs|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|67|POST `/api/model-config/add`|01 / 已交付；最终验收见09|`@Valid @RequestBody ModelConfigDTO config`|`ApiResponse<String>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigDataService.addConfig|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|68|PUT `/api/model-config/update`|01 / 已交付；最终验收见09|`@Valid @RequestBody ModelConfigDTO config`|`ApiResponse<String>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigOpsService.updateAndRefresh|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|69|DELETE `/api/model-config/{id}`|01 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse<String>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigDataService.deleteConfig|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|70|POST `/api/model-config/activate/{id}`|01 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse<String>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigOpsService.activateConfig|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|71|POST `/api/model-config/test/{id}`|01 / 已交付；最终验收见09|`@PathVariable Integer id`|`ApiResponse<String>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigOpsService.testConnection|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|72|GET `/api/model-config/check-ready`|01 / 已交付；最终验收见09|`无`|`ApiResponse<ModelCheckVo>`|200; 200 success=false 业务错误|无（本机管理）|modelConfigDataService.getActiveConfigByType|[services/modelConfig](../../JAVA/data-agent-frontend-nuxt/app/services/modelConfig/index.ts)|
|73|POST `/api/prompt-config/save`|04 / 已交付；最终验收见09|`@RequestBody PromptConfigDTO configDTO`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.saveOrUpdateConfig|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|74|GET `/api/prompt-config/{id}`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.getConfigById|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|75|GET `/api/prompt-config/list`|04 / 已交付；最终验收见09|`无`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.getAllConfigs|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|76|GET `/api/prompt-config/list-by-type/{promptType}`|04 / 已交付；最终验收见09|`@PathVariable(value = "promptType") String promptType, @RequestParam(value = "agentId", required = false) Long agentId`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.getConfigsByType|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|77|GET `/api/prompt-config/active/{promptType}`|04 / 已交付；最终验收见09|`@PathVariable(value = "promptType") String promptType, @RequestParam(value = "agentId", required = false) Long agentId`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.getActiveConfigByType|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|78|GET `/api/prompt-config/active-all/{promptType}`|04 / 已交付；最终验收见09|`@PathVariable(value = "promptType") String promptType, @RequestParam(value = "agentId", required = false) Long agentId`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.getActiveConfigsByType|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|79|DELETE `/api/prompt-config/{id}`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.deleteConfig|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|80|POST `/api/prompt-config/{id}/enable`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.enableConfig|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|81|POST `/api/prompt-config/{id}/disable`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.disableConfig|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|82|GET `/api/prompt-config/types`|04 / 已交付；最终验收见09|`无`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|getSupportedPromptTypes|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|83|POST `/api/prompt-config/batch-enable`|04 / 已交付；最终验收见09|`@RequestBody List<String> ids`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.enableConfigs|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|84|POST `/api/prompt-config/batch-disable`|04 / 已交付；最终验收见09|`@RequestBody List<String> ids`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.disableConfigs|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|85|POST `/api/prompt-config/{id}/priority`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id, @RequestBody Map<String, Object> requestBody`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.updatePriority|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|86|POST `/api/prompt-config/{id}/display-order`|04 / 已交付；最终验收见09|`@PathVariable(value = "id") String id, @RequestBody Map<String, Object> requestBody`|`ResponseEntity<Map<String, Object>>`|200; 200 success=false 业务错误|无（本机管理）|promptConfigService.updateDisplayOrder|[services/prompt](../../JAVA/data-agent-frontend-nuxt/app/services/prompt/index.ts)|
|87|GET `/api/semantic-model`|06 / 已交付；最终验收见09|`@RequestParam(value = "keyword", required = false) String keyword, @RequestParam(value = "agentId", required = false) Long agentId`|`ApiResponse<List<SemanticModel>>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.getAll; semanticModelService.getByAgentId; semanticModelService.search|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|88|GET `/api/semantic-model/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id`|`ApiResponse<SemanticModel>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.getById|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|89|POST `/api/semantic-model`|06 / 已交付；最终验收见09|`@RequestBody @Validated SemanticModelAddDTO semanticModelAddDto`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.addSemanticModel|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|90|PUT `/api/semantic-model/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id, @RequestBody SemanticModel model`|`ApiResponse<SemanticModel>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.getById; semanticModelService.updateSemanticModel|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|91|DELETE `/api/semantic-model/{id}`|06 / 已交付；最终验收见09|`@PathVariable(value = "id") Long id`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.deleteSemanticModel; semanticModelService.getById|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|92|DELETE `/api/semantic-model/batch`|06 / 已交付；最终验收见09|`@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.deleteSemanticModels|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|93|PUT `/api/semantic-model/enable`|06 / 已交付；最终验收见09|`@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.enableSemanticModels|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|94|PUT `/api/semantic-model/disable`|06 / 已交付；最终验收见09|`@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids`|`ApiResponse<Boolean>`|200; 200 success=false 业务错误|无（本机管理）|disableFields|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|95|POST `/api/semantic-model/batch-import`|06 / 已交付；最终验收见09|`@RequestBody @Valid SemanticModelBatchImportDTO dto`|`ApiResponse<BatchImportResult>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.batchImport|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|96|GET `/api/semantic-model/template/download`|06 / 已交付；最终验收见09|`无`|`ResponseEntity<byte[]>`|200/404/500|无（本机管理）|downloadTemplate|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|97|POST `/api/semantic-model/import/excel`|06 / 已交付；最终验收见09|`@RequestPart("file") FilePart file, @RequestPart("agentId") String agentId`|`Mono<ApiResponse<BatchImportResult>>`|200; 200 success=false 业务错误|无（本机管理）|semanticModelService.importFromExcel|[services/semanticModel](../../JAVA/data-agent-frontend-nuxt/app/services/semanticModel/index.ts)|
|98|GET `/api/agent/{agentId}/sessions/stream`|05 / 已交付；最终验收见09|`@PathVariable Integer agentId, ServerHttpResponse response`|`Flux<ServerSentEvent<SessionUpdateEvent>>`|200|Java 无；Python 增加 Agent key/401|streamSessionUpdates|[services/sessionStateManager](../../JAVA/data-agent-frontend-nuxt/app/services/sessionStateManager/index.ts)|

## 逐接口返回和错误分支


### 1. list

```java
@GetMapping("/list")
	public List<Agent> list(@RequestParam(value = "status", required = false) String status,
			@RequestParam(value = "keyword", required = false) String keyword) {
		List<Agent> result;
		if (StringUtils.isNotBlank(keyword)) {
			result = agentService.search(keyword);
		}
		else if (StringUtils.isNotBlank(status)) {
			result = agentService.findByStatus(status);
		}
		else {
			result = agentService.findAll();
		}
		return result;
	}
```


### 2. get

```java
@GetMapping("/{id}")
	public Agent get(@PathVariable Long id) {
		return checkAgentExists(id);
	}
```


### 3. create

```java
@PostMapping
	public Agent create(@RequestBody Agent agent) {
		// Set default status
		if (StringUtils.isBlank(agent.getStatus())) {
			agent.setStatus("draft");
		}
		return agentService.save(agent);
	}
```


### 4. update

```java
@PutMapping("/{id}")
	public Agent update(@PathVariable Long id, @RequestBody Agent agent) {
		checkAgentExists(id);
		agent.setId(id);
		return agentService.save(agent);
	}
```


### 5. delete

```java
@DeleteMapping("/{id}")
	public void delete(@PathVariable Long id) {
		checkAgentExists(id);
		agentService.deleteById(id);
	}
```


### 6. publish

```java
@PostMapping("/{id}/publish")
	public Agent publish(@PathVariable Long id) {
		Agent agent = checkAgentExists(id);
		agent.setStatus("published");
		return agentService.save(agent);
	}
```


### 7. offline

```java
@PostMapping("/{id}/offline")
	public Agent offline(@PathVariable Long id) {
		Agent agent = checkAgentExists(id);
		agent.setStatus("offline");
		return agentService.save(agent);
	}
```


### 8. getApiKey

```java
@GetMapping("/{id}/api-key")
	public ApiResponse<ApiKeyResponse> getApiKey(@PathVariable Long id) {
		Agent agent = checkAgentExists(id);
		String masked = agentService.getApiKeyMasked(id);
		return buildApiKeyResponse(masked, agent.getApiKeyEnabled(), "获取 API Key 成功");
	}
```


### 9. generateApiKey

```java
@PostMapping("/{id}/api-key/generate")
	public ApiResponse<ApiKeyResponse> generateApiKey(@PathVariable Long id) {
		checkAgentExists(id);
		Agent agent = agentService.generateApiKey(id);
		return buildApiKeyResponse(agent.getApiKey(), agent.getApiKeyEnabled(), "生成 API Key 成功");
	}
```


### 10. resetApiKey

```java
@PostMapping("/{id}/api-key/reset")
	public ApiResponse<ApiKeyResponse> resetApiKey(@PathVariable Long id) {
		checkAgentExists(id);
		Agent agent = agentService.resetApiKey(id);
		return buildApiKeyResponse(agent.getApiKey(), agent.getApiKeyEnabled(), "重置 API Key 成功");
	}
```


### 11. deleteApiKey

```java
@DeleteMapping("/{id}/api-key")
	public ApiResponse<ApiKeyResponse> deleteApiKey(@PathVariable Long id) {
		checkAgentExists(id);
		Agent agent = agentService.deleteApiKey(id);
		return buildApiKeyResponse(agent.getApiKey(), agent.getApiKeyEnabled(), "删除 API Key 成功");
	}
```


### 12. toggleApiKey

```java
@PostMapping("/{id}/api-key/enable")
	public ApiResponse<ApiKeyResponse> toggleApiKey(@PathVariable Long id, @RequestParam("enabled") boolean enabled) {
		checkAgentExists(id);
		Agent agent = agentService.toggleApiKey(id, enabled);
		return buildApiKeyResponse(agent.getApiKey() == null ? null : "****", agent.getApiKeyEnabled(),
				"更新 API Key 状态成功");
	}
```


### 13. initSchema

```java
@PostMapping("/init")
	public ApiResponse<?> initSchema(@PathVariable Long agentId) {
		// 防止前端恶意请求，dto数据应该在后端获取
		try {
			AgentDatasource agentDatasource = agentDatasourceService.getCurrentAgentDatasource(agentId);
			log.info("Initializing schema for agent: {}", agentId);

			// Extract data source ID and table list from request
			Integer datasourceId = agentDatasource.getDatasourceId();
			List<String> tables = Optional.ofNullable(agentDatasource.getSelectTables()).orElse(List.of());

			// Validate request parameters
			if (datasourceId == null) {
				throw new InvalidInputException("数据源ID不能为空");
			}

			if (tables.isEmpty()) {
				throw new InvalidInputException("表列表不能为空");
			}

			// Execute Schema initialization
			Boolean result = agentDatasourceService.initializeSchemaForAgentWithDatasource(agentId, datasourceId,
					tables);

			if (result) {
				log.info("Successfully initialized schema for agent: {}, tables: {}", agentId, tables.size());
				return ApiResponse.success("Schema初始化成功");
			}
			else {
				throw new InternalServerException("Schema初始化失败");
			}
		}
		catch (Exception e) {
			log.error("Failed to initialize schema for agent: {}", agentId, e);
			throw new InternalServerException("Schema初始化失败：%s".formatted(e.getMessage()));
		}
	}
```


### 14. getAgentDatasource

```java
@GetMapping
	public ApiResponse<List<AgentDatasource>> getAgentDatasource(@PathVariable Long agentId) {
		try {
			log.info("Getting datasources for agent: {}", agentId);
			List<AgentDatasource> datasources = agentDatasourceService.getAgentDatasource(agentId);
			log.info("Successfully retrieved {} datasources for agent: {}", datasources.size(), agentId);
			return ApiResponse.success("操作成功", datasources);
		}
		catch (Exception e) {
			log.error("Failed to get datasources for agent: {}", agentId, e);
			throw new InvalidInputException("获取数据源失败：%s".formatted(e.getMessage()), List.of());
		}
	}
```


### 15. getActiveAgentDatasource

```java
@GetMapping("/active")
	public ApiResponse<AgentDatasource> getActiveAgentDatasource(@PathVariable Long agentId) {
		try {
			log.info("Getting active datasource for agent: {}", agentId);
			AgentDatasource datasource = agentDatasourceService.getCurrentAgentDatasource(agentId);
			return ApiResponse.success("操作成功", datasource);
		}
		catch (Exception e) {
			log.error("Failed to get active datasource for agent: {}", agentId, e);
			throw new InvalidInputException("获取数据源失败：%s".formatted(e.getMessage()), List.of());
		}
	}
```


### 16. addDatasourceToAgent

```java
@PostMapping("/{datasourceId}")
	public ApiResponse<AgentDatasource> addDatasourceToAgent(@PathVariable Long agentId,
			@PathVariable Integer datasourceId) {
		try {
			if (datasourceId == null) {
				throw new InvalidInputException("数据源ID不能为空");
			}

			AgentDatasource agentDatasource = agentDatasourceService.addDatasourceToAgent(agentId, datasourceId);
			return ApiResponse.success("数据源添加成功", agentDatasource);
		}
		catch (Exception e) {
			throw new InternalServerException("数据源添加失败：%s".formatted(e.getMessage()));
		}
	}
```


### 17. updateDatasourceTables

```java
@PostMapping("/tables")
	public ApiResponse<?> updateDatasourceTables(@PathVariable Long agentId,
			@RequestBody @Validated UpdateDatasourceTablesDTO dto) {
		try {
			dto.setTables(Optional.ofNullable(dto.getTables()).orElse(List.of()));
			agentDatasourceService.updateDatasourceTables(agentId, dto.getDatasourceId(), dto.getTables());
			return ApiResponse.success("更新成功");
		}
		catch (Exception e) {
			log.error("Error: ", e);
			throw new InternalServerException("更新失败：%s".formatted(e.getMessage()));
		}
	}
```


### 18. removeDatasourceFromAgent

```java
@DeleteMapping("/{datasourceId}")
	public ApiResponse<?> removeDatasourceFromAgent(@PathVariable Long agentId, @PathVariable Integer datasourceId) {
		try {
			agentDatasourceService.removeDatasourceFromAgent(agentId, datasourceId);
			return ApiResponse.success("数据源已移除");
		}
		catch (Exception e) {
			throw new InternalServerException("移除失败：%s".formatted(e.getMessage()));
		}
	}
```


### 19. toggleDatasourceForAgent

```java
@PutMapping("/toggle")
	public ApiResponse<AgentDatasource> toggleDatasourceForAgent(@PathVariable Long agentId,
			@RequestBody ToggleDatasourceDTO dto) {
		try {
			Boolean isActive = dto.getIsActive();
			Integer datasourceId = dto.getDatasourceId();
			if (isActive == null || datasourceId == null) {
				throw new InvalidInputException("激活状态不能为空");
			}
			AgentDatasource agentDatasource = agentDatasourceService.toggleDatasourceForAgent(agentId,
					dto.getDatasourceId(), isActive);
			return ApiResponse.success(isActive ? "数据源已启用" : "数据源已禁用", agentDatasource);
		}
		catch (Exception e) {
			throw new InternalServerException("操作失败：%s".formatted(e.getMessage()));
		}
	}
```


### 20. getKnowledgeById

```java
@GetMapping("/{id}")
	public ApiResponse<AgentKnowledgeVO> getKnowledgeById(@PathVariable("id") Integer id) {
		try {
			AgentKnowledgeVO knowledge = agentKnowledgeService.getKnowledgeById(id);
			if (knowledge != null) {
				return ApiResponse.success("查询成功", knowledge);
			}
			else {
				return ApiResponse.error("知识不存在");
			}
		}
		catch (Exception e) {
			log.error("查询知识详情失败：{}", e.getMessage());
			return ApiResponse.error("查询知识详情失败：" + e.getMessage());
		}
	}
```


### 21. createKnowledge

```java
@PostMapping(value = "/create", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	public Mono<ApiResponse<AgentKnowledgeVO>> createKnowledge(@RequestPart("agentId") String agentId,
			@RequestPart("title") String title, @RequestPart("type") String type,
			@RequestPart(value = "question", required = false) String question,
			@RequestPart(value = "content", required = false) String content,
			@RequestPart(value = "file", required = false) FilePart filePart,
			@RequestPart(value = "splitterType", required = false) String splitterType) {

		// 如果没有文件，直接同步处理
		if (filePart == null) {
			return Mono.fromCallable(() -> {
				CreateKnowledgeDTO dto = buildCreateKnowledgeDTO(agentId, title, type, question, content, null,
						splitterType);
				AgentKnowledgeVO knowledge = agentKnowledgeService.createKnowledge(dto);
				return ApiResponse.success("创建知识成功，后台向量存储开始更新，请耐心等待...", knowledge);
			}).subscribeOn(Schedulers.boundedElastic());
		}

		// 有文件时，先读取文件内容再处理
		String filename = filePart.filename();
		String fileContentType = filePart.headers().getContentType() != null
				? filePart.headers().getContentType().toString() : "application/octet-stream";

		return DataBufferUtils.join(filePart.content()).flatMap(dataBuffer -> {
			byte[] bytes = new byte[dataBuffer.readableByteCount()];
			dataBuffer.read(bytes);
			DataBufferUtils.release(dataBuffer);

			return Mono.fromCallable(() -> {
				MultipartFile multipartFile = new ByteArrayMultipartFile(bytes, filename, fileContentType);
				CreateKnowledgeDTO dto = buildCreateKnowledgeDTO(agentId, title, type, question, content, multipartFile,
						splitterType);
				AgentKnowledgeVO knowledge = agentKnowledgeService.createKnowledge(dto);
				return ApiResponse.success("创建知识成功，后台向量存储开始更新，请耐心等待...", knowledge);
			}).subscribeOn(Schedulers.boundedElastic());
		});
	}
```


### 22. updateKnowledge

```java
@PutMapping("/{id}")
	public ApiResponse<AgentKnowledgeVO> updateKnowledge(@PathVariable("id") Integer id,
			@RequestBody UpdateKnowledgeDTO updateKnowledgeDto) {
		AgentKnowledgeVO knowledge = agentKnowledgeService.updateKnowledge(id, updateKnowledgeDto);
		return ApiResponse.success("更新成功", knowledge);
	}
```


### 23. updateRecallStatus

```java
@PutMapping("/recall/{id}")
	public ApiResponse<AgentKnowledgeVO> updateRecallStatus(@PathVariable Integer id,
			@RequestParam(value = "isRecall") Boolean isRecall) {
		AgentKnowledgeVO agentKnowledgeVO = agentKnowledgeService.updateKnowledgeRecallStatus(id, isRecall);
		return ApiResponse.success("更新成功", agentKnowledgeVO);
	}
```


### 24. deleteKnowledge

```java
@DeleteMapping("/{id}")
	public ApiResponse<Boolean> deleteKnowledge(@PathVariable("id") Integer id) {
		return agentKnowledgeService.deleteKnowledge(id) ? ApiResponse.success("删除操作已接收，等待后台删除相关资源...")
				: ApiResponse.error("删除失败");
	}
```


### 25. queryByPage

```java
@PostMapping("/query/page")
	public PageResponse<List<AgentKnowledgeVO>> queryByPage(@Valid @RequestBody AgentKnowledgeQueryDTO queryDTO) {
		try {
			PageResult<AgentKnowledgeVO> pageResult = agentKnowledgeService.queryByConditionsWithPage(queryDTO);
			return PageResponse.success(pageResult.getData(), pageResult.getTotal(), pageResult.getPageNum(),
					pageResult.getPageSize(), pageResult.getTotalPages());
		}
		catch (Exception e) {
			log.error("分页查询知识列表失败：{}", e.getMessage());
			return PageResponse.pageError("分页查询失败：" + e.getMessage());
		}
	}
```


### 26. retryEmbedding

```java
@PostMapping("/retry-embedding/{id}")
	public ApiResponse<AgentKnowledgeVO> retryEmbedding(@PathVariable Integer id) {
		agentKnowledgeService.retryEmbedding(id);
		return ApiResponse.success("重试向量化操作成功，如果是文件解析需要花费点时间，请耐心等待...");
	}
```


### 27. getPresetQuestions

```java
@GetMapping("/{agentId}/preset-questions")
	public ResponseEntity<List<AgentPresetQuestion>> getPresetQuestions(@PathVariable(value = "agentId") Long agentId) {
		try {
			List<AgentPresetQuestion> questions = presetQuestionService.findAllByAgentId(agentId);
			return ResponseEntity.ok(questions);
		}
		catch (Exception e) {
			log.error("Error getting preset questions for agent {}", agentId, e);
			return ResponseEntity.internalServerError().build();
		}
	}
```


### 28. savePresetQuestions

```java
@PostMapping("/{agentId}/preset-questions")
	public ResponseEntity<Map<String, String>> savePresetQuestions(@PathVariable(value = "agentId") Long agentId,
			@RequestBody List<Map<String, Object>> questionsData) {
		try {
			List<AgentPresetQuestion> questions = questionsData.stream().map(data -> {
				AgentPresetQuestion question = new AgentPresetQuestion();
				question.setQuestion((String) data.get("question"));
				Object isActiveObj = data.get("isActive");
				if (isActiveObj instanceof Boolean) {
					question.setIsActive((Boolean) isActiveObj);
				}
				else if (isActiveObj != null) {
					question.setIsActive(Boolean.parseBoolean(isActiveObj.toString()));
				}
				else {
					question.setIsActive(true);
				}
				return question;
			}).toList();

			presetQuestionService.batchSave(agentId, questions);
			return ResponseEntity.ok(Map.of("message", "预设问题保存成功"));
		}
		catch (Exception e) {
			log.error("Error saving preset questions for agent {}", agentId, e);
			return ResponseEntity.internalServerError().body(Map.of("error", "保存预设问题失败: " + e.getMessage()));
		}
	}
```


### 29. deletePresetQuestion

```java
@DeleteMapping("/{agentId}/preset-questions/{questionId}")
	public ResponseEntity<Map<String, String>> deletePresetQuestion(@PathVariable(value = "agentId") Long agentId,
			@PathVariable Long questionId) {
		try {
			presetQuestionService.deleteById(questionId);
			return ResponseEntity.ok(Map.of("message", "预设问题删除成功"));
		}
		catch (Exception e) {
			log.error("Error deleting preset question {} for agent {}", questionId, agentId, e);
			return ResponseEntity.internalServerError().body(Map.of("error", "删除预设问题失败: " + e.getMessage()));
		}
	}
```


### 30. list

```java
@GetMapping
	public ApiResponse<List<BusinessKnowledgeVO>> list(@RequestParam(value = "agentId") String agentIdStr,
			@RequestParam(value = "keyword", required = false) String keyword) {
		List<BusinessKnowledgeVO> result;
		Long agentId = Long.parseLong(agentIdStr);

		if (StringUtils.hasText(keyword)) {
			result = businessKnowledgeService.searchKnowledge(agentId, keyword);
		}
		else {
			result = businessKnowledgeService.getKnowledge(agentId);
		}
		return ApiResponse.success("success list businessKnowledge", result);
	}
```


### 31. get

```java
@GetMapping("/{id}")
	public ApiResponse<BusinessKnowledgeVO> get(@PathVariable(value = "id") Long id) {
		BusinessKnowledgeVO vo = businessKnowledgeService.getKnowledgeById(id);
		if (vo == null) {
			return ApiResponse.error("businessKnowledge not found");
		}
		return ApiResponse.success("success get businessKnowledge", vo);
	}
```


### 32. create

```java
@PostMapping
	public ApiResponse<BusinessKnowledgeVO> create(@RequestBody @Validated CreateBusinessKnowledgeDTO knowledge) {
		return ApiResponse.success("success create businessKnowledge",
				businessKnowledgeService.addKnowledge(knowledge));
	}
```


### 33. update

```java
@PutMapping("/{id}")
	public ApiResponse<BusinessKnowledgeVO> update(@PathVariable(value = "id") Long id,
			@RequestBody UpdateBusinessKnowledgeDTO knowledge) {

		return ApiResponse.success("success update businessKnowledge",
				businessKnowledgeService.updateKnowledge(id, knowledge));
	}
```


### 34. delete

```java
@DeleteMapping("/{id}")
	public ApiResponse<Boolean> delete(@PathVariable(value = "id") Long id) {
		if (businessKnowledgeService.getKnowledgeById(id) == null) {
			return ApiResponse.error("businessKnowledge not found");
		}
		businessKnowledgeService.deleteKnowledge(id);
		return ApiResponse.success("success delete businessKnowledge");
	}
```


### 35. recallKnowledge

```java
@PostMapping("/recall/{id}")
	public ApiResponse<Boolean> recallKnowledge(@PathVariable(value = "id") Long id,
			@RequestParam(value = "isRecall") Boolean isRecall) {
		businessKnowledgeService.recallKnowledge(id, isRecall);
		return ApiResponse.success("success update recall businessKnowledge");
	}
```


### 36. refreshAllKnowledgeToVectorStore

```java
@PostMapping("/refresh-vector-store")
	public ApiResponse<Boolean> refreshAllKnowledgeToVectorStore(@RequestParam(value = "agentId") String agentId) {
		// 校验 agentId 不为空和空字符串
		if (!StringUtils.hasText(agentId)) {
			return ApiResponse.error("agentId cannot be empty");
		}

		try {
			businessKnowledgeService.refreshAllKnowledgeToVectorStore(agentId);
			return ApiResponse.success("success refresh vector store");
		}
		catch (Exception e) {
			log.error("Failed to refresh vector store for agentId: {}", agentId, e);
			return ApiResponse.error("Failed to refresh vector store");
		}
	}
```


### 37. retryEmbedding

```java
@PostMapping("/retry-embedding/{id}")
	public ApiResponse<Boolean> retryEmbedding(@PathVariable(value = "id") Long id) {
		businessKnowledgeService.retryEmbedding(id);
		return ApiResponse.success("success retry embedding");
	}
```


### 38. getAgentSessions

```java
@GetMapping("/agent/{id}/sessions")
	public ResponseEntity<List<ChatSession>> getAgentSessions(@PathVariable(value = "id") Integer id) {
		List<ChatSession> sessions = chatSessionService.findByAgentId(id);
		return ResponseEntity.ok(sessions);
	}
```


### 39. createSession

```java
@PostMapping("/agent/{id}/sessions")
	public ResponseEntity<ChatSession> createSession(@PathVariable(value = "id") Integer id,
			@RequestBody(required = false) Map<String, Object> request) {
		String title = request != null ? (String) request.get("title") : null;
		Long userId = request != null ? toUserId(request.get("userId")) : null;

		ChatSession session = chatSessionService.createSession(id, title, userId);
		return ResponseEntity.ok(session);
	}
```


### 40. clearAgentSessions

```java
@DeleteMapping("/agent/{id}/sessions")
	public ResponseEntity<ApiResponse> clearAgentSessions(@PathVariable(value = "id") Integer id) {
		chatSessionService.clearSessionsByAgentId(id);
		return ResponseEntity.ok(ApiResponse.success("会话已清空"));
	}
```


### 41. getSessionMessages

```java
@GetMapping("/sessions/{sessionId}/messages")
	public ResponseEntity<List<ChatMessage>> getSessionMessages(@PathVariable(value = "sessionId") String sessionId) {
		List<ChatMessage> messages = chatMessageService.findBySessionId(sessionId);
		return ResponseEntity.ok(messages);
	}
```


### 42. saveMessage

```java
@PostMapping("/sessions/{sessionId}/messages")
	public ResponseEntity<ChatMessage> saveMessage(@PathVariable(value = "sessionId") String sessionId,
			@RequestBody ChatMessageDTO request) {
		try {
			if (request == null) {
				return ResponseEntity.badRequest().build();
			}
			ChatMessage message = ChatMessage.builder()
				.sessionId(sessionId)
				.role(request.getRole())
				.content(request.getContent())
				.messageType(request.getMessageType())
				.metadata(request.getMetadata())
				.build();

			ChatMessage savedMessage = chatMessageService.saveMessage(message);

			// Update session activity time
			chatSessionService.updateSessionTime(sessionId);

			if (request.isTitleNeeded()) {
				sessionTitleService.scheduleTitleGeneration(sessionId, message.getContent());
			}

			return ResponseEntity.ok(savedMessage);
		}
		catch (Exception e) {
			log.error("Save message error for session {}: {}", sessionId, e.getMessage(), e);
			return ResponseEntity.internalServerError().build();
		}
	}
```


### 43. pinSession

```java
@PutMapping("/sessions/{sessionId}/pin")
	public ResponseEntity<ApiResponse> pinSession(@PathVariable(value = "sessionId") String sessionId,
			@RequestParam(value = "isPinned") Boolean isPinned) {
		try {
			chatSessionService.pinSession(sessionId, isPinned);
			String message = isPinned ? "会话已置顶" : "会话已取消置顶";
			return ResponseEntity.ok(ApiResponse.success(message));
		}
		catch (Exception e) {
			log.error("Pin session error for session {}: {}", sessionId, e.getMessage(), e);
			return ResponseEntity.internalServerError().body(ApiResponse.error("操作失败"));
		}
	}
```


### 44. renameSession

```java
@PutMapping("/sessions/{sessionId}/rename")
	public ResponseEntity<ApiResponse> renameSession(@PathVariable(value = "sessionId") String sessionId,
			@RequestParam(value = "title") String title) {
		try {
			if (!StringUtils.hasText(title)) {
				return ResponseEntity.badRequest().body(ApiResponse.error("标题不能为空"));
			}

			chatSessionService.renameSession(sessionId, title.trim());
			return ResponseEntity.ok(ApiResponse.success("会话已重命名"));
		}
		catch (Exception e) {
			log.error("Rename session error for session {}: {}", sessionId, e.getMessage(), e);
			return ResponseEntity.internalServerError().body(ApiResponse.error("重命名失败"));
		}
	}
```


### 45. deleteSession

```java
@DeleteMapping("/sessions/{sessionId}")
	public ResponseEntity<ApiResponse> deleteSession(@PathVariable(value = "sessionId") String sessionId) {
		try {
			chatSessionService.deleteSession(sessionId);
			return ResponseEntity.ok(ApiResponse.success("会话已删除"));
		}
		catch (Exception e) {
			log.error("Delete session error for session {}: {}", sessionId, e.getMessage(), e);
			return ResponseEntity.internalServerError().body(ApiResponse.error("删除失败"));
		}
	}
```


### 46. convertAndDownloadHtml

```java
@PostMapping("/sessions/{sessionId}/reports/html")
	public ResponseEntity<byte[]> convertAndDownloadHtml(@PathVariable(value = "sessionId") String sessionId,
			@RequestBody String content) {
		try {
			if (!StringUtils.hasText(content)) {
				return ResponseEntity.badRequest().build();
			}
			log.debug("Download HTML report for session {}", sessionId);
			StringBuilder htmlContent = new StringBuilder();
			htmlContent.append(reportTemplateUtil.getHeader());
			htmlContent.append(content);
			htmlContent.append(reportTemplateUtil.getFooter());
			String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"));
			String filename = "report_" + timestamp + ".html";
			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(new MediaType("text", "html", StandardCharsets.UTF_8));
			headers.setContentDispositionFormData("attachment", filename);
			return ResponseEntity.ok().headers(headers).body(htmlContent.toString().getBytes(StandardCharsets.UTF_8));
		}
		catch (Exception e) {
			log.error("Download HTML report error for session {}: {}", sessionId, e.getMessage(), e);
			return ResponseEntity.internalServerError().build();
		}
	}
```


### 47. getDatasourceTypes

```java
@GetMapping("/types")
	public ApiResponse<List<DatasourceTypeDTO>> getDatasourceTypes() {
		// 定义标准的 JDBC 数据源类型
		List<BizDataSourceTypeEnum> standardTypes = Arrays.asList(BizDataSourceTypeEnum.MYSQL,
				BizDataSourceTypeEnum.POSTGRESQL, BizDataSourceTypeEnum.DAMENG, BizDataSourceTypeEnum.SQL_SERVER,
				BizDataSourceTypeEnum.ORACLE, BizDataSourceTypeEnum.HIVE);

		List<DatasourceTypeDTO> types = standardTypes.stream()
			.map(type -> DatasourceTypeDTO.builder()
				.code(type.getCode())
				.typeName(type.getTypeName())
				.dialect(type.getDialect())
				.protocol(type.getProtocol())
				.displayName(type.getDialect()) // 使用 dialect 作为显示名称
				.build())
			.collect(Collectors.toList());

		return ApiResponse.success("获取数据源类型成功", types);
	}
```


### 48. getAllDatasource

```java
@GetMapping
	public List<Datasource> getAllDatasource(@RequestParam(value = "status", required = false) String status,
			@RequestParam(value = "type", required = false) String type) {

		List<Datasource> result;

		if (StringUtils.isNotBlank(status)) {
			result = datasourceService.getDatasourceByStatus(status);
		}
		else if (StringUtils.isNotBlank(type)) {
			result = datasourceService.getDatasourceByType(type);
		}
		else {
			result = datasourceService.getAllDatasource();
		}

		return result;
	}
```


### 49. getDatasourceById

```java
@GetMapping("/{id}")
	public Datasource getDatasourceById(@PathVariable Integer id) {
		return checkDatasourceExists(id);
	}
```


### 50. getDatasourceTables

```java
@GetMapping("/{id}/tables")
	public List<String> getDatasourceTables(@PathVariable Integer id) {
		checkDatasourceExists(id);
		try {
			return datasourceService.getDatasourceTables(id);
		}
		catch (Exception e) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, e.getMessage());
		}
	}
```


### 51. createDatasource

```java
@PostMapping
	public Datasource createDatasource(@RequestBody Datasource datasource) {
		try {
			return datasourceService.createDatasource(datasource);
		}
		catch (Exception e) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, e.getMessage());
		}
	}
```


### 52. updateDatasource

```java
@PutMapping("/{id}")
	public Datasource updateDatasource(@PathVariable Integer id, @RequestBody Datasource datasource) {
		checkDatasourceExists(id);
		try {
			return datasourceService.updateDatasource(id, datasource);
		}
		catch (Exception e) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, e.getMessage());
		}
	}
```


### 53. deleteDatasource

```java
@DeleteMapping("/{id}")
	public ApiResponse deleteDatasource(@PathVariable Integer id) {
		try {
			checkDatasourceExists(id);
			datasourceService.deleteDatasource(id);
			return ApiResponse.success("数据源删除成功");
		}
		catch (ResponseStatusException e) {
			throw new InvalidInputException(e.getMessage());
		}
		catch (Exception e) {
			throw new InternalServerException("删除失败：" + e.getMessage());
		}
	}
```


### 54. testConnection

```java
@PostMapping("/{id}/test")
	public ApiResponse testConnection(@PathVariable Integer id) {
		try {
			boolean success = datasourceService.testConnection(id);
			return success ? ApiResponse.success("连接测试成功") : ApiResponse.error("连接测试失败");
		}
		catch (Exception e) {
			throw new InternalServerException("测试失败：" + e.getMessage());
		}
	}
```


### 55. getTableColumns

```java
@GetMapping("/{id}/tables/{tableName}/columns")
	public ApiResponse<List<String>> getTableColumns(@PathVariable Integer id, @PathVariable String tableName) {
		try {
			List<String> columns = datasourceService.getTableColumns(id, tableName);
			return ApiResponse.success("获取字段列表成功", columns);
		}
		catch (Exception e) {
			throw new InternalServerException("获取字段列表失败：" + e.getMessage());
		}
	}
```


### 56. getLogicalRelations

```java
@GetMapping("/{id}/logical-relations")
	public ApiResponse<List<LogicalRelation>> getLogicalRelations(@PathVariable(value = "id") Integer datasourceId) {
		try {
			List<LogicalRelation> logicalRelations = datasourceService.getLogicalRelations(datasourceId);
			return ApiResponse.success("success get logical relations", logicalRelations);
		}
		catch (Exception e) {
			log.error("Failed to get logical relations for datasource: {}", datasourceId, e);
			throw new InternalServerException("获取逻辑外键失败：" + e.getMessage());
		}
	}
```


### 57. addLogicalRelation

```java
@PostMapping("/{id}/logical-relations")
	public ApiResponse<LogicalRelation> addLogicalRelation(@PathVariable(value = "id") Integer datasourceId,
			@Valid @RequestBody CreateLogicalRelationDTO dto) {
		try {
			LogicalRelation logicalRelation = LogicalRelation.builder()
				.sourceTableName(dto.getSourceTableName())
				.sourceColumnName(dto.getSourceColumnName())
				.targetTableName(dto.getTargetTableName())
				.targetColumnName(dto.getTargetColumnName())
				.relationType(dto.getRelationType())
				.description(dto.getDescription())
				.build();

			LogicalRelation created = datasourceService.addLogicalRelation(datasourceId, logicalRelation);
			return ApiResponse.success("success create logical relation", created);
		}
		catch (Exception e) {
			log.error("Failed to add logical relation for datasource: {}", datasourceId, e);
			throw new InternalServerException("添加逻辑外键失败：" + e.getMessage());
		}
	}
```


### 58. updateLogicalRelation

```java
@PutMapping("/{id}/logical-relations/{relationId}")
	public ApiResponse<LogicalRelation> updateLogicalRelation(@PathVariable(value = "id") Integer datasourceId,
			@PathVariable Integer relationId, @RequestBody UpdateLogicalRelationDTO dto) {
		try {
			LogicalRelation logicalRelation = LogicalRelation.builder()
				.sourceTableName(dto.getSourceTableName())
				.sourceColumnName(dto.getSourceColumnName())
				.targetTableName(dto.getTargetTableName())
				.targetColumnName(dto.getTargetColumnName())
				.relationType(dto.getRelationType())
				.description(dto.getDescription())
				.build();

			LogicalRelation updated = datasourceService.updateLogicalRelation(datasourceId, relationId,
					logicalRelation);
			return ApiResponse.success("success update logical relation", updated);
		}
		catch (Exception e) {
			log.error("Failed to update logical relation {} for datasource: {}", relationId, datasourceId, e);
			throw new InternalServerException("更新逻辑外键失败：" + e.getMessage());
		}
	}
```


### 59. deleteLogicalRelation

```java
@DeleteMapping("/{id}/logical-relations/{relationId}")
	public ApiResponse<Void> deleteLogicalRelation(@PathVariable(value = "id") Integer datasourceId,
			@PathVariable Integer relationId) {
		try {
			datasourceService.deleteLogicalRelation(datasourceId, relationId);
			return ApiResponse.success("success delete logical relation");
		}
		catch (Exception e) {
			log.error("Failed to delete logical relation {} for datasource: {}", relationId, datasourceId, e);
			throw new InternalServerException("删除逻辑外键失败：" + e.getMessage());
		}
	}
```


### 60. saveLogicalRelations

```java
@PutMapping("/{id}/logical-relations")
	public ApiResponse<List<LogicalRelation>> saveLogicalRelations(@PathVariable(value = "id") Integer datasourceId,
			@RequestBody List<LogicalRelation> logicalRelations) {
		try {
			List<LogicalRelation> saved = datasourceService.saveLogicalRelations(datasourceId, logicalRelations);
			return ApiResponse.success("success save logical relations", saved);
		}
		catch (Exception e) {
			log.error("Failed to save logical relations for datasource: {}", datasourceId, e);
			throw new InternalServerException("批量保存逻辑外键失败：" + e.getMessage());
		}
	}
```


### 61. ok

```java
@GetMapping("ok")
	public String ok() {
		return "ok";
	}
```


### 62. uploadAvatar

```java
@PostMapping(value = "/avatar", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	public Mono<ResponseEntity<UploadResponse>> uploadAvatar(@RequestPart("file") FilePart file) {
		// 验证文件类型
		String contentType = file.headers().getContentType() != null ? file.headers().getContentType().toString()
				: null;
		if (contentType == null || !contentType.startsWith("image/")) {
			return Mono.just(ResponseEntity.badRequest().body(UploadResponse.error("只支持图片文件")));
		}

		if (file.headers().getContentLength() > fileStorageProperties.getImageSize()) {
			return Mono.just(ResponseEntity.badRequest().body(UploadResponse.error("图片大小超过最大限制")));
		}

		// 使用文件存储服务存储文件
		return fileStorageService.storeFile(file, "avatars").map(filePath -> {
			String fileUrl = fileStorageService.getFileUrl(filePath);
			// 提取文件名
			String filename = filePath.substring(filePath.lastIndexOf("/") + 1);
			return ResponseEntity.ok(UploadResponse.ok("上传成功", fileUrl, filename));
		}).onErrorResume(e -> {
			log.error("头像上传失败", e);
			return Mono
				.just(ResponseEntity.internalServerError().body(UploadResponse.error("上传失败: " + e.getMessage())));
		});
	}
```


### 63. getFile

```java
@GetMapping("/**")
	public ResponseEntity<byte[]> getFile(ServerHttpRequest request) {
		try {
			String requestMapPath = this.getClass().getAnnotation(RequestMapping.class).value()[0];
			String requestPath = request.getPath().value();
			String urlPrefix = fileStorageProperties.getUrlPrefix();
			String requestPrefix = requestMapPath + urlPrefix + "/";
			if (!requestPath.startsWith(requestPrefix)) {
				return ResponseEntity.badRequest().build();
			}
			String filePath = requestPath.substring(requestPrefix.length());
			if (filePath.isBlank()) {
				return ResponseEntity.badRequest().build();
			}

			Path basePath = fileStorageProperties.getLocalBasePath().toAbsolutePath().normalize();
			Path fullPath = basePath.resolve(filePath).normalize();
			if (!fullPath.startsWith(basePath)) {
				return ResponseEntity.status(403).build();
			}

			if (!Files.exists(fullPath) || Files.isDirectory(fullPath)) {
				return ResponseEntity.notFound().build();
			}

			byte[] fileContent = Files.readAllBytes(fullPath);
			String contentType = Files.probeContentType(fullPath);

			return ResponseEntity.ok()
				.contentType(MediaType.parseMediaType(contentType != null ? contentType : "application/octet-stream"))
				.body(fileContent);

		}
		catch (IOException e) {
			log.error("文件读取失败", e);
			return ResponseEntity.internalServerError().build();
		}
	}
```


### 64. streamSearch

```java
@GetMapping(value = "/stream/search", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
	public Flux<ServerSentEvent<GraphNodeResponse>> streamSearch(@RequestParam("agentId") String agentId,
			@RequestParam(value = "conversationId", required = false) String conversationId,
			@RequestParam(value = "threadId", required = false) String threadId, @RequestParam("query") String query,
			@RequestParam(value = "humanFeedback", required = false) boolean humanFeedback,
			@RequestParam(value = "humanFeedbackContent", required = false) String humanFeedbackContent,
			@RequestParam(value = "rejectedPlan", required = false) boolean rejectedPlan,
			@RequestParam(value = "nl2sqlOnly", required = false) boolean nl2sqlOnly, ServerHttpResponse response) {
		// Set SSE-related HTTP headers
		response.getHeaders().add("Cache-Control", "no-cache");
		response.getHeaders().add("Connection", "keep-alive");
		response.getHeaders().add("Access-Control-Allow-Origin", "*");

		Sinks.Many<ServerSentEvent<GraphNodeResponse>> sink = Sinks.many().unicast().onBackpressureBuffer();

		GraphRequest request = GraphRequest.builder()
			.agentId(agentId)
			.conversationId(conversationId)
			.threadId(threadId)
			.query(query)
			.humanFeedback(humanFeedback)
			.humanFeedbackContent(humanFeedbackContent)
			.rejectedPlan(rejectedPlan)
			.nl2sqlOnly(nl2sqlOnly)
			.build();
		graphService.graphStreamProcess(sink, request);

		return sink.asFlux().filter(sse -> {
			// 1. 如果 event 是 "complete" 或 "error"，直接放行（不管 text 是否为空）
			if (STREAM_EVENT_COMPLETE.equals(sse.event()) || STREAM_EVENT_ERROR.equals(sse.event())) {
				return true;
			}
			// Protocol events carry state transitions in eventType and do not require
			// display text.
			if (sse.data() != null && sse.data().getEventType() != null
					&& !GraphEventType.NODE_OUTPUT.equals(sse.data().getEventType())) {
				return true;
			}
			// 判断字符串是否为空
			return sse.data() != null && sse.data().getText() != null && !sse.data().getText().isEmpty();
		})
			.doOnSubscribe(subscription -> log.info("Client subscribed to stream, threadId: {}", request.getThreadId()))
			.doOnCancel(() -> {
				log.info("Client disconnected from stream, threadId: {}", request.getThreadId());
				if (request.getThreadId() != null) {
					graphService.stopStreamProcessing(request.getThreadId());
				}
			})
			.doOnError(e -> {
				log.error("Error occurred during streaming, threadId: {}: ", request.getThreadId(), e);
				if (request.getThreadId() != null) {
					graphService.stopStreamProcessing(request.getThreadId());
				}
			})
			.doOnComplete(() -> log.info("Stream completed successfully, threadId: {}", request.getThreadId()));
	}
```


### 65. stopStream

```java
@PostMapping("/stream/stop")
	public ResponseEntity<Void> stopStream(@RequestParam("conversationId") String conversationId,
			@RequestParam(value = "threadId", required = false) String threadId) {
		if (StringUtils.hasText(threadId)) {
			graphService.stopStreamProcessing(threadId);
		}
		else {
			graphService.stopStreamProcessingByConversationId(conversationId);
		}
		return ResponseEntity.noContent().build();
	}
```


### 66. list

```java
@GetMapping("/list")
	public ApiResponse<List<ModelConfigDTO>> list() {
		try {
			return ApiResponse.success("获取模型配置列表成功", modelConfigDataService.listConfigs());
		}
		catch (Exception e) {
			return ApiResponse.error("获取模型配置列表失败: " + e.getMessage());
		}
	}
```


### 67. add

```java
@PostMapping("/add")
	public ApiResponse<String> add(@Valid @RequestBody ModelConfigDTO config) {
		try {
			modelConfigDataService.addConfig(config);
			return ApiResponse.success("配置已保存");
		}
		catch (Exception e) {
			return ApiResponse.error("保存失败: " + e.getMessage());
		}
	}
```


### 68. update

```java
@PutMapping("/update")
	public ApiResponse<String> update(@Valid @RequestBody ModelConfigDTO config) {
		try {
			modelConfigOpsService.updateAndRefresh(config);
			return ApiResponse.success("配置已更新");
		}
		catch (Exception e) {
			return ApiResponse.error("更新失败: " + e.getMessage());
		}
	}
```


### 69. delete

```java
@DeleteMapping("/{id}")
	public ApiResponse<String> delete(@PathVariable Integer id) {
		try {
			modelConfigDataService.deleteConfig(id);
			return ApiResponse.success("配置已删除");
		}
		catch (Exception e) {
			return ApiResponse.error("删除失败: " + e.getMessage());
		}
	}
```


### 70. activate

```java
@PostMapping("/activate/{id}")
	public ApiResponse<String> activate(@PathVariable Integer id) {
		try {
			modelConfigOpsService.activateConfig(id);
			return ApiResponse.success("模型切换成功！");
		}
		catch (Exception e) {
			return ApiResponse.error("切换失败，请检查配置是否正确: " + e.getMessage());
		}
	}
```


### 71. testConnection

```java
@PostMapping("/test/{id}")
	public ApiResponse<String> testConnection(@PathVariable Integer id) {
		try {
			modelConfigOpsService.testConnection(id);
			return ApiResponse.success("连接测试成功！模型可用。");
		}
		catch (Exception e) {
			// 捕获具体的错误信息（如 401 Invalid Key, 404 Not Found 等）返回给前端
			return ApiResponse.error("连接测试失败: " + e.getMessage());
		}
	}
```


### 72. checkReady

```java
@GetMapping("/check-ready")
	public ApiResponse<ModelCheckVo> checkReady() {
		// 检查聊天模型是否已配置且启用
		ModelConfigDTO chatModel = modelConfigDataService.getActiveConfigByType(ModelType.CHAT);
		// 检查嵌入模型是否已配置且启用
		ModelConfigDTO embeddingModel = modelConfigDataService.getActiveConfigByType(ModelType.EMBEDDING);

		boolean chatModelReady = chatModel != null;
		boolean embeddingModelReady = embeddingModel != null;
		boolean ready = chatModelReady && embeddingModelReady;

		return ApiResponse.success("模型配置检查完成",
				ModelCheckVo.builder()
					.chatModelReady(chatModelReady)
					.embeddingModelReady(embeddingModelReady)
					.ready(ready)
					.build());
	}
```


### 73. saveConfig

```java
@PostMapping("/save")
	public ResponseEntity<Map<String, Object>> saveConfig(@RequestBody PromptConfigDTO configDTO) {
		logger.info("保存提示词优化配置请求：{}", configDTO);

		UserPromptConfig savedConfig = promptConfigService.saveOrUpdateConfig(configDTO);

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("message", "优化配置保存成功");
		response.put("data", savedConfig);

		return ResponseEntity.ok(response);
	}
```


### 74. getConfig

```java
@GetMapping("/{id}")
	public ResponseEntity<Map<String, Object>> getConfig(@PathVariable(value = "id") String id) {
		UserPromptConfig config = promptConfigService.getConfigById(id);

		Map<String, Object> response = new HashMap<>();
		if (config != null) {
			response.put("success", true);
			response.put("data", config);
		}
		else {
			response.put("success", false);
			response.put("message", "配置不存在");
		}

		return ResponseEntity.ok(response);
	}
```


### 75. getAllConfigs

```java
@GetMapping("/list")
	public ResponseEntity<Map<String, Object>> getAllConfigs() {
		List<UserPromptConfig> configs = promptConfigService.getAllConfigs();

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("data", configs);
		response.put("total", configs.size());

		return ResponseEntity.ok(response);
	}
```


### 76. getConfigsByType

```java
@GetMapping("/list-by-type/{promptType}")
	public ResponseEntity<Map<String, Object>> getConfigsByType(@PathVariable(value = "promptType") String promptType,
			@RequestParam(value = "agentId", required = false) Long agentId) {
		List<UserPromptConfig> configs = promptConfigService.getConfigsByType(promptType, agentId);

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("data", configs);
		response.put("total", configs.size());

		return ResponseEntity.ok(response);
	}
```


### 77. getActiveConfig

```java
@GetMapping("/active/{promptType}")
	public ResponseEntity<Map<String, Object>> getActiveConfig(@PathVariable(value = "promptType") String promptType,
			@RequestParam(value = "agentId", required = false) Long agentId) {
		UserPromptConfig config = promptConfigService.getActiveConfigByType(promptType, agentId);

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("data", config);
		response.put("hasCustomConfig", config != null);

		return ResponseEntity.ok(response);
	}
```


### 78. getActiveConfigs

```java
@GetMapping("/active-all/{promptType}")
	public ResponseEntity<Map<String, Object>> getActiveConfigs(@PathVariable(value = "promptType") String promptType,
			@RequestParam(value = "agentId", required = false) Long agentId) {
		List<UserPromptConfig> configs = promptConfigService.getActiveConfigsByType(promptType, agentId);

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("data", configs);
		response.put("total", configs.size());
		response.put("hasOptimizationConfigs", !configs.isEmpty());

		return ResponseEntity.ok(response);
	}
```


### 79. deleteConfig

```java
@DeleteMapping("/{id}")
	public ResponseEntity<Map<String, Object>> deleteConfig(@PathVariable(value = "id") String id) {
		boolean deleted = promptConfigService.deleteConfig(id);

		Map<String, Object> response = new HashMap<>();
		if (deleted) {
			response.put("success", true);
			response.put("message", "配置删除成功");
		}
		else {
			response.put("success", false);
			response.put("message", "配置不存在或删除失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 80. enableConfig

```java
@PostMapping("/{id}/enable")
	public ResponseEntity<Map<String, Object>> enableConfig(@PathVariable(value = "id") String id) {
		boolean enabled = promptConfigService.enableConfig(id);

		Map<String, Object> response = new HashMap<>();
		if (enabled) {
			response.put("success", true);
			response.put("message", "配置启用成功");
		}
		else {
			response.put("success", false);
			response.put("message", "配置不存在或启用失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 81. disableConfig

```java
@PostMapping("/{id}/disable")
	public ResponseEntity<Map<String, Object>> disableConfig(@PathVariable(value = "id") String id) {
		boolean disabled = promptConfigService.disableConfig(id);

		Map<String, Object> response = new HashMap<>();
		if (disabled) {
			response.put("success", true);
			response.put("message", "配置禁用成功");
		}
		else {
			response.put("success", false);
			response.put("message", "配置不存在或禁用失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 82. getSupportedPromptTypes

```java
@GetMapping("/types")
	public ResponseEntity<Map<String, Object>> getSupportedPromptTypes() {
		// Supported prompt types
		String[] types = { "report-generator", "planner", "sql-generator", "python-generator", "rewrite" };

		Map<String, Object> response = new HashMap<>();
		response.put("success", true);
		response.put("data", types);

		return ResponseEntity.ok(response);
	}
```


### 83. batchEnableConfigs

```java
@PostMapping("/batch-enable")
	public ResponseEntity<Map<String, Object>> batchEnableConfigs(@RequestBody List<String> ids) {
		boolean success = promptConfigService.enableConfigs(ids);

		Map<String, Object> response = new HashMap<>();
		if (success) {
			response.put("success", true);
			response.put("message", "批量启用配置成功");
		}
		else {
			response.put("success", false);
			response.put("message", "批量启用配置失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 84. batchDisableConfigs

```java
@PostMapping("/batch-disable")
	public ResponseEntity<Map<String, Object>> batchDisableConfigs(@RequestBody List<String> ids) {
		boolean success = promptConfigService.disableConfigs(ids);

		Map<String, Object> response = new HashMap<>();
		if (success) {
			response.put("success", true);
			response.put("message", "批量禁用配置成功");
		}
		else {
			response.put("success", false);
			response.put("message", "批量禁用配置失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 85. updatePriority

```java
@PostMapping("/{id}/priority")
	public ResponseEntity<Map<String, Object>> updatePriority(@PathVariable(value = "id") String id,
			@RequestBody Map<String, Object> requestBody) {
		Integer priority = (Integer) requestBody.get("priority");
		boolean success = promptConfigService.updatePriority(id, priority);

		Map<String, Object> response = new HashMap<>();
		if (success) {
			response.put("success", true);
			response.put("message", "更新优先级成功");
		}
		else {
			response.put("success", false);
			response.put("message", "更新优先级失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 86. updateDisplayOrder

```java
@PostMapping("/{id}/display-order")
	public ResponseEntity<Map<String, Object>> updateDisplayOrder(@PathVariable(value = "id") String id,
			@RequestBody Map<String, Object> requestBody) {
		Integer displayOrder = (Integer) requestBody.get("displayOrder");
		boolean success = promptConfigService.updateDisplayOrder(id, displayOrder);

		Map<String, Object> response = new HashMap<>();
		if (success) {
			response.put("success", true);
			response.put("message", "更新显示顺序成功");
		}
		else {
			response.put("success", false);
			response.put("message", "更新显示顺序失败");
		}

		return ResponseEntity.ok(response);
	}
```


### 87. list

```java
@GetMapping
	public ApiResponse<List<SemanticModel>> list(@RequestParam(value = "keyword", required = false) String keyword,
			@RequestParam(value = "agentId", required = false) Long agentId) {
		List<SemanticModel> result;
		if (keyword != null && !keyword.trim().isEmpty()) {
			result = semanticModelService.search(keyword);
		}
		else if (agentId != null) {
			result = semanticModelService.getByAgentId(agentId);
		}
		else {
			result = semanticModelService.getAll();
		}
		return ApiResponse.success("success list semanticModel", result);
	}
```


### 88. get

```java
@GetMapping("/{id}")
	public ApiResponse<SemanticModel> get(@PathVariable(value = "id") Long id) {
		SemanticModel model = semanticModelService.getById(id);
		return ApiResponse.success("success retrieve semanticModel", model);
	}
```


### 89. create

```java
@PostMapping
	public ApiResponse<Boolean> create(@RequestBody @Validated SemanticModelAddDTO semanticModelAddDto) {
		boolean success = semanticModelService.addSemanticModel(semanticModelAddDto);
		if (success) {
			return ApiResponse.success("Semantic model created successfully", true);
		}
		else {
			return ApiResponse.error("Failed to create semantic model");
		}
	}
```


### 90. update

```java
@PutMapping("/{id}")
	public ApiResponse<SemanticModel> update(@PathVariable(value = "id") Long id, @RequestBody SemanticModel model) {
		if (semanticModelService.getById(id) == null) {
			return ApiResponse.error("Semantic model not found");
		}
		model.setId(id);
		semanticModelService.updateSemanticModel(id, model);
		return ApiResponse.success("Semantic model updated successfully", model);
	}
```


### 91. delete

```java
@DeleteMapping("/{id}")
	public ApiResponse<Boolean> delete(@PathVariable(value = "id") Long id) {
		if (semanticModelService.getById(id) == null) {
			return ApiResponse.error("Semantic model not found");
		}
		semanticModelService.deleteSemanticModel(id);
		return ApiResponse.success("Semantic model deleted successfully", true);
	}
```


### 92. batchDelete

```java
@DeleteMapping("/batch")
	public ApiResponse<Boolean> batchDelete(@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids) {
		semanticModelService.deleteSemanticModels(ids);
		return ApiResponse.success("批量删除成功", true);
	}
```


### 93. enableFields

```java
@PutMapping("/enable")
	public ApiResponse<Boolean> enableFields(@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids) {
		semanticModelService.enableSemanticModels(ids);
		return ApiResponse.success("Semantic models enabled successfully", true);
	}
```


### 94. disableFields

```java
@PutMapping("/disable")
	public ApiResponse<Boolean> disableFields(@RequestBody @NotEmpty(message = "ID列表不能为空") List<Long> ids) {
		ids.forEach(semanticModelService::disableSemanticModel);
		return ApiResponse.success("Semantic models disabled successfully", true);
	}
```


### 95. batchImport

```java
@PostMapping("/batch-import")
	public ApiResponse<BatchImportResult> batchImport(@RequestBody @Valid SemanticModelBatchImportDTO dto) {
		log.info("开始批量导入语义模型: agentId={}, 数量={}", dto.getAgentId(), dto.getItems().size());
		BatchImportResult result = semanticModelService.batchImport(dto);
		log.info("批量导入完成: 总数={}, 成功={}, 失败={}", result.getTotal(), result.getSuccessCount(), result.getFailCount());
		return ApiResponse.success("批量导入完成", result);
	}
```


### 96. downloadTemplate

```java
@GetMapping("/template/download")
	public ResponseEntity<byte[]> downloadTemplate() {
		try {
			ClassPathResource resource = new ClassPathResource("excel/" + TEMPLATE_FILE_NAME);
			if (!resource.exists()) {
				log.error("模板文件不存在: excel/{}", TEMPLATE_FILE_NAME);
				return ResponseEntity.notFound().build();
			}

			byte[] template;
			try (InputStream inputStream = resource.getInputStream()) {
				template = StreamUtils.copyToByteArray(inputStream);
			}

			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
			headers.setContentDisposition(ContentDisposition.attachment().filename(TEMPLATE_FILE_NAME).build());
			return ResponseEntity.ok().headers(headers).body(template);
		}
		catch (IOException e) {
			log.error("读取Excel模板失败", e);
			return ResponseEntity.internalServerError().build();
		}
	}
```


### 97. importExcel

```java
@PostMapping(value = "/import/excel", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	public Mono<ApiResponse<BatchImportResult>> importExcel(@RequestPart("file") FilePart file,
			@RequestPart("agentId") String agentId) {
		Long agentIdLong = Long.parseLong(agentId);
		String filename = file.filename();

		return DataBufferUtils.join(file.content()).flatMap(dataBuffer -> {
			byte[] bytes = new byte[dataBuffer.readableByteCount()];
			dataBuffer.read(bytes);
			DataBufferUtils.release(dataBuffer);

			return Mono.fromCallable(() -> {
				try (InputStream inputStream = new ByteArrayInputStream(bytes)) {
					BatchImportResult result = semanticModelService.importFromExcel(inputStream, filename, agentIdLong);
					return ApiResponse.success("Excel导入完成", result);
				}
			}).subscribeOn(Schedulers.boundedElastic());
		}).onErrorResume(IllegalArgumentException.class, e -> {
			log.error("Excel导入失败: {}", e.getMessage());
			return Mono.just(ApiResponse.error("Excel导入失败: " + e.getMessage()));
		}).onErrorResume(Exception.class, e -> {
			log.error("Excel导入失败", e);
			return Mono.just(ApiResponse.error("Excel导入失败: " + e.getMessage()));
		});
	}
```


### 98. streamSessionUpdates

```java
@GetMapping(value = "/agent/{agentId}/sessions/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
	public Flux<ServerSentEvent<SessionUpdateEvent>> streamSessionUpdates(@PathVariable Integer agentId,
			ServerHttpResponse response) {
		response.getHeaders().add("Cache-Control", "no-cache");
		response.getHeaders().add("Connection", "keep-alive");
		response.getHeaders().add("Access-Control-Allow-Origin", "*");

		log.debug("Client subscribed to session update stream for agent {}", agentId);
		return sessionEventPublisher.register(agentId)
			.doFinally(
					signal -> log.debug("Session update stream finished for agent {} with signal {}", agentId, signal));
	}
```


## Java 全局错误处理基线

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

	@ExceptionHandler(InvalidInputException.class)
	@ResponseStatus(HttpStatus.BAD_REQUEST)
	public ApiResponse<Object> handleInvalidInputException(InvalidInputException e) {
		log.warn("Invalid input: {}", e.getMessage());
		return ApiResponse.error(e.getMessage(), e.getData());
	}

	@ExceptionHandler(InternalServerException.class)
	@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
	public ApiResponse<Object> handleInternalServerException(InternalServerException e) {
		log.error("Internal server error: {}", e.getMessage(), e);
		return ApiResponse.error(e.getMessage());
	}

	@ExceptionHandler(ResponseStatusException.class)
	public ResponseEntity<ApiResponse<Object>> handleResponseStatusException(ResponseStatusException e) {
		String message = e.getReason() == null ? e.getStatusCode().toString() : e.getReason();
		if (e.getStatusCode().is5xxServerError()) {
			log.error("Request failed with status {}: {}", e.getStatusCode(), message, e);
		}
		else {
			log.warn("Request failed with status {}: {}", e.getStatusCode(), message);
		}
		return ResponseEntity.status(e.getStatusCode()).body(ApiResponse.error(message));
	}

	@ExceptionHandler(Exception.class)
	@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
	public ApiResponse<Object> handleGenericException(Exception e) {
		log.error("Unexpected error: {}", e.getMessage(), e);
		return ApiResponse.error("服务器内部错误");
	}

}

```
