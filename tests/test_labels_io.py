# -*- coding: utf-8 -*-
"""라벨 JSON 저장·불러오기·재렌더링 테스트.

**이 데이터 구조는 앱으로 그대로 넘어간다**(`docs/LABELS_SCHEMA.md`).
그래서 여기서 고정하는 것은 '지금 동작'이 아니라 **약속**이다 —
저장한 것을 그대로 다시 그리면 같아야 하고, 남의 라벨은 거부해야 하고,
모르는 필드는 무시해야 한다.

    python tests/test_labels_io.py
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from modules.labels_io import (LabelSchemaError, check_dpi, check_source,  # noqa: E402
                               load_labels, match_labels, save_labels)

SCORES = os.path.join(ROOT, "test_scores")
BACH = os.path.join(SCORES, "bach_minuet_Am.pdf")
CHOPIN = os.path.join(SCORES, "chopin_nocturne_Db_6-8.pdf")

_fail = []
_skip = False


def check(cond, name, detail=""):
    if cond:
        print(f"  [통과] {name}")
    else:
        print(f"  [실패] {name}" + (f" — {detail}" if detail else ""))
        _fail.append(name)


def run_main(*args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "main.py")] + list(args),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def imread(path):
    return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)


def main():
    global _skip
    if not os.path.exists(BACH):
        print("  [건너뜀] test_scores/bach_minuet_Am.pdf 가 없습니다")
        return 0

    tmp = tempfile.mkdtemp(prefix="labels_io_")
    try:
        a, b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
        os.makedirs(a); os.makedirs(b)

        r = run_main(BACH, "--output-dir", a, "--no-debug")
        if r.returncode != 0:
            print(f"  [실패] 첫 인식이 실패했습니다\n{r.stdout[-500:]}")
            return 1
        js = glob.glob(os.path.join(a, "*라벨.json"))[0]
        doc = load_labels(js)
        check(len(doc["labels"]) > 100, "라벨 JSON이 저장된다",
              f"라벨 {len(doc['labels'])}개")

        # --- 1. 저장 -> 재렌더링이 픽셀 단위로 같다 -------------------
        r = run_main(BACH, "--relabel", js, "--output-dir", b, "--no-debug")
        ia = imread(glob.glob(os.path.join(a, "*계이름.png"))[0])
        ib = imread(glob.glob(os.path.join(b, "*계이름.png"))[0])
        same = (r.returncode == 0 and ia.shape == ib.shape
                and int((cv2.absdiff(ia, ib).max(axis=2) > 0).sum()) == 0)
        check(same, "저장한 목록을 다시 그리면 원본과 픽셀 단위로 같다")

        # --- 2. 다른 원본에 적용하면 거부한다 -------------------------
        if os.path.exists(CHOPIN):
            msg = check_source(doc, CHOPIN)
            check(msg is not None and "다른 원본" in msg,
                  "다른 원본에 적용하면 거부한다", repr(msg))
        check(check_source(doc, BACH) is None, "같은 원본이면 통과한다")
        check(check_source(doc, BACH, image_shape=(100, 200)) is not None,
              "이미지 크기가 다르면 거부한다")
        check(check_source(doc, BACH, page=7) is not None,
              "페이지가 다르면 거부한다")

        # --- 3. 필수 필드가 없으면 어디가 문제인지 말한다 --------------
        broken = os.path.join(tmp, "broken.json")
        d = json.loads(json.dumps(doc)); del d["labels"][0]["text"]
        save_labels(broken, d)
        try:
            load_labels(broken)
            check(False, "필수 필드가 없으면 막는다", "예외가 안 났다")
        except LabelSchemaError as e:
            check("text" in str(e) and "0번째" in str(e),
                  "필수 필드가 없으면 어디가 문제인지 말한다", str(e))

        # 배열/객체와 숫자가 손상되면 복원 전에 필드명을 담은 오류를 준다.
        bad_fields = [
            (("staves",), None, "staves 값이 배열"),
            (("labels", 0), None, "labels[0] 값이 객체"),
            (("staves", 0, "line_ys"), [], "staves[0].line_ys 값이 빈 배열"),
            (("labels",), {}, "labels 값이 배열"),
            (("staves", 0), [], "staves[0] 값이 객체"),
            (("staves", 0, "line_ys"), None, "staves[0].line_ys 값이 배열"),
            (("staves", 0, "line_ys", 0), "위", "staves[0].line_ys[0] 값이 숫자"),
            (("staves", 0, "line_ys", 0), float("nan"), "staves[0].line_ys[0] 값이 숫자"),
            (("staves", 0, "id"), None, "staves[0].id 값이 숫자"),
            (("staves", 0, "spacing"), "스무", "staves[0].spacing 값이 숫자"),
            (("staves", 0, "spacing"), 0, "staves[0].spacing 값이 양수"),
            (("staves", 0, "spacing"), float("inf"), "staves[0].spacing 값이 유한한 숫자"),
            (("staves", 0, "bottom_fit"), {}, "staves[0].bottom_fit 값이 숫자"),
            (("staves", 0, "bottom_fit"), float("nan"), "staves[0].bottom_fit 값이 유한한 숫자"),
            (("labels", 0, "staff"), [], "labels[0].staff 값이 숫자"),
            (("labels", 0, "x"), "왼쪽", "labels[0].x 값이 숫자"),
            (("labels", 0, "y"), float("inf"), "labels[0].y 값이 숫자"),
            (("labels", 0, "nx"), None, "labels[0].nx 값이 숫자"),
            (("source",), None, "source 값이 객체"),
            (("source", "page"), [], "source.page 값이 숫자"),
            (("source", "dpi"), "삼백", "source.dpi 값이 숫자"),
            (("schema",), float("inf"), "schema 값이 숫자"),
        ]
        for case, (keys, bad, message) in enumerate(bad_fields):
            d = json.loads(json.dumps(doc))
            target = d
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = bad
            save_labels(broken, d)
            try:
                load_labels(broken)
            except LabelSchemaError as exc:
                check(message in str(exc), f"손상 필드 {keys!r}: {bad!r}", str(exc))
            except Exception as exc:
                check(False, f"손상 필드 {keys!r}: {bad!r}", repr(exc))
            else:
                check(False, f"손상 필드 {keys!r}: {bad!r}", "예외가 안 났다")
            if case < 3:
                r = run_main(BACH, "--relabel", broken, "--output-dir", b)
                check(r.returncode == 1 and message in r.stdout
                      and "Traceback" not in r.stdout + r.stderr,
                      f"손상 사례 {case + 1}: CLI가 메시지로 중단한다", r.stdout + r.stderr)

        # 오래된 정상 파일의 선택 필드 누락과 빈 라벨 목록도 계속 허용한다.
        legacy = json.loads(json.dumps(doc))
        legacy.pop("source")
        for staff in legacy["staves"]:
            staff.pop("bottom_fit", None)
        legacy["labels"] = []
        save_labels(broken, legacy)
        check(load_labels(broken) == legacy, "옛 정상 JSON 값을 바꾸지 않고 읽는다")

        # --- 4. 모르는 필드는 무시한다 --------------------------------
        extra = os.path.join(tmp, "extra.json")
        d = json.loads(json.dumps(doc))
        d["앞으로생길항목"] = {"x": 1}
        d["labels"][0]["앞으로생길필드"] = 123
        save_labels(extra, d)
        c = os.path.join(tmp, "c"); os.makedirs(c)
        r = run_main(BACH, "--relabel", extra, "--output-dir", c, "--no-debug")
        ic = imread(glob.glob(os.path.join(c, "*계이름.png"))[0]) if r.returncode == 0 else None
        check(r.returncode == 0 and ic is not None
              and int((cv2.absdiff(ia, ic).max(axis=2) > 0).sum()) == 0,
              "모르는 필드는 무시하고 그대로 그린다")

        # --- 5. dpi가 이상해도 traceback 대신 문장을 준다 --------------
        # (Codex가 찾은 결함 3번. 예전에는 int()가 그대로 터졌다)
        for bad in ("삼백", "", {"a": 1}, [300], float("inf"), float("nan")):
            d = json.loads(json.dumps(doc)); d["source"]["dpi"] = bad
            msg = check_dpi(d)
            check(isinstance(msg, str) and "숫자가 아닙니다" in msg,
                  f"dpi가 {bad!r} 이어도 예외 대신 문장을 준다", repr(msg))
        d = json.loads(json.dumps(doc)); d["source"]["dpi"] = 400
        check("400dpi" in (check_dpi(d) or ""), "dpi가 다르면 알린다")
        d = json.loads(json.dumps(doc)); del d["source"]["dpi"]
        check(check_dpi(d) is None, "dpi가 없는 옛 파일은 관대하게 넘어간다")

        # --- 6. 보표가 하나 어긋나도 라벨이 고아가 되지 않는다 -----------
        # 보표를 **순번**으로 맞추던 시절에는 맨 위 보표가 하나 밀리면
        # 240개 중 4개만 짝을 찾았다. 그마저도 밀린 번호에서 우연히 맞은
        # 것이라 **남의 수정이 얹힐 자리**였다. y좌표로 바꾼 뒤의 회귀 방지다.
        def _shift(base, k, insert):
            d = json.loads(json.dumps(base))
            for st in d["staves"]:
                if insert:
                    if st["id"] >= k:
                        st["id"] += 1
                elif st["id"] > k:
                    st["id"] -= 1
            for lb in d["labels"]:
                if insert:
                    if lb["staff"] >= k:
                        lb["staff"] += 1
                elif lb["staff"] > k:
                    lb["staff"] -= 1
            if not insert:
                d["staves"] = [st for st in d["staves"] if st["id"] != k or True]
                d["labels"] = [lb for lb in d["labels"] if lb["staff"] != k or True]
            return d

        n_staff = len(doc["staves"])
        for name, k, ins in (("맨 위 보표가 밀림", 0, True),
                             ("가운데 보표가 밀림", n_staff // 2, True)):
            fresh = _shift(doc, k, ins)
            mapping, _orph = match_labels(doc, fresh)
            right = sum(1 for i, j in mapping.items()
                        if (doc["labels"][i]["x"], doc["labels"][i]["y"])
                        == (fresh["labels"][j]["x"], fresh["labels"][j]["y"]))
            check(len(mapping) == right == len(doc["labels"]),
                  f"{name} — 전부 맞는 짝으로 붙는다",
                  f"붙음 {len(mapping)} · 맞는짝 {right} / {len(doc['labels'])}")

        # --- 7. 편집이 반영된다 ---------------------------------------
        edited = os.path.join(tmp, "edited.json")
        d = json.loads(json.dumps(doc))
        n0 = len(d["labels"])
        d["labels"] = d["labels"][3:]
        d["labels"][0]["text"] = "수정됨"
        d["labels"][0]["edited"] = True
        save_labels(edited, d)
        e = os.path.join(tmp, "e"); os.makedirs(e)
        r = run_main(BACH, "--relabel", edited, "--output-dir", e, "--no-debug")
        ie = imread(glob.glob(os.path.join(e, "*계이름.png"))[0]) if r.returncode == 0 else None
        check(r.returncode == 0 and len(d["labels"]) == n0 - 3
              and ie is not None
              and int((cv2.absdiff(ia, ie).max(axis=2) > 0).sum()) > 0,
              "줄을 지우고 값을 고치면 그림에 반영된다")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if _fail:
        print(f"\n실패 {len(_fail)}건: {', '.join(_fail)}")
        return 1
    print("\n[성공] 라벨 JSON 테스트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
