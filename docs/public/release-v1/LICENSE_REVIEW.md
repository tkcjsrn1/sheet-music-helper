# v1.0.0 동봉 고지 검토

프로젝트 소스는 MIT로 공개한다. 동봉 구성요소에는 각자의 라이선스 및 고지를 적용한다.

| 항목 | 확인한 근거 | 공개 전 처리 |
|---|---|---|
| CustomTkinter 도형 글꼴 | 후보 EXE에서 추출한 글꼴은 설치된 6.0.0 파일과 SHA256 fad67e2b060c318b6c8646d087fbd3add938b6676243f14b0c52623179641274로 일치한다. 패키지의 MIT 원문은 확보했다. | PDFium 시험 EXE에서도 같은 해시였다. 같은 바이트의 글꼴이 CustomTkinter 공식 소스에 들어 있고 동일 커밋 루트에 MIT 원문이 있다. 글꼴 내부의 저작권·라이선스 필드는 공백이다. 최종 후보의 바이트와 고지를 대조한다. [공식 글꼴 파일](https://github.com/TomSchimansky/CustomTkinter/blob/33a77cb1dbe40a7d869d7d13567090e21e8846af/customtkinter/assets/fonts/CustomTkinter_shapes_font.otf) · [같은 커밋의 MIT 원문](https://github.com/TomSchimansky/CustomTkinter/blob/33a77cb1dbe40a7d869d7d13567090e21e8846af/LICENSE) |
| 후보 EXE의 실제 버전 | build-info는 Python 3.14.0, OpenCV 5.0.0.93, NumPy 2.5.1, SciPy 1.18.0, Pillow 12.3.0, CustomTkinter 6.0.0, PyInstaller 6.21.0을 기록한다. EXE의 NumPy와 CustomTkinter METADATA도 각각 일치한다. | 나머지 설치본 대응 항목은 최종 산출물에서 실제 버전과 고지를 다시 맞춘다. |
| Certifi MPL 2.0 | certifi Python 코드와 cacert.pem이 EXE에 있다. cacert.pem은 설치 2026.7.22의 파일과 SHA256 9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f로 일치한다. | PyPI 소스 배포본 SHA256을 확인하고 PDFium 시험 EXE의 CA 파일과 바이트 일치를 재확인했다. 동봉 고지에 소스 주소를 실었다. 최종 EXE 버전이 달라지면 해당 버전으로 다시 확인한다. [Certifi 2026.7.22 소스](https://pypi.org/project/certifi/2026.7.22/#files) [MPL 2.0 §3.2](https://www.mozilla.org/en-US/MPL/2.0/) |
| 네이티브 라이브러리 | EXE에 DLL·PYD 199개가 있다. Python/Tcl·Tk, VC Runtime/UCRT, OpenSSL, zlib, OpenCV 및 NumPy/SciPy 라이브러리가 포함된다. | 최종 배포본의 파일별 버전과 재배포 조건·고지 대응을 확인한다. |
| pypdfium2 / PDFium | pypdfium2 5.13.0 바인딩은 Apache-2.0 또는 BSD-3-Clause, PDFium 153.0.7999.0 본체는 BSD 계열 라이선스다. Windows x64 휠의 라이선스 파일 19개에 PDFium 빌드 의존성 고지도 포함돼 있다. [pypdfium2 라이선스](https://github.com/pypdfium2-team/pypdfium2#licensing) · [5.13.0 배포본](https://pypi.org/project/pypdfium2/5.13.0/#files) · [PDFium 원문](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE) | 원문 19개를 고지에 동봉한다. 최종 EXE의 PDFium 버전·아키텍처를 확인하고 휠 원문과 대조한다. |
| 앱 아이콘 | #494에서 코드로 직접 그린 새 시안을 채택했다. | 최종 EXE가 그 아이콘과 일치하는지 확인한다. |

동봉 원문은 [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)에 모았다. PDFium 휠 원문의 SHA256은 [검증 목록](../../measurements/pdfium_license_manifest_5.13.0.json)에 있다. 공개 직전에 최종 EXE의 실제 동봉 버전과 ZIP에 넣은 고지를 함께 대조한다.
