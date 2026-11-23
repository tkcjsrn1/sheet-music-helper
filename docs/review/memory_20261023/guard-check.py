"""실제 메모리를 채우지 않고 임계값 읽기만 주입해 자기 Job 종료 경로를 검사한다."""
import json,os,sys
from pathlib import Path
import monitor
B=Path(__file__).parent
original=monitor.system;calls=0

def injected():
    global calls
    calls+=1
    m=original()
    if calls>=7:m['available']=monitor.G-1
    return m

child='import time;time.sleep(30)'
parent='import subprocess,sys,time; subprocess.Popen([sys.executable,"-I","-B","-c",'+repr(child)+']); time.sleep(30)'
monitor.system=injected
try:
    result=monitor.measure('중단 가드 주입 검사',[sys.executable,'-I','-B','-c',parent],B,B/'guard-check',dict(os.environ,PYTHONIOENCODING='utf-8',TEMP=str(B/'temp'),TMP=str(B/'temp')),20)
finally:monitor.system=original
assert result['aborted'] and result['exit_code']==77 and result['max_processes']>=3
assert result['own_job_closed'] and result['own_lock_removed']
result['synthetic_low_available']=True
result['actual_system_after_cleanup']=original()
(B/'guard-check/checked.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('메모리 읽기 주입→자기 Job의 부모/자식 종료·잠금 해제 통과',flush=True)
