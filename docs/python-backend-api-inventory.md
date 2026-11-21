# Java HTTP 接口基线清单

日期：2026-11-14。来源：上游后端的 14 个 Controller，共 98 个显式 HTTP 映射。仅提取方法和路径，不代表已完成 Python 实现或请求响应契约核验。

此清单不含框架生成的 OpenAPI、静态资源或隐式 HEAD/OPTIONS。完整范围及排除项见 [设计](python-backend-design.md)，验收阶段见 [任务清单](python-backend-tasks.md)。参数、DTO、状态码、鉴权和副作用在实施时逐项补充；所有接口当前均为“待实现 / 待验收”。

Python 扩展包含 `GET /api/sessions/{sessionId}/active-run`、`GET /api/sessions/{sessionId}/runs`、`GET /api/sessions/{sessionId}/runs/{threadId}`，分别用于审核找回、发现终态运行及读取最终快照。原图请求增加可选 feedbackRevision，审核事件增加 planRevision/plan，消息 metadata 使用稳定幂等键；Python stop 增加必填 agentId。运行/结果/标题接口的凭据头及归属校验、删除遇未结束任务返回 409，均是明确兼容差异。详情见 [spec](python-backend-spec.md) 及设计第 5、6 节；新增路由不计入下面 98 个 Java 映射，须单独验收。Python 前端需启用 fetch SSE、版本绑定、结果找回等适配，Java 后端不启用扩展。阶段 0 完成逐接口契约矩阵及差异确认，才进入相应业务实现，路由计数不代表契约完成。

## 分类统计

实现状态补充：Ticket 01 的 61、66–72 已交付；Ticket 02 的 1–4、6–19、27–29、47–55 已交付（[验证与限制](python-ticket02-validation.md)）。其余映射仍待实现；本状态不改变下方原始映射基线。

| Controller | HTTP 映射数 |
| --- | ---: |
| AgentController | 12 |
| AgentDatasourceController | 7 |
| AgentKnowledgeController | 7 |
| AgentPresetQuestionController | 3 |
| BusinessKnowledgeController | 8 |
| ChatController | 9 |
| DatasourceController | 14 |
| EchoController | 1 |
| FileUploadController | 2 |
| GraphController | 2 |
| ModelConfigController | 7 |
| PromptConfigController | 14 |
| SemanticModelController | 11 |
| SessionEventController | 1 |

## 路由清单

来源列记录上游映射注解的位置。接口名未改为 Python 命名，便于与前端逐项对照。

