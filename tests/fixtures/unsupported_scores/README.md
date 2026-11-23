# 현재 미지원 악보 테스트 픽스처

`tests/test_unsupported_scores_xfail.py`가 사용하는 최소 재현 입력이다. 제품 정확도나
오류율을 재는 골든이 아니며, 현재 알려진 한계를 `expectedFailure`로 고정한다.

| 파일 | 원본과 가공 | 권리 |
|---|---|---|
| `satie_ogive3_scan_60pct.jpg` | [Wikimedia Commons의 BnF 초판 스캔](https://commons.wikimedia.org/wiki/File:Ogives_%28pour_piano%29_-_btv1b525030386_%2809_of_16%29.jpg)을 가로·세로 60%로 축소하고 JPEG 품질 75로 저장 | Public Domain 표시 |
| `bach_bwv639_three_staff.png` | [Mutopia BWV 639](https://www.mutopiaproject.org/ftp/BachJS/BWV639/Ich_ruf_zu_dir2/) PDF 2쪽의 첫 3보표 시스템을 300dpi 렌더에서 잘라냄 | Pierre Pouillon 조판, CC BY-SA 3.0. 이 파생 픽스처도 같은 조건으로 제공 |
| `chopin_raindrop_key_change.png` | [Mutopia 쇼팽 전주곡 Op.28 No.15](https://www.mutopiaproject.org/ftp/ChopinFF/O28/Chop-28-15/) PDF 2쪽의 24마디와 조바꿈 뒤 시스템을 300dpi 렌더에서 잘라냄 | 배포처 Public Domain 표시 |
| `beethoven_midscore_symbols.png` | [Mutopia Beethoven Seven Variations WoO 78](https://www.mutopiaproject.org/ftp/BeethovenLv/WoO78/seven_variations_opuswoo78/) PDF 5쪽의 300dpi 렌더에서 `(1000,850)`–`(2481,2250)`을 잘라냄. 반복선 뒤 조표 3플랫 2벌과 곡 중간 높은음자리표 포함 | 배포처 Public Domain 표시 |
| `schubert_triplet_beam_stem.png` | [Mutopia Schubert Impromptu D.899 No.2](https://www.mutopiaproject.org/ftp/SchubertF/D899/SchubertF-D899-2-Impromptu/) PDF 1쪽의 300dpi 렌더에서 `(0,0)`–`(2481,1800)`을 잘라냄. `(929,891)` 빔·기둥 교차점과 비교용 다음 시스템 포함 | 배포처 Public Domain 표시 |

원본 해시와 더 자세한 출처는 `output/unseen-scores-20260829/manifest.json` 및
`SOURCES.md`에 기록했다. output은 Git에 포함되지 않으므로 이 문서에도 원본 URL과
가공 내용을 남긴다.
