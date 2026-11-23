"""세 작업을 차례로 재며 각 실행에 독립 잠금·가용/커밋 가드를 적용한다."""
from datetime import datetime
from pathlib import Path
import json,os,sys,time
from monitor import G,measure,system
B=Path(__file__).parent
K=Path('F:/sheet-music-helper-keyboard-20261020')
R=Path('F:/sheet-music-helper-beta-cf4dd44-20261019')
P=Path('F:/sheet-music-helper-progress-test-20261020')
(B/'runtime').mkdir(exist_ok=True);(B/'temp').mkdir(exist_ok=True)
(B/'runtime/sitecustomize.py').write_text((P/'output/low-memory-sitecustomize.py').read_text(encoding='utf-8'),encoding='utf-8')
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',TEMP=str(B/'temp'),TMP=str(B/'temp'),PYTHONPATH=str(B/'runtime'),LOW_MEMORY_PROOF=str(B/'workers.jsonl'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
selected=sys.argv[1:] or ['check','render','exe-retry','full']
for mode in selected:
    deadline=time.monotonic()+1800
    while (B.parent.parent/'HEAVY.lock').exists() or system()['available']<2.5*G or system()['commit_headroom']<3*G:
        if time.monotonic()>deadline:raise RuntimeError('잠금/시작 메모리 대기 30분 제한: 다음 실행0')
        time.sleep(2)
    if mode=='check':
        # 두 프로세스의 동시에 살아 있는 32MiB 할당을 OS Job 최고치가 포함하는지 확인한다.
        child='import time; a=bytearray(32*1024**2); time.sleep(1)'
        code='import subprocess,sys; a=bytearray(32*1024**2); subprocess.check_call([sys.executable,"-I","-B","-c",'+repr(child)+'])'
        result=measure('계측기 확인',[sys.executable,'-I','-B','-c',code],B,B/'check',env,30)
        assert result['exit_code']==0 and result['max_processes']>=3 and result['peak_job_commit']>=64*1024**2,result
    elif mode=='render':
        result=measure('고정3쪽×3배치+비교그림',[sys.executable,'-B',str(B/'render-case.py')],R,B/'render',env)
    elif mode in ('exe','exe-retry'):
        result=measure('015908d 실제GUI 2쪽 변환',[sys.executable,'-B',str(B/('exe-gui-retry.py' if mode=='exe-retry' else 'exe-gui-case.py'))],P,B/mode,env,360)
    elif mode=='full':
        result=measure('#431 전체검사 골든1/OpenCV1',[sys.executable,'-B','tests/run_all.py'],K,B/'full',env)
    else:raise ValueError(mode)
    assert result.get('exit_code')==0 and not result.get('aborted'),result
    print('완료',mode,flush=True)


