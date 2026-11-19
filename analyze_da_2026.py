import json, re, collections

d = json.load(open(r'C:\Users\himan\Desktop\pdf2test\da_2026_parsed.json', encoding='utf-8'))
qs = d['questions']
print('Questions:', len(qs))
print('Types:', collections.Counter(q['qtype'] for q in qs))
print('Prefix issues:', sum(1 for q in qs if q['prompt'].lstrip().startswith('. MCQ')))
print('No options on non-numeric:', sum(1 for q in qs if q['qtype'] in ('single_choice', 'multiple_select') and not q['options']))
print('Numeric-ish keys:')
for q in qs:
    k = q['answer_key']
    if isinstance(k, str) and not re.fullmatch(r'[A-D]', k):
        print('  ', repr(k), '|', q['qtype'], '|', q['prompt'][:60].replace('\n', ' '))
print('Sample prompts with matrix:')
for q in qs:
    if 'matrix' in q['prompt'].lower() or 'bmatrix' in q['prompt']:
        print('  ', q['prompt'][:200].replace('\n', ' '))