| 编号 | Controller | 方法 | 完整路径 | 来源 |
| ---: | --- | --- | --- | --- |
| 1 | AgentController | GET | `/api/agent/list` | `AgentController.java:50` |
| 2 | AgentController | GET | `/api/agent/{id}` | `AgentController.java:67` |
| 3 | AgentController | POST | `/api/agent` | `AgentController.java:73` |
| 4 | AgentController | PUT | `/api/agent/{id}` | `AgentController.java:83` |
| 5 | AgentController | DELETE | `/api/agent/{id}` | `AgentController.java:91` |
| 6 | AgentController | POST | `/api/agent/{id}/publish` | `AgentController.java:98` |
| 7 | AgentController | POST | `/api/agent/{id}/offline` | `AgentController.java:106` |
| 8 | AgentController | GET | `/api/agent/{id}/api-key` | `AgentController.java:114` |
| 9 | AgentController | POST | `/api/agent/{id}/api-key/generate` | `AgentController.java:122` |
| 10 | AgentController | POST | `/api/agent/{id}/api-key/reset` | `AgentController.java:130` |
| 11 | AgentController | DELETE | `/api/agent/{id}/api-key` | `AgentController.java:138` |
| 12 | AgentController | POST | `/api/agent/{id}/api-key/enable` | `AgentController.java:146` |
| 13 | AgentDatasourceController | POST | `/api/agent/{agentId}/datasources/init` | `AgentDatasourceController.java:49` |
| 14 | AgentDatasourceController | GET | `/api/agent/{agentId}/datasources` | `AgentDatasourceController.java:88` |
| 15 | AgentDatasourceController | GET | `/api/agent/{agentId}/datasources/active` | `AgentDatasourceController.java:102` |
| 16 | AgentDatasourceController | POST | `/api/agent/{agentId}/datasources/{datasourceId}` | `AgentDatasourceController.java:116` |
| 17 | AgentDatasourceController | POST | `/api/agent/{agentId}/datasources/tables` | `AgentDatasourceController.java:133` |
| 18 | AgentDatasourceController | DELETE | `/api/agent/{agentId}/datasources/{datasourceId}` | `AgentDatasourceController.java:148` |
| 19 | AgentDatasourceController | PUT | `/api/agent/{agentId}/datasources/toggle` | `AgentDatasourceController.java:160` |
| 20 | AgentKnowledgeController | GET | `/api/agent-knowledge/{id}` | `AgentKnowledgeController.java:55` |
| 21 | AgentKnowledgeController | POST | `/api/agent-knowledge/create` | `AgentKnowledgeController.java:75` |
| 22 | AgentKnowledgeController | PUT | `/api/agent-knowledge/{id}` | `AgentKnowledgeController.java:129` |
| 23 | AgentKnowledgeController | PUT | `/api/agent-knowledge/recall/{id}` | `AgentKnowledgeController.java:136` |
| 24 | AgentKnowledgeController | DELETE | `/api/agent-knowledge/{id}` | `AgentKnowledgeController.java:146` |
| 25 | AgentKnowledgeController | POST | `/api/agent-knowledge/query/page` | `AgentKnowledgeController.java:152` |
| 26 | AgentKnowledgeController | POST | `/api/agent-knowledge/retry-embedding/{id}` | `AgentKnowledgeController.java:165` |
| 27 | AgentPresetQuestionController | GET | `/api/agent/{agentId}/preset-questions` | `AgentPresetQuestionController.java:41` |
| 28 | AgentPresetQuestionController | POST | `/api/agent/{agentId}/preset-questions` | `AgentPresetQuestionController.java:56` |
| 29 | AgentPresetQuestionController | DELETE | `/api/agent/{agentId}/preset-questions/{questionId}` | `AgentPresetQuestionController.java:88` |
| 30 | BusinessKnowledgeController | GET | `/api/business-knowledge` | `BusinessKnowledgeController.java:40` |
| 31 | BusinessKnowledgeController | GET | `/api/business-knowledge/{id}` | `BusinessKnowledgeController.java:55` |
| 32 | BusinessKnowledgeController | POST | `/api/business-knowledge` | `BusinessKnowledgeController.java:64` |
| 33 | BusinessKnowledgeController | PUT | `/api/business-knowledge/{id}` | `BusinessKnowledgeController.java:70` |
| 34 | BusinessKnowledgeController | DELETE | `/api/business-knowledge/{id}` | `BusinessKnowledgeController.java:78` |
| 35 | BusinessKnowledgeController | POST | `/api/business-knowledge/recall/{id}` | `BusinessKnowledgeController.java:87` |
| 36 | BusinessKnowledgeController | POST | `/api/business-knowledge/refresh-vector-store` | `BusinessKnowledgeController.java:94` |
| 37 | BusinessKnowledgeController | POST | `/api/business-knowledge/retry-embedding/{id}` | `BusinessKnowledgeController.java:111` |
| 38 | ChatController | GET | `/api/agent/{id}/sessions` | `ChatController.java:61` |
| 39 | ChatController | POST | `/api/agent/{id}/sessions` | `ChatController.java:70` |
| 40 | ChatController | DELETE | `/api/agent/{id}/sessions` | `ChatController.java:87` |
| 41 | ChatController | GET | `/api/sessions/{sessionId}/messages` | `ChatController.java:96` |
| 42 | ChatController | POST | `/api/sessions/{sessionId}/messages` | `ChatController.java:105` |
| 43 | ChatController | PUT | `/api/sessions/{sessionId}/pin` | `ChatController.java:140` |
| 44 | ChatController | PUT | `/api/sessions/{sessionId}/rename` | `ChatController.java:157` |
| 45 | ChatController | DELETE | `/api/sessions/{sessionId}` | `ChatController.java:177` |
| 46 | ChatController | POST | `/api/sessions/{sessionId}/reports/html` | `ChatController.java:192` |
| 47 | DatasourceController | GET | `/api/datasource/types` | `DatasourceController.java:61` |
| 48 | DatasourceController | GET | `/api/datasource` | `DatasourceController.java:84` |
| 49 | DatasourceController | GET | `/api/datasource/{id}` | `DatasourceController.java:106` |
| 50 | DatasourceController | GET | `/api/datasource/{id}/tables` | `DatasourceController.java:111` |
| 51 | DatasourceController | POST | `/api/datasource` | `DatasourceController.java:125` |
| 52 | DatasourceController | PUT | `/api/datasource/{id}` | `DatasourceController.java:138` |
| 53 | DatasourceController | DELETE | `/api/datasource/{id}` | `DatasourceController.java:152` |
| 54 | DatasourceController | POST | `/api/datasource/{id}/test` | `DatasourceController.java:170` |
| 55 | DatasourceController | GET | `/api/datasource/{id}/tables/{tableName}/columns` | `DatasourceController.java:184` |
| 56 | DatasourceController | GET | `/api/datasource/{id}/logical-relations` | `DatasourceController.java:198` |
| 57 | DatasourceController | POST | `/api/datasource/{id}/logical-relations` | `DatasourceController.java:213` |
| 58 | DatasourceController | PUT | `/api/datasource/{id}/logical-relations/{relationId}` | `DatasourceController.java:238` |
| 59 | DatasourceController | DELETE | `/api/datasource/{id}/logical-relations/{relationId}` | `DatasourceController.java:264` |
| 60 | DatasourceController | PUT | `/api/datasource/{id}/logical-relations` | `DatasourceController.java:280` |
| 61 | EchoController | GET | `/echo/ok` | `EchoController.java:33` |
| 62 | FileUploadController | POST | `/api/upload/avatar` | `FileUploadController.java:58` |
| 63 | FileUploadController | GET | `/api/upload/**` | `FileUploadController.java:87` |
| 64 | GraphController | GET | `/api/stream/search` | `GraphController.java:49` |
| 65 | GraphController | POST | `/api/stream/stop` | `GraphController.java:106` |
| 66 | ModelConfigController | GET | `/api/model-config/list` | `ModelConfigController.java:40` |
| 67 | ModelConfigController | POST | `/api/model-config/add` | `ModelConfigController.java:51` |
| 68 | ModelConfigController | PUT | `/api/model-config/update` | `ModelConfigController.java:63` |
| 69 | ModelConfigController | DELETE | `/api/model-config/{id}` | `ModelConfigController.java:75` |
| 70 | ModelConfigController | POST | `/api/model-config/activate/{id}` | `ModelConfigController.java:87` |
| 71 | ModelConfigController | POST | `/api/model-config/test/{id}` | `ModelConfigController.java:101` |
| 72 | ModelConfigController | GET | `/api/model-config/check-ready` | `ModelConfigController.java:116` |
| 73 | PromptConfigController | POST | `/api/prompt-config/save` | `PromptConfigController.java:53` |
| 74 | PromptConfigController | GET | `/api/prompt-config/{id}` | `PromptConfigController.java:72` |
| 75 | PromptConfigController | GET | `/api/prompt-config/list` | `PromptConfigController.java:93` |
| 76 | PromptConfigController | GET | `/api/prompt-config/list-by-type/{promptType}` | `PromptConfigController.java:111` |
| 77 | PromptConfigController | GET | `/api/prompt-config/active/{promptType}` | `PromptConfigController.java:130` |
| 78 | PromptConfigController | GET | `/api/prompt-config/active-all/{promptType}` | `PromptConfigController.java:149` |
| 79 | PromptConfigController | DELETE | `/api/prompt-config/{id}` | `PromptConfigController.java:168` |
| 80 | PromptConfigController | POST | `/api/prompt-config/{id}/enable` | `PromptConfigController.java:190` |
| 81 | PromptConfigController | POST | `/api/prompt-config/{id}/disable` | `PromptConfigController.java:212` |
| 82 | PromptConfigController | GET | `/api/prompt-config/types` | `PromptConfigController.java:233` |
| 83 | PromptConfigController | POST | `/api/prompt-config/batch-enable` | `PromptConfigController.java:250` |
| 84 | PromptConfigController | POST | `/api/prompt-config/batch-disable` | `PromptConfigController.java:272` |
| 85 | PromptConfigController | POST | `/api/prompt-config/{id}/priority` | `PromptConfigController.java:295` |
| 86 | PromptConfigController | POST | `/api/prompt-config/{id}/display-order` | `PromptConfigController.java:320` |
| 87 | SemanticModelController | GET | `/api/semantic-model` | `SemanticModelController.java:60` |
| 88 | SemanticModelController | GET | `/api/semantic-model/{id}` | `SemanticModelController.java:76` |
| 89 | SemanticModelController | POST | `/api/semantic-model` | `SemanticModelController.java:82` |
| 90 | SemanticModelController | PUT | `/api/semantic-model/{id}` | `SemanticModelController.java:93` |
| 91 | SemanticModelController | DELETE | `/api/semantic-model/{id}` | `SemanticModelController.java:103` |
| 92 | SemanticModelController | DELETE | `/api/semantic-model/batch` | `SemanticModelController.java:115` |
| 93 | SemanticModelController | PUT | `/api/semantic-model/enable` | `SemanticModelController.java:122` |
| 94 | SemanticModelController | PUT | `/api/semantic-model/disable` | `SemanticModelController.java:129` |
| 95 | SemanticModelController | POST | `/api/semantic-model/batch-import` | `SemanticModelController.java:138` |
| 96 | SemanticModelController | GET | `/api/semantic-model/template/download` | `SemanticModelController.java:146` |
| 97 | SemanticModelController | POST | `/api/semantic-model/import/excel` | `SemanticModelController.java:171` |
| 98 | SessionEventController | GET | `/api/agent/{agentId}/sessions/stream` | `SessionEventController.java:37` |

