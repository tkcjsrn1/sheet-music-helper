"""결과 이미지의 빈 종이 여백에 확신도 범례를 그린다."""

from dataclasses import dataclass
from statistics import median

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


LEGEND = "진한 글씨 = 확실 · 연한 글씨 = 주의\n주황 점선 = 확인 필요"


ALTO_WARNING = "알토 음자리표 보표는 지원하지 않습니다 — 그 보표의 계이름은 틀립니다"
UNKNOWN_CLEF_WARNING = "음자리표를 찾지 못한 줄이 있습니다 — 그 줄의 계이름은 틀릴 수 있습니다"


def alto_warning(labels) -> str:
    """저장 라벨의 알토 신호만 읽는다. 음고·확신도는 바꾸지 않는다."""
    return ALTO_WARNING if any(isinstance(row.get("flags"), list)
                              and "clef_alto" in row["flags"] for row in labels) else ""


def clef_warnings(labels) -> list[str]:
    """저장된 신호의 안내만 모은다. 인식 결과는 바꾸지 않는다."""
    labels = list(labels)
    warnings = [alto_warning(labels)]
    if any(isinstance(row.get("flags"), list) and "clef_unknown" in row["flags"]
           for row in labels):
        warnings.append(UNKNOWN_CLEF_WARNING)
    return [warning for warning in warnings if warning]


def keysig_header_text(symbol: str, count: int, user_key: str = "", labels=()) -> str:
    """읽은 조표와 사용자가 지정한 이동도 조성을 혼동하지 않게 적는다."""
    marks = {"♯": "#", "♭": "b"}
    read = f"{marks[symbol]} {count}개" if symbol in marks and count > 0 else "없음"
    user_key = user_key.replace("♯", "#").replace("♭", "b")
    text = f"조표: {read}{'으로' if read == '없음' else '로'} 읽음"
    text += (f" · 조성 {user_key}(사용자 지정)" if user_key else "")
    return "\n".join([text, *clef_warnings(labels)])


@dataclass
class _Paper:
    gray: np.ndarray
    level: int
    bounds: tuple
    white: int
    required_white: int
    largest: int
    rival: int
    component: int
    labels: np.ndarray | None


def _find_paper(image, retain_labels=False):
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    required_white = gray.size - int((gray.size - 1) * .95)
    white = np.count_nonzero(gray == 255)
    level = 255 if white >= required_white else int(np.percentile(gray, 95))
    if level < 120:
        return None
    light = (gray >= level - 20).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(light)
    if count < 2:
        return None
    index = 1 + int(stats[1:, 4].argmax())
    row = stats[index]
    rival = max(stats[1:index, 4].max(initial=0), stats[index+1:, 4].max(initial=0))
    return _Paper(gray, level, tuple(row[:4]), white, required_white, int(row[4]),
                  int(rival), index, labels if retain_labels else None)


def _paper_after_header(image, paper, rect):
    left, top, right, bottom = rect
    area = (right - left) * (bottom - top)
    gray = paper.gray
    # 밝은 한 픽셀 둘레가 남아 있으면 배지는 그 바깥 성분을 끊지 않는다.
    # 둘레와 95분위수, 최대 성분 순위가 유지되는 경우만 기존 경계를 재사용한다.
    reusable = (paper.level == 255 and paper.white - area >= paper.required_white
                and paper.largest - area > max(paper.rival, area)
                and 0 < left < right < image.width and 0 < top < bottom < image.height
                and paper.labels[top-1, left-1] == paper.component
                and np.all(gray[top-1:bottom+1, left-1:right+1] >= 235))
    paper.labels = None
    if not reusable:
        return _find_paper(image)
    with image.crop(rect) as badge:
        gray[top:bottom, left:right] = cv2.cvtColor(np.asarray(badge), cv2.COLOR_RGB2GRAY)
    return paper


def add_keysig_header(path: str, symbol: str, count: int, font_path: str,
                      spacings, setting_size: int = 18, user_key: str = "",
                      first_staff_top: float | None = None, labels=()) -> bool:
    """상단의 밝은 빈 종이 영역에 읽은 조표를 표시한다."""
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    with image:
        paper = _find_paper(image)
        if not paper or not _draw_header(image, paper, symbol, count, font_path, spacings,
                                         setting_size, user_key, first_staff_top, labels):
            return False
        image.save(path)
        return True


