# -*- coding: utf-8 -*-
"""오선 제거·빔 마스크 캐시: 꺼져 있으면 원래 함수, 켜면 같은 값·복사본·해제."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from modules import notehead_detect as heads
from modules.engine_mask_cache import clear_mask_cache, with_mask_cache, _page_cache
from modules.preprocess import Staff
from modules.verify import beam_mask

img = np.zeros((200, 600), np.uint8)
staff = Staff(line_ys=[60, 72, 84, 96, 108], spacing=12.0, index=0)
for y in staff.line_ys:
    img[y, 20:580] = 255
img[70:80, 100:112] = 255          # 머리
img[130:135, 200:300] = 255        # 빔 비슷한 막대

plain_rm = heads.remove_staff_lines(img, [staff])
plain_bm = beam_mask(img, [staff])


@with_mask_cache
def page():
    a = heads.remove_staff_lines(img, [staff])
    a[:] = 7                                    # 받은 배열을 고쳐도 캐시는 그대로
    b = heads.remove_staff_lines(img, [staff])
    assert np.array_equal(b, plain_rm) and b.flags.writeable
    assert np.array_equal(beam_mask(img, [staff]), plain_bm)
    cache, size = _page_cache.get()
    assert len(cache) == 2 and size[0] > 0      # remove_staff_lines·beam_mask
    other = Staff(line_ys=[61, 73, 85, 97, 109], spacing=12.0, index=0)
    heads.remove_staff_lines(img, [other])      # 보표가 다르면 새 키
    assert len(cache) == 3
    clear_mask_cache()
    assert len(cache) == 0 and size[0] == 0


page()
assert _page_cache.get() is None                # 쪽 밖에서는 꺼짐
clear_mask_cache()                              # 꺼진 상태에서도 안전
print("엔진 마스크 캐시 확인 통과")
