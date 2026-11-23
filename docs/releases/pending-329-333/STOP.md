# #329·#333 포함 베타 — 빌드 전 중단

**새 exe·ZIP은 없다.** 사용자10-13 10시 결정의 허용 범위 밖 기존 라벨 변화가 나와 빌드하지 않았다. selftest 기준 JSON·골든·인식 파일을 수정하지 않았고 PyInstaller·Defender·Actions도 실행하지 않았다.

## 확인 결과

- #329/793c748, #333의 최신판 #336/1b8ee40, 실제CLI 신호 기록을 확인했다. 검사 기준 main은6753dcd다.
- 신호 뒤 Codex 최신 main 전체검사41/41·실패0·건너뜀0. 골든711 및 현재 PDF17 스냅샷 일치. PDF 스냅샷은 CLI가 #329 측정에 따라 갱신한 기준이며, 이전 베타와 무변경이라고 주장하지 않는다.
- 추가 한정 비교는7/8 입력 통과. Aoharu3쪽·바흐·베토벤 기존행/문맥 불변, D♭1쪽은 #329 추가2만, Clara1쪽은 #310 주의 추가1만이다. [쪽별 수](SOURCE_COMPARISON.md).
- 슈베르트 Leipzig1쪽은 #310 주의 추가2 이후 #329에서 기존 E4·미# 1행이 변했다. 원래 `(1983,716)`/check/`glyph_shape`가 `(2010,717)`/check/`weak_side_ink`로 변한다. ID·nx도 좌표에 따라 바뀐다. 음고·표기·등급은 같다. 추가 한정 검사에서는 원래행1이 없어지고 새행10이 생겨 순증9다. 이를 오삭제라고 단정하거나 새행10을 복구10으로 세지 않는다.
- 조표·음자리표·source/staves/music 문맥은 같다. 이전 #217 복구 좌표 `(606,1522)` E4·미·certain은 현재 **소스**에서도 남아 있다. 새 exe 확인은 아니다.

## 대조 방법과 원자료

모든 입력을 현재 소스로 두 번 처리했다. 실제 실행과, 별도 측정 프로세스에서 기존 `_detect_noteheads_in_band(..., second_pair_split=False)` 인자만 사용한 대조다. 제품 파일을 고치지 않았다. 두 실행은 모두 같은 #333 전처리와 #310을 쓴다.

#312→분할OFF 대조는 기존 JSON 행 전체·순서·문맥 불변과 `chord_middle_added`/caution 추가만 확인한다. 대조→현재 실행은 기존 행 전체·순서·문맥 불변을 요구하며 새행만 #329 추가로 분류한다. 슈베르트는 두 번째 비교에서 실패했다. 이 입력은 #312에서 정상 처리된 깨끗한 입력이므로 「#333의 기존 거부 입력 좌표 변화」 예외를 적용하지 않았다.

- [전체 8입력 전후·대조 JSON 압축 원자료](strict-result.json.gz), [원자료 SHA256](record.json), [실패 로그](strict.log), [전체 검사 로그](prebuild-tests.log).
- [슈베르트 전후행과 #217 좌표](schubert-diff.json), [분할OFF 확대](schubert_second_disabled_detail.png), [현재 결과 확대](schubert_actual_detail.png). 결과 일부만이며 원본 악보 전체가 아니다.
- [독립 재현 도구](check_beta_additions.py). 같은 저장소 루트·입력과 설치된 venv에서 새 출력 폴더를 인자로 준다. 원자료에 보존한 #312 기준과 현재 소스를 비교하며 기존 폴더를 덮어쓰지 않는다. 이 커밋의 코드에서 슈베르트 기존행 변화로 실패하는 것이 기록과 같다.

```powershell
& 'C:/Users/user/Desktop/악보헬퍼/venv/Scripts/python.exe' docs/releases/pending-329-333/check_beta_additions.py output/beta329-independent-repro
```

## 남긴 것

사용자 판단 필요: #329의 위 기존 라벨 교체가 원본의 같은 음표를 더 정확한 중심에 붙인 것인지 CLI가 독립 확인하고, 이번 빌드의 「추가만」 허용 범위와 어떻게 맞출지 정해야 한다. 기준을 덮어쓰거나 판정 코드를 바꾸지 않는다.

미완료 마지막 폴더 기억은 요청대로 제외한다. 쪽별 확인 개수는 실패 재현→구현 후6 GUI 검사 통과·합성 화면까지 보존했지만 전체/3쪽 기본 출력 검사는 남아 있으며 채택하지 않았다. F:output/parked-page-review-counts-20261013.patch SHA2562a5c1d31a15a9c7947e639f4a89baa5e6ddcc4fda1fac5087a39601af5932fa9, output/page-review-counts-suite-20261013.log·page-review-counts-captures-20261013/. 제품 트리는 원상태이고 stash·공유C:·기존 빌드를 보존했다.

기울기 거부 안내와 나머지 큐3(d)는 남았다. #333 이후 일반1~3° 입력의 거부 전제가 달라졌으므로 재현부터 다시 해야 한다. 기존 `test_photo_correct.test_default_path_does_not_touch_the_image`는 실제 전처리가 성공해도 `assertRaises` 안에서 인위적으로 StaffNotFoundError를 올려 통과하는 검사다. 이를 실제 거부 증거로 쓰지 않았다. 새 정책에 맞는 실제 동작 검사로 정리할 후속 항목이며 이번 기록에서 고치지 않았다.

신고·exe 직접 클릭·스피커 청취·실제 다운로드 SmartScreen은 미확인 유지. 새 베타 해시나 경로를 만들어 쓰지 않는다. CLI 대기는 아직 해제하지 않았다.
