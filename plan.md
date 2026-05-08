# Plan: Replace OCR with hash + embedding card matching

## Goal

Identify each photographed Pokémon card by matching it against a local catalog, replacing the brittle OCR step. Output the matched card name to drive output filenames.

Languages in scope: **English + Japanese**.

## Architecture

```
[phone photo]
   ↓ findCardModel (YOLO, existing)
[card crop]
   ↓ perspective rectify → 224×224
[normalized card]
   ↓ CLIP embedding (512-d) + pHash(art region) (64-bit)
[query features]
   ↓ pHash filter top-50 → CLIP cosine rerank
[matched card_id]
   ↓ SQLite lookup
[card name → filename]
```

Two-phase system:
- **Catalog** (one-time, offline): scrape API → compute features → save
- **Match** (per upload): rectify → embed → look up

## Storage layout

```
catalog/
  cards.db          # SQLite, ~50k rows
  embeddings.npy    # (~50000, 512) float32 ≈ 100 MB
  images/           # ~3-5 GB during build, deletable after
```

### SQLite schema

```sql
CREATE TABLE cards (
  idx        INTEGER PRIMARY KEY,    -- maps to embeddings.npy row
  card_id    TEXT NOT NULL,          -- TCGdex local id, e.g. "sv05-039"
  lang       TEXT NOT NULL,          -- "en" or "jp"
  name       TEXT NOT NULL,
  set_id     TEXT,
  number     TEXT,
  rarity     TEXT,
  image_url  TEXT,
  phash      BLOB,                   -- 8-byte packed 64-bit pHash
  UNIQUE(card_id, lang)
);
CREATE INDEX idx_name ON cards(name);
CREATE INDEX idx_set  ON cards(set_id);
CREATE INDEX idx_lang ON cards(lang);
```

Row identity is `(card_id, lang)` — the same card in both languages is two rows with two embeddings, two pHashes. The `idx` column ties each row to its embedding row in `embeddings.npy`.

### Why this split

Embeddings stay in `.npy` because the match step needs a contiguous `(N, 512)` float32 array in memory to compute cosine similarity in a single numpy operation (~10 ms for 50k cards). Storing them as SQLite BLOBs would force per-query deserialization and defeat that.

Everything else lives in SQLite for incremental updates (new sets), indexed lookups, and type safety.

## Files

### New

- `catalog/build_catalog.py` — scrapes TCGdex, downloads images, computes features, writes SQLite + `.npy`
- `catalog/cards.db` — generated
- `catalog/embeddings.npy` — generated
- `match.py` — `Matcher.match(crop_bgr) -> (name, card_id, lang, confidence)`

### Modified

- `main.py` — replace `extractText(...)` call with `matcher.match(...)`. Drop EasyOCR import + reader setup.
- `pyproject.toml` — add `open_clip_torch`, `imagehash`, `requests`. Remove `easyocr`, `pytesseract` once OCR is fully removed.

### Untouched

- `findCard.pt`, `findNameNumber.pt` — YOLO card detection still used. Second-stage `findNameNumber` becomes optional / unused for the match path.
- `debug.py` — repurpose to dump match results instead of OCR comparisons.

## Implementation steps

### Step 1 — TCGdex scrape (~3-4 hr, mostly waiting)

- Endpoint: `GET https://api.tcgdex.net/v2/{lang}/cards`. Free, no API key required, no documented rate limit (be polite — small delay between requests).
- For each language in `["en", "jp"]`:
  - Page through the cards endpoint
  - `INSERT OR IGNORE` each card into `cards` with metadata + image URL
  - Download `images.small` (or equivalent) on demand into `catalog/images/<lang>/<card_id>.png`
- Restartable: existing `(card_id, lang)` rows are skipped on re-run.

### Step 2 — Feature computation (~10 min on GPU / ~40 min on CPU)

- Load CLIP ViT-B/32 from `open_clip` (~150 MB one-time download).
- Allocate `embeddings = np.zeros((N, 512), dtype=np.float32)` where N = `SELECT COUNT(*) FROM cards`.
- Iterate DB rows in `idx` order:
  - Crop top ~55% (art region), compute pHash → 8-byte blob → `UPDATE cards SET phash = ? WHERE idx = ?`
  - Resize full card to 224×224, run CLIP, L2-normalize → write into `embeddings[idx]`
