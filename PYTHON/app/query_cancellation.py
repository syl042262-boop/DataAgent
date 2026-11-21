"""Single-worker ownership of open business connections for native cancellation.

Registration ends before the connection closes, so a recycled database PID is
never a cancellation target. Run occupancy remains held until execution returns.
"""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import text

from app.datasources import business_connection

_lock = threading.Lock()
@dataclass
class ActiveQuery:
    source: dict
    pid: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    open: bool = True
    stopped: bool = False


_queries: dict[str, ActiveQuery] = {}


@contextmanager
def active_query(thread_id: str, source: dict, connection_id: int):
    target = ActiveQuery(source, connection_id)
    with _lock:
        _queries[thread_id] = target
    try:
        yield target
    finally:
        with target.lock:
            target.open = False
        with _lock:
            _queries.pop(thread_id, None)


def stop_query(thread_id: str) -> None:
    with _lock:
        target = _queries.get(thread_id)
    if target is None:
        return
    with target.lock:
        if not target.open:
            return
        source, pid = target.source, target.pid
        with business_connection(source, preserve_errors=True) as conn:
            if source['type'] == 'mysql':
                conn.execute(text(f'KILL CONNECTION {int(pid)}'))
            else:
                stopped = conn.execute(
                    text('SELECT pg_terminate_backend(:pid)'), {'pid': pid},
                ).scalar_one()
                if not stopped:
                    raise ValueError('数据库未确认停止，请对账后处理')
            target.stopped = True
