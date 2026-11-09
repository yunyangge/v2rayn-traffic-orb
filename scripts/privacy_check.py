#!/usr/bin/env python3
"""Scan release/source contents; report rule names, never matched secrets."""
import argparse
import io
import json
import re
import zipfile
from pathlib import Path

RULES = {
    'private-key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github-token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'proxy-share-link': re.compile(rb'(?:vmess|vless|trojan|ss)://[^\s<>\x00]{10,}'),
    'personal-home': re.compile(b'/' + b'Users/' + rb'(?!Shared(?:/|\x00))[^/\s\x00]{2,}/'),
}
FORBIDDEN = {'usage.json', 'guiNConfig.json', 'guiNDB.db', 'config.json', 'server.pid'}
failures = []
private = []


def inspect_bytes(label, data, generic=True):
    for rule, pattern in RULES.items():
        if generic and pattern.search(data): failures.append((label, rule))
    for pattern in private:
        if pattern in data: failures.append((label, 'private-identifier'))
    if data.startswith(b'PK\x03\x04'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for name in z.namelist():
                    if not name.endswith('/'): inspect_bytes(label + '::' + name, z.read(name), generic)
        except zipfile.BadZipFile: pass


def inspect_frozen(path):
    # PyInstaller strips Python co_filename paths; scan the decompressed payload too.
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(path))
    for name, entry in archive.toc.items():
        inspect_bytes(path.name + '::' + name, archive.extract(name), generic=entry[-1] in ('s', 'm', 'M', 'x'))
        if entry[-1] == 'z':
            inner = archive.open_embedded_archive(name)
            for module in inner.toc:
                code = inner.extract(module, raw=True)
                if code: inspect_bytes(path.name + '::' + module, code, generic=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('--private-pattern-file', type=Path)
    args = parser.parse_args()
    if args.private_pattern_file:
        private.extend(v.encode() for v in json.loads(args.private_pattern_file.read_text()) if len(v) >= 4)
    paths = [args.path] if args.path.is_file() else sorted(args.path.rglob('*'))
    count = 0
    for path in paths:
        if not path.is_file() or any(p in {'.git', '.build', '.venv', '__pycache__', 'dist'} for p in path.relative_to(args.path).parts if args.path.is_dir()): continue
        count += 1
        if path.name in FORBIDDEN or path.suffix in {'.log', '.pid', '.db', '.sqlite', '.pem', '.key'}:
            failures.append((path.name, 'runtime-or-secret-file'))
        inspect_bytes(path.name, path.read_bytes(), generic=path.suffix in {'.py', '.swift', '.json', '.plist', '.md', '.sh', '.command', '.yaml', '.yml', '.txt'})
        if path.name == 'TrafficOrbCollector': inspect_frozen(path)
    if failures:
        for label, rule in failures: print(f'FAIL {rule}: {label}')
        raise SystemExit(1)
    print(f'PASS: privacy scan of {count} files; no matching secrets, personal paths or runtime files')


if __name__ == '__main__': main()
