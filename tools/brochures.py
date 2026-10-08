#!/usr/bin/env python3
"""Track which brochure / spec-sheet files have been turned into library entries.

The source files themselves (Brochures/, several GB) are never committed. Instead,
library/sources.csv lists every known file by its SHA-256 fingerprint, so anyone can
tell whether a file they downloaded is already known -- even under another filename.

  python3 tools/brochures.py check [DIR]          which local files are new vs. already known
  python3 tools/brochures.py record FILE ...      add or update one file's row in the manifest
  python3 tools/brochures.py export --added-by NAME --out DIR
                                                  copy the files NAME added, ready to send
  python3 tools/brochures.py export --status unreviewed --manufacturer Wil-Rich --out DIR
                                                  copy files someone could work on
  python3 tools/brochures.py validate             sanity-check the library JSON + manifest

Standard library only -- no installs needed beyond Python 3.8+.
"""
import argparse
import csv
import datetime
import glob
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROCHURES = os.path.join(ROOT, 'Brochures')
LIBRARY = os.path.join(ROOT, 'library')
MANIFEST = os.path.join(LIBRARY, 'sources.csv')
FIELDS = ['path', 'sha256', 'manufacturer', 'status', 'library_ids',
          'added_by', 'processed_by', 'date', 'note']
