# -*- coding: utf-8 -*-
"""center_split(§1-54)는 꽉 찬 머리에만 — 머리 유형은 `drop_offstaff_ghosts`가 검출 결과 그대로 `result.head_filled`에 남긴다."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from modules.notehead_detect import Notehead
from modules.preprocess import Staff
from modules.verify import drop_offstaff_ghosts

staff = Staff(line_ys=[60, 72, 84, 96, 108], spacing=12.0, index=0)
img = np.zeros((200, 300), np.uint8)
for y in staff.line_ys:
    img[y, 10:290] = 255
res = SimpleNamespace(binary=img, staves=[staff])
heads = [Notehead(x=100, y=78, staff_index=0, filled=True), Notehead(x=150, y=90, staff_index=0, filled=False)]
kept, _ = drop_offstaff_ghosts(res, heads)
assert res.head_filled == {(0, 100, 78): True, (0, 150, 90): False}
drop_offstaff_ghosts(res, [Notehead(x=200, y=84, staff_index=0, filled=True)])     # 두 번째 검출(화음 구제)은 더한다
assert res.head_filled[(0, 200, 84)] is True and len(res.head_filled) == 3
print("center_split 머리 유형 기록 확인 통과")
