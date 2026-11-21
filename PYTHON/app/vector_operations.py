"""Offline embedding-space migration; rebuild all records before changing the active model.

Stop the Python server before this maintenance command. Online activation guards
remain unchanged. Failures leave the old default selected and can be retried.
"""

import argparse
import json

from sqlalchemy import text

from app.config import Settings
from app.database import migrate, open_database
from app.knowledge_store import TABLES, KnowledgeStore, embedding_config, embedding_space
from app.migration import MigrationError
from app.model_config import ModelStore, validate_credentials


def require_idle(conn):
    if conn.execute(
        text(
            "SELECT 1 FROM agent_run WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED') LIMIT 1"
        )
    ).first():
        raise MigrationError("Nonterminal runs exist; finish or reconcile before index maintenance")
    if conn.execute(
        text("SELECT 1 FROM agent_cleanup_job WHERE status<>'COMPLETED' LIMIT 1")
    ).first():
        raise MigrationError("Finish pending resource cleanup before index maintenance")


def rebuild_and_activate(settings, model_id):
    engine = open_database(settings.database_url)
    try:
        migrate(engine)
        with engine.connect() as lock:
            if (
                lock.exec_driver_sql(
                    "SELECT GET_LOCK('dataagent_python_vector_migration',30)"
                ).scalar()
                != 1
            ):
                raise MigrationError("Vector migration lock unavailable")
            lock.commit()
            try:
                require_idle(lock)
                models = ModelStore(engine)
                target = models.read(model_id)
                if target.modelType != "EMBEDDING":
                    raise MigrationError("Select an EMBEDDING model")
                validate_credentials(target)
                previous = embedding_config(engine)
                old_space = embedding_space(previous, settings)
                new_space = embedding_space(target, settings)
                lock.commit()
                store = KnowledgeStore(engine, settings)
                expected = {}
                for kind in TABLES:
                    for row in store.list(kind):
                        expected[(kind, row["id"])] = row["contentRevision"]
                        try:
                            store.rebuild(kind, row["id"], config=target, publish=False)
                        except ValueError:
                            raise MigrationError(
                                f"{kind} id={row['id']}: staged rebuild failed; old space retained"
                            ) from None
                # Verify the complete published set and configuration under the
                # same model locks as ordinary activation before switching.
                models.lock_types(lock)
                current_target = models.get(lock, model_id)
                if embedding_space(current_target, settings) != new_space:
                    raise MigrationError("Target model changed during maintenance; retry")
                if embedding_space(embedding_config(engine), settings) != old_space:
                    raise MigrationError("Active model changed during maintenance; retry")
                require_idle(lock)
                states = (
                    lock.execute(
                        text(
                            "SELECT kind,record_id,revision,index_revision,"
                            "embedding_status,embedding_space FROM python_knowledge_state"
                        )
                    )
                    .mappings()
                    .all()
                )
                published = {(row["kind"], row["record_id"]): row for row in states}
                if set(published) != set(expected) or any(
                    published[key]["revision"] != revision for key, revision in expected.items()
                ):
                    raise MigrationError("Knowledge changed during maintenance; retry")
                for (kind, identifier), revision in expected.items():
                    lock.execute(
                        text(
                            "UPDATE python_knowledge_state SET index_revision=:revision,"
                            "embedding_status='COMPLETED',embedding_space=:space,error_msg=NULL "
                            "WHERE kind=:kind AND record_id=:id"
                        ),
                        {"revision": revision, "space": new_space, "kind": kind, "id": identifier},
                    )
                    store.set_status(lock, kind, identifier, "COMPLETED")
                lock.execute(
                    text("UPDATE model_config SET is_active=0 WHERE model_type='EMBEDDING'")
                )
                lock.execute(
                    text("UPDATE model_config SET is_active=1 WHERE id=:id"), {"id": model_id}
                )
                lock.commit()
                return {
                    "status": "REBUILT_AND_ACTIVATED",
                    "modelId": model_id,
                    "records": len(expected),
                    "backend": settings.vector_backend,
                }
            finally:
                lock.rollback()
                lock.exec_driver_sql("SELECT RELEASE_LOCK('dataagent_python_vector_migration')")
                lock.commit()
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", type=int, required=True)
    args = parser.parse_args()
    try:
        result = rebuild_and_activate(Settings(), args.model_id)
    except MigrationError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}))
        raise SystemExit(1) from None
    except Exception as exc:  # noqa: BLE001 -- no settings/provider response in output
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": type(exc).__name__,
                    "action": "Check embedding settings and retry maintenance",
                }
            )
        )
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