## 源码 SHA-256 快照

用于检查后续源码是否变化；非 Java 服务运行结果或接口兼容性证明。

| 文件 | SHA-256 |
| --- | --- |
| AgentController.java | `53f697b1940346f0f7072b2d104169c2ce6a53133004f75c32f8e4078abc8ca7` |
| AgentDatasourceController.java | `15702187d9917d72831afa7141553b71d9f51e7139348eac2e94b501b4140d59` |
| AgentKnowledgeController.java | `3f05787d652ad314bc9b3524a01f4fc2cfab173eb5098b5e350627cdb32d5621` |
| AgentPresetQuestionController.java | `7b02d290da6f99496e9f8c215454a1323b0426fcdb0177709c09eabdf1d0f377` |
| BusinessKnowledgeController.java | `596fb6289c3a80d629ad4d3e24926f673794568eccc3f7be76735c9857fd5085` |
| ChatController.java | `81171a78c289e8d3f1965183f3e8fd13cdbf3170034856e6612193e09b6d7335` |
| DatasourceController.java | `88fdd3be837b841835a4bc99a846326535fa82384be7dc31a720655718e447ab` |
| EchoController.java | `6886e32f8b566c89207e38331d6292050fb8da4a1afebd33bc5c91b0c0e1d4f0` |
| FileUploadController.java | `5a182caeac9ce40d03a07be980e6451c20b15471c992a9bacc0f706d3fb2450c` |
| GraphController.java | `7e404eee66d8cd9b8e9fb131974a241461c401089f41e81b23add8b8e82288e1` |
| ModelConfigController.java | `923fbf22de079cd754ecd69290c84c49b8c75a55566859aac734f42fae8e4512` |
| PromptConfigController.java | `c3c7401aced8ac964e08fa4787d19d00ebaab9b46a71a68e8e16d90ae0606553` |
| SemanticModelController.java | `700b68177250bc010c1fcd0f393a5cb2a716d6613419635af0e87552da6f8284` |
| SessionEventController.java | `f02c4f8d1143df6423c82229a406c9e0524acfe81cd95cd046e1385efd9ba6b4` |
