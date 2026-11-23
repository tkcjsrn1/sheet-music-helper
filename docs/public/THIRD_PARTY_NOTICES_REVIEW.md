# 공개 후보 116f32d 제3자 고지 검토

후보에 동봉하는 고지는 빌드의 루트 `THIRD_PARTY_NOTICES.txt`다. 공개용 확장 초안은 [라이선스 전문](notices-20261026/THIRD_PARTY_NOTICES_DRAFT.txt)과 [파일별 대응표](notices-20261026/MATCHED_LICENSES.md)를 함께 사용한다. 원문과 바이트 범위가 연결되어 있어 그대로 보존한다.

#461의 입력 안내와 #466의 220ms 표시 보정은 기존 Pillow·WinMM을 사용한다. 8df72c9 대비 spec, requirements와 재생 모듈의 코드 diff는 없다. 이것만으로 116f32d의 전체 아카이브 버전과 자료 권리가 확인되는 것은 아니다.

공개 패키지에서 확인할 항목은 CustomTkinter 도형 글꼴 적용 범위, 설치본으로만 확인한 17개 모듈의 실제 바이너리 버전, Certifi MPL 소스 제공 방식, native DLL·런타임·데이터 고지 완결성이다. 모두 미확인 상태를 유지한다. PyMuPDF는 exe에서 제외하며 소스 PDF 배포 방식은 별도 검토한다. [기존 라이선스 목록](LICENSE_INVENTORY.md)