def _draw_header(image, surface, symbol, count, font_path, spacings, setting_size=18,
                 user_key="", first_staff_top=None, labels=()):
    gray, paper = surface.gray, surface.level
    x, y, width, height = surface.bounds
    label = keysig_header_text(symbol, count, user_key, labels)
    size = legend_font_size(spacings, setting_size)
    font = ImageFont.truetype(font_path, size if "\n" in label else max(28, round(size * 1.6)))
    draw = ImageDraw.Draw(image)
    # 두 경고가 함께 있으면 각 경고를 한 줄로 두어 상단 여백에 넣는다.
    if label.count("\n") == 1:
        label = label.replace(" — ", "\n— ")
    box = (draw.multiline_textbbox if "\n" in label else draw.textbbox)((0, 0), label, font=font)
    badge_width, badge_height = box[2] - box[0] + 16, box[3] - box[1] + 12
    pad = 18
    top_limit = min(y + height // 4, int(first_staff_top or image.height))
    for top in range(y + pad, top_limit - badge_height - pad, 10):
        for left in (x + width - badge_width - pad, x + pad):
            if left < x + pad or left + badge_width > x + width - pad:
                continue
            region = gray[top - 8:top + badge_height + 8,
                          left - 8:left + badge_width + 8]
            if region.size == 0 or np.any(region < paper - 30):
                continue
            draw.rounded_rectangle((left, top, left + badge_width, top + badge_height),
                                   radius=4, fill="white", outline="#777777")
            draw_label = draw.multiline_text if "\n" in label else draw.text
            draw_label((left + 8 - box[0], top + 6 - box[1]), label,
                      font=font, fill="#222222")
            return left, top, left + badge_width + 1, top + badge_height + 1
    return None


def legend_font_size(spacings, setting_size: int) -> int:
    """라벨과 같은 보표 간격 비율을 쓰고 최소 16px을 보장한다."""
    values = [spacing for spacing in spacings if spacing > 0]
    return (max(16, round(median(values) * 1.1 * setting_size / 18))
            if values else max(16, setting_size))


def add_legend(path: str, font_path: str, font_size: int = 16,
               photo_input: bool = False) -> bool:
    """악보 잉크와 겹치지 않는 여백이 있을 때만 그린다."""
    if photo_input:
        return False
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    with image:
        paper = _find_paper(image)
        if not paper or not _draw_legend(image, paper, font_path, font_size):
            return False
        image.save(path)
        return True


def _draw_legend(image, surface, font_path, font_size=16):
    gray, paper = surface.gray, surface.level
    x, y, width, height = surface.bounds
    font = ImageFont.truetype(font_path, font_size)
    draw = ImageDraw.Draw(image)
    box = draw.multiline_textbbox((0, 0), LEGEND, font=font, spacing=2)
    text_width, text_height = box[2] - box[0], box[3] - box[1]
    legend_width, legend_height = text_width + 12, text_height + 12
    pad = 18
    if width < legend_width + 2 * pad or height < legend_height + 2 * pad:
        return False

    corners = (
        (x + width - legend_width - pad, y + height - legend_height - pad),
        (x + pad, y + height - legend_height - pad),
        (x + width - legend_width - pad, y + pad),
        (x + pad, y + pad),
    )
    # 가장 빈 구석을 택하고, 안전 여백까지 잉크가 있으면 그리지 않는다.
    candidates = []
    for left, top in corners:
        region = gray[top - 10:top + legend_height + 10,
                      left - 10:left + legend_width + 10]
        dark = int(np.count_nonzero(region < paper - 30))
        candidates.append((dark, left, top))
    dark, left, top = min(candidates)
    if dark:
        return False
    draw.rounded_rectangle((left, top, left + legend_width, top + legend_height),
                           radius=4, fill="white", outline="#aaaaaa")
    draw.multiline_text((left + 6 - box[0], top + 6 - box[1]), LEGEND,
                        font=font, fill="#555555", spacing=2)
    return True


def annotation_writer(path, *, header=None, legend=None):
    '''라벨이 그려진 메모리 이미지에 배지를 더해 한 번만 기록한다.'''
    from modules.renderer import _save_rendered_image

    status = {"header": False, "legend": False}
    if header is None and legend is None:
        return None, status

    def write(image):
        surface = _find_paper(image, retain_labels=header is not None and legend is not None)
        if surface is not None:
            if header is not None:
                box = _draw_header(image, surface, **header)
                status["header"] = box is not None
                if legend is not None and box is not None:
                    surface = _paper_after_header(image, surface, box)
                else:
                    surface.labels = None
            if legend is not None and surface is not None:
                status["legend"] = _draw_legend(image, surface, **legend)
        if any(status.values()):
            image.save(path)
        else:
            _save_rendered_image(image, path)

    return write, status
