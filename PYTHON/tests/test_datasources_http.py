import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.main import create_app


@pytest.fixture
def query_source():
    url = make_url(os.environ["DATAAGENT_TEST_DATABASE_URL"])
    database = "dataagent_query_" + uuid.uuid4().hex
    engine = create_engine(url.set(database=None))
    with engine.begin() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE `{database}`")
        connection.exec_driver_sql(
            f"CREATE TABLE `{database}`.sales (id INT PRIMARY KEY, amount DECIMAL(12,2))"
        )
        connection.exec_driver_sql(f"INSERT INTO `{database}`.sales VALUES (1,12.50)")
    try:
        yield {
            "name": "Sales DB",
            "type": "mysql",
            "host": url.host,
            "port": url.port or 3306,
            "databaseName": database,
            "username": url.username,
            "password": url.password,
        }
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database}`")
        engine.dispose()


def test_real_mysql_configuration_selection_and_restart(query_source):
    with TestClient(create_app()) as client:
        types = client.get("/api/datasource/types").json()["data"]
        assert [item["typeName"] for item in types] == ["mysql", "postgresql"]
        datasource = client.post("/api/datasource", json=query_source).json()
        path = f"/api/datasource/{datasource['id']}"
        assert datasource["password"] == "******"
        assert client.post(path + "/test").json()["success"]
        assert client.get(path + "/tables").json() == ["sales"]
        assert client.get(path + "/tables/sales/columns").json()["data"] == ["id", "amount"]
        agent = client.post("/api/agent", json={"name": "Analyst"}).json()
        bindings = f"/api/agent/{agent['id']}/datasources"
        assert client.post(bindings + "/init").json()["success"] is False
        assert client.post(bindings + f"/{datasource['id']}").json()["success"]
        assert client.post(bindings + f"/{datasource['id']}").json()["success"]
        assert len(client.get(bindings).json()["data"]) == 1
        selected = {"datasourceId": datasource["id"], "tables": ["sales"]}
        assert client.post(bindings + "/tables", json=selected).json()["success"]
        assert not client.post(
            bindings + "/tables", json={**selected, "tables": ["absent"]}
        ).json()["success"]
        assert client.get(bindings + "/active").json()["data"]["selectTables"] == ["sales"]
        assert client.post(bindings + "/init").json()["success"]
        assert client.get(bindings + "/active").json()["data"]["schemaInitialized"] is True
        assert (
            client.put(path, json={"name": "Renamed", "password": "******"}).json()["name"]
            == "Renamed"
        )
    with TestClient(create_app()) as client:
        assert client.post(path + "/test").json()["success"]
        assert client.get(bindings + "/active").json()["data"]["selectTables"] == ["sales"]
        assert client.delete(bindings + f"/{datasource['id']}").json()["success"]
        assert client.get(bindings).json()["data"] == []
        client.post(bindings + f"/{datasource['id']}")
        client.post(bindings + "/tables", json=selected)
        assert client.delete(path).json()["success"]
        assert client.get(bindings).json()["data"] == []
        assert client.get(path).status_code == 404


def test_bad_credentials_types_and_concurrent_bindings(query_source):
    with TestClient(create_app()) as client:
        bad = client.post(
            "/api/datasource", json={**query_source, "password": "invalid-secret"}
        ).json()
        result = client.post(f"/api/datasource/{bad['id']}/test")
        assert not result.json()["success"]
        assert "invalid-secret" not in result.text
        assert client.get(f"/api/datasource/{bad['id']}").json()["testStatus"] == "failed"
        assert not client.post("/api/datasource", json={**query_source, "type": "oracle"}).json()[
            "success"
        ]
        identifiers = [
            client.post("/api/datasource", json=query_source).json()["id"] for _ in range(2)
        ]
        agent = client.post("/api/agent", json={"name": "Concurrent"}).json()["id"]
        path = f"/api/agent/{agent}/datasources"
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda i: client.post(path + f"/{i}"), identifiers))
        assert all(result.json()["success"] for result in results)
        rows = client.get(path).json()["data"]
        assert len(rows) == 2
        assert sum(row["isActive"] for row in rows) == 1
        inactive = next(row for row in rows if not row["isActive"])
        assert not client.put(
            path + "/toggle", json={"datasourceId": inactive["datasourceId"], "isActive": True}
        ).json()["success"]


def test_mysql_connection_url_and_rejection_of_embedded_secrets(query_source):
    with TestClient(create_app()) as client:
        url = (
            f"jdbc:mysql://{query_source['host']}:{query_source['port']}/"
            f"{query_source['databaseName']}?useSSL=false&characterEncoding=UTF-8&connectTimeout=5000"
        )
        source = client.post("/api/datasource", json={**query_source, "connectionUrl": url}).json()
        assert source["connectionUrl"] == url
        assert client.post(f"/api/datasource/{source['id']}/test").json()["success"]
        for bad in [
            "mysql://user:secret@localhost/db",
            "jdbc:mysql://localhost/db?password=secret",
            "jdbc:mysql://localhost/db?unsupported=true",
        ]:
            result = client.post("/api/datasource", json={**query_source, "connectionUrl": bad})
            assert not result.json()["success"]
            assert "secret" not in result.text
