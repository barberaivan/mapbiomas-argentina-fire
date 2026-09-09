// Standalone figure: the same diagram, cropped to its content, for the paper.
// `width: auto` is LaTeX's `standalone`.  Include the PDF at scale 1.0.
#import "../lib/style.typ": *
#import "../diagrams/method-scheme.typ": method-scheme

#set page(width: auto, height: auto, margin: 4pt)
#set text(font: font-sans, size: 8pt, fill: c-ink)
#set par(leading: leading)

#method-scheme()
