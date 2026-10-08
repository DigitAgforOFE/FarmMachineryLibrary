# Equipment library schema (draft v1)

One JSON file per manufacturer, under `library/manufacturers/<slug>.json`. Each file holds
one or more **model families** — a family is a named product line that may cover several
purchasable SKUs ("variants") differing only in a small set of numeric fields (working
width, shank/bottom/row count...). A family with a single SKU is just a family with one
variant.

## Why this shape

- **`constants`** vs **`variants`**: fields that are the same across every SKU in the
  family (overall depth, hitch type, tooth spec) live once in `constants`, not repeated
  per variant. This is what let us calibrate the Dirt Dog side-view photo without even
  knowing which of the 6 SKUs it was — overall depth/height don't change with width.
- **`countField`** per category (in `categories.json`): the library doesn't hardcode
  "shanks" as *the* count field, because it isn't — plows count bottoms, row crop tools
  count rows, disks count blades. The matching/UI code should ask `categories.json`
  which field to look for rather than assuming.
- **`variants` stay a flat array of only the fields that vary.** Two variants can share
  width but differ in count (APP66-5 vs APP66-7) — that's the exact case where the
  photo's shank count is the tiebreaker after width has already narrowed the field.
- **`source`** distinguishes a manufacturer spec sheet (trust it fully) from an
  operator's **manual** (its Specifications & Capacities table — same trust, but say
  which page) from a
  marketplace listing (aggregate signal only, no per-unit dimensions) from a
  **candidate** entry auto-logged when a processor couldn't find a match (unverified —
  matching code should prefer non-candidate entries, and someone should periodically
  review candidates before they start being offered as suggested matches).
- **`referencePhotos`** point at real confirmed photos of this exact family, for the
  dichotomous ID wizard to show "does yours look like this?" comparisons. Empty until a
  processed session confirms one.

## Entry shape

```jsonc
{
  "id": "dirtdog-app",              // stable slug, used as a foreign key elsewhere
  "manufacturer": "Dirt Dog",
  "modelFamily": "APP",
  "displayName": "Dirt Dog All Purpose Plow (APP)",
  "category": "Chisel Plows",       // must match a key in categories.json
  "source": {
    "type": "spec_sheet",           // "spec_sheet" | "manual" | "marketplace_listing" | "candidate"
    "verified": true,               // false if the source table didn't reconcile cleanly
    "note": "manufacturer spec sheet, provided directly"  // cite file name/doc code + page; say what was omitted and why
  },
  "constants": {                    // same for every variant in this family
    "overallDepthIn": 39.75,
    "overallHeightIn": 40.375,
    "holeSpacingIn": 1,
    "hitch": "Cat 1 STD & Cat 1 Quick Hitch",
    "tooth": "5/16\" x 2\" x 10 1/8\" Reversible 1080 High Carbon 38-44 Rockwell C",
    "frame": "2 1/2\" x 2 1/2\" x 3/8\" angle steel, 1/2\" x 2 1/2\" A-frame",
    "shankSpacingAdjustIn": 1,
    "digDepthRangeIn": [10, 12],
    "recommendedHpPerShank": 7
  },
  "variants": [                     // only the fields that differ between SKUs
    { "sku": "APP48-3", "workingWidthIn": 44, "overallWidthIn": 49.625, "shanks": 3, "weightLb": 206, "minHP": 24 }
    // ...
  ],
  "referencePhotos": [
    { "path": "IMG_6216_Dirt-Dog-All-Purpose-Plow-1.jpg.webp", "role": "back", "sku": null },
    { "path": "IMG_6220_Dirt-Dog-All-Purpose-Plow.jpg.webp", "role": "side", "sku": null }
  ]
}
```

`sku: null` on a reference photo means it's confirmed as this *family* but the exact
variant wasn't pinned down from the photo alone (e.g. shank count wasn't clearly
countable) — still useful for category/brand-level visual ID, not yet for full
auto-calibration.

## sources.csv — which files the library was built from

The brochure collection itself (`Brochures/<Manufacturer>/...`, several GB) is not in
git. [sources.csv](sources.csv) lists every known file instead, one row per distinct file
content, keyed by SHA-256 so a renamed copy is still recognized. Maintain it with
`tools/brochures.py` (see [CONTRIBUTING.md](../CONTRIBUTING.md)), not by hand.

| column | meaning |
|---|---|
| `path` | location under `Brochures/` in the main collection |
| `sha256` | fingerprint of the file's contents |
| `manufacturer` | top-level folder under `Brochures/` |
| `status` | `processed` (fed the entries in `library_ids`), `skipped` (nothing usable — say why in `note`), `related` (a variant of a processed file: translation, parts manual, quick-reference card, .xlsx twin, saved web page), `unreviewed` (in the collection, not yet looked at) |
| `library_ids` | `;`-separated library entry ids this file fed |
| `added_by` | who first contributed the file (`baseline` = the collection as of 2026-10-06) |
| `processed_by`, `date` | who last set the status, and when |
| `note` | anything the next person should know |

The `baseline` rows were inferred automatically by matching file names and document
codes against each entry's `source.note`; `processed` there means "cited by an entry",
and some `unreviewed` files may in fact have been looked at and set aside.
