# Java 框架表单列清单

按上游 pom.xml 固定 Spring AI 1.1.2、Spring AI Alibaba 1.1.2.2 核对，不计入 13 张业务表，也不执行到 Python 管理库。

|框架表|字段/索引与归属|迁移决定|
|---|---|---|
|SPRING_AI_CHAT_MEMORY|conversation_id、content、type、timestamp；会话/时间复合索引；由 JDBC ChatMemory 初始化|由成功轮次重建 Python turn，不导入旧框架对象|
|GRAPH_THREAD|thread_id 主键、thread_name、is_released；名称与释放标记唯一索引；由 MysqlSaver 初始化|不复制，以 Python threadId 和 saver 新建|
|GRAPH_CHECKPOINT|checkpoint_id 主键、thread_id 外键、node_id、next_node_id、state_data、saved_at；线程删除级联；state_data 包含 Java 二进制序列化包装|禁止在 Python 反序列化或直接迁移，历史展示消息不受影响|

核对来源：[Spring AI v1.1.2 schema](https://raw.githubusercontent.com/spring-projects/spring-ai/v1.1.2/memory/repository/spring-ai-model-chat-memory-repository-jdbc/src/main/resources/org/springframework/ai/chat/memory/repository/jdbc/schema-mysql.sql)、[Alibaba v1.1.2.2 MysqlSaver](https://raw.githubusercontent.com/alibaba/spring-ai-alibaba/v1.1.2.2/spring-ai-alibaba-graph-core/src/main/java/com/alibaba/cloud/ai/graph/checkpoint/savers/mysql/MysqlSaver.java)。部署实例是否实际建表、表名大小写和现存数据需在 Ticket 16 只读核验；本次已确认版本源码定义，不将未附带 SQL 当成没有框架表。

Python saver 3.1.3 setup 的 checkpoints/writes 在独立 SQLite 文件内，MySQL 迁移表 python_schema_migration 单独记录 001/002。saver 版本与数据库文件配套备份；升级需中断/重启/恢复回归，不能由业务 ORM 接管或修改 saver 表。
