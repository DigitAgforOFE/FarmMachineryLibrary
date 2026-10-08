# Farm Machinery Library

A structured database of manufacturer specifications for **tillage implements**: working
widths, number of shanks / disks / rows, spacing, weights and transport dimensions. The
data is transcribed from brochures, spec sheets and operator's manuals, and it feeds the
[Machinery Image Processor](https://github.com/DigitAgforOFE/MachineryImageProcessor).

---

## Why we are building this

On-farm experiments (OFE) compare practices in real fields, and tillage is one of the
practices that matters most. To describe a tillage pass properly we need to know the
implement: which tools touch the soil, how far apart they are, how wide the machine
works and how aggressive it is (for example its contribution to the
Soil Tillage Intensity Rating, STIR, used by USDA-NRCS).

In practice, farmers rarely know these details off-hand, and measuring a machine in the
field is slow. The **Machinery Image Processor** lets someone photograph an implement with
a phone and click on its parts to measure it. Measurements from a photo have limits, though:
- perspective distorts sizes
- some tools are hidden
- every photo needs a scale reference

Most implements in use are standard products, built by a known manufacturer in a known
size, and their exact dimensions are already published. This library collects those
published numbers so that:

1. **A photo can be matched to a real model.** Counting 7 shanks spread over about 15 ft
   narrows the candidates to a handful of products.
2. **Once the model is known, its official dimensions replace guesswork.** They calibrate
   the photo and fill in what the photo can't show.
3. **The tillage pass can be described consistently** across farms and experiments, from
   the same reference data.

## How the data will be used

| Use | What it needs from the library | Status |
|---|---|---|
| **Identify the implement** in a photo: filter candidates by category, tool count, spacing and working width, then confirm with reference photos | `category`, the count field (`shanks`, `blades`, `rows`...), spacing, working width | Planned in the app |
| **Calibrate the photo**: use a known published dimension (working width, overall depth/height) as the scale reference | widths, transport and overall dimensions | Planned in the app |
| **Describe the tillage pass** for OFE: convert a model's spec into a tillage input (tool type, spacing, depth, full-width vs strips) for the cross-section profile and STIR | `category`, spacing, working depth, tool description | Prototyped, not yet in the app |
| **Fill gaps** when a photo can't show something (hidden shanks, depth range, weight) | any field in the entry | Planned |

The app does not read this library yet; wiring it in is the next development step on
the app side. The data is collected first so that it is ready, and because it takes
the longest to build.

## How the library is built

Building the library is split between two roles:

```
 Students / owner                              Owner (processing, with Claude Code)
 ───────────────────────────────               ─────────────────────────────────────
 1. Find documents online           ──┐
    (brochures, spec sheets,          │
    operator's manuals)               │
 2. `check`: is it new?               │
 3. `record`: register it ────────────┼──▶ sources.csv on GitHub (pull request)
 4. `export`: hand the files over ────┴──▶ shared drive (Box)
                                             5. Merge pull requests, `import` files
                                                into Brochures/
                                             6. Extract the spec tables into
                                                library/manufacturers/*.json
                                             7. Mark each file processed / skipped /
                                                related in sources.csv
                                             8. `validate`, review, commit
```

- **Collecting** is described step by step in [CONTRIBUTING.md](CONTRIBUTING.md), with
  pictures of perfect and useless documents.
- **Merging** students' work (pull requests plus the files from Box) is described in
  [CONTRIBUTING.md → For the project owner](CONTRIBUTING.md#for-the-project-owner-merging-contributions).
- **Processing** follows the extraction rules at the end of CONTRIBUTING.md: never guess,
  check every number against the source, cite the document and page, keep the source's
  units. Scanned documents are read from page images.
- **Every document is tracked**, including the ones that turned out useless, so nobody
  reviews the same file twice. Documents are identified by their SHA-256 fingerprint, so a
  renamed copy is still recognized.
- **The documents themselves are never put on GitHub.** They are large and copyrighted.
  The owner keeps the collection in `Brochures/`, backed up on Box.

### Document statuses (`library/sources.csv`)

| Status | Meaning |
|---|---|
| `processed` | Its specifications are in the library (`library_ids` says which entries) |
| `related` | Same content as a processed document (another edition, a translation, a spreadsheet twin) |
| `skipped` | Reviewed, nothing usable (parts list, no spec table, not tillage...); `note` says why |
| `unreviewed` | Collected but not processed yet: this is the to-do list |

## Components

| Path | What it is |
|---|---|
| [`library/manufacturers/`](library/manufacturers/) | **The library.** One JSON file per manufacturer. Each file holds *model families* (e.g. "Great Plains Turbo-Max"); each family lists its *variants* (the sizes/SKUs you can buy) with their numbers. |
| [`library/categories.json`](library/categories.json) | The implement categories (Disks, Rippers, Field Cultivators...) and which field holds each category's tool count. |
| [`library/schema.md`](library/schema.md) | The entry format and why it is shaped that way. |
| [`library/sources.csv`](library/sources.csv) | Every known source document: fingerprint, status, which entries it fed, who added it, notes. Opens in Excel / Google Sheets. |
| [`tools/brochures.py`](tools/brochures.py) | Command-line tool (Python 3.8+, no installs) for checking, registering, exporting, reporting progress and validating. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Guide for contributors: setup, what to collect, the workflow, extraction rules. |
| [`docs/examples/`](docs/examples/) | Example pages of good and useless documents, used by the guide. |
| `Brochures/` *(not in git)* | The document collection itself, organized as `Brochures/<Manufacturer>/...`. |

### `tools/brochures.py` commands

Run from the repository folder:

| Command | What it does |
|---|---|
| `python3 tools/brochures.py status` | **Progress summary**: documents by status and library entries per manufacturer |
| `python3 tools/brochures.py status --html progress.html` | Same, as a web page (see below) |
| `python3 tools/brochures.py check` | Lists which files in `Brochures/` are new, already known, or waiting |
| `python3 tools/brochures.py record FILE --status unreviewed --by NAME` | Registers a new document |
| `python3 tools/brochures.py export --added-by NAME --out DIR` | Copies the documents someone added, ready to upload to Box |
| `python3 tools/brochures.py import HANDOFF_DIR` | Owner: adds a student's handoff to `Brochures/`, never overwriting existing files |
| `python3 tools/brochures.py missing` | Owner: registered documents whose file hasn't arrived yet |
| `python3 tools/brochures.py tidy` | Repairs `sources.csv` after merging (git conflict marks, the same document registered twice) |
| `python3 tools/brochures.py validate` | Checks the JSON files and `sources.csv` for errors (run before every commit) |

On Windows, type `py` instead of `python3`.

## Seeing progress

```bash
git pull                                              # get everyone's latest work
python3 tools/brochures.py status --html progress.html
```

Then open `progress.html` in any web browser (double-click it). The page shows:
- the totals: library entries, models, documents known, documents used, documents still
  waiting
- for each manufacturer, a bar splitting its documents into processed / related /
  skipped / waiting, plus how many entries and models it contributes
- how many entries each implement category has, which shows where coverage is thin

The page is a snapshot. Run the command again after pulling to refresh it.
`progress.html` is a generated file, so don't commit it. To see progress without a
browser, run the plain `status` command.

As of the first release (October 2026), the library has **289 entries covering about
2,170 models from 30 manufacturers**, built from 985 reviewed documents.

## Getting started

- **To help collect documents:** read [CONTRIBUTING.md](CONTRIBUTING.md) from the top.
- **To use the data:** read [`library/schema.md`](library/schema.md), then load the JSON
  files in `library/manufacturers/`. Each entry's `source.note` says exactly which
  document and page its numbers came from. Entries marked `"verified": false` contain
  partial or uncertain data and should be treated with care.
