\version "2.26.0"
% 소스 정답용: 각 음표를 별도 줄에 명시한다.
#(set-global-staff-size 16)
\header { title = "Hollow-note fixture" subtitle = "Whole / half notes - staff size 16" tagline = ##f }
\paper { #(set-paper-size "a4") top-margin = 12\mm bottom-margin = 12\mm left-margin = 14\mm right-margin = 14\mm print-page-number = ##f system-system-spacing.basic-distance = #22 }
\layout { indent = 0\mm \context { \Score \remove "Bar_number_engraver" } }
trebleMusic = {
  e'1
  |
  \stemUp
  e'2
  g'2
  |
  g'1
  |
  \stemDown
  g'2
  b'2
  |
  \break
  b'1
  |
  \stemUp
  b'2
  d''2
  |
  d''1
  |
  \stemDown
  d''2
  f''2
  |
  \break
  f''1
  |
  \stemUp
  f''2
  a''2
  |
  a''1
  |
  \stemDown
  a''2
  e'2
  |
}
bassMusic = {
  e,1
  |
  \stemUp
  e,2
  g,2
  |
  g,1
  |
  \stemDown
  g,2
  b,2
  |
  \break
  b,1
  |
  \stemUp
  b,2
  d2
  |
  d1
  |
  \stemDown
  d2
  f2
  |
  \break
  f1
  |
  \stemUp
  f2
  a2
  |
  a1
  |
  \stemDown
  a2
  e,2
  |
}
\score { \new PianoStaff <<
 \new Staff = "treble" { \clef treble \key c \major \time 4/4 \trebleMusic }
 \new Staff = "bass" { \clef bass \key c \major \time 4/4 \bassMusic }
 >> \layout { } \midi { \tempo 4 = 96 } }
