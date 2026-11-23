"""music21 저작권 만료 악곡의 첫 쪽을 두 Verovio 글꼴로 렌더링한다.

별도 설치: pip install verovio music21 cairosvg
인식 파이프라인은 실행하지 않는다.
"""

import csv
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import cairosvg
import music21
import verovio
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "test_scores" / "verovio"
CORPUS = Path(music21.__file__).parent / "corpus"
NS = "{http://www.w3.org/2000/svg}"
SCORES = (
    ("mozart_k545", "mozart/k545/movement1_exposition.mxl", None),
    ("bach_bwv846", "bach/bwv846.mxl", None),
    ("joplin_maple_leaf", "joplin/maple_leaf_rag.mxl", None),
    ("clara_polonaise_1", "schumann_clara/polonaise_op1n1.mxl", None),
    ("clara_polonaise_2", "schumann_clara/polonaise_op1n2.mxl", None),
    ("clara_polonaise_3", "schumann_clara/polonaise_op1n3.mxl", None),
    ("clara_polonaise_4", "schumann_clara/polonaise_op1n4.mxl", None),
    ("schubert_lindenbaum_piano", "schubert/Lindenbaum.xml", "P2"),
    ("schumann_op48no2_piano", "schumann_robert/opus48no2.mxl", "P2"),
    ("beethoven_op18no1", "beethoven/opus18no1/movement1.mxl", None),
)
ACCIDENTALS = {"s": "#", "f": "b", "n": "natural", "ss": "##", "x": "##", "ff": "bb"}


def musicxml(path: Path, piano_part: str | None) -> str:
    if path.suffix == ".mxl":
        with zipfile.ZipFile(path) as archive:
            member = next(name for name in archive.namelist()
                          if name.endswith(".xml") and not name.startswith("META-INF"))
            raw = archive.read(member)
    else:
        raw = path.read_bytes()
    root = ET.fromstring(raw)
    if piano_part:
        part_list = root.find("part-list")
        for item in list(part_list):
            if item.tag != "score-part" or item.get("id") != piano_part:
                part_list.remove(item)
        for part in list(root.findall("part")):
            if part.get("id") != piano_part:
                root.remove(part)
    return ET.tostring(root, encoding="unicode")


def note_rows(svg: str, toolkit) -> list[dict]:
    root = ET.fromstring(svg)
    inner = next(node for node in root if node.tag == NS + "svg")
    _, _, svg_width, svg_height = map(float, inner.get("viewBox").split())
    sx = float(root.get("width").removesuffix("px")) / svg_width
    sy = float(root.get("height").removesuffix("px")) / svg_height
    parents = {child: parent for parent in root.iter() for child in parent}
    rows = []
    for note in root.iter():
        if note.get("class") != "note":
            continue
        rect = next((child for child in note.iter()
                     if child.tag == NS + "rect"
                     and parents[child].get("class") == "note bounding-box"), None)
        if rect is None:
            raise ValueError(f"음표 머리 상자 없음: {note.get('id')}")
        dx = dy = 0.0
        ancestor = parents.get(rect)
        while ancestor is not None:
            transform = ancestor.get("transform")
            if transform:
                match = re.fullmatch(r"translate\(\s*([\d.-]+)[, ]+([\d.-]+)\s*\)", transform)
                if not match:
                    raise ValueError(f"지원하지 않는 SVG 변환: {transform}")
                dx += float(match[1])
                dy += float(match[2])
            ancestor = parents.get(ancestor)
        accidental = ""
        for child in note.iter():
            if child.get("class") == "accid":
                attrs = toolkit.getElementAttr(child.get("id"))
                # accid.ges는 조표 등으로 바뀐 음고이며, 악보에 인쇄된 임시표가 아니다.
                accidental = ACCIDENTALS.get(attrs.get("accid"), "")
                break
        ancestor = parents.get(note)
        chord = False
        chord_node = None
        while ancestor is not None:
            if ancestor.get("class") == "chord":
                chord = True
                chord_node = ancestor
                break
            ancestor = parents.get(ancestor)
        attrs = toolkit.getElementAttr(note.get("id"))
        chord_attrs = toolkit.getElementAttr(chord_node.get("id")) if chord_node is not None else {}
        rows.append(dict(page=1,
                         x=round((float(rect.get("x")) + float(rect.get("width")) / 2 + dx) * sx, 2),
                         y=round((float(rect.get("y")) + float(rect.get("height")) / 2 + dy) * sy, 2),
                         note_name=note.get("data-pname", "").upper(),
                         octave=note.get("data-oct", ""),
                         accidental=accidental, chord=int(chord),
                         grace=int(bool(attrs.get("grace") or chord_attrs.get("grace"))),
                         cue=int((attrs.get("cue") or chord_attrs.get("cue")) == "true")))
    return rows


def resource_path() -> tuple[str, str | None]:
    path = str(Path(verovio.__file__).parent / "data")
    if path.isascii():
        return path, None
    for letter in "ZYXW":
        drive = letter + ":"
        if not os.path.exists(drive + "/"):
            subprocess.run(["subst", drive, path], check=True)
            return drive + "/", drive
    raise RuntimeError("Verovio 폰트용 빈 ASCII 드라이브 문자가 없습니다")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    resource, mapped = resource_path()
    try:
        verovio.setDefaultResourcePath(resource)
        manifest = []
        for name, relative, piano_part in SCORES:
            data = musicxml(CORPUS / relative, piano_part)
            for font in ("Bravura", "Leipzig"):
                toolkit = verovio.toolkit()
                toolkit.setOptions({"inputFrom": "musicxml", "font": font,
                                    "pageWidth": 2100, "pageHeight": 2970, "scale": 100,
                                    "svgBoundingBoxes": True,
                                    "svgAdditionalAttribute": ["note@pname", "note@oct"]})
                if not toolkit.loadData(data):
                    raise RuntimeError(f"Verovio 입력 실패: {relative}")
                svg = toolkit.renderToSVG(1)
                rows = note_rows(svg, toolkit)
                toolkit.setOptions({"svgBoundingBoxes": False})
                clean = toolkit.renderToSVG(1)
                stem = f"{name}_{font.lower()}_p1"
                png = OUTPUT / (stem + ".png")
                cairosvg.svg2png(bytestring=clean.encode("utf-8"), write_to=str(png))
                with Image.open(png) as transparent:
                    white = Image.new("RGBA", transparent.size, "white")
                    white.alpha_composite(transparent.convert("RGBA"))
                    white.convert("RGB").save(png)
                with (OUTPUT / (stem + ".tsv")).open("w", encoding="utf-8", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=list(rows[0]), delimiter="\t")
                    writer.writeheader()
                    writer.writerows(rows)
                manifest.append({"score": name, "source": relative, "font": font,
                                 "pages_in_source": toolkit.getPageCount(),
                                 "notes_on_page": len(rows), "piano_part": piano_part})
                print(stem, len(rows), "음표")
                if name == "mozart_k545" and font == "Bravura":
                    overlay = Image.open(png).convert("RGB")
                    draw = ImageDraw.Draw(overlay)
                    for row in rows[::max(1, len(rows) // 24)][:24]:
                        x, y = row["x"], row["y"]
                        draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline="red", width=2)
                    overlay.save(OUTPUT / "coordinate_check_24.png")
        (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    finally:
        if mapped:
            subprocess.run(["subst", mapped, "/D"], check=True)


if __name__ == "__main__":
    main()
