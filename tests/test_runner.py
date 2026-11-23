"""검증 누락은 실제 자식 프로세스에서도 성공 종료가 되면 안 된다."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_all


class RunnerTests(unittest.TestCase):
    def invoke(self, scripts):
        with tempfile.TemporaryDirectory() as folder:
            for name, body in scripts.items():
                (Path(folder) / name).write_text(body, encoding='utf-8')
            output = io.StringIO()
            with patch.object(run_all, 'HERE', folder), contextlib.redirect_stdout(output):
                code = 0
                try:
                    run_all.main()
                except SystemExit as exc:
                    code = exc.code
            return code, output.getvalue()

    def test_success_and_child_failure_keep_running_other_tests(self):
        self.assertEqual(self.invoke({'test_ok.py': 'print("정상")'})[0], 0)
        code, output = self.invoke({'test_bad.py': 'raise SystemExit(2)',
                                    'test_ok.py': 'print("정상")'})
        self.assertEqual(code, 1)
        self.assertIn('[통과] test_ok.py', output)
        self.assertIn('통과 1 · 건너뜀 0 · 실패 1', output)

    def test_skip_on_either_stream_is_incomplete(self):
        for body in ('print("[건너뜀] 검증 입력 없음")',
                     'import sys; print("[건너뜀] 검증 입력 없음", file=sys.stderr)'):
            with self.subTest(body=body):
                code, output = self.invoke({'test_missing.py': body,
                                            'test_ok.py': 'print("정상")'})
                self.assertEqual(code, 1)
                self.assertIn('통과 1 · 건너뜀 1 · 실패 0', output)
                self.assertIn('검증 입력 없음', output)

    def test_standard_unittest_skip_is_incomplete_but_expected_failure_is_allowed(self):
        skipped = 'import unittest\nclass Case(unittest.TestCase):\n @unittest.skip("검증 입력 없음")\n def test_missing(self): self.fail()\nunittest.main()'
        code, output = self.invoke({'test_missing.py': skipped})
        self.assertEqual(code, 1)
        self.assertIn('통과 0 · 건너뜀 1 · 실패 0', output)
        self.assertIn('skipped=1', output)
        expected = 'import unittest\nclass Case(unittest.TestCase):\n @unittest.expectedFailure\n def test_known(self): self.fail()\nunittest.main()'
        self.assertEqual(self.invoke({'test_known.py': expected})[0], 0)

    def test_failure_keeps_traceback_before_unittest_summary(self):
        body = ('import sys\nprint("AssertionError: 입력칸 보호 실패", file=sys.stderr)\n'
                'print("\\n" * 8 + "FAILED (failures=1)", file=sys.stderr)\nraise SystemExit(1)')
        code, output = self.invoke({'test_trace.py': body})
        self.assertEqual(code, 1)
        self.assertIn('AssertionError: 입력칸 보호 실패', output)
        self.assertIn('FAILED (failures=1)', output)

    def test_no_tests_is_not_success(self):
        code, output = self.invoke({})
        self.assertEqual(code, 1)
        self.assertIn('테스트 파일', output)


if __name__ == '__main__':
    unittest.main()
