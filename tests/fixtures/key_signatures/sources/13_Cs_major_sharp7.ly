\version "2.26.0"

rightBase = \fixed c' {
c4 d e g | f e d c | e f g a | g2 c'2 |
c'4 b a g | f e d c | d e f d | c1 \break
c4 d e g | f e d c | e f g a | g2 c'2 |
c'4 b a g | f e d c | d e f d | c1 \break
c4 d e g | f e d c | e f g a | g2 c'2 |
c'4 b a g | f e d c | d e f d | c1 \break
c4 d e g | f e d c | e f g a | g2 c'2 |
c'4 b a g | f e d c | d e f d | c1 \break
}

leftBase = \fixed c {
c2 g | f g | c a | g c |
c g | f e | d g | c1 \break
c2 g | f g | c a | g c |
c g | f e | d g | c1 \break
c2 g | f g | c a | g c |
c g | f e | d g | c1 \break
c2 g | f g | c a | g c |
c g | f e | d g | c1 \break
}

\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 14\mm
  right-margin = 14\mm
  ragged-last-bottom = ##f
  print-page-number = ##f
}

\layout {
  indent = 0\mm
  short-indent = 0\mm
  \context { \Score \remove "Bar_number_engraver" }
}

\score {
  \new PianoStaff <<
    \new Staff = "right" {
      \clef treble
      \key cis \major
      \time 4/4
      \transpose c cis \rightBase
    }
    \new Staff = "left" {
      \clef bass
      \key cis \major
      \time 4/4
      \transpose c cis \leftBase
    }
  >>
}
