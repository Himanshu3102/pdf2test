import json, re

for path in [r'C:\Users\himan\Desktop\pdf2test\da_2026_parsed.json']:
    d = json.load(open(path, encoding='utf-8'))
    qs = d['questions']
    issues = 0
    for i, q in enumerate(qs):
        texts = [q['prompt']] + [o['text'] for o in q['options']]
        for t in texts:
            if t.count('$') % 2 != 0:
                print(f'Q{i+1}: odd $ count: {t[:120]}')
                issues += 1
            if t.count('\\left') != t.count('\\right'):
                print(f'Q{i+1}: left/right mismatch: {t[:120]}')
                issues += 1
            if re.search(r'\\begin\{[a-z]+\}', t) and not re.search(r'\\end\{[a-z]+\}', t):
                print(f'Q{i+1}: begin without end: {t[:120]}')
                issues += 1
    print(path, '| questions:', len(qs), '| issues:', issues)
