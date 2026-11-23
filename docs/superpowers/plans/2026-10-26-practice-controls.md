# 구간 반복·빠르기 Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans. 사용자 무인 실행/질문 금지가 설계 재승인·실행방법 질문보다 우선한다.

**Goal:** 현재 음높이 듣기에 음 단위 반복·0.5~1.5배 빠르기.
**Architecture:** audio_plan 원래 라벨 대응 유지, 시간 길이 목록만 별도 변환. 기존 WinMM·재생 token과 Tk UI를 재사용.
**Tech Stack:** Python/Tk/ctypes, 새 의존성0.
**Spec:** docs/PRACTICE_CONTROLS.md

## Global Constraints
- 판정/labels_io/골든/DECISIONS/규약 변경0. 기본 PNG·JSON 바이트0.
- 전체/렌더/GUI 실행은 HEAVY.lock·가용2.5GiB/중1GiB 가드·골든1/OpenCV1. 전부F:.
- 기능은 draft PR만, 병합0. C공유/stash/기존빌드 보존.

## Review Focus
- 화음 일부를 경계로 골라도 전체 화음과 원래 label index 보존.
- check제외 경계/역순/부분경계/NaN 배율은 거부, 임의 경계 이동0.
- 반복의 마지막 음/중지/장치 실패에서 note-off/reset/close 보장.
- 쪽/편집·중지 후 늦은 반복 이벤트는 강조를 바꾸지 않음.
- 기본1.0·반복OFF·경계없음의 기존 호출·시간·문서/출력 불변.

### Task 1: 반복 재생 통합
**Files:** modules/label_audio.py, gui.py, tests/test_practice_audio.py, tests/test_gui_practice_controls.py, tests/test_gui_piano_widget.py
**Interfaces:**
- Consumes: audio_plan(doc,skip_check), play_piano(groups,cancel,duration=.28,on_group=None), PlaybackCursor token.
- Produces: practice_plan(plan, *,speed=1.0,start=None,end=None,durations=None) → (선택계획,길이목록); play_piano(..., *,durations=None,repeat=False).
- [x] Step1 데이터·취소·기존기본값 검사 작성, 기능없음 assert RED 확인.
- [x] Step2 선택·시간 축/WinMM 반복 최소 구현, 순수 관련검사 GREEN.
- [x] Step3 GUI 경계·스냅샷·중지/문서교체 검사 RED→구현→GREEN. 기존 기본 호출 유지.
- [x] Step4 잠금 아래 합성 Tk 캡처·기본3쪽 PNG/JSON6파일0·전체 실패0/건너뜀0. 예상 결과 골든711/PDF17 유지.
- [ ] Step5 독립 읽기전용 검토, 중요한 지적 RED→GREEN 수정. WORKLOG 결과와 함께 [codex] 커밋·push·draft PR, 병합0.

## 실행 기록
Pre-flight: 시간목록은 새 dict 필드 없이 별도 인자, 기존 계획indices를 다시 매기지 않음. 사용자 질문 생략·보수적 선택은 WORKLOG 판단 필요에 기록한다.
