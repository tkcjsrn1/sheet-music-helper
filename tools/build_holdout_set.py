# -*- coding: utf-8 -*-
"""보류(holdout) 세트 — 채점 전용, 문턱 유도 · 시뮬레이션 판정에 쓰지 않는다 (2026-10-12, DECISIONS §3 원칙 · test_scores/verovio_holdout/README.md).

`build_verovio_set.py`의 함수(MusicXML 파트 추출 `musicxml` · 머리 좌표 `note_rows` · 폰트 경로 `resource_path`)와
같은 Verovio 옵션(2100×2970, scale 100)으로 그린다. 다른 점 셋:
  ① 지금 세트에 없는 곡, 쪽마다 글꼴 하나(Bravura · Leipzig 반반), 2쪽 이상도 쓴다(`_p<쪽>`)
  ② PNG 변환은 cairosvg 대신 PyMuPDF(이 PC에 cairo DLL이 없다) — `check`로 기존 세트 한 쪽을 다시 그려 화소 대조
  ③ .krn은 music21로 MusicXML로 바꾸고, .musicxml 구성원은 .xml로 옮겨 같은 함수에 넣는다
정답 보강(`measure_verovio.svg_truth`)도 같은 SVG에서 만들어 debug/vrv_holdout/truth/에 둔다.

    python tools/build_holdout_set.py check     # 기존 mozart_k545 Bravura 1쪽: PyMuPDF 재렌더 vs 저장된 PNG
    python tools/build_holdout_set.py build
"""
import csv
import json
import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.modules.setdefault("cairosvg", types.ModuleType("cairosvg"))     # PNG 단계는 PyMuPDF로 한다
import build_verovio_set as B  # noqa: E402

OUTPUT = os.path.join(ROOT, "test_scores", "verovio_holdout")
TRUTH = os.path.join(ROOT, "debug", "vrv_holdout", "truth")
# (이름, 코퍼스 경로, 피아노 파트, 쪽, 글꼴) — 조표 · 박자 · 꾸밈음 · 셈여림 · 16분 겹빔이 고루 들도록
HOLDOUT = (
    ("weber_concertino_piano", "weber/concertino_clarinet.mxl", "P2", 1, "Bravura"),       # ♭ · 2/2 · 꾸밈음 · 셈여림 · 16분
    ("weber_concertino_piano", "weber/concertino_clarinet.mxl", "P2", 2, "Leipzig"),
    ("clara_trio_op17_3_piano", "schumann_clara/opus17/movement3.xml", "P3", 1, "Leipzig"),  # ♯1 · 6/8 · 꾸밈음 · 16분
    ("clara_trio_op17_3_piano", "schumann_clara/opus17/movement3.xml", "P3", 2, "Bravura"),
    ("handel_lascia_piano", "handel/rinaldo/Lascia_chio_pianga.mxl", "P2", 1, "Bravura"),     # ♯2 · 3/4 · 셈여림
    ("verdi_donna_mobile", "verdi/laDonnaEMobile.mxl", None, 1, "Leipzig"),                    # ♭2 · 3/8 · 꾸밈음
    ("schoenberg_op19_2", "schoenberg/opus19/movement2.mxl", None, 1, "Bravura"),              # 무조 · 임시표 · 셈여림
    ("schoenberg_op19_6", "schoenberg/opus19/movement6.mxl", None, 1, "Leipzig"),
    ("aloha_oe_piano", "liliuokalani/aloha_oe.mxl", "P6", 1, "Bravura"),                       # ♯1 · 4/4
    ("beach_prayer_piano", "beach/prayer_of_a_tired_child.musicxml", "P5", 1, "Leipzig"),      # ♭3 · 4/4 · 셈여림
    ("chopin_mazurka06_2", "chopin/mazurka06-2.krn", None, 1, "Bravura"),                      # ♯4 c#단조 · 3/4
    ("cpebach_h186", "cpebach/h186.mxl", None, 1, "Leipzig"),                                  # ♯3 · 4/4
)
OPTS = {"pageWidth": 2100, "pageHeight": 2970, "scale": 100}


