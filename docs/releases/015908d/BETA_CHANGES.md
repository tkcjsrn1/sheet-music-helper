# e141908 → 015908d 변화 수

변화 수만 기록하며 정확도 판정이 아니다. 승인된 CLI main1019 전체 라벨 행과 새 소스/exe 행을 대조했다. 전체 전후 행은 strict-rows.json.gz에 보존했다.

| 입력 | 라벨 수 | 추가 | 이전 좌표 사라짐 | 표기 변경 | 확신도 변경 |
|---|---:|---:|---:|---:|---:|
| aoharu_p1 | 226 | 0 | 0 | 0 | 0 |
| aoharu_p2 | 327 | 0 | 0 | 0 | 0 |
| aoharu_p3 | 158 | 0 | 0 | 0 | 0 |
| chopin_Db_p1 | 262 | 0 | 0 | 5 | 0 |
| bach_p1 | 182 | 0 | 0 | 0 | 0 |
| clef_change_clara1 | 601 | 0 | 0 | 6 | 0 |
| alto_beethoven1 | 223 | 0 | 0 | 0 | 0 |
| schubert_restored | 504 | 13 | 2 | 0 | 0 |
| clara1_leipzig | 611 | 1 | 0 | 0 | 0 |
| clara2_bravura | 619 | 45 | 4 | 0 | 0 |
| clara2_leipzig | 596 | 30 | 3 | 0 | 0 |
| schubert_bravura | 504 | 12 | 0 | 0 | 0 |

9개 사라진 옛 좌표는 승인된 #408 wide_triple 분할 전후 행으로 coordinate_replacements.json에 대응을 보존했다. 같은 소리를 지웠다는 뜻으로 단정하지 않으며, 숫자만 바꾸어 통과시키지 않았다.

슈베르트 Leipzig 보호 라벨 `(606,1522)=E4 미 certain`은 새 실제 exe JSON에 남아 있다.
