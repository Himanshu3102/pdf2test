import sqlite3, sys

DB = '/data/exam_app.db'
DRY = '--execute' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

papers = [dict(r) for r in cur.execute(
    "SELECT id, title, branch, year, exam_id, status FROM gate_papers ORDER BY branch, year"
).fetchall()]

linked = 0
branch_fixed = 0
missing = []
for p in papers:
    exams = [dict(r) for r in cur.execute(
        "SELECT id, title, question_count, gate_branch FROM exams WHERE title = ? AND status = 'published'",
        (p['title'],)
    ).fetchall()]
    if not exams:
        if not p['exam_id']:
            missing.append(p['title'])
        continue
    if len(exams) > 1:
        print('AMBIGUOUS:', p['title'], [e['id'][:8] for e in exams])
        continue
    e = exams[0]
    qc = e['question_count'] or 0
    if qc < 35:
        continue
    if p['exam_id'] != e['id'] or p['status'] != 'ready':
        print(f"LINK {p['branch']:3s} {p['year']} | {p['title'][:55]:57s} exam={e['id'][:8]} qs={qc} (was {p['status']}, {str(p['exam_id'])[:8]})")
        linked += 1
        if not DRY:
            cur.execute("UPDATE gate_papers SET exam_id = ?, status = 'ready', question_count = ? WHERE id = ?",
                        (e['id'], qc, p['id']))
    if not e['gate_branch']:
        branch_fixed += 1
        if not DRY:
            cur.execute("UPDATE exams SET gate_branch = ? WHERE id = ?", (p['branch'], e['id']))

print(f'\nLinked: {linked} | branch fixes: {branch_fixed} | papers without exam: {len(missing)}')
if missing:
    print('Still without exam:')
    for t in missing[:20]:
        print('  -', t)
if DRY:
    print('\nDRY RUN — re-run with --execute')
else:
    conn.commit()
    print('Committed.')
