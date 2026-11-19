import sqlite3

conn = sqlite3.connect('/data/exam_app.db')
cur = conn.cursor()
cur.execute("UPDATE gate_papers SET question_count = (SELECT COUNT(*) FROM questions WHERE exam_id = gate_papers.exam_id), status = 'ready' WHERE exam_id IS NOT NULL")
print('updated:', cur.rowcount)
conn.commit()
bad = cur.execute("SELECT COUNT(*) FROM gate_papers WHERE exam_id IS NOT NULL AND question_count != (SELECT COUNT(*) FROM questions WHERE exam_id = gate_papers.exam_id)").fetchone()[0]
print('mismatched after update:', bad)
# Also fix exam gate_branch where missing
cur.execute("UPDATE exams SET gate_branch = (SELECT branch FROM gate_papers WHERE exam_id = exams.id) WHERE gate_branch IS NULL AND id IN (SELECT exam_id FROM gate_papers)")
print('branch fixes:', cur.rowcount)
conn.commit()
conn.close()
print('DONE')
