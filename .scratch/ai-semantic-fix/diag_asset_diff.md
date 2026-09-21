# Diag: diacritic-restoration regression failures with rebuilt assets (2026-09-21)

Forensic, read-only analysis. No code/config/asset was modified; no build was run; `.env` was not read.
Interpreter: `.venv\Scripts\python.exe`. Verification method: (1) asset diffing with Unicode NFC folding,
(2) a faithful mini-replica of `_score_with_bigrams`, and (3) the **real** `_rule_restore` from
`backend/app/normalizer/diacritic_restorer.py` exec'd in memory with stubbed `app.*` imports, run over
all 51 cases of `chat_regression_test.csv` against both asset sets.

**Verdict (short):** The rebuild did not just "re-sort" candidates — it (1) shrank the per-word candidate
cap from 8 to 5 (deleting `lắm`, `bận`, … outright), (2) re-cut the bigram index at 200,000 entries after
chat data inflated the pool, evicting the small news bigrams (`chúc_bạn` 90→absent, `mấy_giờ` 81→absent)
that were the *only* context evidence the old assets provided for these cases, (3) **permanently lost
counts** to the streaming builder's mid-run pruning (698 bigrams have live count < backup count —
impossible under pure accumulation), and (4) the chat corpus at weight 3 actively boosted the *wrong*
readings (`máy_hôm` 0→126, `sao_máy` 0→270). The 4 cases had been passing the 0.6 token-accuracy
threshold by a 0–1 token margin; the rebuild shaved 1–2 tokens each and dropped them below it.

---

## (a) Inventory

| File (relative to `backend/data/diacritic/`) | Bytes | Entries | Notes |
|---|---|---|---|
| `word_map.json` (LIVE) | 321,198 | 7,170 | md5 `048771ee2e2e`, mtime 2026-09-21 14:45:00, values all NFC |
| `bigram_freq.json` (LIVE) | 4,951,861 | 200,000 | md5 `e9e91262457c`, all values **float** |
| `diacritic_assets_manifest.json` (LIVE) | 796 | — | inputs: ViDiacritics_val + train **+ 4 chat CSVs** (Dev, history_export, Test, Train); `word_map_entries: 7170`, `bigram_entries: 200000`, builder `build_diacritic_streaming.py`, generated 2026-09-21T07:45:00Z |
| `backup/20260921_144452/word_map.json` | 350,100 | 7,022 | original assets; all 5 backup dirs **byte-identical** (md5 `5808f062e0c0`) |
| `backup/20260921_144452/bigram_freq.json` | 4,551,105 | 200,000 | md5 `3f77b5c1c4fa`, all values **int** |
| `backup/20260921_144452/diacritic_assets_manifest.json` | 280 | — | see below |
| `context_phrases.json` (LIVE only, not in backup) | 162,485 | 5,000 | mtime 2026-05-28 — **not rebuilt**, identical for both runs; contains *none* of the failing pairs (`chuc ban`, `ngon nhe`, `may gio`, `tot lam`, …) |
| `chat_regression_test.csv` | 3,020 | 51 cases | mtime 2026-05-24 09:52 — authored right after the original build |
| `.smoke/` | — | wm 985 / bg 8,481 | smoke build from sample_5k.csv, 12:40 attempt |

Backups exist at `20260921_{032912, 124046, 131651, 135725, 144452}` — five identical snapshots of the
original 2026-05-24 assets (file mtimes 09:47:38–40), taken before each rebuild attempt.

**Backup manifest (original assets):**
```json
{ "bigram_entries": 200000, "builder": "build_diacritic_streaming.py",
  "generated_at": "2026-05-23T12:47:40.421512+00:00",
  "inputs": ["data\\DataDauCau\\ViDiacritics_val.csv", "data\\DataDauCau\\ViDiacritics_train.csv"],
  "word_map_entries": 7022 }
```

## (b) Per-key comparison

### word_map candidates (NFC-folded; "pos" = index of the chat-expected form)

