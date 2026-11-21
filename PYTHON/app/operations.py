"""Local recovery CLI. Only positively stopped runs may be resolved as failed."""

import argparse
import json
import socket
import uuid

import psutil
import redis
from sqlalchemy import text

from app.config import Settings
from app.database import open_database
from app.datasources import business_connection, require_datasource
from app.run_coordination import RunCoordinator, RunHandle


def stopped_evidence(conn, run):
    original = json.loads(run['request']) if isinstance(run['request'], str) else run['request']
    worker = original.get('_worker') or {}
    if worker.get('host') != socket.gethostname() or not worker.get('pid') or not worker.get('started'):
        raise ValueError('缺少可核对的本机 worker 身份，不能安全收尾')
    try:
        process = psutil.Process(int(worker['pid']))
        if process.create_time() == worker['started']:
            raise ValueError('原 worker 进程仍存在，必须先确认停止')
    except psutil.NoSuchProcess:
        pass
    effects = conn.execute(text(
        "SELECT query_id FROM graph_effect WHERE thread_id=:tid AND status='IN_FLIGHT'"
    ), {'tid': run['thread_id']}).scalars().all()
    if effects:
        snapshot = json.loads(run['config_snapshot']) if isinstance(run['config_snapshot'], str) else run['config_snapshot']
        target = snapshot['datasource']
        source = require_datasource(conn, target['id'])
        identity = {'type': 'type', 'host': 'host', 'port': 'port', 'databaseName': 'database_name',
                    'schemaName': 'schema_name', 'connectionUrl': 'connection_url', 'username': 'username'}
        if any(target.get(key) != source.get(field) for key, field in identity.items()):
            raise ValueError('数据源身份已改变，不能用当前目标证明旧查询停止')
        with business_connection(source, preserve_errors=True) as business:
            for pid in effects:
                if not pid or not str(pid).isdigit():
                    raise ValueError('缺少可核对的数据库连接身份')
                sql = ('SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID=:pid'
                       if source['type'] == 'mysql' else
                       'SELECT COUNT(*) FROM pg_stat_activity WHERE pid=:pid')
                if business.execute(text(sql), {'pid': int(pid)}).scalar_one():
                    raise ValueError('数据库连接仍存在，不能确认查询停止')
    return {'workerStopped': worker, 'databaseConnectionsAbsent': list(effects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'resolve-failed'])
    parser.add_argument('--thread-id')
    parser.add_argument('--expected-version', type=int)
    parser.add_argument('--operator')
    parser.add_argument('--reason')
    args = parser.parse_args()
    settings = Settings()
    engine = open_database(settings.database_url)
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        with engine.connect() as conn:
            records = conn.execute(text(
                'SELECT thread_id,agent_id,conversation_id,status,version,owner,checkpoint_id,error FROM agent_run '
                + ('WHERE thread_id=:tid ' if args.thread_id else '')
                + 'ORDER BY created_at,thread_id'
            ), {'tid': args.thread_id}).mappings().all()
            rows = [dict(row) for row in records]
            if args.command == 'inspect':
                for row in rows:
                    row['uncertainEffects'] = [dict(effect) for effect in conn.execute(text(
                        "SELECT effect_key,status,query_id,owner FROM graph_effect WHERE thread_id=:tid "
                        "AND status IN ('PREPARED','IN_FLIGHT')"
                    ), {'tid': row['thread_id']}).mappings()]
        if args.command == 'inspect':
            print(json.dumps(rows, ensure_ascii=False))
            return
        if (not args.thread_id or args.expected_version is None or
                not args.operator or not args.reason or len(rows) != 1):
            parser.error('resolve-failed 必须提供唯一 thread-id、expected-version、operator 和 reason')
        row = rows[0]
        coordinator = RunCoordinator(engine, client)
        with coordinator._session_lock(row['agent_id'], row['conversation_id']) as (conn, token):
            run = conn.execute(text('SELECT * FROM agent_run WHERE thread_id=:tid FOR UPDATE'),
                               {'tid': args.thread_id}).mappings().one()
            repeated = conn.execute(text(
                'SELECT 1 FROM agent_operation_audit WHERE thread_id=:tid AND expected_version=:version '
                'AND operator=:operator AND reason=:reason LIMIT 1'
            ), {'tid': args.thread_id, 'version': args.expected_version,
                'operator': args.operator, 'reason': args.reason}).scalar()
            if run['status'] == 'FAILED' and repeated:
                print(json.dumps({'threadId': args.thread_id, 'status': 'FAILED'}))
                return
            if run['status'] != 'RECOVERY_REQUIRED' or run['version'] != args.expected_version:
                raise ValueError('运行状态或 version 不匹配；请重新 inspect')
            evidence = stopped_evidence(conn, run)
            conn.execute(text(
                'INSERT INTO agent_operation_audit(operation_id,thread_id,expected_version,operator,reason,evidence) '
                'VALUES (:id,:tid,:version,:operator,:reason,:evidence)'
            ), {'id': str(uuid.uuid4()), 'tid': args.thread_id, 'version': args.expected_version,
                'operator': args.operator, 'reason': args.reason, 'evidence': json.dumps(evidence)})
            conn.execute(text('UPDATE agent_run SET owner=:owner,version=version+1 WHERE thread_id=:tid'),
                         {'owner': token, 'tid': args.thread_id})
            conn.execute(text("UPDATE graph_effect SET status='FAILED' WHERE thread_id=:tid "
                              "AND status='IN_FLIGHT'"), {'tid': args.thread_id})
        coordinator.fail_run(RunHandle(args.thread_id, row['agent_id'], row['conversation_id'],
                                      args.expected_version + 1, token), reason='人工对账收尾：' + args.reason)
        print(json.dumps({'threadId': args.thread_id, 'status': 'FAILED'}))
    finally:
        client.close()
        engine.dispose()


if __name__ == '__main__':
    main()
