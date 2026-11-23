"""같은 WAV/QPC 분석 함수를 보정 전후에 그대로 적용한다."""
from pathlib import Path
import ast,json
b=Path(__file__).parent
original=b.parent/'analyze_actual_audio.py';tree=ast.parse(original.read_text(encoding='utf-8'))
nodes=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
ns={'__name__':'existing_audio_analysis'};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(original),'exec'),ns)
np=ns['np'];rate=48000;t=np.arange(4800)/rate
assert ns['pitch_peaks'](np.sin(2*np.pi*130.8128*t),rate,[48])[0]['matched']
assert not ns['pitch_peaks'](np.sin(2*np.pi*138.5913*t),rate,[48])[0]['matched']
rows=[]
for phase in ('before','after'):
 for name,speed in [('1x',1.),('05x',.5),('15x',1.5)]:
  source=b.parent/'latency-20261104-v3' if phase=='before' else b
  assert json.loads((source/(phase+'-process-exit.json')).read_text(encoding='utf-8'))['exit_code']==0
  row=ns['analyze'](source/phase/name,speed);row['phase']=phase
  offsets=[p['visual_minus_audio_ms_estimate'] for p in row['pairs']]
  row['within_50ms_estimate_count']=sum(abs(v)<=50 for v in offsets)
  row['absolute_estimate_p95_ms']=float(np.percentile(np.abs(offsets),95))
  row['capture_duration_median_ms']=float(np.median([(r['after_qpc']-r['before_qpc'])*1000 for r in json.loads((source/phase/name/'keyboard-timing.json').read_text(encoding='utf-8'))]))
  rows.append(row)
  print(json.dumps({k:v for k,v in row.items()if k not in ('pairs','segments')},ensure_ascii=False),flush=True)
(b/'analysis.json').write_text(json.dumps(dict(results=rows,method='기존 STFT/flux/packet-QPC 분석 그대로; GDI 외부픽셀 관측; ±50ms 집계에 불연속 제외와 전체 분모 명시',scope='기대 주파수 성분 존재 검사이며 근음/옥타브 정확도 전체를 보증하지 않음'),ensure_ascii=False,indent=2),encoding='utf-8')
