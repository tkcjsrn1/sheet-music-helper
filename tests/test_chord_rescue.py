# -*- coding: utf-8 -*-
"""붙은 화음 구제(`modules/chord_rescue.py`) 회귀 검사 — 2026-09-29.

1. 구멍 채움: 원본이 어두운 닫힌 구멍만 채운다 — 밝은 구멍(빈 음표 링)과 가장자리에 닿은 배경은 안 건드린다
2. 합치기 · 2b(좌표 단위):
   - 두 머리 접합부의 가운데 유령은 지운다
   - **쌓인 3화음의 진짜 가운데 음은 지우지 않는다** — 위 · 아래 추가 라벨이 딱 1sp씩 떨어진 최악의 경우 포함
   - 기존 라벨 ±0.5sp 안의 보강 라벨은 더하지 않는다
   - enable=False(사진 모드)면 아무것도 안 한다
3. 실제 쪽: B♭m 4쪽 (914, 2948) E5 — 쌓인 3화음의 진짜 가운데 음. 교체 방식(기각 25)에서 사라졌던 자리다.
   두 번 돌려 합친 뒤에도 남아야 한다(검증용 악보가 없으면 건너뜀)
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from modules.chord_rescue import hole_filled_binary, merge_additive  # noqa: E402

SP = 20.0
BBM = os.path.join(ROOT, "test_scores", "chopin_nocturne_Bbm.pdf")


class HoleFill(unittest.TestCase):
    def test_dark_hole_only(self):
        binary = np.zeros((60, 90), np.uint8)
        gray = np.full((60, 90), 255, np.uint8)
        for cx in (20, 60):                           # 링 두 개: 테두리 전경, 속 3×3 배경
            binary[20:29, cx - 4:cx + 5] = 255
            binary[23:26, cx - 1:cx + 2] = 0
        gray[23:26, 19:22] = 0                        # 왼쪽 링 속은 원본에서 검다(뚫린 꽉 찬 머리)
        gray[23:26, 59:62] = 250                      # 오른쪽 링 속은 밝다(빈 음표)
        gray[0:5, :] = 0                              # 가장자리에 닿은 어두운 배경 — 닫힌 구멍 아님
        out = hole_filled_binary(binary, gray)
        self.assertTrue((out[23:26, 19:22] == 255).all(), "원본이 어두운 닫힌 구멍은 채워야 한다")
        self.assertTrue((out[23:26, 59:62] == 0).all(), "빈 음표 링 속(밝음)은 건드리지 않는다")
        self.assertTrue((out[0:5, :] == 0).all(), "가장자리에 닿은 배경은 채우지 않는다")
        self.assertEqual(int((out != binary).sum()), 9)


class Merge(unittest.TestCase):
    def test_middle_ghost_deleted(self):
        # 실측 모양(중점 어긋남 0.27~0.33): 추가 라벨이 기존 라벨 위 0.55sp · 아래 0.8sp → 어긋남 0.3
        base = [(100.0, 100.0)]
        extra = [(100.0, 100.0 - 0.55 * SP), (100.0, 100.0 + 0.8 * SP)]
        added, deleted = merge_additive(base, extra, SP)
        self.assertEqual(added, [0, 1])
        self.assertEqual(deleted, [0])

    def test_true_triad_middle_kept_when_already_labeled(self):
        # 쌓인 3화음, 세 머리 다 기존 라벨 있음 — 보강이 같은 셋을 내도 더하지도 지우지도 않는다
        ys = (80.0, 100.0, 120.0)
        base = [(100.0, y) for y in ys]
        extra = [(101.0, y + 2) for y in ys]
        self.assertEqual(merge_additive(base, extra, SP), ([], []))

    def test_true_triad_middle_kept_worst_case(self):
        # 최악의 경우: 3화음 위 · 아래 머리가 기존에 누락이라 둘 다 추가 라벨이 됨 — 가운데(진짜)는 1sp씩 떨어져 있다
        base = [(100.0, 100.0)]
        extra = [(100.0, 100.0 - SP), (100.0, 100.0 + SP)]
        added, deleted = merge_additive(base, extra, SP)
        self.assertEqual(added, [0, 1])
        self.assertEqual(deleted, [], "3화음 진짜 가운데 음(중점 어긋남 0.5sp)을 지우면 안 된다")

    def test_tolerance_boundary(self):
        # 쌍 간격 조건(≤1.6sp)은 통과하지만 중점 어긋남 0.45 > 0.416 — 허용오차가 막아야 한다
        base = [(100.0, 100.0)]
        extra = [(100.0, 100.0 - 0.95 * SP), (100.0, 100.0 + 0.6 * SP)]
        self.assertEqual(merge_additive(base, extra, SP)[1], [], "중점 어긋남 0.45sp는 지우면 안 된다")
        extra = [(100.0, 100.0 - 0.9 * SP), (100.0, 100.0 + 0.6 * SP)]        # 어긋남 0.40 — 지운다
        self.assertEqual(merge_additive(base, extra, SP)[1], [0])

    def test_disabled_is_noop(self):
        # 사진 모드는 enable=False — 가운데 유령 모양이어도 더하지도 지우지도 않는다
        base = [(100.0, 100.0)]
        extra = [(100.0, 100.0 - 0.55 * SP), (100.0, 100.0 + 0.8 * SP)]
        self.assertEqual(merge_additive(base, extra, SP, enable=False), ([], []))

    def test_near_extra_not_added(self):
        base = [(100.0, 100.0)]
        extra = [(100.0 + 0.45 * SP, 100.0 - 0.45 * SP), (100.0, 100.0 + 0.55 * SP)]
        added, _ = merge_additive(base, extra, SP)
        self.assertEqual(added, [1])


class Confidence(unittest.TestCase):
    def test_added_label_is_caution(self):
        from types import SimpleNamespace
        from modules.labels_io import mark_accidental_candidates, flags_of, confidence_of
        rows = [{"staff": 0, "x": 10, "y": 20}]
        rows = mark_accidental_candidates(rows, [SimpleNamespace(staff_index=0, x=10, y=20)], "chord_rescue_added")
        self.assertEqual(confidence_of(flags_of(rows[0])), "caution", "구제로 추가된 라벨은 주의여야 한다(DECISIONS 1-9)")


class RealPage(unittest.TestCase):
    def test_bbm4_triad_middle_survives(self):
        if not os.path.exists(BBM):
            print("[건너뜀] 검증용 악보가 없습니다: chopin_nocturne_Bbm.pdf")
            return
        import check_accidental_fix as C
        from modules.chord_rescue import detect_noteheads_rescue
        base = C.snapshot_page("test_scores/chopin_nocturne_Bbm.pdf", 3)["labels"]
        orig = C.detect_noteheads
        C.detect_noteheads = detect_noteheads_rescue
        try:
            extra = C.snapshot_page("test_scores/chopin_nocturne_Bbm.pdf", 3)["labels"]
        finally:
            C.detect_noteheads = orig
        sp = 19.7                                     # B♭m 300dpi 오선 간격 중앙값
        mid = [i for i, l in enumerate(base) if abs(l["x"] - 914) <= 0.5 * sp and abs(l["y"] - 2948) <= 0.5 * sp]
        self.assertTrue(mid and base[mid[0]]["pitch"] == "E5", "기존 파이프라인이 (914, 2948) E5를 내야 한다(전제)")
        _added, deleted = merge_additive([(l["x"], l["y"]) for l in base], [(l["x"], l["y"]) for l in extra], sp)
        self.assertNotIn(mid[0], deleted, "쌓인 3화음의 진짜 가운데 음 E5가 2b로 지워졌다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
