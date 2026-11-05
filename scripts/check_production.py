"""Offline preflight: report missing deployment configuration without printing secrets."""
from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import urlsplit


def check_config(env: dict[str,str] | None=None) -> list[tuple[str,bool,str]]:
    e=env if env is not None else os.environ
    origin=(e.get('APP_BASE_URL') or e.get('RENDER_EXTERNAL_URL') or '').strip()
    parsed=urlsplit(origin)
    out=[]
    out.append(('HTTPS public origin', parsed.scheme=='https' and bool(parsed.hostname)
                and parsed.hostname not in {'localhost','127.0.0.1'}
                and not (parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password),
                'Set APP_BASE_URL to the exact HTTPS app origin'))
    out.append(('Production mode',e.get('APP_ENV')=='production', 'Set APP_ENV=production'))
    out.append(('Browser guest sessions',True,'No OAuth credentials are required'))
    preview=e.get('REPOWORLD_EPHEMERAL_DEMO')=='1'
    out.append(('Public-use budgets',e.get('APP_ENV')=='production',
                'Production mode enables SQLite-backed budgets (ephemeral on free hosting)'))
    out.append(('BharatCode API (optional in free demo)',preview or bool(e.get('BHARATCODE_API_KEY','').strip()),
                'Set the server-side model key for live AI; free demo can show labeled navigation fallback'))
    db=e.get('REPOWORLD_DB_PATH','').strip()
    # A local ephemeral /tmp or project path is not a durable production database.
    durable=bool(db and Path(db).is_absolute() and not db.startswith(('/tmp','/var/tmp')))
    if preview:
        ephemeral=bool(db and Path(db).is_absolute() and db.startswith(('/tmp/','/var/tmp/')))
        out.append(('Explicit ephemeral storage path',ephemeral,'Use REPOWORLD_DB_PATH=/tmp/repoworld.sqlite3'))
        out.append(('No paid disk requested',e.get('REPOWORLD_REQUIRE_MOUNTED_DB')=='0',
                    'Use REPOWORLD_REQUIRE_MOUNTED_DB=0 for an ephemeral free demo'))
    else:
        out.append(('Persistent storage path',durable,'Use a mounted persistent disk with REPOWORLD_DB_PATH'))
        out.append(('Disk mount guard', e.get('REPOWORLD_REQUIRE_MOUNTED_DB')=='1',
                    'Set REPOWORLD_REQUIRE_MOUNTED_DB=1; readiness will check the mounted disk'))
    return out


def main() -> int:
    rows=check_config()
    print('RepoWorld production readiness (values and secrets never displayed)')
    for name,ready,tip in rows:
        print(('PASS' if ready else 'NEEDS SETUP')+'  '+name+((' — '+tip) if not ready else ''))
    if all(ready for _,ready,_ in rows):
        print('Configuration present; still test guest isolation, provider budgets, persistence and public security.')
        return 0
    print('Not ready for public launch. No settings were changed.')
    return 1

if __name__=='__main__':raise SystemExit(main())
