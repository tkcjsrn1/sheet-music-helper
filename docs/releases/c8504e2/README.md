# 지인 베타 후보 — 2026-09-30

빌드 기준은 PR #115가 병합된 main `c8504e29ef4c6e5ef053e814d104b9d8d1647f8a`이며 `dirty=false`다. 최소 라벨 글꼴 16px이 포함됐다. exe와 ZIP은 저장소에 커밋하지 않았다.

| 항목 | 결과 |
|---|---|
| exe | `dist/c8504e29ef4c-20260930-135227-042501/악보헬퍼.exe` · 106,281,799바이트 · SHA-256 `CDB56C0C537668C1224524892D0A661E6D69122CD7CDDC1AF10E2F72F0A367B2` |
| ZIP | `dist/악보헬퍼-c8504e29ef4c-20260930-135227-042501.zip` · 111,764,658바이트 · SHA-256 `B3F437947FD0E5E022D4F920C5897F707DD53EDBE732F143ECAB63FD1B73D87C` |
| 빌드 | 공식 `build.py` 종료 0, 전체 테스트 17/17 통과·건너뜀 0·실패 0, 골든 711개 불변, PDF 라이브러리 제외. [빌드 정보](build-info.json) |
| Defender | exe·ZIP 각각 `MpCmdRun.exe -Scan -ScanType 3 -File` 종료 0, `found no threats`. 엔진 `1.1.26080.3`, 정의 `1.459.462.0`, 서비스 `4.18.26080.4`. |

ZIP은 exe, `build-info.json`, `먼저 읽어주세요.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.txt` 다섯 파일이다. 새 폴더에 풀어 `settings.json`과 `output`이 없는 상태에서 실행했고, exe 옆 `output`에 PNG와 라벨 JSON이 생겼다.

같은 입력 PNG·설정으로 소스와 exe를 각각 실행했다. RE:Aoharu 1쪽 [결과](aoharu_p1.png)는 라벨 226개(확실 225·주의 1·확인 필요 0), 쇼팽 D♭ 1쪽 [결과](chopin_Db_p1.png)는 255개(확실 208·주의 35·확인 필요 12)다. 두 결과 모두 디코딩한 RGB 픽셀과 라벨 JSON 전체가 소스·exe 사이에서 같고, exe JSON을 소스 CLI로 재렌더링한 PNG도 픽셀 일치했다. 입력·결과 해시는 [검증 기록](verification.json)에 있다. D♭ 300dpi 결과는 직전 베타 `fa2b915`와도 RGB 픽셀 전체가 같다.

작은 보표 사진 입력의 배치 한계는 [16px 후보 측정](../../review/font_sp/CLAMP_CANDIDATES.md)에 기록했다. 축소한 **합성** 쇼팽 D♭ 사진에서는 새 하한 적용 후 라벨 겹침 2쌍이 생겼고, 그중 한 쌍은 실제 글자 획 4픽셀이 교차했다. 이 빌드는 해당 한계를 알고 있는 베타 후보이며 실제 사진에서의 가독성은 아직 검증하지 않았다.

Python이 없는 별도 PC 실행과 실제 다운로드 후 SmartScreen 화면은 미확인이다. 최종 배포는 사용자 확인 뒤 결정한다.
