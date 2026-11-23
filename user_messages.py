# -*- coding: utf-8 -*-
"""CLI와 GUI가 함께 쓰는 사용자 안내 문구."""


def staff_count_confirmation(count: int) -> str:
    """검출 결과를 단정하지 않고 원본과 대조하도록 안내한다."""
    return (
        f"악보 줄 {count}개를 찾았습니다. "
        "원본 악보의 줄 수와 맞는지 확인해 주세요."
    )


def conversion_failure_message(error: Exception, path: str = "") -> str | None:
    """확인할 수 있는 실패만 설명하고, 예상 밖 오류는 원래 진단을 남긴다."""
    from modules.preprocess import PhotoRejectedError, StaffNotFoundError, SheetMusicImageError
    if isinstance(error, PhotoRejectedError):
        return "사진을 안전하게 보정하지 못했습니다.\n해결: 스캐너·복사기·거치대로 정면에서 다시 찍어 주세요"
    if isinstance(error, StaffNotFoundError):
        return "악보 줄을 찾지 못했습니다.\n해결: 작거나 흐린 이미지는 원본 크기의 선명한 악보로 바꿔 주세요. 사진이라면 사진 모드로 다시 시도해 보세요"
    if isinstance(error, SheetMusicImageError):
        return "악보 파일을 읽지 못했습니다.\n해결: 파일이 열리는지 확인하고 PNG/JPG 이미지로 다시 저장해 선택해 주세요"
    from PIL import Image
    if isinstance(error, Image.DecompressionBombError):
        return "이미지 크기가 너무 커 안전하게 열지 못했습니다.\n해결: 이미지 편집기에서 크기를 줄이거나 악보를 쪽별 이미지로 나누어 다시 선택해 주세요"
    import cv2
    if isinstance(error, cv2.error) and getattr(error, "func", None) in ("cv::resize", "resize") and "!dsize.empty()" in str(error):
        return "이미지 크기를 처리하지 못했습니다.\n해결: 작게 잘린 이미지 대신 원본 크기의 선명한 악보 이미지를 선택해 주세요"
    if path.lower().endswith(".pdf"):
        try:
            import fitz
        except ImportError:
            return None
        if isinstance(error, (fitz.FileDataError, fitz.EmptyFileError)):
            return "PDF가 비어 있거나 손상되어 열지 못했습니다.\n해결: 원본 PDF를 다시 받거나 열리는 프로그램에서 PNG/JPG 이미지로 저장해 선택해 주세요"
        if isinstance(error, ValueError):
            try:
                with fitz.open(path) as pdf:
                    if pdf.needs_pass:
                        return "비밀번호가 걸린 PDF를 열지 못했습니다.\n해결: 비밀번호를 해제한 사본이나 PNG/JPG 이미지로 다시 선택해 주세요"
            except (OSError, RuntimeError):
                pass
    return None


# labels_io의 등급 판정용 신호만 설명한다. 기록 전용 신호로 새 주의를 만들지 않는다.
REVIEW_REASON_MESSAGES = {
    "double_acc": "겹임시표(bb/##)는 아직 정확히 읽지 못해요.",
    "clef_alto": "알토 음자리표는 지원하지 않아 이 줄의 계이름이 틀려요.",
    "clef_unknown": "음자리표를 찾지 못해 이 줄의 계이름이 틀릴 수 있어요.",
    "clef_changed": "줄 중간에 음자리표가 바뀌어 이후 계이름이 틀릴 수 있어요.",
    "accidental_unstable": "이미지를 조금 옮기면 임시표 판정이 달라져요.",
    "flat_propagated": "내림표가 뒤 음에 잘못 이어졌을 수 있어요.",
    "accidental_candidate": "임시표 기호와 음표를 구분하기 어려워 남겨 둔 음이에요.",
    "grace_size": "꾸밈음처럼 작은 음표는 아직 지원하지 않아요.",
    "beam_gap": "빔 사이 빈틈처럼 보여 음표가 아닐 수 있어요.",
    "beam_sloped": "빔 위나 빔 사이에 있어 음표가 아닐 수 있어요.",
    "narrow_hole": "글자 고리처럼 보여 음표가 아닐 수 있어요.",
    "text_row": "악보 밖 글자 줄에 있어 음표가 아닐 수 있어요.",
    "side_pair": "같은 음이 바로 옆에 하나 더 있어 음표가 아닐 수 있어요.",
    "chord_column": "화음 왼쪽에 엇갈려 쌓인 임시표를 읽은 음이니 원본과 대조해 주세요.",
    "glyph_shape": "임시표 기호를 음표로 읽었을 수 있어요.",
    "clef_glyph": "음자리표 기호를 음표로 읽었을 수 있어요.",
    "weak_side_ink": "음표 머리 양옆의 모양이 약해 다른 기호일 수 있어요.",
    "beam_adjacent": "굵은 획에 붙어 있어 음표가 아닐 수 있어요.",
    "vertical_blocked": "다른 획과 겹쳐 음표 모양을 확인해 주세요.",
    "chord_rescue_added": "붙은 화음에서 추가로 찾은 음이니 원본과 대조해 주세요.",
    "chord_middle_added": "화음 가운데에서 추가로 찾은 음이니 원본과 대조해 주세요.",
    "wide_triple": "세 음이 붙은 화음 덩어리를 나눠 찾은 음이니 원본과 대조해 주세요.",
    "header_reopened": "줄 첫머리 조표·박자표 바로 뒤에서 새로 찾은 음이니 원본과 대조해 주세요.",
    "ledger_short": "덧줄이 짧게 그려진 자리에서 찾은 음이니 원본과 대조해 주세요.",
    "center_split": "음표 머리 위에 이음줄이 붙어 줄·칸 높이가 한 칸 어긋났을 수 있어요.",
}


def label_review_reason(label: dict) -> str:
    """저장된 등급·신호를 읽어 설명만 한다. 확신도나 라벨은 바꾸지 않는다."""
    if label.get('user_created'):
        return '사용자가 추가한 라벨입니다.'
    if label.get('confidence') in ('check', 'caution'):
        flags = label.get('flags', [])
        if not isinstance(flags, list):
            flags = []
        reasons = [text for flag, text in REVIEW_REASON_MESSAGES.items() if flag in flags]
        reason = ' / '.join(reasons) if reasons else '자세한 이유가 기록되지 않아 원본과 대조해 주세요.'
        level = '확인 필요' if label['confidence'] == 'check' else '주의'
        message = f'{level}: {reason}'
    else:
        message = '추가 확인 사유가 기록되지 않았어요.'
    return f'사용자 수정 라벨입니다. 원래 판정: {message}' if label.get('edited') else message