| Key | LIVE (max 5) | BACKUP (max 8) | Diff | Expected form: live pos / backup pos |
|---|---|---|---|---|
| chuc | chức, chục, chúc, chực, chuc | chức, chục, chúc, chực, chuc, chưc | DIFF | chúc: 2 / 2 |
| ban | bản, bán, bạn, ban, bàn | bản, bán, bạn, ban, bàn, bắn, bẩn, **bận** | DIFF | bạn: 2 / 2; bán: 1 / 1; **bận: absent / 7** |
| may | máy, may, mấy, mây, mày | máy, may, mây, mấy, mày, mẩy, mảy, mầy | DIFF | mấy: 2 / 3 |
| lam | làm, lâm, lãm, lạm, lầm | làm, lâm, lãm, lạm, lầm, **lắm**, lam, lẫm | DIFF | **lắm: absent / 5** |
| qua | — (key absent) | — (key absent) | SAME | quá: unreachable from assets in **both** |
| tot | tốt, tót, tột, tọt, tôt | tốt, tót, tột, tọt, tot, tôt, tổt | DIFF | tốt: 0 / 0 |
| roi | rồi, rơi, rời, rối, roi | rồi, rơi, rời, rối, roi, rỗi, rói, rọi | DIFF | rồi: 0 / 0 |
| gio | giờ, gió, giò, giỗ, giở | giờ, gió, giò, giỗ, giở, giơ, giỏ, gio | DIFF | giờ: 0 / 0 |
| hom | hôm, hòm, hom, hóm, hợp | hôm, hòm, hom, hóm, hợp, hõm, hổm, hỗm | DIFF | hôm: 0 / 0 |
| nay | này, nay, nảy, nấy, náy | này, nay, nảy, nấy, náy, nãy, nẩy, nậy | DIFF | nay: 1 / 1 |
| sao | — (key absent) | — (key absent) | SAME | sao: unreachable in both |
| vay | vậy, vay, váy, vây, vẫy | vậy, vay, váy, vây, vẫy, vảy, vầy, vẩy | DIFF | vậy: 0 / 0 |
| ngu | ngủ, ngư, ngữ, ngũ, ngụ | ngủ, ngư, ngữ, ngũ, ngụ, ngự, ngừ, ngu | DIFF | ngủ: 0 / 0 |
| ngon | — (key absent) | — (key absent) | SAME | — |
| nhe | nhẹ, nhé, nhe, nhè, nhẽ | nhẹ, nhé, nhe, nhè, nhẽ, nhễ, nhê, nhể | DIFF | nhé: 1 / 1 (nhẹ first in **both**) |
| vo | vợ, vô, võ, vỡ, vỏ | vợ, vô, võ, vỡ, vỏ, vở, vờ, vỗ | DIFF | vợ: 0 / 0 |
| thi | — (key absent; runtime builtin `thi→thì,thị,thí` not applied by the test path) | — | SAME | — |
| met | mệt, mét, met, mẹt, mết | mệt, mét, met, mẹt, mết, mêt | DIFF | mệt: 0 / 0 |

Candidate **order barely changed**; the regression is **truncation**: LIVE caps lists at 5, BACKUP at 8.

**word_map aggregates:** LIVE len histogram 1:5585, 2:471, 3:239, 4:185, **5:690** (max=5, mean 1.59);
BACKUP …, 5:140, 6:143, 7:92, **8:423** (max=8, mean 1.95). Backup keys truncated at 5: **658**;
candidate forms lost: **2,436**; keys present only in backup: **48**; only in live: 196.
Both files have **0** entries whose first candidate equals the key (drop rule applied in both builds).

### bigram counts (LIVE | BACKUP; 0 = key absent)

