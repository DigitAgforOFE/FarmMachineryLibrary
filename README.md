# Farm Machinery Library

Manufacturer specifications for tillage implements: working widths, shank / disk / row
counts, weights, transport dimensions. They were transcribed from brochures, spec sheets
and operator's manuals. The library is used by the
[Machinery Image Processor](https://github.com/DigitAgforOFE/MachineryImageProcessor) to
identify implements in smartphone photos and calibrate measurements against their
published dimensions.

## What's here

| Path | Contents |
|---|---|
| [library/manufacturers/](library/manufacturers/) | One JSON file per manufacturer; each holds model families and their variants (SKUs) |
| [library/categories.json](library/categories.json) | Implement categories and which field holds each one's count (shanks, blades, rows...) |
| [library/schema.md](library/schema.md) | Entry format and conventions |
| [library/sources.csv](library/sources.csv) | Every source document known to the project, identified by SHA-256, with its status and the entries it fed |
| [tools/brochures.py](tools/brochures.py) | Check which local documents are new, register them, export handoffs, validate the library |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to help: finding documents, the workflow, extraction rules |

The source documents themselves are not in this repository, because they are large and
copyrighted. `sources.csv` records them by fingerprint so a copy can always be matched.

## Quick start

```bash
python3 tools/brochures.py validate      # sanity-check the library
python3 tools/brochures.py check         # which files in Brochures/ are new to the project
```

Python 3.8+ only, no dependencies.
