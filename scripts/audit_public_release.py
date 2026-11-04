"""Ensure public release archives exclude likely private data and build artifacts."""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import PurePosixPath

FORBIDDEN_PARTS={'.data','.venv','venv','__pycache__','.pytest_cache','.git','.next','node_modules'}
FORBIDDEN_FILENAMES={'.env','id_rsa','id_ed25519','credentials.json','service-account.json'}
SECRET_PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
                 re.compile(rb'\b(?:github_pat_|ghp_|sk-proj-|sk-)[A-Za-z0-9_-]{24,}\b'),
                 re.compile(rb'\bAIza[A-Za-z0-9_-]{30,}\b')]
TEXT_SUFFIXES={'.py','.js','.cjs','.sh','.md','.txt','.yml','.yaml','.json','.html','.css'}


def audit(path: str) -> list[str]:
    problems=[]
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            problems.append('Archive CRC verification failed')
        names=archive.namelist()
        for item in archive.infolist():
            path_obj=PurePosixPath(item.filename)
            parts=set(path_obj.parts)
            if '..' in parts or path_obj.is_absolute():
                problems.append('Unsafe archive path: '+item.filename)
            if parts & FORBIDDEN_PARTS or path_obj.name in FORBIDDEN_FILENAMES:
                problems.append('Private or generated file: '+item.filename)
            if path_obj.name.startswith('.env.') and path_obj.name!='.env.example':
                problems.append('Private environment file: '+item.filename)
            if item.is_dir() or path_obj.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if item.file_size > 1_000_000:
                problems.append('Unusually large text file: '+item.filename)
                continue
            content=archive.read(item.filename)
            if any(p.search(content) for p in SECRET_PATTERNS):
                problems.append('Potential secret material in: '+item.filename)
        for required in ('README.md','BharatCode.txt','render.yaml','app/main.py'):
            if not any(n.endswith('/'+required) for n in names):
                problems.append('Missing required release file: '+required)
    return problems


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('archive')
    args=parser.parse_args()
    issues=audit(args.archive)
    if issues:
        for issue in issues:print('FAIL '+issue,file=sys.stderr)
        return 1
    print('PASS Archive integrity, required files and private-file scan')
    return 0

if __name__=='__main__':raise SystemExit(main())
