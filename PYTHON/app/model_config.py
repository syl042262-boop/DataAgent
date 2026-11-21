"""Model configuration HTTP DTO, persistence and OpenAI-compatible transport."""

import json
import math
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import MetaData, Table, insert, select, text, update
from sqlalchemy.engine import Connection, Engine


class ModelConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = None
    provider: str = Field(min_length=1, max_length=255)
    baseUrl: str = Field(min_length=1, max_length=255)
    apiKey: str | None = Field(default=None, max_length=255)
    modelName: str = Field(min_length=1, max_length=255)
    modelType: Literal["CHAT", "EMBEDDING"]
    temperature: float = Field(default=0.0, ge=0, le=2, allow_inf_nan=False)
    maxTokens: int = Field(default=2000, gt=0)
    isActive: bool = False
    completionsPath: str | None = Field(default=None, max_length=255)
    embeddingsPath: str | None = Field(default=None, max_length=255)
    proxyEnabled: bool = False
    proxyHost: str | None = Field(default=None, max_length=255)
    proxyPort: int | None = Field(default=None, ge=1, le=65535)
    proxyUsername: str | None = Field(default=None, max_length=255)
    proxyPassword: str | None = Field(default=None, max_length=255)

    @field_validator("baseUrl")
    @classmethod
    def http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("baseUrl 必须是不含凭据、查询及片段的 HTTP(S) URL")
        return value.rstrip("/")

    @field_validator("completionsPath", "embeddingsPath")
    @classmethod
    def relative_endpoint(cls, value: str | None) -> str | None:
        if value and (
            not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value
        ):
            raise ValueError("模型路径必须是 / 开头的相对路径")
        return value

    @model_validator(mode="after")
    def proxy_complete(self):
        if self.proxyEnabled and (not self.proxyHost or not self.proxyPort):
            raise ValueError("代理启用时必须提供主机和端口")
        return self


def snake(name: str) -> str:
    return "".join("_" + c.lower() if c.isupper() else c for c in name)


def as_dto(row: Any, masked: bool = False) -> ModelConfig:
    result = ModelConfig.model_validate(
        {name: row[snake(name)] for name in ModelConfig.model_fields}
    )
    if masked:
        result.apiKey = "****" if result.apiKey else None
        result.proxyPassword = "****" if result.proxyPassword else None
    return result


