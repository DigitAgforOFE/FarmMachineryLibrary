# Notes for Claude Code

- This repo is the equipment library used by the Machinery Image Processor app
  (https://github.com/DigitAgforOFE/MachineryImageProcessor).
- Equipment library: people collect documents into `Brochures/`; processing them is
  Claude's job. Every `unreviewed` row in `library/sources.csv` is pending work. Follow
  the **Extraction rules** in [CONTRIBUTING.md](CONTRIBUTING.md) exactly,
  and the format in [library/schema.md](library/schema.md). In particular:
  - never guess or fill in values the source doesn't state; omit them and explain why
    in `source.note`
  - verify table values against the PDF's text layer (pypdf), not just a visual read
  - reuse existing field names and unit suffixes; don't convert units
  - after adding entries, record each source file with `python3 tools/brochures.py record`
    and run `python3 tools/brochures.py validate`
- Never edit `library/sources.csv` by hand, and never commit files from `Brochures/`.
