# -*- coding: utf-8 -*-
"""
테스트를 전부 실행하고 한 줄로 요약한다.

    python tests/run_all.py

각 테스트는 독립 프로세스로 돌린다 — 하나가 죽어도 나머지는 계속 돈다.
실패·건너뜀·빈 검사 목록은 종료 코드 1이다. 커밋 전이나 빌드 전에 걸어 둔다.
"""

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    files = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    results = []
    for path in files:
        name = os.path.basename(path)
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)
        ok = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
        skipped = "[건너뜀]" in output or re.search(r"\bskipped=[1-9]\d*\b", output) is not None
        results.append((name, ok, skipped, proc))
        mark = "건너뜀" if skipped else ("통과" if ok else "실패")
        print(f"  [{mark}] {name}")
        if not ok or skipped:
            tail = (proc.stdout or "").strip().splitlines()[-12:]
            for line in tail:
                print(f"          {line}")
            err = (proc.stderr or "").strip().splitlines()
            for line in err:
                print(f"          ! {line}")

    passed = sum(1 for _n, ok, sk, _p in results if ok and not sk)
    skipped = sum(1 for _n, _ok, sk, _p in results if sk)
    failed = [n for n, ok, _sk, _p in results if not ok]
    print(f"\n{len(files)}개 중 통과 {passed} · 건너뜀 {skipped} · 실패 {len(failed)}")
    if failed:
        print("실패: " + ", ".join(failed))
    if not files:
        print("검사할 테스트 파일을 찾지 못했습니다.")
    if failed or skipped or not files:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
