# 라이브러리·폰트 확인 목록 (공개 전 초안)

기준 제품 d69a025, 조사 환경2026-10-26. [로컬 metadata·archive 증거](LICENSE_EVIDENCE.json)를 보존했다. 설치 환경 목록은 실제 동봉 목록과 같지 않다. 기존 [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.txt)를 자동으로 완전하다고 판정하지 않는다. 아래는 공개/라이선스 선택 승인이 아니다.

| 구분 | 실제 조사 버전 | 라이선스/확인 근거 | 남은 일 |
|---|---|---|---|
| 프로젝트 자체 | root LICENSE | MIT, 2026 정혁 | 제3자 악보/폰트에 일괄 적용하지 않음 |
| CPython·Tk | Python3.14.0 / Tk8.6 고지 | Python/Tcl·Tk 원문 기존 고지 | 최종 빌드 runtime 버전과 대조 |
| OpenCV Python | 5.0.0.93 | metadata Apache2.0, wrapper·내장 구성요소 고지 별도 | wheel 내 제3자 부분도 보존 |
| NumPy | 2.5.1 | BSD3·0BSD·MIT·Zlib·CC0 복수 metadata | OpenBLAS 등 binary 고지 포함 대조 |
| SciPy | 1.18.0 | BSD3 및 binary에 포함된 별도 라이선스 | 설치 metadata 긴 전문을 단일 SPDX로 축약하지 않음 |
| Pillow | 12.3.0 | metadata MIT-CMU, 배포 고지 원문 | imagecodec 포함 대조 |
| CustomTkinter | 6.0.0 | 실제 LICENSE/기존 고지 MIT | metadata CC0 표기와 불일치, LICENSE 기준 재확인 |
| darkdetect / packaging | 0.8.0 / 26.2 | BSD3 / Apache2 또는 BSD2 | binary 고지 최종 대조 |
| PyInstaller (빌드) | 6.21.0 | GPL2+bootloader exception | 예외가 의존성의 고지 의무를 없애지 않음 |
| altgraph·pefile·pywin32-ctypes·hooks-contrib (빌드) | 증거 JSON | 각 배포판 LICENSE | 최종 사용/배포분 구분 |
| Matplotlib와 부속/폰트 | 3.11.2 | **실제 exe에 폰트40개 동봉** | 기존 고지에서 matplotlib/DejaVu/STIX 이름 미발견, 공개 전 정리 |
| PyMuPDF (소스 PDF 선택) | 1.28.0 | AGPL3 또는 상업 라이선스 | 현 exe spec fitz/pymupdf 제외, 공개 소스 PDF 경로 선택 별도 검토 |
| Verovio·music21·CairoSVG (개발 자료) | 6.3.0 / 10.5.0 / 2.9.1 | LGPL3 / BSD3(코퍼스 별도) / LGPL3+ | 제품 기본 의존성으로 간주하지 않음, 코퍼스 인코딩 권리 별도 |

PyInstaller 공식 [라이선스 설명](https://pyinstaller.org/en/stable/license.html)은 부트로더 예외를 설명한다. [PyMuPDF 공식 라이선스](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)는 AGPL/상업 선택을 안내한다. [CustomTkinter LICENSE](https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE)와 설치본 원문을 우선 대조한다. [Verovio 공식 설명](https://book.verovio.org/introduction/licensing.html)은 LGPL3 조건과 고지를 안내한다. 원문 최신 문서 버전이 설치 버전과 같다는 뜻은 아니다.

## 폰트: 발견한 공개 전 보류 사항

실제 d69a025 exe를 **실행하지 않고** CArchiveReader 목차·font byte hash를 대조했다. 총43개가 로컬 설치본과 SHA256까지 같았다.

- CustomTkinter: Roboto-Regular/Medium2개 + shapes1개. Roboto는 Version2.137(2017), 내부 name13에 Apache2.0, name14에 Apache URL이 있다. 최신 Roboto의 라이선스로 대신 판정하지 않는다.
- shapes: 라이선스 name13/14는 빈칸. 상위 CustomTkinter MIT 적용 범위·제작 출처 확인이 필요하다.
- Matplotlib: DejaVu/STIX/Computer Modern/LastResort 계열40개. 부속 폰트의 각각 LICENSE/고지를 점검해야 한다. 단순히 Matplotlib 라이선스 한 줄로 덮지 않는다.
- 기존 THIRD_PARTY_NOTICES에서 Roboto·shapes·matplotlib·DejaVu·STIX 문자열이 없었다. **이름 검색은 법적 누락 확정은 아니지만, 해당 원문과의 매칭이 아직 안 됐으므로 공개 전 보류**한다. beta/고지 파일을 이번 문서 PR에서 바꾸지는 않는다.
- 악보 라벨의 맑은 고딕 등 Windows 설치 글꼴은 시스템에서 읽는다. 이번 exe 글꼴 목차에는 Malgun이 없었다. [Microsoft 글꼴 FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq)에 따라 시스템 사용과 폰트 파일 재배포를 구분하고, Windows 폰트를 임의로 동봉하지 않는다.
- 피아노는 Windows WinMM의 설치된 MIDI 신시사이저를 사용한다. 별도 SoundFont 파일을 동봉하지 않는다. 플랫폼 음원/장치 사용 조건을 자체 샘플 라이선스로 오해하지 않는다.

사용자 판단 필요: 동봉 폰트와 Matplotlib 부속 고지/출처를 보완하고 공개 라이선스 선택 확정 — 택한 쪽: 공개 보류, 새 패키징 변경 없이 조사 결과만 보존.

[실제 PYZ 목차 대응21개 배포판](BUNDLED_MODULES.md)도 함께 목록으로 남겼다. 고지 검토는 직접 의존성 표에 한정하지 않는다.

## 2026-10-27 원문 매칭 후속

[동봉 항목별 원문 대응과 미확인](notices-20261026/MATCHED_LICENSES.md)을 추가했다. 후보21/21 설치 배포판 LICENSE·폰트42/43의 원문을 확인하고 기존 고지를 보존한 THIRD_PARTY_NOTICES_DRAFT 전문을 만들었다. shapes1개 개별 범위·실제 버전17개·MPL 소스 제공 방식·native 전체 완결성은 미확인이다. 10-26 수집·10-27 단위 재검증이며 현재 exe에 고지를 다시 넣지는 않았다. 위의 미완료 조사 기록은 이 후속으로 보완한다. 공개 승인은 별개다.
