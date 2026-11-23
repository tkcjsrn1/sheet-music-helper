# cebae18 배포 전 점검

- 공식 build.py / run_all31/31 실패0·건너뜀0·골든711/PDF17쪽 스냅샷 유지.
- exe/ZIP Defender 탐지0, 종료0.
- Aoharu/D♭/바흐/Verovio Clara1: 소스·exe JSON 전체/PNG 픽셀/JSON 재렌더링 일치. 기존 세 입력은 dff19b2와도 결과 무변경.
- settings 없는 새 폴더·Python 없는 PATH·exe 옆 output·ZIP5파일 확인.
- D-3 exe 수정 JSON: 진한 글씨·점선 제거·원래 확신도 보존. 소스 GUI 클릭·추가·삭제·여러 번 되돌리기와 화면6장 보존.
- Actions37148263284: 같은 커밋1회 성공, 빌드31/31 및 두 selftest/현재 기준 JSON 일치. 재계산한 기준 내용 변화0.
- 미확인: exe 직접 GUI, 실제 다운로드 SmartScreen, 실제 사용자 PC·스피커 청취.

경로·해시·실행 범위·한계는 [README](README.md), 수치는 [verification.json](verification.json). exe는 커밋하지 않는다.

## 2026-10-04 사용자 확인 및 GUI 재확인

사용자 수동 확인: 논리 화면 약1456×819에서 변환·조표 머리말·범례·라벨 수정/삭제/되돌리기·영역 선택·듣기 시작/중지·문제 신고 ZIP 동작. 여러 이미지 선택·사진 모드·라벨 추가는 미확인.

Codex의 exe 직접 클릭 재시도는 Computer Use 초기화 오류로 중단했다. exe를 실행하거나 위 세 항목을 클릭하지 않았다.
```
failed to write kernel assets: 지정된 경로를 찾을 수 없습니다. (os error 3)
```

아래는 **소스 GUI**의 1280×700 검사이며 cebae18 exe 캡처가 아니다. 원본 악보를 제외한 빈 미리보기/자체 생성 라벨만 포함한다.
- [수정 전](gui_before_1280x700.png): 변환 버튼 y863으로 화면 아래.
- [수정 후](gui_after_1280x700.png): 파일 선택 y94·변환 y182, 스크롤 후에도 고정.
- [되돌린 라벨 선택](undo_restored_label.png): 삭제 취소 후 복원된12행 선택. 수정 취소17행도 통과.
- 목록→입력칸 빠른 전환100회: 선택 이동 재현 안 됨(소스 Tk 이벤트 검사).
- 수정 후 run_all34/34 실패0·건너뜀0, 골든711·PDF17쪽 스냅샷 유지. 기본 GUI 변환 Aoharu1~3/D♭1쪽 PNG·JSON4/4 바이트 일치.

현재 exe GUI의 미확인3항목은 그대로 남긴다. 새 버튼 배치는 병합 후 새 베타부터 포함한다.
