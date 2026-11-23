# 지인 베타 후보 — 2026-09-30

빌드 기준은 main `fa2b9156426285d990566b763091ed1747891970`이며 `dirty=false`다. PR #107 화음 구제와 #108 보표 간격 비례 글꼴, #109 정정된 동봉 안내문이 포함됐다. 바이너리는 저장소에 커밋하지 않았다.

| 항목 | 결과 |
|---|---|
| exe | `dist/fa2b91564262-20260930-021858-561166/악보헬퍼.exe` · 106,280,533바이트 · SHA-256 `0073EBE8A0A691152BDAE2BFF2D4860FA4FE335DB30121963D07B432F8ECCF51` |
| ZIP | `dist/악보헬퍼-fa2b91564262-20260930-021858-561166.zip` · 111,761,466바이트 · SHA-256 `FA1965B656EA37A6D439328B93E43CB95991B392025CA62DA0B63E92FC50E60F` |
| 빌드 | `venv/Scripts/python.exe build.py` 종료 0, 전체 테스트 실패 0·건너뜀 0, 골든 711개 무변경, PDF 라이브러리 제외. [빌드 정보](build-info.json) |
| Defender | exe·ZIP 각각 `MpCmdRun.exe -Scan -ScanType 3 -File` 종료 0, `found no threats`. 엔진 `1.1.26080.3`, 정의 `1.459.462.0`, 서비스 `4.18.26080.4`. |

ZIP에는 exe, `build-info.json`, `먼저 읽어주세요.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.txt` 다섯 파일만 있다. 새 폴더에 압축을 풀어 `settings.json`과 `output`이 없는 상태에서 실행했고, exe 옆 `output`에 PNG와 라벨 JSON이 생겼다.

같은 입력 PNG·설정으로 소스 GUI와 exe를 각각 실행했다. RE:Aoharu 1쪽 [결과](aoharu_p1.png)는 라벨 226개(확실 225·주의 1·확인 필요 0), 쇼팽 D♭ 1쪽 [결과](chopin_Db_p1.png)는 255개(확실 208·주의 35·확인 필요 12)다. 두 쪽 모두 디코딩한 RGB 픽셀과 라벨 JSON 전체가 소스·exe 사이에서 일치했고, exe JSON 재렌더링도 픽셀이 같았다. 입력·결과 해시는 [검증 기록](verification.json)에 있다. 쇼팽 입력은 PDF 1쪽을 300dpi로 한 번 렌더링한 PNG를 양쪽에 사용했다.

사용자 요청 확인: D♭ 1쪽 보표 간격은 모두 19.1~19.4px이고 기본 설정에서 글꼴은 모두 21px이다. 겹침에 따른 자동 글꼴 축소는 없다. B♭m 4쪽 52~57마디의 점선 `시b` 여섯 개는 JSON에서 모두 `weak_side_ink`, `vertical_blocked`, `off_staff`를 기록했다. `weak_side_ink`가 「확인 필요」 등급을 만든다. 두 항목의 제품 코드는 수정하지 않았다.

Python이 없는 별도 PC 실행과 실제 다운로드 뒤 SmartScreen 화면은 이 PC에서 검증하지 않았다. 최종 배포 여부는 사용자 확인이 남아 있다.
