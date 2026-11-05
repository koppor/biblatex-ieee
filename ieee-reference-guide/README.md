# The IEEE Reference Guide typeset with `biblatex-ieee`

This directory contains the examples of the
[IEEE Reference Guide, V 3.28.2025](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf)
as a `biblatex` database (`ieee-reference-guide.bib`) and two documents that typeset them with this style:

- `ieee-reference-guide-biblatex.tex` shows each example next to the text of the guide and the entry of the database,
  so that differences can be spotted by eye.
- `ieee-reference-guide-typeset.tex` typesets the guide itself with LaTeX, each example printed by this style,
  so that its PDF can be compared with the original one, e.g., using [diff-pdf](https://vslavik.github.io/diff-pdf/).

Compile with `latexmk ieee-reference-guide-biblatex ieee-reference-guide-typeset` (LuaLaTeX and biber, see `.latexmkrc`;
the repository's style files are used, not the installed ones).
The `IEEE Reference Guide` workflow builds both PDFs and uploads them as artifacts.

Questions about the guide itself (inconsistent or erroneous examples) go to IEEE via [IEEE Reference Assistant](https://refassist.ieee.org/).