def load_xml(rel, part):
    """MusicXML 문자열(파트 추출은 `B.musicxml`). .krn은 music21로 바꾸고, 구성원이 .musicxml인 .mxl · .musicxml 파일은 .xml로 옮겨 넘긴다."""
    import shutil
    import tempfile
    import zipfile
    from pathlib import Path
    p = B.CORPUS / rel
    if p.suffix == ".krn":
        import music21
        from music21.musicxml.m21ToXml import GeneralObjectExporter
        return GeneralObjectExporter(music21.converter.parse(str(p))).parse().decode("utf-8")
    raw = None
    if p.suffix == ".musicxml":
        raw = p.read_bytes()
    elif p.suffix == ".mxl":
        names = zipfile.ZipFile(p).namelist()
        if not any(n.endswith(".xml") and not n.startswith("META-INF") for n in names):
            raw = zipfile.ZipFile(p).read(next(n for n in names if n.endswith(".musicxml")))
    if raw is None:
        return B.musicxml(p, part)
    d = tempfile.mkdtemp()
    try:
        q = Path(d) / "s.xml"
        q.write_bytes(raw)
        return B.musicxml(q, part)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def svg_png(svg, path):
    """PyMuPDF로 SVG → 2100×2970 흰 바탕 RGB PNG."""
    import fitz
    import cv2
    import xml.etree.ElementTree as ET
    # MuPDF는 Verovio의 중첩 <svg viewBox>를 무시해 위치 · 배율이 어긋난다 → 바깥 svg에 안쪽 viewBox를 옮기고 안쪽 껍질을 벗긴다
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg)
    inner = next(c for c in root if c.tag == B.NS + "svg")
    root.set("viewBox", inner.get("viewBox"))
    i = list(root).index(inner)
    root.remove(inner)
    g = ET.Element(B.NS + "g", {k: v for k, v in inner.attrib.items() if k not in ("viewBox", "x", "y", "width", "height", "overflow")})
    g.extend(list(inner))
    root.insert(i, g)
    # 획 색은 <style>의 id 선택자 `path {stroke:currentColor}`로만 주는데 MuPDF가 그 CSS를 안 읽는다 → 속성으로 직접
    for el in root.iter():
        if el.tag in tuple(B.NS + t for t in ("path", "rect", "ellipse", "polygon", "polyline")) and "stroke" not in el.attrib:
            el.set("stroke", "#000000")
    # MuPDF는 currentColor를 못 읽어 오선 · 기둥 · 마디선 획이 빠진다 → 검정으로
    svg = ET.tostring(root, encoding="unicode").replace("currentColor", "#000000")
    doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    pg = doc[0]
    m = fitz.Matrix(2100 / pg.rect.width, 2970 / pg.rect.height)
    pix = pg.get_pixmap(matrix=m, alpha=False)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    assert img.shape[:2] == (2970, 2100), img.shape
    open(path, "wb").write(cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))[1].tobytes())


def toolkit(data, font):
    import verovio
    tk = verovio.toolkit()
    tk.setOptions({"inputFrom": "musicxml", "font": font, **OPTS, "svgBoundingBoxes": True,
                   "svgAdditionalAttribute": ["note@pname", "note@oct"]})
    if not tk.loadData(data):
        raise RuntimeError("Verovio 입력 실패")
    return tk


def check():
    """기존 세트 mozart_k545 Bravura 1쪽을 PyMuPDF로 다시 그려 저장된(cairosvg) PNG와 대조."""
    import verovio
    import cv2
    import tempfile
    resource, mapped = B.resource_path()
    try:
        verovio.setDefaultResourcePath(resource)
        tk = toolkit(B.musicxml(B.CORPUS / "mozart/k545/movement1_exposition.mxl", None), "Bravura")
        tk.setOptions({"svgBoundingBoxes": False})
        out = os.path.join(tempfile.gettempdir(), "holdout_check.png")
        svg_png(tk.renderToSVG(1), out)
    finally:
        if mapped:
            import subprocess
            subprocess.run(["subst", mapped, "/D"], check=True)
    a = cv2.imdecode(np.fromfile(out, np.uint8), cv2.IMREAD_GRAYSCALE)
    b = cv2.imdecode(np.fromfile(os.path.join(ROOT, "test_scores", "verovio", "mozart_k545_bravura_p1.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    ia, ib = a < 128, b < 128
    print("잉크 화소", ia.sum(), ib.sum(), "· 이진 불일치", (ia ^ ib).sum(), f"({(ia ^ ib).sum() / max(1, ib.sum()) * 100:.2f}% of 잉크)",
          "· 회색 절대차 평균", float(np.abs(a.astype(int) - b.astype(int)).mean()))
    return out


def build():
    import verovio
    sys.path.insert(0, HERE)
    import measure_verovio as V
    os.makedirs(OUTPUT, exist_ok=True)
    os.makedirs(TRUTH, exist_ok=True)
    resource, mapped = B.resource_path()
    manifest = []
    try:
        verovio.setDefaultResourcePath(resource)
        for name, rel, part, page, font in HOLDOUT:
            tk = toolkit(load_xml(rel, part), font)
            assert page <= tk.getPageCount(), (name, page, tk.getPageCount())
            svg = tk.renderToSVG(page)
            rows = B.note_rows(svg, tk)
            for r in rows:
                r["page"] = page
            t = V.svg_truth(svg, tk)
            assert len(t["notes"]) == len(rows), (name, len(t["notes"]), len(rows))
            tk.setOptions({"svgBoundingBoxes": False})
            stem = f"{name}_{font.lower()}_p{page}"
            svg_png(tk.renderToSVG(page), os.path.join(OUTPUT, stem + ".png"))
            with open(os.path.join(OUTPUT, stem + ".tsv"), "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
                w.writeheader()
                w.writerows(rows)
            json.dump(t, open(os.path.join(TRUTH, stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            manifest.append(dict(stem=stem, score=name, source=rel, piano_part=part, page=page, font=font,
                                 pages_in_source=tk.getPageCount(), notes_on_page=len(rows),
                                 grace=sum(int(r["grace"]) for r in rows), staves=len(t["staves"]),
                                 keys=sorted({k["val"] for s in t["staves"] for k in s["keysigs"]}),
                                 boxes={c: sum(b["cls"] == c for b in t["boxes"]) for c in ("dynam", "beam", "accid")}))
            print(stem, manifest[-1], flush=True)
    finally:
        if mapped:
            import subprocess
            subprocess.run(["subst", mapped, "/D"], check=True)
    json.dump(manifest, open(os.path.join(OUTPUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    {"check": check, "build": build}[sys.argv[1]]()
