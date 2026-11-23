# inputs/ 출처 · 라이선스 (원본은 커밋하지 않는다 — `/inputs/` 무시)

## inputs/mutopia/ — 실사용 대용 세트 (2026-10-13 야간 큐 2(a))

[Mutopia Project](https://www.mutopiaproject.org/)의 피아노 독주곡 중 **라이선스가 「Public Domain」으로 표시된 것만** 골랐다(목록 표의 라이선스 칸으로 확인, CC 계열 제외).
A4 PDF를 받아 앞 1~2쪽만 잘라 저장했다(`fitz`). 전부 LilyPond 조판이라 PDF 글리프로 정답 머리를 뽑을 수 있다. 원본 PDF는 `debug/mutopia_dl/`(커밋 안 함).

| 파일 | 곡 | Mutopia 경로(`https://www.mutopiaproject.org/ftp/` 뒤) | 쪽 | 고른 이유 |
|---|---|---|---:|---|
| `schubert_impromptu_ges.pdf` | 슈베르트, 즉흥곡 G♭장조 D899-3 | `SchubertF/D899/SchubertF-D899-3-Impromptu/SchubertF-D899-3-Impromptu-a4.pdf` | 2 | 조표 ♭6 · 화음 반주 |
| `schubert_moment_3_fmin.pdf` | 슈베르트, 악흥의 순간 3번 F단조 D780 | `SchubertF/D780/MomentsNo3/MomentsNo3-a4.pdf` | 2 | 조표 ♭4 |
| `beethoven_pathetique_1.pdf` | 베토벤, 소나타 8번 「비창」 1악장 | `BeethovenLv/O13/pathetique-1/pathetique-1-a4.pdf` | 2 | 두꺼운 화음 · 낮은음 덧줄 |
| `brahms_intermezzo_118_2.pdf` | 브람스, 간주곡 Op.118-2 | `BrahmsJ/O118/intermezzo/intermezzo-a4.pdf` | 1 | 내성 화음 |
| `grieg_hall_mountain_king.pdf` | 그리그, 「산왕의 궁전에서」 Op.46 | `GriegE/O46/Dans_l_antre_du_roi_de_la_montagne/Dans_l_antre_du_roi_de_la_montagne-a4.pdf` | 1 | 낮은음 옥타브 · 덧줄 |

이 세트는 문턱 유도에 쓰지 않는다(실사용 대용 점검). 결과는 `docs/INPUTS_REVIEW.md`.
