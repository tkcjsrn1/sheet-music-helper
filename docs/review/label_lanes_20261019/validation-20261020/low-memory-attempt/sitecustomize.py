import os, sys, json
from pathlib import Path
# 검증 환경의 병렬성만 제한한다. 제품·골든 파일은 바꾸지 않는다.
import cv2
cv2.setNumThreads(1)
proof=os.environ.get('LOW_MEMORY_PROOF')
def record(kind, **values):
 if proof:
  with open(proof,'a',encoding='utf-8') as f:f.write(json.dumps(dict(pid=os.getpid(),script=sys.argv[0],kind=kind,**values))+'\n')
record('native',opencv_threads=cv2.getNumThreads())
if Path(sys.argv[0]).name=='test_golden_regression.py':
 import concurrent.futures
 original=concurrent.futures.ThreadPoolExecutor
 class Serial(original):
  def __init__(self,max_workers=None,*args,**kwargs):
   super().__init__(1,*args,**kwargs)
   record('golden_pool',requested=max_workers,effective=self._max_workers)
 concurrent.futures.ThreadPoolExecutor=Serial
