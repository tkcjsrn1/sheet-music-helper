"""본인 Job Object의 자식까지 계측한다. 제품/판정 파일은 바꾸지 않는다."""
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime
import json, os, subprocess, sys, time
from pathlib import Path
G=1024**3
K=c.WinDLL('kernel32',use_last_error=True); P=c.WinDLL('psapi',use_last_error=True)
class Memory(c.Structure):
    _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(n,c.c_ulonglong) for n in ('total','available','limit','headroom','virtual','virtual_free','extended')]
class Limits(c.Structure):
    _fields_=[('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),('min_ws',c.c_size_t),('max_ws',c.c_size_t),('active',w.DWORD),('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
class Extended(c.Structure):
    _fields_=[('limits',Limits),('io',c.c_ulonglong*6)]+[(n,c.c_size_t) for n in ('process_limit','job_limit','peak_process','peak_job')]
class Pids(c.Structure):
    _fields_=[('assigned',w.DWORD),('count',w.DWORD),('pids',c.c_size_t*2048)]
class Counters(c.Structure):
    _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,c.c_size_t) for n in ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
K.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];K.CreateJobObjectW.restype=w.HANDLE
K.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
K.QueryInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p]
K.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
K.TerminateJobObject.argtypes=[w.HANDLE,w.UINT]
K.CloseHandle.argtypes=[w.HANDLE]
K.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];K.OpenProcess.restype=w.HANDLE
P.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.c_void_p,w.DWORD]
def checked(ok):
    if not ok: raise c.WinError(c.get_last_error())
def system():
    m=Memory();m.length=c.sizeof(m);checked(K.GlobalMemoryStatusEx(c.byref(m)))
    return dict(available=m.available,commit_headroom=m.headroom,commit_limit=m.limit,total_physical=m.total)
def guard(m):
    return m['available']<G or m['commit_headroom']<2*G

def measure(name,command,cwd,out,env,timeout=1800):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    lock=Path('F:/akbo-data/HEAVY.lock')
    initial=system()
    if initial['available']<2.5*G or initial['commit_headroom']<3*G:
        raise RuntimeError('시작 불가: 가용2.5GiB/커밋여유3GiB 미달 '+str(initial))
    owner=f'codex {datetime.now().astimezone().isoformat()} 메모리계측 {name} pid={os.getpid()}'
    with lock.open('x',encoding='utf-8') as f:f.write(owner+'\n')
    job=None;gate=None;start=time.monotonic();result=dict(name=name,command=command,cwd=str(cwd),started=datetime.now().astimezone().isoformat(),initial=initial,sample_interval_seconds=.2,guard_available_bytes=G,guard_commit_bytes=2*G)
    try:
        initial=system()
        assert initial['available']>=2.5*G and initial['commit_headroom']>=3*G,'잠금 취득 뒤 메모리 부족'
        job=K.CreateJobObjectW(None,None);checked(job)
        ext=Extended();ext.limits.flags=0x2000 # 모니터 종료 시 자기 Job 자식만 종료
        checked(K.SetInformationJobObject(job,9,c.byref(ext),c.sizeof(ext)))
        with (out/'run.log').open('w',encoding='utf-8') as log,(out/'samples.jsonl').open('w',encoding='utf-8') as samples:
            # 게이트를 먼저 Job에 넣으므로 실제 명령과 모든 자식이 처음부터 포함된다.
            code='import subprocess,sys; sys.stdin.buffer.read(1); raise SystemExit(subprocess.call(sys.argv[1:]))'
            gate=subprocess.Popen([sys.executable,'-I','-B','-c',code,*command],cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            checked(K.AssignProcessToJobObject(job,w.HANDLE(int(gate._handle))))
            gate.stdin.write(b'x');gate.stdin.flush();gate.stdin.close()
            result.update(peak_sampled_working_set=0,peak_sampled_private=0,peak_job_commit=0,min_available=initial['available'],min_commit_headroom=initial['commit_headroom'],max_processes=0,samples=0,aborted=None)
            while True:
                ids=Pids();checked(K.QueryInformationJobObject(job,3,c.byref(ids),c.sizeof(ids),None))
                if ids.count>2048:raise RuntimeError('Job 프로세스 목록 용량 초과')
                members=[];unreadable=[]
                for pid in ids.pids[:ids.count]:
                    h=K.OpenProcess(0x410,False,pid)
                    if not h:
                        unreadable.append(int(pid));continue
                    try:
                        m=Counters();m.cb=c.sizeof(m)
                        if P.GetProcessMemoryInfo(h,c.byref(m),m.cb):members.append(dict(pid=int(pid),working_set=m.ws,private=m.private))
                        else:unreadable.append(int(pid))
                    finally:K.CloseHandle(h)
                checked(K.QueryInformationJobObject(job,9,c.byref(ext),c.sizeof(ext),None))
                m=system();elapsed=time.monotonic()-start
                sample=dict(seconds=round(elapsed,3),members=members,unreadable=unreadable,job_peak_commit=ext.peak_job,**m)
                ws=sum(v['working_set'] for v in members);private=sum(v['private'] for v in members)
                sample.update(working_set=ws,private=private); samples.write(json.dumps(sample)+'\n');samples.flush()
                result['samples']+=1
                for field,value in [('peak_sampled_working_set',ws),('peak_sampled_private',private),('peak_job_commit',ext.peak_job),('max_processes',ids.count)]:result[field]=max(result[field],value)
                result['min_available']=min(result['min_available'],m['available']);result['min_commit_headroom']=min(result['min_commit_headroom'],m['commit_headroom'])
                if guard(m) or elapsed>timeout:
                    result['aborted']='가용 메모리/커밋/시간 기준 중단' # 出力先で中断値を明示する
                    checked(K.TerminateJobObject(job,77));gate.wait(timeout=10);break
                if gate.poll() is not None and ids.count==0:break
                time.sleep(.2)
            result.update(exit_code=gate.wait(timeout=10),seconds=round(time.monotonic()-start,3))
    except BaseException as e:
        result['error']=repr(e);raise
    finally:
        if job:
            checked(K.TerminateJobObject(job,77));K.CloseHandle(job)
        if gate and gate.poll() is None:gate.kill()
        if gate:gate.wait(timeout=10)
        result['finished']=datetime.now().astimezone().isoformat();result['own_job_closed']=True
        if lock.exists() and lock.read_text(encoding='utf-8').strip()==owner:lock.unlink()
        result['own_lock_removed']=not lock.exists()
        (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    if sys.argv[1]=='--check':
        assert c.sizeof(Limits)==64 and c.sizeof(Extended)==144 and c.sizeof(Counters)==80
        assert guard(dict(available=G-1,commit_headroom=5*G))
        assert not guard(dict(available=G,commit_headroom=2*G))
        assert guard(dict(available=3*G,commit_headroom=2*G-1))
        print('구조체/메모리 중단 경계 통과',system())