| Bigram | LIVE | BACKUP | Role in failing cases |
|---|---|---|---|
| chúc_bạn | **0 (absent)** | **90** | sole evidence for `chúc`/`bạn` in case 9 |
| chức_bạn | 0 | 0 | — |
| chức_bán | 255.0 | 255 | news noise that pulls `chuc→chức`, `ban→bán` |
| chúc_bán | 0 | 0 | — |
| bạn_ngủ | 209.0 | 209 | rescues `ngu→ngủ` after `bạn` |
| bán_ngủ | 0 | 0 | — |
| ngủ_ngon | 1260.0 | 1260 | — |
| ngon_nhẹ | 0 | 0 | `nhe` tie in **both** → first candidate `nhẹ` |
| ngon_nhé | 0 | 0 | `nhé` unreachable from bigrams in **both** |
| mấy_giờ | **0 (absent)** | **81** | sole evidence for `mấy` in case 10 |
| máy_giờ | 0 | 0 | — |
| rồi_bạn | 103.0 | 103 | loses to… |
| rồi_bán | 431.0 | 431 | …`ban→bán` in **both** (pre-existing error) |
| tốt_lắm | 267.0 | 150 | chat-boosted (+117 = 39×3); decisive for case 43 under backup |
| tốt_làm | 0 | 0 | — |
| bận_quá | 0 | 0 | `bận` has no bigram evidence in either |
| bạn_quá | 167.0 | 164 | — |
| bán_quá | 94.0 | 91 | — |
| quá_vậy | 0 | 0 | — |
| qua_vậy | 0 | 0 | — |
| hôm_nay | 36122.0 | 35765 | — |
| máy_hôm | **126.0** | **0** | **chat boosted the wrong reading** |
| mấy_hôm | 330.0 | 261 | +69 = 23×3 |
| nay_bận | 0 | 0 | — |
| nay_bạn | 211.0 | 205 | — |
| nay_bán | 94.0 | 91 | — |
| hôm_bận | 0 | 0 | — |
| chúc_ngủ | 0 | 0 | — |
| sao_máy (extra) | **270.0** | 0 | **new chat bigram; decisive against `mấy` in case 49** |

**Bigram loss/gain analysis (200k cut):** min count kept rose **80 → 82**. All **2,834** bigrams present
in backup but absent in live had backup counts in **80–149** (2,759 in 80–89, 75 in 90–149) — exactly the
old cut boundary. 2,834 new bigrams entered (1,316 @80–89, 1,247 @90–149, 271 @150+). Of 197,166 common
keys, 31,374 increased (chat, +588,121 total) but **698 DECREASED** (deficit 3,350), e.g. `phép_nhưng`
114→86, `quá_một` 114→92, `cầm_mới` 120→98 — proof that the streaming builder's mid-run prune
**reset counts**, not merely selected a top-N (a pure merge can never decrease a count).

## (c) Builder semantics comparison

| Parameter | build_diacritic_index.py / build_bigram_index.py (mtime 05-18) | build_diacritic_assets.py (05-18) | build_diacritic_streaming.py CURRENT (mtime 09-21 17:55) | Evidence in assets |
|---|---|---|---|---|
| min_freq | 2 | 2 | 2 (`DEFAULT_MIN_FREQ`, L51) | same in both (no effect) |
| max entries/word | 5 (default, L35) | 5 (default, L33) | **5** (`DEFAULT_MAX_ENTRIES`, L52); ps1 wrapper does **not** pass `--max-entries-per-word` | backup max **8** ⇒ original built with 8 (older default/flag; exact old source lost); live max **5** ⇒ **8→5 regression** |
| bigram top-N | 10,000 default (L45) | 100,000 default (L34) | 100,000 default (L53); ps1 passes **220,000** (L89, ps1 mtime 17:56 = edited *after* the rebuild) | backup = exactly **200,000**; live = exactly **200,000** ⇒ the 14:45 rebuild ran with top-N **200,000** |
| counts dtype | **int** (`counter[key] += 1`, build_bigram_index L53) | int | **float** (`weight = float(weights.get(...))`, L194) | live all float; backup all int |
| chat weighting | none | none | `--weight PATH=FLOAT` (chat ×3) | +3.0 increments: tốt_lắm +117=39×3, mấy_hôm +69=23×3, hôm_nay +357 |
| inputs | news CSVs | news CSVs | news + chat CSVs | manifests quoted above |
| "drop when most-common form == no-diacritic key" | `if forms and forms[0] != nd_word` (build_diacritic_index L74) | inherits | identical rule (streaming L281) | 0 identity-first entries in **both** files ⇒ **not causal** |
| mid-run pruning | none (exact in-memory Counter) | none | **prune to top-300,000 whenever >450,000** at 1M-line chunk boundaries (L224–233) | **698 common bigrams live<backup** ⇒ count reset / data loss (streaming-only) |

