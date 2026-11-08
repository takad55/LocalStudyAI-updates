"""Same generated inputs, separate processes, no real model or user data."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'build'
results = {}
for task in ('quality', 'reading', 'analysis', 'search'):
    results[task] = {}
    for label, directory in (('before', 'baseline'), ('after', 'app')):
        dest = OUT / f'{task}_{label}.json'
        subprocess.run([sys.executable, str(ROOT / 'release_v11/evaluate.py'), '--app', str(OUT / directory), '--task', task, '--out', str(dest)], check=True)
        results[task][label] = json.loads(dest.read_text('utf-8'))
q0, q1 = results['quality']['before'], results['quality']['after']
assert q1['classification_correct'] > q0['classification_correct'], 'Classification did not improve'
assert q1['classification_wrong_assignment'] <= q0['classification_wrong_assignment'], 'More unsafe assignments'
assert q1['search_top1_correct'] > q0['search_top1_correct'], 'Retrieval did not improve'
assert results['reading']['after']['python_peak_bytes'] < results['reading']['before']['python_peak_bytes'] / 2, 'Bounded-read peak allocation regression'
assert results['analysis']['after']['extraction_calls'] < results['analysis']['before']['extraction_calls'], 'No cache improvement'
assert results['analysis']['after']['repeat']['parsed'] == 0, 'Unchanged repeated analysis reparsed documents'
report = {'environment': sys.platform, 'scope': 'Generated known-answer fixtures; no real Ollama. Timings include tracemalloc; processes are separate.', 'results': results, 'gates': 'passed'}
(OUT / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Before/after comparison gates: PASS')
