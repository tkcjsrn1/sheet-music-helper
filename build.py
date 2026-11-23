# -*- coding: utf-8 -*-
"""원본 spec 빌드 → 전체 테스트 → 라이선스 검사 → 커밋 정보와 ZIP 생성."""

import argparse
import ast
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
SPEC_NAME = '악보헬퍼.spec'
EXE_NAME = '악보헬퍼.exe'
VERSION_INFO_NAME = 'assets/version_info.txt'
PACKAGE_SOURCE_NAMES = ('먼저 읽어주세요.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.txt')
NOTICE_DISTRIBUTIONS = ('opencv-python', 'numpy', 'scipy', 'Pillow', 'customtkinter', 'pyinstaller')
SUMMARY = re.compile(r'(\d+)개 중 통과 (\d+) · 건너뜀 (\d+) · 실패 (\d+)')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def source_snapshot():
    """빌드 중 변경을 감지한다. ignore된 exe·venv·debug는 입력에 포함하지 않는다."""
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
    ).decode('utf-8').split('\0')
    result = {}
    for name in sorted(set(names) - {''}):
        path = ROOT / name
        if path.is_symlink():
            result[name] = hashlib.sha256(os.readlink(path).encode('utf-8')).hexdigest().upper()
        elif path.is_file():
            result[name] = sha256(path)
        else:
            result[name] = None
    return result