No `.git` repository exists (`fatal: not a git repository`), so the exact pre-rebuild source of
`build_diacritic_streaming.py` cannot be recovered from history; the parameters above are inferred from
asset evidence + manifests + current sources. `.gitignore` does **not** ignore
`backend/data/diacritic/*.json` (only `backend/data/DataDauCau/*.csv` and `.checkpoints/`) — but with no
repo, nothing is actually versioned.

## (d) ROOT CAUSE

### Timeline (file mtimes)
05-18 builders → **05-24 09:47 original assets built (news-only), 09:52 the 51-case regression CSV
authored against them** → 05-28 context_phrases.json + regression test → 09-21 03:29…14:44 five backup
snapshots → **14:45 rebuild written (news + 4 chat CSVs ×3)** → 17:55 streaming builder edited,
17:56 ps1 edited (top-n 220000), **17:59 restorer edited: +6 built-in phrase overrides**.

### Test mechanics that set the pass/fail line
`tests/test_diacritic_regression.py` runs `_rule_restore(text, word_map, bigram_freq)` — i.e. **no file
context phrases**, only `_BUILTIN_CONTEXT_PHRASE_OVERRIDES` — and asserts per-case
`token_accuracy ≥ 0.6` (0.0 for `ambiguous`) plus overall ≥ 0.70. The 4 cases were passing by a margin of
0–1 tokens (0.60, 0.75, 1.00, 0.71); the rebuild pushed them to 0.40, 0.50, 0.50, 0.57.

### The four regressions, with exact numbers

1. **word_map cap 8 → 5** (ps1 never pins `--max-entries-per-word`; current default is 5 while the
   original build used 8). 658 keys truncated, 2,436 forms deleted — including **`lắm` (rank 6 of
   `lam`)** and **`bận` (rank 8 of `ban`)**. Consequence: `tot lam` → `lắm` is **impossible** with live
   assets (case 43 fails deterministically), and `bận` is unreachable in case 49.
2. **Bigram top-200k re-cut with an inflated pool.** Chat ×3 added 2,834 new bigrams, the cut threshold
   rose 80 → 82, and the marginal news bigrams were evicted — among them the *only* context evidence for
   the failing cases: **`chúc_bạn` 90 → absent**, **`mấy_giờ` 81 → absent**.
3. **Streaming mid-run prune = permanent count loss.** Pruning to top-300k at 1M-line chunk boundaries
   resets counts; 698 bigrams ended **lower** than in the news-only backup (Σ deficit 3,350). This is why
   `chúc_bạn` (90 > 82) could vanish entirely, and why some totals shrank despite *adding* data.
4. **Chat ×3 actively boosts the wrong readings.** `máy_hôm` 0→126 and new `sao_máy` 270 make `máy` score
   **396 vs `mấy` 330** in case 49, while news-noise `chức_bán` 255 (unchanged) dominates `chuc`/`ban`
   once `chúc_bạn` is gone.

### Per-case scoring (real `_rule_restore`, prev+next max, tie → first candidate)

| Case | Decision | BACKUP | LIVE |
|---|---|---|---|
| 9 `chuc ban ngu ngon nhe` | `chuc`: chức 255 (chức_bán) > chúc 90 (chúc_bạn) → chức in **both**; `ban`: bạn 90+209=299 > bán 255 → **bạn** \| bạn 0+209=209 < bán 255+0 → **bán**; `nhe`: ngon_nhẹ=ngon_nhé=0 → tie → first = **nhẹ in both** (nhé never asset-derivable) | `chức bạn ngủ ngon nhẹ` = 3/5 = **0.60 PASS** | `chức bán ngủ ngon nhẹ` = 2/5 = **0.40 FAIL** |
| 10 `may gio roi ban` | `may`: mấy = mấy_giờ 81 > máy 0 → **mấy** \| all 0 → tie → first **máy**; `ban`: rồi_bán 431 > rồi_bạn 103 → bán in both | `mấy giờ rồi bán` = 3/4 = **0.75 PASS** | `máy giờ rồi bán` = 2/4 = **0.50 FAIL** |
| 43 `tot lam` | `tot`→tốt (0) both; `lam`: backup tốt_lắm 150 > 0 → **lắm**; live `lắm` not a candidate; tie → first **làm** | `tốt lắm` = **1.00 PASS** | `tốt làm` = **0.50 FAIL** |
| 49 `sao may hom nay ban qua vay` | `may`: backup mấy 0+261=261 > máy 0 → **mấy** \| live máy 270+126=**396** > mấy 0+330=330 → **máy**; `ban`: bạn 211+167=378 > bán 185 → bạn in both (bận unreachable); `qua`: no key in **either** map → `quá` unreachable | `sao mấy hôm nay bạn qua vậy` = 5/7 = **0.71 PASS** | `sao máy hôm nay bạn qua vậy` = 4/7 = **0.57 FAIL** |

