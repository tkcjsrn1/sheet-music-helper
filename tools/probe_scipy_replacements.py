import json
import cv2
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import find_peaks

rng = np.random.default_rng(20260829)
maximum_cases = 0
peak_cases = 0

def finite_peaks_distance_two(values, height):
    # 현재 호출(height + distance=2)에 한정한 비교용 순차 구현. 배포 코드가 아니다.
    values = list(values)
    found = []
    i = 1
    while i < len(values) - 1:
        if values[i - 1] < values[i]:
            end = i
            while end + 1 < len(values) and values[end + 1] == values[i]:
                end += 1
            if end < len(values) - 1 and values[end + 1] < values[i] and values[i] >= height:
                found.append((i + end) // 2)
            i = end
        i += 1
    return found

for length in (1, 2, 3, 7, 64, 2048):
    for _ in range(20):
        values = rng.integers(0, 100, length, dtype=np.int32)
        for bridge in (3, 5):
            want = maximum_filter1d(values, size=bridge, mode='constant')
            actual = cv2.dilate(values.astype(np.float64).reshape(1, -1),
                                np.ones((1, bridge), np.uint8),
                                borderType=cv2.BORDER_CONSTANT, borderValue=0).ravel().astype(np.int32)
            np.testing.assert_array_equal(actual, want)
            maximum_cases += 1

for length in (0, 1, 2, 3, 7, 64, 2048):
    for _ in range(40):
        values = rng.integers(0, 10, length).astype(np.float64)
        for height in (0, 3, 9, 10):
            want = find_peaks(values, height=height, distance=2)[0].tolist()
            actual = finite_peaks_distance_two(values, height)
            assert actual == want, (values, height, actual, want)
            peak_cases += 1
print(json.dumps(dict(maximum_filter_cases=maximum_cases, find_peaks_cases=peak_cases,
                      mismatches=0, scope='synthetic finite vectors; current arguments only')))
