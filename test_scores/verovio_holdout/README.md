# 보류(holdout) 세트 — 채점 전용

**이 세트는 문턱 유도 · 시뮬레이션 판정 · 원인 측정에 쓰지 않는다. 채점만 한다**(`docs/DECISIONS.md` §3 원칙 9).
변경을 채택한 **뒤에** 결과만 확인한다. 이 세트를 보고 문턱을 고치면 그때부터 보류 세트가 아니다 — 새로 만든다.

개발 세트(`test_scores/verovio/`)에 없는 music21 10.5.0 코퍼스 곡 10개의 12쪽, 쪽마다 글꼴 하나(Bravura 6 · Leipzig 6), Verovio 6.3.0.
정답 머리 4,502(꾸밈음 11 포함). 재생성 `python tools/build_holdout_set.py build`(정답 보강 JSON은 `debug/vrv_holdout/truth/`), 채점 `python tools/score_holdout.py run|score <이름>`.

| 파일 | 곡 · 코퍼스 경로 | 파트 · 쪽 | 조표 · 박자 · 특징 |
|---|---|---|---|
| `weber_concertino_piano_bravura_p1` · `_leipzig_p2` | 베버, 클라리넷 콘체르티노 `weber/concertino_clarinet.mxl` | P2 피아노 · 1 · 2쪽 | ♭3 · 3/4 · 셈여림 · 16분 |
| `clara_trio_op17_3_piano_leipzig_p1` · `_bravura_p2` | 클라라 슈만, 피아노 3중주 Op.17 3악장 `schumann_clara/opus17/movement3.xml` | P3 피아노 · 1 · 2쪽 | ♯1 · 6/8 · 16분 |
| `handel_lascia_piano_bravura_p1` | 헨델, Lascia ch'io pianga `handel/rinaldo/Lascia_chio_pianga.mxl` | P2 피아노 | ♯2/♯3 · 3/4 · 셈여림 |
| `verdi_donna_mobile_leipzig_p1` | 베르디, La donna è mobile `verdi/laDonnaEMobile.mxl` | 전체 | ♭2 · 3/8 · 꾸밈음 6 |
| `schoenberg_op19_2_bravura_p1` · `schoenberg_op19_6_leipzig_p1` | 쇤베르크, Op.19 제2 · 6곡 `schoenberg/opus19/` | 전체 | 무조 · 임시표 · 셈여림 |
| `aloha_oe_piano_bravura_p1` | 릴리우오칼라니, Aloha ʻOe `liliuokalani/aloha_oe.mxl` | P6 피아노 | ♯1 · 4/4 |
| `beach_prayer_piano_leipzig_p1` | 비치, Prayer of a Tired Child `beach/prayer_of_a_tired_child.musicxml` | P5 피아노 | ♭3 · 4/4 · 셈여림 |
| `chopin_mazurka06_2_bravura_p1` | 쇼팽, 마주르카 Op.6-2 `chopin/mazurka06-2.krn`(music21로 MusicXML 변환) | 전체 | ♯4 · 3/4 · 셈여림 |
| `cpebach_h186_leipzig_p1` | C.P.E. 바흐 H.186 `cpebach/h186.mxl` | 전체 | ♯3 · 4/4 · 꾸밈음 4 |

**개발 세트와 다른 점 — PNG 변환기.** 이 PC에 cairo DLL이 없어 `cairosvg` 대신 PyMuPDF로 그렸다(Verovio 중첩 viewBox · CSS `stroke:currentColor`를 속성으로 펴서).
같은 방법으로 개발 세트 mozart_k545 Bravura 1쪽을 다시 그려 대조: 이진 화소 불일치 2.1%(가장자리), 제품 라벨 196 대 198 — 차이는 주로 「Allegro」 같은 **글자의 글꼴**(MuPDF 대체 세리프)과 4px 이내 위치. 따라서 글자 유령은 개발 세트와 1:1로 비교하지 않는다.
TSV 형식 · 좌표계는 개발 세트와 같다(`page` 열은 실제 쪽 번호). 저작권 · 인코딩 권리 주의는 `test_scores/verovio/README.md`와 같다.