### Verification matrix (real code, all 51 cases)

| Configuration | Per-case fails | Overall |
|---|---|---|
| BACKUP assets + pre-patch builtins (current set minus the 6 pairs below) | **0** | 87.7% |
| LIVE assets + pre-patch builtins | **4** = CSV 9, 10, 43, 49 — exactly the reported failures, with exactly the reported outputs | 85.2% |
| BACKUP assets, no phrase overrides at all | 4 cases above still pass (0.60/0.75/1.00/0.71) | 83.2% |
| LIVE assets, no phrase overrides | 4 fails above + 5 context-phrase cases that need the older builtins | 80.7% |
| LIVE assets + **current** (post-17:59) builtins | **0** (0.80 / 1.00 / 1.00 / 1.00) | — |

The overall-aggregate assert (≥0.70) passes in every configuration — only the per-case 0.6 asserts flip.

### Why "passed before, fails now" — one sentence
The old assets supplied, through marginal-but-real statistics (word_map ranks 6–8 and bigrams counted
80–90), exactly the one-token evidence each fragile case needed; the rebuild deleted those statistics
(cap 5, 200k re-cut, prune count-loss) while chat ×3 boosted competing wrong readings, and the 0.6
threshold turned each single lost token into a test failure.

### Current state & risk
The 17:59 patch added **6** built-in overrides — `(chuc,ban)→chúc bạn`, `(may,gio)→mấy giờ`,
`(may,hom)→mấy hôm`, `(tot,lam)→tốt lắm`, `(roi,ban)→rồi bạn`, `(ban,qua)→bận quá` — which make the suite
green again **without fixing the assets**: case 49 outputs `bận quá` purely from the hardcoded phrase
(neither asset set contains a `qua` key, and live `ban` has no `bận`), and case 9 still gets `nhẹ`
(0.80 = 4/5; no `("ngon","nhe")` override). Any *unseen* phrasing still hits the degraded assets, and
`máy_hôm`/`sao_máy` remain live traps for nearby inputs.

### Recommended remediations (for the parent to decide; nothing executed here)
1. Rebuild with `--max-entries-per-word 8` (pin it in `rebuild_diacritic_assets.ps1`), restoring `lắm`, `bận`, …
2. Make the streaming build count-exact: raise `--bigram-prune-keep` above the true unique-bigram count
   (or disable prune) so mid-run pruning cannot reset counts; keep `--bigram-top-n` ≥ 220,000 with the
   final cut, or exclude chat-only keys from competing for the news top-N.
3. Reconsider chat weighting (×3 boosts `máy_hôm`/`sao_máy` noise); verify `chúc_bạn` ≥ 90 and
   `mấy_giờ` ≥ 81 in the rebuilt file as acceptance checks.
4. Keep the built-in phrase overrides as a belt-and-braces layer, but treat them as stopgap, not fix.

## Appendix — method & provenance
- All numbers measured from the files at `backend/data/diacritic/` (live md5 `048771ee2e2e`/`e9e91262457c`,
  backup `5808f062e0c0`/`3f77b5c1c4fa`) using `.venv\Scripts\python.exe`; JSON loaded fully, lookups NFC-folded
  (both asset sets are 100% NFC, so folding did not change any result).
- Real-code verification: `diacritic_restorer.py` exec'd in memory with `from app.*` imports stubbed;
  `_rule_restore` run over all 51 CSV rows; no test runner executed, no files written except this report.
- The pre-patch builtin set was reconstructed as "current 52 keys minus the 6 pairs whose key tokens and
  values both come from the failing vocabulary"; with that set, backup reproduces the "all pass" premise
  exactly (0 fails) and live reproduces exactly the 4 reported failures — strong mutual confirmation.
