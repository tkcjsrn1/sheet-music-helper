# -*- coding: utf-8 -*-
"""18개 보호 검사의 실패 감도를 검증한다. 인식 수정 결과를 만드는 도구가 아니다.

수정 전 d07d244의 임시표 함수만 메모리에 불러와 검사한다. 파일을 되돌리거나
제품 판정을 덮어쓰지 않는다. 양성 대조군은 검사 검증용으로 음표를 복원한 배열이다.
도구의 종료 코드 0은 결함 해결이 아니라 음성·양성·변이 대조 검증 성공을 뜻한다.
"""

import argparse
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

import test_naturals_real as tests

BASELINE = "d07d244"
SCORES = {"db": "chopin_nocturne_Db_6-8.pdf", "bbm": "chopin_nocturne_Bbm.pdf",
          "em": "chopin_nocturne_Em.pdf"}


def case_details(name):
    matched = re.fullmatch(r"test_(carry|direct)_(db|bbm|em)_p(\d+)_x(\d+)_y(\d+)", name)
    if not matched:
        raise AssertionError(f"좌표별 검사 이름이 아닙니다: {name}")
    cause, score, page, x, y = matched.groups()
    return cause, (SCORES[score], int(page) - 1), int(x), int(y)


def run_cases(names, page_function):
    with patch.object(tests, "_carry_page", page_function):
        suite = unittest.TestSuite(tests.AccidentalDeletionTests(name) for name in names)
        return unittest.TextTestRunner(stream=io.StringIO()).run(suite)


def require_failures(result, count):
    assert result.testsRun == count and len(result.failures) == count
    assert not result.errors and not result.expectedFailures and not result.unexpectedSuccesses
    assert not result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/accidental-test-sensitivity.json")
    args = parser.parse_args()
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:modules/accidental_detect.py"], cwd=ROOT)
    baseline = types.ModuleType("modules._accidental_regression_baseline")
    baseline.__package__ = "modules"
    exec(compile(source, f"{BASELINE}:modules/accidental_detect.py", "exec"), baseline.__dict__)
    names = sorted(name for name in dir(tests.AccidentalDeletionTests)
                   if name.startswith(("test_carry_", "test_direct_")))
    details = {name: case_details(name) for name in names}
    expected = {(key, x, y) for key, points in tests.ACCIDENTAL_VICTIMS.items()
                for x, y, _text in points}
    assert len(names) == len(expected) == 18
    assert {(key, x, y) for _cause, key, x, y in details.values()} == expected
    assert sum(cause == "carry" for cause, *_ in details.values()) == 9
    tests._carry_page.cache_clear()
    actual_page = tests._carry_page
    cases = []
    with ExitStack() as stack:
        stack.enter_context(patch.object(tests, "annotate_accidentals", baseline.annotate_accidentals))
        stack.enter_context(patch.object(tests, "remove_accidental_ghosts", baseline.remove_accidental_ghosts))

        def restored_page(filename, page):
            before, after = actual_page(filename, page)
            restored = list(after)
            for x, y, _text in tests.ACCIDENTAL_VICTIMS.get((filename, page), ()):
                assert not tests._near(after, x, y), "옛 코드에서 결함이 재현되지 않습니다."
                hits = tests._near(before, x, y)
                assert len(hits) == 1
                restored.extend(hits)
            return before, restored

        # 전제 실패나 정상 유령의 복귀를 예상 실패가 가리지 않는지도 먼저 확인한다.
        preconditions = run_cases([
            "test_preconditions_are_real_candidates_before_accidental_filter",
            "test_existing_glyph_and_empty_space_removals_stay_removed"], actual_page)
        assert preconditions.wasSuccessful()
        with ExitStack() as decorators:
            for name in names:
                decorators.enter_context(patch.object(getattr(tests.AccidentalDeletionTests, name),
                                                      "__unittest_expecting_failure__", False,
                                                      create=True))
            require_failures(run_cases(names, actual_page), 18)
            positive = run_cases(names, restored_page)
            assert positive.testsRun == 18 and positive.wasSuccessful()
            for name, (cause, key, x, y) in details.items():
                for mutation in ("delete", "text"):
                    def changed_page(filename, page):
                        before, after = restored_page(filename, page)
                        if (filename, page) != key:
                            return before, after
                        if mutation == "delete":
                            after = [(n, text) for n, text in after
                                     if not (abs(n.x - x) <= 4 and abs(n.y - y) <= 4)]
                        else:
                            after = [(n, "__wrong__" if abs(n.x - x) <= 4 and abs(n.y - y) <= 4
                                      else text) for n, text in after]
                        return before, after
                    require_failures(run_cases([name], changed_page), 1)
                cases.append({"test": name, "cause": cause, "source": key[0], "page": key[1] + 1,
                              "point": [x, y], "old_code_fails": True,
                              "artificial_positive_passes": True,
                              "deletion_detected": True, "wrong_text_detected": True})

        # 동일 쪽의 다른 실패가 한 좌표의 unexpected success를 가려서는 안 된다.
        first = names[0]
        _cause, key, x, y = details[first]

        def one_restored_page(filename, page):
            before, after = actual_page(filename, page)
            if (filename, page) == key:
                after = list(after) + tests._near(before, x, y)
            return before, after

        # 나중에 제품 수정으로 표시가 해제되어도, 이 대조에서는 모두 xfail로 재현한다.
        with ExitStack() as decorators:
            for name in names:
                decorators.enter_context(patch.object(getattr(tests.AccidentalDeletionTests, name),
                                                      "__unittest_expecting_failure__", True,
                                                      create=True))
            partial = run_cases(names, one_restored_page)
        assert len(partial.expectedFailures) == 17 and len(partial.unexpectedSuccesses) == 1
        assert partial.unexpectedSuccesses[0]._testMethodName == first
        assert not partial.errors and not partial.failures and not partial.wasSuccessful()
    actual_page.cache_clear()
    report = {"baseline": BASELINE, "baseline_source_sha256": hashlib.sha256(source).hexdigest(),
              "test_source_sha256": hashlib.sha256(Path(tests.__file__).read_bytes()).hexdigest(),
              "cases": cases, "old_code_failures": 18, "positive_controls": 18,
              "mutation_failures": 36, "partial_expected_failures": 17,
              "partial_unexpected_successes": 1,
              "note": "배열 복원은 검사 검증용이며 인식 수정 결과가 아닙니다."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("실패 감도 검증 통과: 옛 코드 18개 실패, 양성 대조 18개 통과, 삭제/표기 변이 36개 감지")
    print("부분 복원: expected failure 17개 + unexpected success 1개, 성공으로 숨겨지지 않음")


if __name__ == "__main__":
    main()