- Save `embeddings.npy`.
- Restartable: skip rows where `phash IS NOT NULL` and the embedding row is non-zero.

### Step 3 — Perspective rectification

The current YOLO model gives a bounding box, not corners. Two options:

- **Option A (simple)**: just resize the bbox crop to 224×224. Works well if cards are photographed roughly square-on.
- **Option B (robust)**: detect the card's actual 4 corners with `cv2.findContours` within the bbox + `cv2.approxPolyDP`, then `cv2.getPerspectiveTransform` to unwarp to a canonical rectangle.

Start with A. Add B only if validation shows tilted-photo failures.

### Step 4 — Match function

```python
class Matcher:
    def __init__(self):
        self.conn = sqlite3.connect("catalog/cards.db")
        self.embeddings = np.load("catalog/embeddings.npy")  # (N, 512)
        rows = self.conn.execute("SELECT idx, phash FROM cards ORDER BY idx").fetchall()
        self.phashes = np.stack([np.frombuffer(p, dtype=np.uint8) for _, p in rows])  # (N, 8)

    def match(self, crop_bgr):
        # 1. Rectify + resize → 224×224
        # 2. CLIP embed → (1, 512), L2-normalized
        # 3. pHash on art region → uint8(8,)
        # 4. Hamming distance via XOR + popcount → top 50 indices
        # 5. cosine sim = embeddings[top50] @ query → best
        # 6. SELECT name, card_id, lang FROM cards WHERE idx = ?
        # 7. return (name, card_id, lang, score)
```

Both arrays live in memory after init (~100 MB embeddings + ~400 KB phashes).

Language is an **output**, not an input — the closest match wins regardless of language.

### Step 5 — Integration in main.py

Replace:

```python
namePlateStr = extractText(namePlate, reader)
```

with:

```python
name, card_id, lang, conf = matcher.match(crop_image)
namePlateStr = name if conf > 0.7 else "unknown"
```

The output filename uses the matched language's name (kanji for JP, latin for EN). If always-romanized output is preferred later, we can add a `name_en` lookup when a JP card matches.

### Step 6 — Validation & threshold tuning

1. Run match on the cards in `cardinput/`, compare matched names to ground truth.
2. Tune confidence threshold per language (JP may need slightly different threshold than EN).
3. If holos misrank: add Step 3 Option B (perspective rectify).
4. If specific cards consistently miss: consider storing multiple embeddings per card (API image + a few sample phone photos) — production card-recognition systems do this.

## Risks / things to watch

1. **TCGdex coverage gaps** — likely missing some old Japanese promos and very recent releases. ~95% coverage is realistic; the gap lands as "unknown" filenames.
2. **Same-art reprints** — Charizard Base Set vs Charizard Base Set 2 share artwork. Embedding returns whichever is closest; for filename purposes both are "Charizard" so this is fine, but the matched `card_id` may not be the exact print photographed.
3. **EN↔JP cross-matches** — an English photo may occasionally match a Japanese card if the EN entry is missing. The Japanese name comes back. Not a bug, but worth knowing.
4. **Holographic JP cards** — JP holos use slightly different foil patterns than EN. CLIP usually handles this but watch for it during validation.
5. **Card backs in input** — existing `main.py` already pairs front+back. Backs should fall below the confidence threshold and label as "unknown", or be skipped earlier by checking YOLO output.

## Effort estimate

~1.5 days of focused work:

- 4 hr scrape (two languages, more cards)
- 1 hr feature pipeline
- 2 hr match + integration
- 2 hr validation/tuning across both languages

## Decisions locked in

1. **Catalog scope**: all cards, English + Japanese
2. **Embedding model**: CLIP ViT-B/32
3. **Data source**: TCGdex (pokemontcg.io is no longer usable)
4. **OCR fallback**: none — low-confidence matches get labeled "unknown"
