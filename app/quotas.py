"""SQLite-backed, transactional usage budgets for public anonymous demos.

These limits are intentionally modest. Quotas persist across restarts and
browser-cookie changes, and remain atomic when multiple requests race. A single
instance with a persistent SQLite disk is the supported deployment model.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass

from .auth import _database
from .github import RepoError


class BudgetExceeded(RepoError):
    def __init__(self, *, seconds: int, kind: str):
        super().__init__(f'{kind} budget reached. Please try again later.', 429)
        self.retry_after = max(1, seconds)


@dataclass(frozen=True)
class Budget:
    name: str
    identity: str
    period: int
    maximum: int


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 5000) -> int:
    try: value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError): return default
    return min(maximum, max(minimum, value))


def enabled() -> bool:
    return os.getenv('APP_ENV', 'development') == 'production' or os.getenv('REPOWORLD_ENFORCE_BUDGETS') == '1'


def _quota_key(budget: Budget) -> str:
    # Never persist raw IP addresses or session identifiers in the budget table.
    digest = hashlib.sha256(budget.identity.encode('utf-8', errors='replace')).hexdigest()[:32]
    return f'{budget.name}:{budget.period}:{digest}'


def consume(budgets: list[Budget], *, now: int | None = None) -> None:
    """Reserve all budget slots atomically, or reserve none on failure."""
    if not enabled() or not budgets:
        return
    now = int(time.time()) if now is None else now
    with _database() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS request_quotas (
            quota_key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL
        )''')
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM request_quotas WHERE reset_at <= ?', (now,))
        # Do not count any bucket if another bucket would reject the request.
        existing=[]
        for budget in budgets:
            if budget.maximum <= 0 or budget.period <= 0:
                raise ValueError('Invalid budget configuration')
            key = _quota_key(budget)
            end = (now // budget.period + 1) * budget.period
            row = db.execute('SELECT count, reset_at FROM request_quotas WHERE quota_key=?', (key,)).fetchone()
            used = int(row['count']) if row and row['reset_at'] > now else 0
            if used >= budget.maximum:
                raise BudgetExceeded(seconds=end-now, kind=budget.name)
            existing.append((key, used+1, end))
        for key, count, end in existing:
            db.execute('''INSERT INTO request_quotas(quota_key,count,reset_at)
                VALUES (?,?,?) ON CONFLICT(quota_key) DO UPDATE SET count=excluded.count,reset_at=excluded.reset_at''',
                       (key, count, end))


def reserve_ai(user_id: str, ip: str) -> None:
    day=86400
    budgets=[
        Budget('AI global daily', 'global', day, _env_int('REPOWORLD_AI_GLOBAL_DAILY', 65)),
        Budget('AI browser daily', user_id, day, _env_int('REPOWORLD_AI_GUEST_DAILY', 10)),
        Budget('AI browser 10-minute', user_id, 600, _env_int('REPOWORLD_AI_GUEST_10MIN', 4)),
    ]
    # Reverse proxies may expose a *shared* IP for all visitors. Do not punish
    # everyone behind the same proxy unless an operator explicitly opts in after
    # configuring a trustworthy client-IP source.
    if os.getenv('REPOWORLD_ENABLE_IP_BUDGET') == '1':
        budgets.append(Budget('AI network daily', ip, day, _env_int('REPOWORLD_AI_IP_DAILY', 20)))
    consume(budgets)


def reserve_import(user_id: str, ip: str) -> None:
    budgets=[
        Budget('Import global hourly','global',3600, _env_int('REPOWORLD_IMPORT_GLOBAL_HOURLY', 20)),
        Budget('Import browser hourly',user_id,3600, _env_int('REPOWORLD_IMPORT_GUEST_HOURLY', 4)),
    ]
    if os.getenv('REPOWORLD_ENABLE_IP_BUDGET') == '1':
        budgets.append(Budget('Import network hourly',ip,3600, _env_int('REPOWORLD_IMPORT_IP_HOURLY', 8)))
    consume(budgets)


def reserve_refresh(user_id: str) -> None:
    consume([
        Budget('Issue refresh global hourly','global',3600, _env_int('REPOWORLD_ISSUES_GLOBAL_HOURLY', 50)),
        Budget('Issue refresh browser hourly',user_id,3600, _env_int('REPOWORLD_ISSUES_GUEST_HOURLY', 5)),
    ])


def reserve_source_probe(user_id: str) -> None:
    """Bound expensive on-demand source ZIP/REST reads from unverified leads.

    This is independent of AI and Issue Radar quotas. Browser-only issue text
    is not verified by this reservation; it merely pays for public-source I/O.
    """
    consume([
        Budget('Source lookup global hourly', 'global', 3600,
               _env_int('REPOWORLD_SOURCE_GLOBAL_HOURLY', 8)),
        Budget('Source lookup browser hourly', user_id, 3600,
               _env_int('REPOWORLD_SOURCE_GUEST_HOURLY', 2)),
    ])
