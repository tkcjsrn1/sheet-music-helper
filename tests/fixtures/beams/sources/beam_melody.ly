\version "2.26.0"
% 빔 경로 관찰용 자작 선율. 각 음표의 음높이와 길이를 생략하지 않는다.
% 한 줄에 음표 하나만 두어 PDF point-and-click의 소스 줄과 정답을 대응한다.
\header { title = "Beam fixture" subtitle = "Eighths / sixteenths / hollow controls" tagline = ##f }
\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 14\mm
  right-margin = 14\mm
  print-page-number = ##f
  system-system-spacing.basic-distance = #22
}
\layout {
  indent = 0\mm
  \context { \Score \remove "Bar_number_engraver" }
}

trebleMusic = {
  \autoBeamOff
  % 마디 1
  \stemUp
  e'8[
  e'8
  e'8
  e'8]
  e'8[
  e'8
  e'8
  e'8]
  |
  % 마디 2
  \stemDown
  d''16[
  d''16
  d''16
  d''16
  d''16
  d''16
  d''16
  d''16]
  d''16[
  d''16
  d''16
  d''16
  d''16
  d''16
  d''16
  d''16]
  |
  \break
  % 마디 3
  \stemUp
  c'8[
  d'8
  e'8
  f'8]
  g'8[
  f'8
  e'8
  d'8]
  |
  % 마디 4
  \stemDown
  g'16[
  f'16
  e'16
  d'16
  g'16
  f'16
  e'16
  d'16]
  g'16[
  f'16
  e'16
  d'16
  g'16
  f'16
  e'16
  d'16]
  |
  \break
  % 마디 5
  \stemUp
  d'2
  e'2
  |
  % 마디 6
  \stemDown
  g'2
  f'2
  |
}

bassMusic = {
  \autoBeamOff
  % 마디 1
  \stemUp
  g,8[
  g,8
  g,8
  g,8]
  g,8[
  g,8
  g,8
  g,8]
  |
  % 마디 2
  \stemDown
  b,16[
  b,16
  b,16
  b,16
  b,16
  b,16
  b,16
  b,16]
  b,16[
  b,16
  b,16
  b,16
  b,16
  b,16
  b,16
  b,16]
  |
  \break
  % 마디 3
  \stemUp
  c8[
  b,8
  a,8
  g,8]
  f,8[
  g,8
  a,8
  b,8]
  |
  % 마디 4
  \stemDown
  c16[
  d16
  e16
  f16
  c16
  d16
  e16
  f16]
  c16[
  d16
  e16
  f16
  c16
  d16
  e16
  f16]
  |
  \break
  % 마디 5
  \stemUp
  b,2
  c2
  |
  % 마디 6
  \stemDown
  d2
  c2
  |
}

\score {
  \new PianoStaff <<
    \new Staff = "treble" { \clef treble \key c \major \time 4/4 \trebleMusic }
    \new Staff = "bass" { \clef bass \key c \major \time 4/4 \bassMusic }
  >>
  \layout { }
  \midi { \tempo 4 = 96 }
}
