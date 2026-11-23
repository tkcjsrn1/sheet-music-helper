# exe 모듈 목차와 배포판 대응 (라이선스 조사 보조)

실제 d69a025의 PYZ 목차를 **실행 없이** 읽어 설치 배포판 metadata에 연결했다. 코드가 목차에 있다는 뜻이며 실제 이 입력에서 호출됐다는 뜻은 아니다. 버전/라이선스 값은 조사 설치환경의 값이다. 폰트43개와 달리 모든 Python 모듈을 설치본과 바이트 대조한 것은 아니므로 최종 릴리스의 버전 고지는 build manifest와 다시 맞춘다.

| 대응 배포판 | 설치 버전 | metadata 표기/원문 확인 |
|---|---|---|
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| contourpy | 1.3.3 | BSD 3-Clause License /  |
| customtkinter | 6.0.0 | Creative Commons Zero v1.0 Universal |
| cycler | 0.12.1 | 배포판 LICENSE 원문 확인(증거 JSON 경로) |
| darkdetect | 0.8.0 | BSD-3-Clause |
| defusedxml | 0.7.1 | PSFL |
| fonttools | 4.63.0 | MIT |
| kiwisolver | 1.5.0 | 배포판 LICENSE 원문 확인(증거 JSON 경로) |
| matplotlib | 3.11.2 | 배포판 LICENSE 원문 확인(증거 JSON 경로) |
| more-itertools | 11.1.0 | MIT |
| numpy | 2.5.1 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| pillow | 12.3.0 | MIT-CMU |
| pycparser | 3.0 | BSD-3-Clause |
| pyparsing | 3.3.2 | MIT |
| python-dateutil | 2.9.0.post0 | Dual License |
| scipy | 1.18.0 | 배포판 LICENSE 원문 확인(증거 JSON 경로) |
| setuptools | 83.0.0 | MIT |
| six | 1.17.0 | MIT |

CustomTkinter의 CC0 metadata와 MIT LICENSE 불일치는 상위 조사표에 보류로 남겼다. Certifi의 MPL2.0처럼 단순히 모든 내장 패키지가 MIT/BSD라고 부를 수 없는 항목도 있다. Python/Tk·OpenCV 같은 native 코드·각 DLL/코덱·root certificate/데이터의 고지까지 이 대응표가 완성한 것은 아니다.

추출/대응 코드와 원문 위치는 [증거](LICENSE_EVIDENCE.json)의 archive_pyz_distribution_candidates·unmapped_top_modules에 있다. music21/Verovio/CairoSVG/PyMuPDF를 이 PYZ 대응 결과에서 발견하지 않았으며, 설치됐다는 사실만으로 제품에 넣었다고 쓰지 않았다. 기존 고지와 빠짐없이 매칭할 때까지 공개 보류다.
