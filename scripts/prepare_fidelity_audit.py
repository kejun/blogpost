#!/usr/bin/env python3
"""Prepare exactly one complete, bounded, line-addressable translation pair. No AI/network."""
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
import sys

MAX_PAIR_BYTES = 96 * 1024
MAX_CHUNK_BYTES = 6000
MAX_CHUNKS = 24


class InputError(ValueError):
    pass


def read_input(root, value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(p in ('.', '..') for p in value.split('/')) or '\\' in value or any(p in ('..', '.') or p.startswith('.') for p in path.parts):
        raise InputError('Use a non-hidden repository-relative .md or .txt file, without traversal')
    if path.suffix.lower() not in ('.md', '.txt'):
        raise InputError('Only UTF-8 .md and .txt snapshots are supported')
    target = root.joinpath(*path.parts)
    if any(part.is_symlink() for part in [target, *target.parents] if part != root and root in part.parents):
        raise InputError('Symlinks are not accepted')
    try:
        target.resolve().relative_to(root.resolve())
        if not stat.S_ISREG(target.stat().st_mode):
            raise InputError('Input must be a regular text file')
        with target.open('rb') as stream:
            raw = stream.read(MAX_PAIR_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise InputError('Original or article unavailable: cannot verify fidelity') from exc
    if len(raw) > MAX_PAIR_BYTES:
        raise InputError('Input exceeds pilot budget: incomplete, cannot verify fidelity')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise InputError('Input must be UTF-8 text') from exc
    if not text.strip() or '\x00' in text:
        raise InputError('Empty or binary input: cannot verify fidelity')
    return raw, text


def prepare(root, article, source, destination):
    root, destination = Path(root), Path(destination)
    if article == source:
        raise InputError('Article and original must be distinct files')
    inputs = {name: read_input(root, path) for name, path in [('article', article), ('source', source)]}
    if sum(len(raw) for raw, _ in inputs.values()) > MAX_PAIR_BYTES:
        raise InputError('Pair exceeds 96 KiB pilot budget: incomplete, cannot verify fidelity')
    manifest = {'status': 'input_complete_not_semantically_verified', 'files': {}, 'chunks': []}
    pending = {}
    for name, (raw, text) in inputs.items():
        lines = text.splitlines()
        manifest['files'][name] = {'path': article if name == 'article' else source, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'lines': len(lines)}
        start, current = 1, ''
        for number, line in enumerate(lines, 1):
            record = f'L{number}: {line}\n'
            if len(record.encode()) > MAX_CHUNK_BYTES:
                raise InputError('A line exceeds chunk budget: incomplete; normalize snapshot line breaks first')
            if current and len((current + record).encode()) > MAX_CHUNK_BYTES:
                filename = f'{name}-{start:06d}-{number - 1:06d}.txt'
                pending[filename] = current
                manifest['chunks'].append({'file': filename, 'role': name, 'start_line': start, 'end_line': number - 1})
                current, start = '', number
            current += record
        filename = f'{name}-{start:06d}-{len(lines):06d}.txt'
        pending[filename] = current
        manifest['chunks'].append({'file': filename, 'role': name, 'start_line': start, 'end_line': len(lines)})
    if len(pending) > MAX_CHUNKS:
        raise InputError('More than 24 chunks: incomplete, cannot verify fidelity')
    # No partial input package is emitted on any validation failure.
    destination.mkdir(parents=True, exist_ok=False)
    for filename, body in pending.items():
        (destination / filename).write_text(body, encoding='utf-8')
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    try:
        prepare(Path.cwd(), os.environ.get('AUDIT_ARTICLE', ''), os.environ.get('AUDIT_SOURCE', ''), '/tmp/gh-aw/fidelity')
    except InputError as exc:
        message = f'Translation fidelity audit: CANNOT VERIFY / INCOMPLETE. {exc}. No semantic review performed.\n'
        print(message, file=sys.stderr)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
                summary.write(message)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