def check_spec(path):
    """spec을 실행하기 전에 제외 설정과 customtkinter 수집을 정적으로 확인한다."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    analyses = [n for n in calls if n.func.id == 'Analysis']
    if len(analyses) != 1:
        raise RuntimeError('spec의 Analysis 설정을 하나로 확인할 수 없습니다.')
    excluded = next((k.value for k in analyses[0].keywords if k.arg == 'excludes'), None)
    try:
        excluded = set(ast.literal_eval(excluded))
    except (TypeError, ValueError, SyntaxError):
        raise RuntimeError('spec의 excludes를 정적 목록으로 확인할 수 없습니다.') from None
    if not {'fitz', 'pymupdf'} <= excluded:
        raise RuntimeError('spec에서 fitz와 pymupdf를 모두 제외해야 합니다. 빌드를 중단합니다.')
    collected = any(n.func.id == 'collect_all' and n.args and
                    isinstance(n.args[0], ast.Constant) and n.args[0].value == 'customtkinter'
                    for n in calls)
    if not collected:
        raise RuntimeError('spec의 customtkinter collect_all 설정이 없습니다.')
    executables = [n for n in calls if n.func.id == 'EXE']
    if len(executables) != 1:
        raise RuntimeError('spec의 EXE 설정을 하나로 확인할 수 없습니다.')
    version_node = next((k.value for k in executables[0].keywords if k.arg == 'version'), None)
    try:
        version_name = ast.literal_eval(version_node)
    except (TypeError, ValueError, SyntaxError):
        raise RuntimeError('spec의 Windows 버전 정보 파일을 확인할 수 없습니다.') from None
    if Path(version_name).as_posix() != VERSION_INFO_NAME:
        raise RuntimeError(f'spec은 {VERSION_INFO_NAME}를 Windows 버전 정보로 사용해야 합니다.')
    if not (Path(path).parent / version_name).is_file():
        raise RuntimeError(f'Windows 버전 정보 파일이 없습니다: {version_name}')


def package_sources():
    """배포 ZIP에 넣을 검토 가능한 정적 파일을 반환한다."""
    paths = [ROOT / name for name in PACKAGE_SOURCE_NAMES]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError('배포 파일이 없습니다: ' + ', '.join(missing))
    notices = (ROOT / 'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8-sig')
    expected = [f'Python {platform.python_version()}'] + [
        f'{name} {importlib.metadata.version(name)}' for name in NOTICE_DISTRIBUTIONS
    ]
    stale = [marker for marker in expected if marker not in notices]
    if stale:
        raise RuntimeError('제3자 라이선스 고지가 현재 빌드 버전과 다릅니다: ' + ', '.join(stale))
    return paths


def check_test_result(returncode, stdout, stderr=''):
    """러너는 건너뜀이 있어도 0으로 끝날 수 있으므로 종료 코드만 믿지 않는다."""
    matches = SUMMARY.findall(stdout)
    if returncode or not matches or '[건너뜀]' in stdout + stderr or '[실패]' in stdout + stderr:
        raise RuntimeError('전체 테스트 실패·건너뜀 또는 요약 누락: 패키지를 만들지 않습니다.')
    total, passed, skipped, failed = map(int, matches[-1])
    if total == 0 or passed != total or skipped != 0 or failed != 0:
        raise RuntimeError('전체 테스트는 실패 0 · 건너뜀 0이어야 합니다.')
    return dict(total=total, passed=passed, skipped=skipped, failed=failed)


def check_archive(exe):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(exe)
    pyz = archive.open_embedded_archive('PYZ.pyz')
    forbidden = [n for n in list(archive.toc) + list(pyz.toc)
                 if 'fitz' in n.lower() or 'mupdf' in n.lower()]
    if forbidden:
        raise RuntimeError('배포 금지 항목이 exe에 포함됐습니다: ' + ', '.join(forbidden))
    return dict(outer_entries=len(archive.toc), python_modules=len(pyz.toc), forbidden_entries=[])


def build(allow_dirty=False):
    if os.name != 'nt':
        raise RuntimeError('Windows exe 빌드는 Windows에서 실행하세요.')
    spec = ROOT / SPEC_NAME
    check_spec(spec)
    static_package_files = package_sources()
    commit = git('rev-parse', 'HEAD')
    if not re.fullmatch(r'[0-9a-f]{40,64}', commit):
        raise RuntimeError('Git 커밋 해시를 확인할 수 없습니다.')
    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    status = git('status', '--porcelain', '--untracked-files=all')
    dirty = bool(status)
    if dirty and not allow_dirty:
        raise RuntimeError('미커밋 변경이 있습니다. 커밋 후 빌드하세요. 개발 검증만 --allow-dirty를 허용합니다.')
    before = source_snapshot()
    started = datetime.now().astimezone()
    tag = commit[:12] + '-' + started.strftime('%Y%m%d-%H%M%S-%f') + ('-dirty' if dirty else '')
    destination = ROOT / 'dist' / tag
    destination.mkdir(parents=True, exist_ok=False)
    logs = ROOT / 'debug' / 'build-pipeline' / tag
    logs.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
               '--distpath', str(destination), '--workpath', str(ROOT / 'build' / tag), str(spec)]
    print('원본 spec으로 빌드 중: ' + tag, flush=True)
    with (logs / 'build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('빌드 실패. 판정 코드를 수정하지 말고 로그를 확인하세요: ' + str(logs / 'build.log'))

    print('빌드 후 전체 테스트 실행', flush=True)
    tests = subprocess.run([sys.executable, 'tests/run_all.py'], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
    (logs / 'tests.log').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    print(tests.stdout, flush=True)
    summary = check_test_result(tests.returncode, tests.stdout, tests.stderr)
    exe = destination / EXE_NAME
    archive = check_archive(exe)
    if git('rev-parse', 'HEAD') != commit or source_snapshot() != before:
        raise RuntimeError('빌드·테스트 도중 소스 또는 커밋이 바뀌었습니다. 패키지를 만들지 않습니다.')

    # 배포 메타데이터에는 내부 검증 파일 이름 대신 전체 소스의 해시를 기록한다.
    fingerprint = hashlib.sha256(json.dumps(before, sort_keys=True).encode('utf-8')).hexdigest().upper()

    metadata = dict(commit=commit, branch=branch, dirty=dirty,
                    started_at=started.isoformat(), finished_at=datetime.now().astimezone().isoformat(),
                    python=sys.version, platform=platform.platform(),
                    versions={name: importlib.metadata.version(name) for name in
                              ('pyinstaller', 'opencv-python', 'numpy', 'scipy', 'Pillow', 'customtkinter')},
                    spec=dict(path=SPEC_NAME, sha256=sha256(spec)),
                    exe=dict(path=EXE_NAME, sha256=sha256(exe), bytes=exe.stat().st_size),
                    package_files={path.name: sha256(path) for path in static_package_files},
                    tests=summary, archive=archive, source_snapshot_sha256=fingerprint)
    manifest = destination / 'build-info.json'
    manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    package = ROOT / 'dist' / ('악보헬퍼-' + tag + '.zip')
    with zipfile.ZipFile(package, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
        zipped.write(exe, EXE_NAME)
        zipped.write(manifest, manifest.name)
        for path in static_package_files:
            zipped.write(path, path.name)
    print('검증 완료: ' + str(exe), flush=True)
    print('커밋 정보: ' + str(manifest), flush=True)
    print('패키지: ' + str(package), flush=True)
    print('SHA-256: ' + metadata['exe']['sha256'], flush=True)
    if dirty:
        print('주의: 미커밋 변경을 포함한 개발 검증 빌드입니다. 배포용으로 사용하지 마세요.', flush=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-dirty', action='store_true', help='개발 검증용. 산출물에 dirty 상태를 명시한다')
    args = parser.parse_args()
    try:
        build(args.allow_dirty)
    except (OSError, RuntimeError, subprocess.CalledProcessError, SyntaxError) as exc:
        print('[실패] ' + str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
