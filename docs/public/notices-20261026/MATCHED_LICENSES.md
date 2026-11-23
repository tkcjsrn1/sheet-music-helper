# 라이선스 원문 매칭 후속 (2026-10-26)

**고지 초안이며 공개·재배포 승인이나 법적 완결성 판정이 아니다.** 기존 d69a025 exe/ZIP과 실제 `THIRD_PARTY_NOTICES.txt`는 바꾸지 않았다. 새 고지는 [THIRD_PARTY_NOTICES_DRAFT.txt](THIRD_PARTY_NOTICES_DRAFT.txt), 전 항목 대응은 [MATCHED_LICENSES.json](MATCHED_LICENSES.json)에 있다. #443에서 보류했던 원문 확인을 보완한다.

## 확인 범위

- PYZ 후보21개 모두 설치 배포판의 LICENSE 전문을 찾았다. package의 license 폴더 아래 `.py/.pyc`를 라이선스 텍스트로 잘못 넣지 않고 LICENSE/COPYING/NOTICE 파일 이름만 수집했다. FontTools·NumPy·SciPy·setuptools의 내장 구성요소 고지도 함께 보존했다.
- 62개 고유 원문/저작권 텍스트를 합류했다. 기존 고지 전문은 그대로 포함하고 중복 텍스트는 본문 안의 동일 바이트 범위를 참조한다. 원본 byte SHA256·줄끝만 정규화한 text SHA256·고지 내 byte offset/길이를 대응표에 남겼다. 영어 원문을 번역하거나 다른 라이선스로 덮지 않았다.
- Certifi의 파일은 MPL2.0 링크/고지이므로 [Mozilla 공식 전문](https://www.mozilla.org/media/MPL/2.0/index.815ca599c9df.txt)도 넣었다. Roboto2.137(2017)는 실제 폰트의 Apache2.0 표기·Google 저작권과 [Apache2.0 원문](https://www.apache.org/licenses/LICENSE-2.0.txt)을 맞췄다(원문은 설치 packaging의 LICENSE.APACHE와도 대조). 최신 Roboto의 다른 버전 라이선스로 바꾸지 않았다.
- 설치본 CustomTkinter의 LICENSE는 MIT였다. metadata의 CC0 표기는 고지 근거로 쓰지 않았다. [상류 LICENSE](https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE)와 구별해 설치본 원문을 보존했다.

| 동봉 폰트 묶음 | 수 | 원문 근거 | 상태 |
|---|---:|---|---|
| Roboto Regular/Medium | 2 | name13 Apache2.0 + Google 저작권 + Apache 전문 | 원문 확인 |
| DejaVu | 14 | 실제 LICENSE_DEJAVU(Bitstream Vera+Arev) | 원문 확인 |
| STIX | 17 | 실제 LICENSE_STIX: STIX 고지·OFL1.1 + Matplotlib LICENSE의 파일 범위 | 원문 확인 |
| BaKoMa CM | 8 | Matplotlib LICENSE의 `cm*.ttf` 명시·BaKoMa Fonts Licence | 원문 확인 |
| LastResortHE | 1 | Matplotlib LICENSE의 해당 파일 명시·OFL1.1 | 원문 확인 |
| CustomTkinter shapes | 1 | 상위 MIT는 있으나 폰트의 name0/13/14가 빈칸 | **개별 적용 범위 미확인** |

43개 모두 이전 actual-exe archive 해시와 현재 로컬 폰트 해시가 같음을 확인했다. 그중42개는 해당 파일 범위/원문을 연결했다. STIX의 「STIX Font License」라는 제목만 보고 별도 라이선스로 추측하지 않고 본문의 **OFL1.1**을 직접 확인했다. 도형 폰트1개는 상위 MIT를 임의 적용해 완료로 처리하지 않는다.

## 남아 있는 미확인

1. CustomTkinter 도형 폰트 개별 적용 범위/제작 출처.
2. 실제 build-info와 버전이 맞는 후보는 NumPy·SciPy·Pillow·CustomTkinter4개다. 나머지17개는 설치본 원문 대응이며, 실제 binary의 버전/전체 코드까지 byte 동일하다고 확정한 것은 아니다.
3. MPL 소스/수정 대응 자료를 어느 배포 위치에서 제공할지. 전문 복사만으로 배포 의무가 끝났다고 하지 않는다.
4. 후보21개 외 native DLL·시스템 runtime·모든 데이터/폰트의 최종 고지 완결성. 기존 원문을 보존했지만 이 조사만으로 전부 감사 완료라고 하지 않는다.

공개 자료 권리·원본/판본/인코딩 문제는 이 라이브러리 고지와 별개로 보류한다. 공개 결정·새 저장소·새 패키징은 실행하지 않았다.

## 단위 검사와 재현

`python docs/public/notices-20261026/test_notices.py -v`는 표준 라이브러리만 사용한다. 후보21/폰트43/42확인·1미확인, 원문62개 해시/byte 범위, 고지 훼손 탐지, 라이선스 계열 연결, 원 고지 보존, MPL/Apache 전문, 실제 binary 버전의 미확인 표시를 검사했다. **9개 통과.** [로그](unit.log)를 보존했다.

[수집 코드](collect.py)는 설치된 파일·폰트 name-table와 기존 archive 증거를 읽으며, 최초 MPL 전문이 없을 때만 공식 텍스트를 받는다. F: 임시 경로/해당 venv·기존 build-info가 필요한 내부 재현 코드이며 제품 실행 경로가 아니다. 이번에는 렌더/빌드/GUI/exe/전체 검사를 하지 않았다.
