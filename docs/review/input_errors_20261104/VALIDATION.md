# 큰 이미지·손상 PDF 입력 안내 보완

## 문제와 최소 수정

Pillow DecompressionBombError는 OSError의 하위 예외가 아니어서 미리보기 콜백 밖으로 빠져나갔다. 이를 잡아 크기 축소/쪽별 분할 안내를 표시한다. 미리보기만 고치면 변환의 OpenCV 읽기로 넘어갈 수 있으므로, 각 _convert_page에서 이미지 헤더를 먼저 확인한다. 큰 쪽만 실패 처리하고 다음 정상 쪽은 계속 처리한다. 기존 파일 읽기 OSError는 전처리의 기존 오류 처리로 위임한다. 픽셀 제한을 늘리거나 인식 문턱을 고치지 않는다.

PyMuPDF FileDataError/EmptyFileError는 PDF를 다시 받거나 이미지로 저장하도록 안내한다. 일반 RuntimeError를 손상 PDF로 단정하지 않는다. 비밀번호 검사와 알 수 없는 오류의 원래 진단은 유지한다. 배포 exe의 PDF 미지원은 그대로다.

## 검증

- 동일 작은 경계 검사에서 수정 전 두 예외 실패 재현([원문](before-boundaries.log.gz)), 수정 후 새 단위6건 통과. 작은 합성 이미지에서만 Pillow 한도를 낮춘 단위 검사이며 finally에서 원상 복귀한다.
- 전체 검사 실패0·건너뜀0, 골든711/PDF17 유지. [전체 원문](run-all.log.gz). 골든 워커1/OpenCV1, 원자 HEAVY.lock, 시작 가용2.5GiB/실행 중1GiB 중단. [전체 메모리](full-memory.json): 작업 트리 합산 WS 최대573.8MiB(공유 페이지 중복 포함), private 최대486.1MiB, 가용 최저2884.3MiB.
- 동일 절대 입력·기본 GUI 설정으로 Aoharu1/D♭1/바흐1을 수정 전 main과 후보에서 각각 처리했다. PNG3·JSON3 **바이트 동일**, 인식 데이터 변화0. [입력·출력 SHA와 대조](normal-byte-comparison.json).
- [6종 실제 소스 GUI 작업자](hostile-results.json): 빈 쪽·4도 회전·1×1 저해상도·잘린 PDF·200MP PNG는 친절한 설명과 해결 방법을 남겨 정상 종료했고, 한글·공백 경로의 실제 Aoharu 악보는 변환에 성공했다. 예기치 못한 오류/traceback 안내와 멈춤은 관측되지 않았다.
- 200MP PNG는 기본 Pillow 한도 그대로 시험했다. 20000×10000 단색1비트 PNG를 행 단위 압축해 생성했으며 거대한 배열을 만들거나 제한을 해제하지 않았다. GUI 미리보기와 변환 모두 디코딩 전 거부했다. 원본 악보·오입력 이미지·PDF는 Git에 넣지 않았다.
- 소스 GUI 검증이며 새 exe를 빌드하지 않았다. [대조/오입력 메모리](verification-memory.json): WS 최대443.8MiB, 가용 최저3418.3MiB. 본인 Job·잠금 정리 완료.

## 범위와 남긴 것

변경은 gui.py/user_messages.py와 단위 검사뿐이다. 판정·골든·JSON 형식·정상 출력 경로 변경0. 독립 읽기 검토에서 중요 문제0. 사용자 요청에 따라 PR만 올리고 병합하지 않는다. 임의로 손상된 모든 이미지 형식의 완전한 안전성을 보증하는 검사는 아니며, 알려진 두 예외와 지정 입력6종을 확인했다.
