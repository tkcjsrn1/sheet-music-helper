"""측정 전용 래퍼 — 입력 경로에 'pdfium'이 들어 있으면 전처리 결과에 raster_source="pdfium"을 달고 main.py를 그대로 실행한다.
(#499 PDF 입력 코드가 이 표시를 넘기기 전까지 B안을 PDFium 렌더에서 재기 위한 것. 제품 코드 무변경.)
    python tools/measure_main_as_render.py <코드 루트> <main.py 인자...>   (흔들림 도구: AKBO_MAIN_WRAPPER=tools/measure_main_as_render.py)"""
import sys, os
CODE = sys.argv[1]
sys.argv = [os.path.join(CODE, "main.py")] + sys.argv[2:]
sys.path.insert(0, CODE)
os.chdir(CODE)
import main as M
_orig = M.preprocess
def _pre(path, *a, **k):
    r = _orig(path, *a, **k)
    if "pdfium" in str(path).lower():
        r.raster_source = "pdfium"
    return r
M.preprocess = _pre
M.main()
