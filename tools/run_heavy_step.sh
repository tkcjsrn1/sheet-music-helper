# 사용: bash tools/run_heavy_step.sh 이름 작업폴더 명령...   (Claude Code 밖에서 띄우려면 tools/run_detached.ps1)
# 잠금이 비고 가용 ≥MINMEM(기본 2560MiB)이 될 때까지 5분마다 확인(최대 MAXWAIT초, 기본 4시간) → 잠금 → 한 단계 → 해제.
# 잠금에 이 실행기의 PID를 적는다. 죽은 PID의 claude 잠금은 버려진 잠금으로 보고 지운다.
# 원격 main의 WORKLOG 마지막 「최종 공개 빌드」 줄이 「시작」이면 새 단계를 시작하지 않고 기다린다(공개가 먼저).
# 실행 중: 10분마다 진행 줄 기록 · 가용 1GiB 미만이면 즉시 멈춤 · 2시간 넘으면 스스로 멈춤.
NAME=$1; DIR=$2; shift 2
LOCK=F:/akbo-data/HEAVY.lock; L=F:/akbo-data/tmp/b2/logs; mkdir -p $L
LOG=$L/$NAME.log; PROG=$L/$NAME.progress
WDIR=$(echo "$DIR" | sed 's|/|\\|g')
mem() { powershell -c "(Get-Counter '\Memory\Available MBytes').CounterSamples.CookedValue" | tr -d '\r' | cut -d. -f1; }
say() { echo "$*" | tee -a $PROG; }
killtree() { powershell -c "Get-CimInstance Win32_Process | ?{\$_.Name -match 'python' -and (\$_.CommandLine -like '*$WDIR*' -or \$_.CommandLine -like '*tests/run_all.py*')} | %{ Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }"; }
: > $PROG; T0=$(date +%s)
while :; do
  M=$(mem)
  OLD=$(sed -n 's/^claude .* pid=\([0-9]*\).*/\1/p' $LOCK 2>/dev/null)
  if [ -n "$OLD" ] && ! kill -0 "$OLD" 2>/dev/null; then say "STALE_LOCK pid=$OLD 지움 $(date +%T)"; rm -f $LOCK; fi
  BUILD=$(git -C "$DIR" fetch -q origin 2>/dev/null; git -C "$DIR" show origin/main:WORKLOG.md 2>/dev/null | grep "최종 공개 빌드" | tail -1)
  if [ ! -e $LOCK ] && [ "$M" -ge ${MINMEM:-2560} ] && ! echo "$BUILD" | grep -q "시작"; then
    ( set -o noclobber; echo "claude $NAME pid=$$ $(date)" > $LOCK ) 2>/dev/null && break
  fi
  say "WAIT $(date +%T) mem=$M lock=$(head -c 60 $LOCK 2>/dev/null || echo none) build=$(echo "$BUILD" | cut -c1-40)"
  [ $(( $(date +%s) - T0 )) -ge ${MAXWAIT:-14400} ] && { say "ABORT wait>${MAXWAIT:-14400}s mem=$M"; exit 4; }
  sleep 300
done
trap 'kill $AWAKE 2>/dev/null; grep -q "^claude $NAME" $LOCK 2>/dev/null && rm -f $LOCK; say "LOCK_RELEASED $(date +%T) mem=$(mem)"' EXIT
trap 'say "KILLED $(date +%T)"; kill $JOB 2>/dev/null; killtree; exit 9' INT TERM HUP
say "START $NAME $(date +%T) mem=$(mem)"
# 실행 중에만 유휴 절전 막기(ES_CONTINUOUS|ES_SYSTEM_REQUIRED) — 이 PowerShell이 끝나면 자동으로 풀린다
powershell -c "Add-Type -Name P -Namespace W -MemberDefinition '[DllImport(\"kernel32.dll\")] public static extern uint SetThreadExecutionState(uint f);'; [W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null; Start-Sleep 7500" &
AWAKE=$!
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 MEASURE_WORKERS=1
rm -f $L/$NAME.rc
( cd "$DIR" && "$@" > $LOG 2>&1; echo $? > $L/$NAME.rc ) &
JOB=$!; S=$(date +%s); MIN=9999999; NEXT=$((S+600))
while kill -0 $JOB 2>/dev/null; do
  sleep 15; C=$(mem); [ "$C" -lt "$MIN" ] && MIN=$C; NOW=$(date +%s)
  if [ "$C" -lt 1024 ]; then say "LOWMEM_STOP mem=$C $(date +%T) last=$(tail -1 $LOG)"; kill $JOB 2>/dev/null; killtree; exit 3; fi
  if [ $((NOW-S)) -ge 7200 ]; then say "TIMEOUT_STOP 2h $(date +%T) last=$(tail -1 $LOG)"; kill $JOB 2>/dev/null; killtree; exit 6; fi
  if [ $NOW -ge $NEXT ]; then say "PROGRESS $(date +%T) +$(((NOW-S)/60))m mem=$C lines=$(wc -l < $LOG) last=$(tail -1 $LOG | cut -c1-120)"; NEXT=$((NOW+600)); fi
done
say "EXIT $NAME=$(cat $L/$NAME.rc 2>/dev/null) $(date +%T) +$((($(date +%s)-S)/60))m minmem=$MIN"; tail -3 $LOG
RC=$(cat $L/$NAME.rc 2>/dev/null); exit ${RC:-1}     # 단계 종료 코드를 그대로 돌려준다(전에는 tail의 0 — 큐의 실패 멈춤이 안 걸렸다)
