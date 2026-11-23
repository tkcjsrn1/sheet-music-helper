# -*- coding: utf-8 -*-
"""빌드에서 실패·건너뜀·라이선스 제외 누락이 성공으로 처리되지 않는지 확인한다."""

import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from build import PACKAGE_SOURCE_NAMES, check_spec, check_test_result, package_sources
from gui import _filetypes_for_runtime


class TestResultGateTests(unittest.TestCase):
    def test_accepts_variable_nonzero_test_counts(self):
        for total in (1, 9):
            with self.subTest(total=total):
                self.assertEqual(check_test_result(0, f'{total}개 중 통과 {total} · 건너뜀 0 · 실패 0')['passed'], total)

    def test_rejects_skip_even_when_runner_exits_zero(self):
        for output in ('3개 중 통과 2 · 건너뜀 1 · 실패 0',
                       '[건너뜀] fixture\n3개 중 통과 3 · 건너뜀 0 · 실패 0'):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                check_test_result(0, output)

    def test_rejects_failure_empty_or_inconsistent_summary(self):
        for code, output in ((1, '3개 중 통과 3 · 건너뜀 0 · 실패 0'),
                             (0, '3개 중 통과 2 · 건너뜀 0 · 실패 1'),
                             (0, '0개 중 통과 0 · 건너뜀 0 · 실패 0'),
                             (0, '3개 중 통과 2 · 건너뜀 0 · 실패 0'), (0, '')):
            with self.subTest(code=code, output=output), self.assertRaises(RuntimeError):
                check_test_result(code, output)


class SpecGateTests(unittest.TestCase):
    @staticmethod
    def _write_spec(tmp, content):
        root = Path(tmp)
        version = root / 'assets' / 'version_info.txt'
        version.parent.mkdir()
        version.write_text('version metadata', encoding='utf-8')
        spec = root / 'test.spec'
        spec.write_text(content, encoding='utf-8')
        return spec

    def test_static_check_does_not_execute_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self._write_spec(
                tmp,
                "raise RuntimeError('실행되면 안 됨')\ncollect_all('customtkinter')\n"
                "Analysis([], excludes=['fitz', 'pymupdf'])\n"
                "EXE(version='assets/version_info.txt')\n",
            )
            check_spec(spec)

    def test_missing_exclusion_assets_or_version_stops_before_build(self):
        valid_exe = "\nEXE(version='assets/version_info.txt')"
        for content in ("collect_all('customtkinter')\nAnalysis([], excludes=['fitz'])" + valid_exe,
                        "Analysis([], excludes=['fitz', 'pymupdf'])" + valid_exe,
                        "collect_all('customtkinter')\nAnalysis([], excludes=dynamic_list)" + valid_exe,
                        "collect_all('customtkinter')\nAnalysis([], excludes=['fitz', 'pymupdf'])\nEXE()"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                spec = self._write_spec(tmp, content)
                with self.assertRaises(RuntimeError):
                    check_spec(spec)


class DistributionPackageTests(unittest.TestCase):
    def test_package_contains_user_docs_but_not_personal_settings(self):
        self.assertEqual(
            PACKAGE_SOURCE_NAMES,
            ('먼저 읽어주세요.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.txt'),
        )
        self.assertNotIn('settings.json', PACKAGE_SOURCE_NAMES)
        self.assertEqual([path.name for path in package_sources()], list(PACKAGE_SOURCE_NAMES))

    def test_release_copyright_matches_the_distribution_identity(self):
        root = Path(__file__).resolve().parents[1]
        copyright_notice = 'Copyright (c) 2026 tkcjsrn1'
        version = (root / 'assets' / 'version_info.txt').read_text(encoding='utf-8')
        self.assertIn(copyright_notice, (root / 'LICENSE').read_text(encoding='utf-8').splitlines())
        self.assertIn("StringStruct('CompanyName', 'tkcjsrn1')", version)
        self.assertIn(f"StringStruct('LegalCopyright', '{copyright_notice}')", version)

    def test_packaged_file_picker_excludes_pdf_and_all_files(self):
        packaged = ' '.join(pattern for _label, pattern in _filetypes_for_runtime(True))
        source = ' '.join(pattern for _label, pattern in _filetypes_for_runtime(False))
        self.assertNotIn('*.pdf', packaged)
        self.assertNotIn('*.*', packaged)
        self.assertIn('*.pdf', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
