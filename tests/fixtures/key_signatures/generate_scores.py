"""동일한 선율을 15개 장조로 이조한 조표 검증 악보를 생성한다."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--lilypond",
    help="LilyPond 실행 파일 경로. 생략하면 PATH에서 찾고, 없으면 .ly만 생성",
)
args = parser.parse_args()
lilypond = args.lilypond or shutil.which("lilypond")

SOURCES = ROOT / "sources"
PDFS = ROOT / "pdf"
SOURCES.mkdir(parents=True, exist_ok=True)
PDFS.mkdir(parents=True, exist_ok=True)

KEYS = [
    dict(order=1, slug="C_major_0", name="C major", lily="c", transpose="c",
         symbol="", count=0, letters=[]),
    dict(order=2, slug="G_major_sharp1", name="G major", lily="g", transpose="g,",
         symbol="sharp", count=1, letters=["F"]),
    dict(order=3, slug="D_major_sharp2", name="D major", lily="d", transpose="d",
         symbol="sharp", count=2, letters=["F", "C"]),
    dict(order=4, slug="A_major_sharp3", name="A major", lily="a", transpose="a,",
         symbol="sharp", count=3, letters=["F", "C", "G"]),
    dict(order=5, slug="E_major_sharp4", name="E major", lily="e", transpose="e",
         symbol="sharp", count=4, letters=["F", "C", "G", "D"]),
    dict(order=6, slug="B_major_sharp5", name="B major", lily="b", transpose="b,",
         symbol="sharp", count=5, letters=["F", "C", "G", "D", "A"]),
    dict(order=7, slug="Fs_major_sharp6", name="F-sharp major", lily="fis", transpose="fis",
         symbol="sharp", count=6, letters=["F", "C", "G", "D", "A", "E"]),
    dict(order=8, slug="Db_major_flat5", name="D-flat major", lily="des", transpose="des",
         symbol="flat", count=5, letters=["B", "E", "A", "D", "G"]),
    dict(order=9, slug="Ab_major_flat4", name="A-flat major", lily="aes", transpose="aes,",
         symbol="flat", count=4, letters=["B", "E", "A", "D"]),
    dict(order=10, slug="Eb_major_flat3", name="E-flat major", lily="ees", transpose="ees",
         symbol="flat", count=3, letters=["B", "E", "A"]),
    dict(order=11, slug="Bb_major_flat2", name="B-flat major", lily="bes", transpose="bes,",
         symbol="flat", count=2, letters=["B", "E"]),
    dict(order=12, slug="F_major_flat1", name="F major", lily="f", transpose="f",
         symbol="flat", count=1, letters=["B"]),
    dict(order=13, slug="Cs_major_sharp7", name="C-sharp major", lily="cis", transpose="cis",
         symbol="sharp", count=7, letters=["F", "C", "G", "D", "A", "E", "B"]),
    dict(order=14, slug="Gb_major_flat6", name="G-flat major", lily="ges", transpose="ges",
         symbol="flat", count=6, letters=["B", "E", "A", "D", "G", "C"]),
    dict(order=15, slug="Cb_major_flat7", name="C-flat major", lily="ces", transpose="ces",
         symbol="flat", count=7, letters=["B", "E", "A", "D", "G", "C", "F"]),
]

RIGHT_SYSTEM = """c4 d e g | f e d c | e f g a | g2 c'2 |
c'4 b a g | f e d c | d e f d | c1 \\break"""
LEFT_SYSTEM = """c2 g | f g | c a | g c |
c g | f e | d g | c1 \\break"""

TEMPLATE = r'''\version "2.26.0"

rightBase = \fixed c' {
%(right)s
}

leftBase = \fixed c {
%(left)s
}

\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 14\mm
  right-margin = 14\mm
  ragged-last-bottom = ##f
  print-page-number = ##f
}

\layout {
  indent = 0\mm
  short-indent = 0\mm
  \context { \Score \remove "Bar_number_engraver" }
}

\score {
  \new PianoStaff <<
    \new Staff = "right" {
      \clef treble
      \key %(key)s \major
      \time 4/4
      \transpose c %(transpose)s \rightBase
    }
    \new Staff = "left" {
      \clef bass
      \key %(key)s \major
      \time 4/4
      \transpose c %(transpose)s \leftBase
    }
  >>
}
'''

right = "\n".join([RIGHT_SYSTEM] * 4)
left = "\n".join([LEFT_SYSTEM] * 4)
manifest = []
for key in KEYS:
    base = f"{key['order']:02d}_{key['slug']}"
    text = TEMPLATE % dict(right=right, left=left,
                           key=key["lily"], transpose=key["transpose"])
    ly_path = SOURCES / f"{base}.ly"
    ly_path.write_text(text, encoding="utf-8")
    item = dict(key)
    item.update(source=str(ly_path.relative_to(ROOT)), pdf=f"pdf/{base}.pdf")
    manifest.append(item)

(ROOT / "manifest.json").write_text(
    json.dumps({"generator": "LilyPond 2.26.0", "keys": manifest},
               ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"wrote {len(manifest)} LilyPond sources and manifest")

if lilypond:
    for item in manifest:
        source = ROOT / item["source"]
        output_base = (ROOT / item["pdf"]).with_suffix("")
        subprocess.run(
            [lilypond, "-dno-point-and-click", "-o", str(output_base), str(source)],
            check=True,
        )
    print(f"compiled {len(manifest)} PDFs with {lilypond}")
else:
    print("LilyPond를 찾지 못해 .ly와 manifest.json만 생성했습니다.")
