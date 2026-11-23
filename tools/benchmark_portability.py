# -*- coding: utf-8 -*-
"""Windows에서 실제 CLI 파이프라인의 해상도별 시간·프로세스 메모리를 잰다."""

import argparse
import contextlib
import ctypes
from ctypes import wintypes
from datetime import datetime
import gc
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def memory_mib():
    """현재 RSS와 프로세스 생애 전체 RSS 최고치(Windows Working Set)를 반환한다."""
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    data = Counters()
    data.cb = ctypes.sizeof(data)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(data), data.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return data.WorkingSetSize / 2**20, data.PeakWorkingSetSize / 2**20


def worker(args):
    # 부모의 PDF 래스터화·리사이즈 메모리가 이 프로세스에 섞이지 않는다.
    imported = time.perf_counter()
    import main as app
    import cv2
    import_elapsed = time.perf_counter() - imported
    baseline_rss, _ = memory_mib()
    stats = {}
    original_preprocess = app.preprocess
    original_render = app.render_solfege_on_image

    def preprocess(*values, **kwargs):
        result = original_preprocess(*values, **kwargs)
        stats['width'] = result.original_bgr.shape[1]
        stats['height'] = result.original_bgr.shape[0]
        return result

    def render(*values, **kwargs):
        stats['recognition_s'] = time.perf_counter() - stats['start']
        stats['label_count'] = len(values[1])
        return original_render(*values, **kwargs)

    app.preprocess = preprocess
    app.render_solfege_on_image = render
    options = argparse.Namespace(save_source=False, no_debug=True, audit=False,
                                 clef='auto', verify=False, notation='solfege-fixed',
                                 key='', minor=False, font_size=18, color='#dc1414')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sampled_peak = [baseline_rss]
    stop = threading.Event()

    def sample():
        while not stop.wait(0.01):
            sampled_peak[0] = max(sampled_peak[0], memory_mib()[0])

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    runs = []
    try:
        for i in range(args.repeats + 1):
            gc.collect()
            stats.clear()
            stats['start'] = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                app.run_page(options, args.worker, 0, str(out))
            total = time.perf_counter() - stats['start']
            runs.append(dict(index=i, recognition_s=stats['recognition_s'],
                             total_s=total, label_count=stats['label_count']))
    finally:
        stop.set()
        sampler.join()
    _, peak = memory_mib()
    print(json.dumps(dict(width=stats['width'], height=stats['height'], runs=runs,
                          import_s=import_elapsed, baseline_rss_mib=baseline_rss,
                          processing_peak_sampled_mib=sampled_peak[0], peak_rss_mib=peak,
                          opencv_threads=cv2.getNumThreads()), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'debug' / 'portability'))
    parser.add_argument('--repeats', type=int, default=3, help='첫 실행 이후 반복 횟수')
    parser.add_argument('--scales', type=float, nargs='+', default=[0.5, 1.0, 1.5])
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('메모리 계측은 Windows 전용입니다.')
    if args.repeats < 1 or any(not (0 < s <= 2) for s in args.scales):
        parser.error('repeats는 1 이상, scales는 0 초과 2 이하여야 합니다.')
    if args.worker:
        worker(args)
        return

    import cv2
    from modules.preprocess import load_image
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = dict(measured_at=datetime.now().astimezone().isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  engine_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD:modules'], cwd=ROOT, text=True).strip(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  python=sys.version, platform=platform.platform(),
                  versions={name: importlib.metadata.version(name) for name in
                            ('numpy', 'scipy', 'opencv-python', 'Pillow', 'PyMuPDF')},
                  repeats=args.repeats, cases=[])
    sources = [('aoharu_p1', ROOT / 'sample_images' / 'KakaoTalk_20260731_162400402.png'),
               ('chopin_Db_p1', ROOT / 'test_scores' / 'chopin_nocturne_Db_6-8.pdf')]
    for name, source in sources:
        original = load_image(str(source), pdf_page=0, pdf_dpi=300)
        for scale in args.scales:
            size = (round(original.shape[1] * scale), round(original.shape[0] * scale))
            img = (original if scale == 1 else cv2.resize(original, size,
                   interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC))
            path = out / f'{name}-{scale:g}.png'
            ok, encoded = cv2.imencode('.png', img)
            if not ok:
                raise RuntimeError('측정 입력 PNG 인코딩 실패')
            encoded.tofile(path)
            started = time.perf_counter()
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(path),
                                   '--repeats', str(args.repeats), '--output', str(out / 'rendered')],
                                  cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                                  env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=300)
            case = dict(source=name, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        scale=scale, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        process_wall_s=time.perf_counter() - started)
            if proc.returncode:
                case.update(error=proc.stderr[-4000:], stdout=proc.stdout[-2000:])
            else:
                case.update(json.loads(proc.stdout))
                warm = case['runs'][1:]
                case['warm_recognition_median_s'] = statistics.median(r['recognition_s'] for r in warm)
                case['warm_total_median_s'] = statistics.median(r['total_s'] for r in warm)
                case['warm_total_range_s'] = [min(r['total_s'] for r in warm), max(r['total_s'] for r in warm)]
            report['cases'].append(case)
            (out / 'benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: case[k] for k in ('source', 'scale', 'width', 'height',
                  'warm_recognition_median_s', 'warm_total_median_s', 'peak_rss_mib', 'error') if k in case},
                  ensure_ascii=False), flush=True)
    if any('error' in c for c in report['cases']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