class ModelStore:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.table = Table("model_config", MetaData(), autoload_with=engine)

    def list(self) -> list[ModelConfig]:
        with self.engine.connect() as connection:
            return [
                as_dto(row, masked=True)
                for row in connection.execute(
                    select(self.table)
                    .where(self.table.c.is_deleted == 0)
                    .order_by(self.table.c.id.desc())
                ).mappings()
            ]

    def get(self, connection: Connection, identifier: int) -> ModelConfig:
        row = (
            connection.execute(
                select(self.table)
                .where(self.table.c.id == identifier, self.table.c.is_deleted == 0)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ValueError("配置不存在")
        return as_dto(row)

    def lock_types(self, connection: Connection) -> None:
        connection.execute(
            text("SELECT model_type FROM python_model_type_lock ORDER BY model_type FOR UPDATE")
        ).all()

    def add(self, config: ModelConfig) -> None:
        if (config.apiKey and "****" in config.apiKey) or (
            config.proxyPassword and "****" in config.proxyPassword
        ):
            raise ValueError("新增配置不能使用脱敏凭据")
        values = {snake(k): v for k, v in config.model_dump(exclude={"id", "isActive"}).items()}
        values.update(api_key=config.apiKey or "", is_active=False, is_deleted=0)
        with self.engine.begin() as connection:
            connection.execute(insert(self.table).values(**values))

    def update(self, config: ModelConfig) -> None:
        if config.id is None:
            raise ValueError("id 必填")
        with self.engine.begin() as connection:
            self.lock_types(connection)
            old = self.get(connection, config.id)
            if config.modelType != old.modelType:
                raise ValueError("模型类型不允许修改")
            for field in ("apiKey", "proxyPassword"):
                value = getattr(config, field)
                if not value or "****" in value:
                    setattr(config, field, getattr(old, field))
            if old.isActive and old.modelType == "EMBEDDING":
                validate_embedding_space(old, config)
            values = {snake(k): v for k, v in config.model_dump(exclude={"id", "isActive"}).items()}
            connection.execute(
                update(self.table).where(self.table.c.id == config.id).values(**values)
            )

    def delete(self, identifier: int) -> None:
        with self.engine.begin() as connection:
            self.lock_types(connection)
            config = self.get(connection, identifier)
            if config.isActive:
                raise ValueError(
                    "该配置当前正在使用中，无法删除！请先激活其他配置，再进行删除操作。"
                )
            connection.execute(
                update(self.table).where(self.table.c.id == identifier).values(is_deleted=1)
            )

    def activate(self, identifier: int) -> None:
        with self.engine.begin() as connection:
            self.lock_types(connection)
            config = self.get(connection, identifier)
            validate_credentials(config)
            if config.modelType == "EMBEDDING":
                current = (
                    connection.execute(
                        select(self.table).where(
                            self.table.c.model_type == "EMBEDDING",
                            self.table.c.is_active == 1,
                            self.table.c.is_deleted == 0,
                        )
                    )
                    .mappings()
                    .first()
                )
                if current:
                    validate_embedding_space(as_dto(current), config)
            connection.execute(
                update(self.table)
                .where(self.table.c.model_type == config.modelType)
                .values(is_active=False)
            )
            connection.execute(
                update(self.table).where(self.table.c.id == identifier).values(is_active=True)
            )

    def ready(self) -> dict[str, bool]:
        with self.engine.connect() as connection:
            types = set(
                connection.execute(
                    select(self.table.c.model_type).where(
                        self.table.c.is_active == 1, self.table.c.is_deleted == 0
                    )
                ).scalars()
            )
        return {
            "chatModelReady": "CHAT" in types,
            "embeddingModelReady": "EMBEDDING" in types,
            "ready": {"CHAT", "EMBEDDING"} <= types,
        }

    def read(self, identifier: int) -> ModelConfig:
        with self.engine.begin() as connection:
            return self.get(connection, identifier)

    def active_chat(self) -> ModelConfig:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(self.table).where(
                        self.table.c.model_type == "CHAT",
                        self.table.c.is_active == 1,
                        self.table.c.is_deleted == 0,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ValueError("未配置激活的 CHAT 模型")
            return as_dto(row)


def validate_credentials(config: ModelConfig) -> None:
    if config.provider.lower() != "custom" and not config.apiKey:
        raise ValueError("apiKey must not be empty")


def validate_embedding_space(current: ModelConfig, target: ModelConfig) -> None:
    fields = ("provider", "baseUrl", "modelName", "embeddingsPath")
    if any(getattr(current, field) != getattr(target, field) for field in fields):
        raise ValueError(
            "Embedding model hot switch is unsafe for existing vectors. "
            "Create a new versioned collection and rebuild vectors before switching."
        )


def _post_model_json(
    config: ModelConfig, path: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    proxy = None
    if config.proxyEnabled:
        auth = (config.proxyUsername or "", config.proxyPassword or "")
        proxy = httpx.Proxy(
            f"http://{config.proxyHost}:{config.proxyPort}", auth=auth if auth[0] else None
        )
    try:
        with httpx.Client(timeout=timeout, proxy=proxy, trust_env=False) as client:
            response = client.post(
                config.baseUrl + path,
                json=payload,
                headers={"Authorization": f"Bearer {config.apiKey}"} if config.apiKey else {},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as error:
        # Never echo upstream bodies/URLs: they can contain credentials.
        raise ValueError(
            f"模型服务返回 HTTP {error.response.status_code}，请检查凭据、路径和额度"
        ) from None
    except httpx.RequestError:
        raise ValueError("模型服务连接失败或超时，请检查地址和代理") from None


def chat_completion(
    config: ModelConfig, messages: list[dict[str, str]], timeout: float
) -> str:
    validate_credentials(config)
    path = config.completionsPath or "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": config.modelName,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.maxTokens,
    }
    result = _post_model_json(config, path, payload, timeout)
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("模型返回格式无效") from None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型返回内容为空/无效")
    return content.strip()


def chat_completion_chunks(config: ModelConfig, messages: list[dict[str, str]], timeout: float):
    """Read provider SSE deltas; accept non-streaming JSON providers explicitly."""
    validate_credentials(config)
    proxy = None
    if config.proxyEnabled:
        auth = (config.proxyUsername or '', config.proxyPassword or '')
        proxy = httpx.Proxy(f'http://{config.proxyHost}:{config.proxyPort}',
                            auth=auth if auth[0] else None)
    try:
        with httpx.Client(timeout=timeout, proxy=proxy, trust_env=False) as client:  # noqa: SIM117
            with client.stream('POST', config.baseUrl + (config.completionsPath or
                               '/v1/chat/completions'),
                               headers={'Authorization': f'Bearer {config.apiKey}'},
                               json={'model': config.modelName, 'messages': messages,
                                     'temperature': config.temperature,
                                     'max_tokens': config.maxTokens, 'stream': True}) as response:
                response.raise_for_status()
                if 'text/event-stream' not in response.headers.get('content-type', ''):
                    response.read()
                    yield response.json()['choices'][0]['message']['content']
                    return
                finished = False
                for line in response.iter_lines():
                    if not line.startswith('data:'):
                        continue
                    raw = line[5:].strip()
                    if raw == '[DONE]':
                        finished = True
                        break
                    payload = json.loads(raw)
                    choices = payload.get('choices') or []
                    if not choices:
                        continue
                    if choices[0].get('finish_reason') == 'stop':
                        finished = True
                    chunk = choices[0].get('delta', {}).get('content')
                    if chunk:
                        yield chunk
                if not finished:
                    raise ValueError('报告模型流在完成前断开')
    except httpx.HTTPStatusError as error:
        raise ValueError(f'模型服务返回 HTTP {error.response.status_code}') from None
    except httpx.RequestError:
        raise ValueError('模型服务连接失败或超时') from None


def test_model(config: ModelConfig, timeout: float, expected_dimension: int = 0) -> None:
    validate_credentials(config)
    is_chat = config.modelType == "CHAT"
    path = (config.completionsPath if is_chat else config.embeddingsPath) or (
        "/v1/chat/completions" if is_chat else "/v1/embeddings"
    )
    payload: dict[str, Any] = {"model": config.modelName}
    if is_chat:
        payload.update(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=config.temperature,
            max_tokens=config.maxTokens,
        )
    else:
        payload.update(input="Test", encoding_format="float")
    result = _post_model_json(config, path, payload, timeout)
    try:
        if is_chat:
            content = result["choices"][0]["message"]["content"]
            valid = isinstance(content, str) and bool(content.strip())
        else:
            vector = result["data"][0]["embedding"]
            valid = (
                isinstance(vector, list)
                and bool(vector)
                and all(
                    isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in vector
                )
            )
        if not valid:
            raise ValueError("模型返回内容或向量为空/无效")
        if not is_chat and expected_dimension > 0 and len(vector) != expected_dimension:
            raise ValueError(
                f"Embedding dimension {len(vector)} does not match vector-store dimension "
                f"{expected_dimension}. Rebuild vectors before switching."
            )
    except (KeyError, IndexError, TypeError):
        raise ValueError("模型返回格式无效") from None
