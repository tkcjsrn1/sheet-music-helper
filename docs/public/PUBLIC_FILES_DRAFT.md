# 공개 저장소 파일 허용 목록 초안

기준은 내부 공개 후보 `116f32d`다. 기존 private 저장소에서 새로 복사할 파일을 아래와 같이 검토한다. 실제 저장소 생성과 복사는 승인 뒤에 한다.

| 범위 | 복사 후보 | 확인 |
|---|---|---|
| 런타임 | `gui.py`, `main.py`, `user_messages.py`, `modules/*.py` | 116f32d의 추적 파일만 복사. 파일 내용과 외부 자료 참조 재검토 |
| 빌드 | `build.py`, `악보헬퍼.spec`, `requirements.txt`, `assets/version_info.txt` | 소스 PDF 경로와 PyMuPDF 공개 방식 결정. exe에는 PyMuPDF 제외 유지 |
| 아이콘 | `assets/make_icon.py`, `assets/icon.ico`, `assets/icon.png` | 생성기 및 이미지 권리 확인 뒤 포함. 보류 시 허용된 대체 아이콘으로 별도 빌드 |
| 텍스트 | `LICENSE`, 최종 `THIRD_PARTY_NOTICES.txt`, 최종 `README.md`, `먼저 읽어주세요.txt` | 동봉 목록과 버전 확인, 초안의 상대 링크를 새 경로에 맞춤 |
| 사용자 문서 | 승인한 `USER_GUIDE.md`, `SMARTSCREEN.md`, `FEEDBACK_FORM.md` | 검증 기록이나 원본 악보가 노출되는 링크 제거 |
| 검사·워크플로 | 별도로 승인한 합성 자료와 단위 검사만 | 기존 selftest workflow와 공식 전체 검사에 private 자료가 필요하다. 공개용 검사 목록을 먼저 정의 |

공개 제외 대상에는 `.git`, WORKLOG, 내부 협업 문서, 기존 이력 그림, `sample_images/`, `test_scores/`, 비공개 fixtures·golden, `docs/releases/`·`docs/review/` 원자료, 신고 ZIP, 캐시와 임시 산출물이 포함된다. 공개용 빌드 검증은 private 전체 검사와 별도로 설계한다. [이관 절차](MIGRATION_DRAFT.md)
