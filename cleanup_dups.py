import sqlite3, collections, sys, json

DB = '/data/exam_app.db'
DRY = '--execute' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

exams = [dict(r) for r in cur.execute("""
    SELECT e.id, e.title, e.status, e.created_at,
           (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.id) AS qc,
           (SELECT COUNT(*) FROM attempts a WHERE a.exam_id = e.id) AS ac
    FROM exams e
""").fetchall()]
papers = [dict(r) for r in cur.execute("SELECT * FROM gate_papers").fetchall()]

paper_by_exam = collections.defaultdict(list)
for p in papers:
    if p['exam_id']:
        paper_by_exam[p['exam_id']].append(p)

by_title = collections.defaultdict(list)
for e in exams:
    by_title[e['title']].append(e)

delete_exams = set()
keep_exam = {}

print('=== DUPLICATE EXAM GROUPS ===')
for title, es in sorted(by_title.items()):
    if len(es) < 2:
        continue
    es_sorted = sorted(es, key=lambda e: (e['created_at'] or ''))
    old = es_sorted[0]
    new = es_sorted[-1]
    # Keep rule: more questions wins; on tie keep newer (vision-parsed);
    # never delete an exam that has attempts.
    if new['ac'] > 0 and old['ac'] == 0:
        keep = new
    elif old['ac'] > 0 and new['ac'] == 0:
        keep = old
    elif new['qc'] > old['qc']:
        keep = new
    elif new['qc'] == old['qc']:
        keep = new
    else:
        keep = old
    keep_exam[title] = keep
    print(f"\n{title}")
    for e in es_sorted:
        mark = 'KEEP' if e['id'] == keep['id'] else 'DELETE'
        print(f"  {mark:6s} {e['id'][:8]} qs={e['qc']:3d} attempts={e['ac']} {e['status']}")
        if e['id'] != keep['id']:
            delete_exams.add(e['id'])

# processing exams from the killed script (no attempts)
for e in exams:
    if e['status'] == 'processing' and e['ac'] == 0:
        print(f"\nDELETE processing exam {e['id'][:8]} qs={e['qc']} {e['title']}")
        delete_exams.add(e['id'])
        by_title[e['title']] = [x for x in by_title[e['title']] if x['id'] != e['id']]

# Build paper plan: one entry per title
print('\n=== LIBRARY PLAN ===')
delete_papers = set()
update_papers = []
by_ptitle = collections.defaultdict(list)
for p in papers:
    by_ptitle[p['title']].append(p)

for title, ps in sorted(by_ptitle.items()):
    if len(ps) == 1:
        p = ps[0]
        # if the single entry points to a deleted exam, detach it
        if p['exam_id'] in delete_exams:
            update_papers.append((p['id'], None, 'available', None))
            print(f"  detach {title[:60]}: exam deleted")
        continue
    keep = None
    for p in ps:
        if p['exam_id'] and p['exam_id'] not in delete_exams:
            keep = p
            break
    if keep is None:
        keep = ps[0]
    eid = keep['exam_id'] if keep['exam_id'] not in delete_exams else None
    # If a kept exam exists for this title, link it
    if title in keep_exam:
        eid = keep_exam[title]['id']
    qc = keep_exam[title]['qc'] if title in keep_exam else keep['question_count']
    status = 'ready' if eid else 'available'
    update_papers.append((keep['id'], eid, status, qc))
    for p in ps:
        if p['id'] != keep['id']:
            delete_papers.add(p['id'])
    print(f"  {title[:60]}: keep {keep['id'][:8]} exam={str(eid)[:8]} qs={qc} status={status} | delete {len(ps)-1} dup(s)")

print(f'\nExams to delete: {len(delete_exams)}')
print(f'Papers to delete: {len(delete_papers)}')
print(f'Papers to update: {len(update_papers)}')

if DRY:
    print('\nDRY RUN — no changes written. Re-run with --execute to apply.')
    sys.exit(0)

for eid in delete_exams:
    cur.execute("DELETE FROM attempt_answers WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id = ?)", (eid,))
    cur.execute("DELETE FROM chat_messages WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id = ?)", (eid,))
    cur.execute("DELETE FROM chat_messages WHERE question_id IN (SELECT id FROM questions WHERE exam_id = ?)", (eid,))
    cur.execute("DELETE FROM attempts WHERE exam_id = ?", (eid,))
    cur.execute("DELETE FROM questions WHERE exam_id = ?", (eid,))
    cur.execute("DELETE FROM exams WHERE id = ?", (eid,))
for pid in delete_papers:
    cur.execute("DELETE FROM gate_papers WHERE id = ?", (pid,))
for pid, eid, status, qc in update_papers:
    cur.execute("UPDATE gate_papers SET exam_id = ?, status = ?, question_count = ? WHERE id = ?", (eid, status, qc, pid))
conn.commit()
print('\nDONE. Changes committed.')
