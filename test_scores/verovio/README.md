# Verovio 다른 조판 검증 세트

저작권 보호 기간이 끝난 곡 10개의 **첫 쪽**을 Verovio 6.3.0의 Bravura·Leipzig 글꼴로 각각 그렸다. PNG 20장과 같은 이름의 TSV 20개가 있다. 9곡은 피아노 2단 악보(성악곡 두 곡은 피아노 반주 파트만 추출)이고, 베토벤 현악 4중주 한 곡은 다른 편성 대조군이다. 인식기는 이 자료에 실행하지 않았다.

| 파일 접두어 | 작곡가·곡 | music21 10.5.0 코퍼스 경로 | 추출 파트 |
|---|---|---|---|
| `mozart_k545` | 모차르트, 피아노 소나타 K.545 1악장 | `mozart/k545/movement1_exposition.mxl` | 전체 |
| `bach_bwv846` | 바흐, 평균율 1권 BWV 846 | `bach/bwv846.mxl` | 전체 |
| `joplin_maple_leaf` | 조플린, Maple Leaf Rag | `joplin/maple_leaf_rag.mxl` | 전체 |
| `clara_polonaise_1` ~ `4` | 클라라 슈만, 폴로네즈 Op.1 제1~4곡 | `schumann_clara/polonaise_op1n1.mxl` ~ `polonaise_op1n4.mxl` | 전체 |
| `schubert_lindenbaum_piano` | 슈베르트, Der Lindenbaum | `schubert/Lindenbaum.xml` | P2 피아노 |
| `schumann_op48no2_piano` | 로베르트 슈만, Op.48 제2곡 | `schumann_robert/opus48no2.mxl` | P2 피아노 |
| `beethoven_op18no1` | 베토벤, 현악 4중주 Op.18 제1번 1악장 | `beethoven/opus18no1/movement1.mxl` | 전체 |

원곡은 저작권 만료 악곡이다. **전자 악보의 인코딩 권리는 별개다.** [music21 코퍼스 안내](https://github.com/cuthbertLab/music21#license-coverage-and-otherprior-licenses)는 코퍼스의 개별 악보에 별도 권리·비상업 제한이 있을 수 있다고 명시한다. 원본 MusicXML은 이 저장소에 복사하지 않았으며, 출처 경로와 재생성 스크립트를 남겼다. 출력에 사용된 [Bravura](https://github.com/steinbergmedia/bravura/blob/master/LICENSE.txt)와 [Leipzig](https://github.com/rism-digital/leipzig)는 SIL OFL 1.1 글꼴이다. 이 세트는 저장소 내부 검증용이며 다른 용도로 재배포하기 전 해당 코퍼스 항목의 권리를 확인해야 한다.

각 TSV의 `page`는 1, `x`·`y`는 2100×2970 PNG의 음표 머리 중심 픽셀 좌표다. `note_name`과 `octave`는 SVG의 음고 정보, `accidental`은 **실제로 인쇄된** 임시표(`#`, `b`, `natural`, 없으면 빈 칸), `chord`는 화음 구성음이면 1이다. 조표로 바뀐 음고(`accid.ges`)는 인쇄된 임시표로 기록하지 않았다. 글꼴마다 첫 쪽에 들어가는 마디 수가 다를 수 있으므로 같은 곡의 두 TSV 행 수가 다를 수 있다. `manifest.json`에 각 파일의 행 수와 원본 쪽 수를 기록했다.

`accidental=##`는 인쇄된 겹올림도 포함한다. `grace`·`cue`는 각각 꾸밈음·작게 인쇄된 안내 음표이면 1이다. 원본 SVG를 모든 TSV 행과 좌표까지 대조해 집계한 결과 전체 8,033행 중 꾸밈음 92개, 안내 음표 8개, 인쇄된 겹올림 2개다. `docs/VEROVIO_MEASURE.md` §0의 「작은 머리 66개」와 집계가 다르므로 측정 문서의 분모는 재확인이 필요하다.

`coordinate_check_24.png`에는 모차르트 Bravura 1쪽에서 24개 음표 머리 중심을 빨간 원으로 표시했다. 원이 실제 머리에 겹치는지 확대 확인했다. Verovio SVG의 페이지 여백 이동을 좌표에 포함한다. 박자·음가나 이명동음 표기까지 검증한 정답은 아니며, `accidental`은 조표의 적용 반음이 아닌 눈에 보이는 기호다.

재생성: 프로젝트 가상환경에 `verovio==6.3.0`, `music21==10.5.0`, `cairosvg==2.9.1`, Pillow를 설치한 뒤 `python tools/build_verovio_set.py`를 실행한다. Windows 비 ASCII 사용자 경로에서는 스크립트가 빈 드라이브 문자를 잠시 연결해 Verovio 글꼴을 읽고 종료 때 해제한다.
