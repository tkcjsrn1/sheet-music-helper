"""한 쪽 안에서 같은 입력으로 반복 계산되는 오선 제거·빔 마스크를 재사용한다.

`with_mask_cache`로 감싼 호출 안에서만 켜진다. 감싸지 않으면 원래 함수를 그대로 부른다.
키는 배열 바이트(SHA256)·형상·dtype, 보표 좌표, 여유 상수다. 꺼낼 때마다 복사해 주고
저장본은 쓰기 금지로 둔다. 쪽당 상한 64MiB, 쪽이 끝나거나 렌더 직전에 비운다.
"""
from contextvars import ContextVar
from functools import wraps
from hashlib import sha256

import numpy as np

_MAX_BYTES = 64 * 1024 * 1024
_page_cache = ContextVar("page_mask_cache", default=None)


def with_mask_cache(function):
    @wraps(function)
    def run(*args, **kwargs):
        token = _page_cache.set(({}, [0]))
        try:
            return function(*args, **kwargs)
        finally:
            _page_cache.reset(token)
    return run


def clear_mask_cache():
    state = _page_cache.get()
    if state is not None:
        cache, size = state
        cache.clear()
        size[0] = 0


def cache_mask(function):
    @wraps(function)
    def run(binary, staves):
        state = _page_cache.get()
        if state is None or binary.nbytes > _MAX_BYTES:
            return function(binary, staves)
        from . import notehead_detect as heads  # 순환 import 피하려 지연
        cache, size = state
        layout = tuple((s.top, s.bottom, s.spacing, tuple(s.line_ys)) for s in staves)
        key = (function, binary.shape, binary.dtype.str,
               sha256(np.ascontiguousarray(binary)).digest(),
               layout, heads.BASE_MARGIN_SP, heads.LEDGER_MARGIN_SP)
        saved = cache.get(key)
        if saved is not None:
            return saved.copy()
        value = function(binary, staves)
        if size[0] + value.nbytes <= _MAX_BYTES:
            # 원본 함수가 반환하던 쓰기 가능한 배열을 각 호출에 준다.
            saved = value.copy()
            saved.setflags(write=False)
            cache[key] = saved
            size[0] += saved.nbytes
        return value
    return run