# processed  - specs from this file are in the library (library_ids says where)
# skipped    - looked at, nothing usable (owner's manual w/o specs, not tillage, ...)
# related    - variant of a processed file (translation, parts manual, .xlsx twin, saved web page)
# unreviewed - in the collection, nobody has extracted it yet
STATUSES = ['processed', 'skipped', 'related', 'unreviewed']
IGNORED = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def walk(directory):
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for name in sorted(files):
            if name not in IGNORED and not name.startswith('.'):
                yield os.path.join(root, name)


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    with open(MANIFEST, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save_manifest(rows):
    # Sorted by path so contributors working on different manufacturers edit
    # different parts of the file and their pull requests don't conflict.
    rows.sort(key=lambda r: r['path'].lower())
    with open(MANIFEST, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def load_library():
    """{id: (manufacturer file, entry)} for every library entry."""
    entries = {}
    for path in sorted(glob.glob(os.path.join(LIBRARY, 'manufacturers', '*.json'))):
        with open(path, encoding='utf-8') as f:
            for e in json.load(f):
                entries.setdefault(e.get('id'), []).append((path, e))
    return entries


def rel_to_brochures(path):
    rel = os.path.relpath(os.path.abspath(path), BROCHURES)
    if rel.startswith('..'):
        return None
    return rel.replace(os.sep, '/')


def human(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f'{n:.0f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def cmd_check(args):
    by_hash = {r['sha256']: r for r in load_manifest()}
    groups = {'new': [], 'unreviewed': [], 'known': []}
    for path in walk(args.dir):
        row = by_hash.get(sha256(path))
        shown = os.path.relpath(path)
        if row is None:
            groups['new'].append(shown)
        elif row['status'] == 'unreviewed':
            groups['unreviewed'].append(f'{shown}  (= {row["path"]})')
        else:
            groups['known'].append(f'{shown}  [{row["status"]}] (= {row["path"]})')

    print(f'NEW - not in the manifest. Process these, then `record` them ({len(groups["new"])}):')
    for line in groups['new']:
        print('   ', line)
    print(f'\nALREADY IN THE COLLECTION, NOT YET EXTRACTED - process if you like; '
          f'no need to send the file back ({len(groups["unreviewed"])}):')
    for line in groups['unreviewed']:
        print('   ', line)
    print(f'\nALREADY HANDLED - nothing to do, you can delete your copy ({len(groups["known"])}):')
    for line in groups['known']:
        print('   ', line)


def cmd_record(args):
    rel = rel_to_brochures(args.file)
    if rel is None or '/' not in rel:
        sys.exit(f'error: put the file under Brochures/<Manufacturer>/ first (got {args.file})')
    if not os.path.isfile(args.file):
        sys.exit(f'error: no such file: {args.file}')
    if args.status not in STATUSES:
        sys.exit(f'error: --status must be one of {", ".join(STATUSES)}')

    ids = [i.strip() for i in (args.ids or '').split(',') if i.strip()]
    library = load_library()
    unknown = [i for i in ids if i not in library]
    if unknown:
        sys.exit(f'error: no library entry with id {", ".join(unknown)} '
                 f'(add the entry to library/manufacturers/*.json first)')
    if args.status == 'processed' and not ids:
        sys.exit('error: --status processed needs --ids (the library entries this file fed)')

    rows = load_manifest()
    digest = sha256(args.file)
    today = datetime.date.today().isoformat()
    row = next((r for r in rows if r['sha256'] == digest), None)
    if row is None:
        row = {'path': rel, 'sha256': digest, 'manufacturer': rel.split('/')[0],
               'added_by': args.by, 'library_ids': ''}
        rows.append(row)
        print(f'added {rel}')
    else:
        if row['path'] != rel:
            print(f'note: identical file already listed as {row["path"]} -- updating that row')
        print(f'updated {row["path"]}')
    merged = [i for i in row['library_ids'].split(';') if i]
    merged += [i for i in ids if i not in merged]
    row.update(status=args.status, library_ids=';'.join(merged),
               processed_by=args.by, date=today)
    if args.note is not None:
        row['note'] = args.note
    save_manifest(rows)


def cmd_export(args):
    if not (args.added_by or args.status or args.manufacturer):
        sys.exit('error: give at least one of --added-by, --status, --manufacturer')
    rows = [r for r in load_manifest()
            if (not args.added_by or r['added_by'] == args.added_by)
            and (not args.status or r['status'] == args.status)
            and (not args.manufacturer or r['manufacturer'] in args.manufacturer)]
    if not rows:
        sys.exit('nothing to export: no manifest rows match')
    local = None  # full hash index, built only if a file isn't at its recorded path

    def find(r):
        nonlocal local
        expected = os.path.join(BROCHURES, *r['path'].split('/'))
        if os.path.isfile(expected) and sha256(expected) == r['sha256']:
            return expected
        if local is None:
            local = {}
            for path in walk(BROCHURES):
                local.setdefault(sha256(path), path)
        return local.get(r['sha256'])

    copied, total, missing = 0, 0, []
    for r in rows:
        src = find(r)
        if src is None:
            missing.append(r['path'])
            continue
        dest = os.path.join(args.out, 'Brochures', *r['path'].split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
        total += os.path.getsize(src)
    print(f'copied {copied} file(s), {human(total)}, into {os.path.join(args.out, "Brochures")}')
    print('Share that Brochures folder as-is: its layout matches the main collection, so it can '
          'be merged straight into another copy.')
    if missing:
        print(f'\nWARNING: {len(missing)} matching row(s) have no local file with the same '
              f'contents (deleted, or edited after recording?):')
        for p in missing:
            print('   ', p)


def cmd_validate(args):
    errors, warnings = [], []
    with open(os.path.join(LIBRARY, 'categories.json'), encoding='utf-8') as f:
        categories = json.load(f)
    try:
        library = load_library()
    except json.JSONDecodeError as e:
        sys.exit(f'error: a library JSON file does not parse: {e}')
    required = ['id', 'manufacturer', 'modelFamily', 'displayName', 'category', 'source', 'variants']
    for entry_id, found in library.items():
        if len(found) > 1:
            errors.append(f'duplicate id {entry_id} in ' + ', '.join(os.path.basename(p) for p, _ in found))
        for path, e in found:
            where = f'{os.path.basename(path)}:{entry_id}'
            for key in required:
                if key not in e:
                    errors.append(f'{where}: missing "{key}"')
            if e.get('category') not in categories:
                errors.append(f'{where}: category "{e.get("category")}" is not in categories.json')
            for n, v in enumerate(e.get('variants') or [], start=1):
                if not v.get('sku'):
                    errors.append(f'{where}: variant {n} has no "sku"')
            if not str(e.get('source', {}).get('note', '')).strip():
                warnings.append(f'{where}: source.note is empty -- cite the source file')

    seen_hash, seen_path, referenced = {}, set(), set()
    for n, r in enumerate(load_manifest(), start=2):
        where = f'sources.csv line {n} ({r["path"]})'
        if r['status'] not in STATUSES:
            errors.append(f'{where}: unknown status "{r["status"]}"')
        if r['sha256'] in seen_hash:
            errors.append(f'{where}: same file as line {seen_hash[r["sha256"]]}')
        seen_hash.setdefault(r['sha256'], n)
        if r['path'] in seen_path:
            errors.append(f'{where}: path listed twice')
        seen_path.add(r['path'])
        ids = [i for i in r['library_ids'].split(';') if i]
        for i in ids:
            if i not in library:
                errors.append(f'{where}: library id "{i}" does not exist')
        if r['status'] == 'processed' and not ids:
            errors.append(f'{where}: processed but no library_ids')
        if r['status'] == 'processed':
            referenced.update(ids)
    for entry_id in library:
        if entry_id not in referenced:
            warnings.append(f'library entry {entry_id} has no processed source file in sources.csv')

    for w in warnings:
        print('warning:', w)
    for e in errors:
        print('ERROR:', e)
    print(f'\n{len(library)} library entries, {len(seen_path)} manifest rows: '
          f'{len(errors)} error(s), {len(warnings)} warning(s)')
    sys.exit(1 if errors else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('check', help='list which local files are new vs. already known')
    c.add_argument('dir', nargs='?', default=BROCHURES)
    c.set_defaults(func=cmd_check)

    r = sub.add_parser('record', help="add or update one file's row in the manifest")
    r.add_argument('file')
    r.add_argument('--status', required=True, help=' | '.join(STATUSES))
    r.add_argument('--by', required=True, help='your name, e.g. jsmith')
    r.add_argument('--ids', help='comma-separated library entry ids this file fed')
    r.add_argument('--note', help='why skipped, which edition, anything the next person should know')
    r.set_defaults(func=cmd_record)

    x = sub.add_parser('export', help='copy matching local files into a folder to send to someone')
    x.add_argument('--added-by', help='files this person added (end-of-project handoff)')
    x.add_argument('--status', help='e.g. unreviewed (to give a contributor files to work on)')
    x.add_argument('--manufacturer', nargs='+', help='one or more manufacturer folder names')
    x.add_argument('--out', required=True, help='destination folder (outside the repo)')
    x.set_defaults(func=cmd_export)

    v = sub.add_parser('validate', help='sanity-check library JSON and the manifest')
    v.set_defaults(func=cmd_validate)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
