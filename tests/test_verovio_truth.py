"""Verovio 정답 TSV의 꾸밈음·겹올림 표기가 빠지지 않았는지 확인한다."""

import csv
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1] / "test_scores" / "verovio"
    files = sorted(root.glob("*_p1.tsv"))
    assert len(files) == 20
    rows = []
    for path in files:
        with path.open(encoding="utf-8", newline="") as stream:
            rows.extend(csv.DictReader(stream, delimiter="\t"))
    assert len(rows) == 8033
    assert sum(row["grace"] == "1" for row in rows) == 92
    assert sum(row["cue"] == "1" for row in rows) == 8
    assert sum(row["accidental"] == "##" for row in rows) == 2


if __name__ == "__main__":
    main()
