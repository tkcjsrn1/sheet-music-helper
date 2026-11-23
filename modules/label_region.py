"""전체 쪽에서 인식한 라벨의 머리 중심을 선택 영역으로 거른다. 인식/배치 변경 없음."""
import copy


def filter_region(doc: dict, x1: float, y1: float, x2: float, y2: float) -> dict:
    """끝점을 포함한 사각형을 사본에 적용한다. 드래그 방향은 어느 쪽이든 가능하다."""
    source = doc.get('source') if isinstance(doc, dict) else None
    if not isinstance(source, dict):
        raise ValueError('원본 이미지 정보가 없습니다.')
    width, height = source.get('width'), source.get('height')
    if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0
            or not isinstance(doc.get('labels'), list)):
        raise ValueError('원본 이미지 크기와 라벨 목록을 확인해 주세요.')
    for value, limit in ((x1, width), (x2, width), (y1, height), (y2, height)):
        if type(value) not in (int, float) or not 0 <= value <= limit:
            raise ValueError('선택 영역 좌표가 원본 이미지 범위를 벗어납니다.')
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    if left == right or top == bottom:
        raise ValueError('선택 영역에 가로·세로 길이가 있어야 합니다.')
    result = copy.deepcopy(doc)
    selected = []
    for i, label in enumerate(result['labels']):
        if not isinstance(label, dict):
            raise ValueError(f'{i + 1}번째 라벨 좌표를 확인해 주세요.')
        x, y = label.get('x'), label.get('y')
        if (type(x) not in (int, float) or type(y) not in (int, float)
                or not 0 <= x <= width or not 0 <= y <= height):
            raise ValueError(f'{i + 1}번째 라벨 좌표를 확인해 주세요.')
        if left <= x <= right and top <= y <= bottom:
            selected.append(label)
    result['labels'] = selected
    return result
