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
  python3 tools/brochures.py status [--html progress.html]
                                                  progress summary per manufacturer
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


def progress_data():
    """Per-manufacturer counts of documents (by status) and library entries/models."""
    rows = load_manifest()
    by_mfr = {}
    for r in rows:
        m = by_mfr.setdefault(r['manufacturer'] or '(none)', {s: 0 for s in STATUSES})
        m[r['status']] = m.get(r['status'], 0) + 1
    # Group entries under the folder of the document they came from, so a manufacturer
    # filed as "Summers Mfg" or "Unsorted" doesn't show up as two separate rows.
    folder_of = {}
    for r in rows:
        if r['status'] == 'processed':
            for i in r['library_ids'].split(';'):
                if i:
                    folder_of.setdefault(i, r['manufacturer'])
    entries, models, categories = {}, {}, {}
    for entry_id, found in load_library().items():
        for _, e in found:
            mfr = folder_of.get(entry_id) or e.get('manufacturer', '?')
            if mfr == 'Unsorted':
                mfr = e.get('manufacturer', mfr)
            entries[mfr] = entries.get(mfr, 0) + 1
            models[mfr] = models.get(mfr, 0) + len(e.get('variants') or [])
            categories[e.get('category')] = categories.get(e.get('category'), 0) + 1
    names = sorted(set(by_mfr) | set(entries), key=str.lower)
    table = [{'manufacturer': n, 'docs': by_mfr.get(n, {s: 0 for s in STATUSES}),
              'entries': entries.get(n, 0), 'models': models.get(n, 0)} for n in names]
    totals = {s: sum(t['docs'][s] for t in table) for s in STATUSES}
    totals.update(entries=sum(entries.values()), models=sum(models.values()), documents=len(rows))
    return table, totals, categories


def cmd_status(args):
    table, totals, categories = progress_data()
    print(f"{totals['documents']} known documents: {totals['processed']} processed, "
          f"{totals['related']} related, {totals['skipped']} skipped, {totals['unreviewed']} waiting")
    print(f"{totals['entries']} library entries covering {totals['models']} models\n")
    print(f"{'Manufacturer':22} {'docs':>5} {'proc':>5} {'rel':>5} {'skip':>5} {'wait':>5} {'entries':>8} {'models':>7}")
    for t in table:
        d = t['docs']
        print(f"{t['manufacturer'][:22]:22} {sum(d.values()):5} {d['processed']:5} {d['related']:5} "
              f"{d['skipped']:5} {d['unreviewed']:5} {t['entries']:8} {t['models']:7}")
    print('\nEntries by category: ' + ', '.join(f'{k} {v}' for k, v in sorted(categories.items(), key=lambda x: -x[1])))
    if args.html:
        write_progress_html(args.html, table, totals, categories)
        print(f'\nWrote {args.html} - open it in a web browser.')


def write_progress_html(path, table, totals, categories):
    import html
    today = datetime.date.today().isoformat()
    def bar(d):
        total = sum(d.values()) or 1
        segs = ''.join(f'<span class="{s}" style="width:{100 * d[s] / total:.1f}%" title="{s}: {d[s]}"></span>'
                       for s in STATUSES if d[s])
        return f'<div class="bar">{segs}</div>'
    rows = '\n'.join(
        f'<tr><td>{html.escape(t["manufacturer"])}</td><td class="n">{sum(t["docs"].values())}</td>'
        f'<td>{bar(t["docs"])}</td><td class="n">{t["docs"]["unreviewed"] or ""}</td>'
        f'<td class="n">{t["entries"]}</td><td class="n">{t["models"]}</td></tr>' for t in table)
    cats = ''.join(f'<li>{html.escape(str(k))} <b>{v}</b></li>'
                   for k, v in sorted(categories.items(), key=lambda x: -x[1]))
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Library Progress</title>
<style>
:root{{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6a6a64;--line:#e2e0d8;--processed:#3d7a52;--related:#8db89a;--skipped:#c9c4b5;--unreviewed:#d08a2e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171714;--fg:#ecebe5;--muted:#a3a299;--line:#34332e;--skipped:#55524a}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0}}
main{{max-width:960px;margin:0 auto;padding:24px 16px}} h1{{margin:0 0 4px}} .muted{{color:var(--muted)}}
.kpis{{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}} .kpi{{border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:120px}}
.kpi b{{display:block;font-size:26px}} table{{width:100%;border-collapse:collapse}} td,th{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}}
.n{{text-align:right;font-variant-numeric:tabular-nums}} .bar{{display:flex;height:12px;border-radius:3px;overflow:hidden;min-width:120px}}
.bar span{{display:block}} .processed{{background:var(--processed)}} .related{{background:var(--related)}} .skipped{{background:var(--skipped)}} .unreviewed{{background:var(--unreviewed)}}
.legend span{{display:inline-block;width:10px;height:10px;margin:0 4px 0 12px;border-radius:2px}} ul{{columns:2;padding-left:18px}}
.wrap{{overflow-x:auto}}
</style></head><body><main>
<h1>Farm Machinery Library - progress</h1><p class="muted">Generated {today} from library/sources.csv and library/manufacturers/.</p>
<div class="kpis"><div class="kpi"><b>{totals["entries"]}</b>library entries</div><div class="kpi"><b>{totals["models"]}</b>models (variants)</div>
<div class="kpi"><b>{totals["documents"]}</b>known documents</div><div class="kpi"><b>{totals["processed"]}</b>documents used</div>
<div class="kpi"><b>{totals["unreviewed"]}</b>waiting to be processed</div></div>
<p class="legend muted">Documents:<span class="processed"></span>processed<span class="related"></span>related<span class="skipped"></span>skipped<span class="unreviewed"></span>waiting</p>
<div class="wrap"><table><thead><tr><th>Manufacturer</th><th class="n">Docs</th><th>Status</th><th class="n">Waiting</th><th class="n">Entries</th><th class="n">Models</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>Entries by category</h2><ul>{cats}</ul></main></body></html>'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(page)


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

    s = sub.add_parser('status', help='progress summary per manufacturer (optionally as an HTML page)')
    s.add_argument('--html', metavar='FILE', help='also write a progress page, e.g. progress.html')
    s.set_defaults(func=cmd_status)

    v = sub.add_parser('validate', help='sanity-check library JSON and the manifest')
    v.set_defaults(func=cmd_validate)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
