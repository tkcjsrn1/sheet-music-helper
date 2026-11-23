# C-12: exe용 PDF 입력 대체 라이브러리 1차 조사

2026-10-01 · 제품 코드와 배포 빌드는 변경하지 않았다. 이 문서는 `pypdfium2==5.13.0`의 배포 가능성과 렌더 차이만 확인한다. PDF 입력을 exe에 지원한다는 결정은 아니다.

## 라이선스와 고지

- [pypdfium2 공식 저장소](https://github.com/pypdfium2-team/pypdfium2#licensing)는 바인딩을 Apache-2.0 또는 BSD-3-Clause 조건으로 제공한다. 함께 들어가는 PDFium과 그 의존성의 라이선스는 별개이며, 바이너리 배포에는 해당 고지를 함께 실어야 한다고 명시한다. [PDFium 원본 LICENSE](https://github.com/chromium/pdfium/blob/main/LICENSE)도 바이너리 재배포 시 저작권·조건·면책 문구를 문서나 동봉 자료에 재현하도록 요구한다.
- Windows x64 휠 5.13.0에는 라이선스 파일 19개, 총 133.5 KiB가 있다. PDFium 본체와 FreeType·ICU·이미지 코덱 등의 고지다. 라이선스 검토와 동봉 목록 확정은 실제 배포 전에 필요하다.
- 실험용 PyInstaller exe에는 `pdfium.dll`이 들어갔지만 `pypdfium2`의 라이선스 파일은 자동으로 들어가지 않았다. 따라서 제품에 도입한다면 빌드 고지 생성과 ZIP 내용 검사를 따로 추가해야 한다.
- 현재 PyMuPDF는 소스 전용이며 exe에서 계속 제외한다. 이 조사로 현 배포 방침을 바꾸지 않는다.

## Windows 크기

같은 Python 3.14·PyInstaller·NumPy·Pillow를 양쪽에 넣은 최소 실험 exe를 만들었다. 둘 다 onefile이며 PDFium 쪽은 바흐 첫 쪽을 실제로 300dpi 렌더해 `2481 × 3508`을 출력했다.

| 실험 exe | 크기 |
|---|---:|
| NumPy·Pillow 기준 | 28,149,558 B |
| 기준 + pypdfium2 | 31,940,922 B |
| **증가** | **3,791,364 B (3.62 MiB)** |

`pypdfium2`의 [PyPI Windows x64 휠](https://pypi.org/project/pypdfium2/5.13.0/)은 약 3.9 MB, 설치된 `pdfium.dll`은 6.92 MiB다. 위 증가분은 공통 의존성을 양쪽에 넣은 **실험용 exe 차이**다. 실제 제품 spec의 증가분과 ZIP 크기는 빌드해 보지 않았으므로 확정하지 않는다.

## 300dpi 렌더 비교

현재 제품과 같은 PyMuPDF 1.28.0 `Matrix(300/72, 300/72)`와 PDFium `render(scale=300/72)`를 비교했다. 각 엔진에서 첫 쪽을 세 번 열어 렌더·BGR 변환까지 실행한 중앙값이다. 화소 비율은 각 이미지의 공통 영역에서 RGB 세 채널 중 한 채널이라도 다른 픽셀의 비율이다. 크기가 다른 경우 남는 1px 행은 비율에서 제외했다.

| 악보 첫 쪽 | PyMuPDF 크기 | PDFium 크기 | 다른 픽셀 | 채널 차이 >10인 픽셀 | 시간 PyMuPDF / PDFium |
|---|---:|---:|---:|---:|---:|
| 바흐 미뉴에트 | 2481×3508 | 2481×3508 | 4.08% | 3.40% | 0.028 / 0.097초 |
| 쇼팽 Em | 2550×3300 | 2550×3301 | 7.21% | 6.19% | 0.047 / 0.101초 |
| 쇼팽 B♭m | 2480×3509 | 2480×3509 | 5.57% | 5.09% | 0.047 / 0.092초 |
| 쇼팽 D♭ | 2481×3508 | 2481×3508 | 5.17% | 4.24% | 0.040 / 0.096초 |

측정 도구는 [`tools/measure_pdfium.py`](../tools/measure_pdfium.py)다. 제품 환경을 바꾸지 않으려고 `python -m pip install --no-deps --target output/pdfium_pkg pypdfium2==5.13.0`으로 따로 설치하고, `PYTHONPATH=output/pdfium_pkg`에서 네 PDF 경로를 도구에 인자로 넘겼다. [PDFium API](https://pypdfium2-team.github.io/pypdfium2/python_api.html)는 PDF 좌표 단위당 픽셀 수를 `scale`로 받으므로 300dpi에 `300/72`를 사용했다. 이 4쪽 측정은 렌더러 교체 시 입력 화소와 한 쪽의 높이가 달라진다는 증거일 뿐, 인식 정확도나 전체 PDF의 속도를 판정하지 않는다. PDF 스냅샷·골든 보존을 주장할 수 없다.

## 다음 판단

PDFium은 라이선스 조건을 준수하며 동봉할 가능성이 있는 후보지만, **현재 exe에 바로 넣을 수 있는 대체품으로 확인되지는 않았다.** 도입을 검토할 때는 17쪽 전체를 같은 300dpi로 렌더해 좌표·보표·조표·라벨 변화를 검사하고, 새 오삭제가 0인지 원본 악보와 대조해야 한다. 그 뒤 실제 제품 spec으로 크기와 라이선스 고지 동봉을 검증한다. 그전까지 exe는 여러 이미지 입력을 사용하고 PDF는 소스 전용으로 둔다.


## 2차: 같은 제품 경로의 PDF 17쪽 대조 (2026-10-03)

기준 main `82b4399`, 300dpi, pypdfium2 5.13.0 / PDFium 153.0.7999.0. 제품 파일·의존성·spec은 변경하지 않았다. 별도 프로세스에서 `preprocess.load_image`만 PDFium 렌더로 대체하고, 화음 구제를 포함한 나머지 제품 CLI 전체를 그대로 실행했다. PDFium 객체는 프로세스 안에서 차례로 열고 닫았다. [공식 API](https://pypdfium2-team.github.io/pypdfium2/python_api.html#pypdfium2.PdfPage.render)의 `scale=300/72`를 사용하며 추가 크기 보정은 하지 않았다.

측정 전 함정 점검: 최소 렌더 사본 대신 실제 제품 호출을 사용한다(A-3b). 대조 PyMuPDF 17쪽을 기존 PDF 스냅샷과 줄 단위로 먼저 확인한다. 아래 차이는 음표 정답 판정이 아니라 **좌표·음고·임시표·표기·확신도 일곱 필드의 정확한 행 차이**다. 좌표가 1px만 달라도 양쪽 차이에 들어간다. 따라서 이 표의 차이를 오삭제·유령 수로 읽으면 안 된다. 조표와 음자리표도 따로 비교했다.

| 쪽 | PyMuPDF 라벨 | PDFium 라벨 | PyMuPDF에만 있는 행 | PDFium에만 있는 행 |
|---|---:|---:|---:|---:|
| bach | 184 | 189 | 104 | 109 |
| bbm1 | 280 | 280 | 211 | 211 |
| bbm2 | 308 | 306 | 193 | 191 |
| bbm3 | 340 | 337 | 240 | 237 |
| bbm4 | 343 | 340 | 234 | 231 |
| bbm5 | 335 | 336 | 226 | 227 |
| bbm6 | 218 | 225 | 170 | 177 |
| db1 | 255 | 257 | 126 | 128 |
| db2 | 364 | 367 | 197 | 200 |
| db3 | 322 | 315 | 162 | 155 |
| db4 | 309 | 310 | 183 | 184 |
| db5 | 369 | 353 | 218 | 202 |
| db6 | 333 | 335 | 178 | 180 |
| em1 | 299 | 300 | 180 | 181 |
| em2 | 347 | 351 | 215 | 219 |
| em3 | 298 | 304 | 171 | 177 |
| em4 | 200 | 202 | 116 | 118 |
| 합계 | 5104 | 5107 | 3124 | 3127 |

- PyMuPDF 대조는 **기존 PDF 스냅샷 17/17 완전 일치**. PDFium 17/17 처리 성공, 보표 수·조표·보표별 음자리표 문맥은 17/17 일치했다. **라벨 수만 같아도 결과는 같지 않다**(예: bbm1 280→280, 양쪽 차이 각211행).
- 모든 차이 행과 쪽별 크기·문맥은 [원자료](measurements/pdfium_17pages_82b4399.json)에 있다. Em은 PDFium 높이가 1px 늘어난다. 페이지 좌표부터 새로 대조해야 하므로 기존 골든을 PDFium 결과로 바꾸지 않았다.
- 실제 음표 소실/유령 여부는 원본 대조가 아직 없다. 현재 입력을 바로 대체할 근거가 아니며 **사용자 판단 필요: 도입 여부는 미결정, 오삭제 전수 검증이 먼저**다. 현 제품 경로는 그대로다.

재현:

```powershell
$env:PYTHONIOENCODING='utf-8'
venv\Scripts\python.exe -m pip install --no-deps --target output/pdfium_pkg pypdfium2==5.13.0
venv\Scripts\python.exe tools/measure_pdfium_recognition.py --package output/pdfium_pkg --output output/pdfium_17pages.json
```

### 제품 spec 사본의 크기·고지 동봉

최소 exe 대신 같은 제품 spec의 사본으로 기준/동봉 후보를 빌드했다. 후보는 PDFium 모듈·DLL·고지만 추가했으며 PDF 입력을 제품에 연결하지 않았다. **실험 바이너리이며 배포 후보가 아니다.**

| 제품 spec 사본 | 크기 |
|---|---:|
| 기준 | 118,597,326 B |
| PDFium + 고지19개 | 122,517,214 B |
| 증가 | **3,919,888 B (3.74 MiB)** |

[크기·SHA-256·번들 검사](measurements/pdfium_exe_size_82b4399.json): 기준에는 PDFium DLL/고지가 없고 후보에는 `pypdfium2_raw/pdfium.dll`과 고지19개가 있다. ZIP 크기와 실행 성능은 이번 크기 비교 범위에 없다. 재현은 `tools/build_pdfium_probe.py --package output/pdfium_pkg --output output/pdfium-probe --report output/pdfium-size.json`이다. 두 exe와 빌드 캐시를 둘 공간을 확보해야 한다.

[공식 라이선스 안내](https://github.com/pypdfium2-team/pypdfium2#licensing)에 따라 바인딩·PDFium·번들 의존성19파일 전체를 [동봉 고지 후보](measurements/pdfium_notice_candidate_5.13.0.txt)에 모았다. 파일별 원본 바이트 SHA-256은 [manifest](measurements/pdfium_license_manifest_5.13.0.json)에 있다. FreeType 고지만 원본 CP1252를 손실 없이 UTF-8로 옮겼고 나머지는 UTF-8이다. 실제 도입 때 기존 `THIRD_PARTY_NOTICES.txt`에 합쳐 넣고 번들/ZIP을 다시 검증해야 한다. 지금 제품 고지는 바꾸지 않았다.

측정 중 어댑터의 PdfPage 컨텍스트 관리 오류를 고쳤다. 그 실패를 PDFium 인식 실패로 기록하지 않았고 17쪽을 처음부터 다시 돌렸다. 이후 디스크 공간 소진으로 중단된 실행/전체 테스트도 유효한 검사로 세지 않았다. 이번에 만든 실험 캐시만 정리한 뒤 새 측정과 전체 테스트를 다시 실행했다. 기존 베타·사용자 파일·stash는 보존했다. 기준 실험 exe는 크기/해시/번들 증거를 기록한 뒤 공간 확보를 위해 제거했다.
