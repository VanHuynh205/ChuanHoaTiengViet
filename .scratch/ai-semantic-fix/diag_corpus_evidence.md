# Corpus Evidence Diagnosis — "chat domain" vs news for diacritic restoration

**Date:** 2026-09-21 · **Scope:** read-only measurement of `backend/data/DataDauCau/` corpora + live assets · **No code/config/data modified.**
**Method:** Python streaming scripts (`.venv\Scripts\python.exe`), `csv.DictReader`, token = `\w+` on NFC-normalized lowercased text; bigram = adjacent token pair counted in the **with_diacritics** column (this matches the builder: `build_diacritic_streaming.py` L207–209 counts bigrams from `tokenize_words(with_d)` × weight). News streamed line-by-line (never fully loaded); progress every 500k rows. News totals: **val 1,254,965 + train 10,039,717 = 11,294,682 rows** (1.9 GB).

---

## 1. Chat file profiles

| File | Rows | Words (with_diacritics, ws-split) | Domain verdict |
|---|---:|---:|---|
| `chat/Dev.csv` | 1,111 | 39,016 | **Smartphone e-commerce reviews** (vivo: "Máy ok, k chê điểm nào, chính thức là fans ViVo…") |
| `chat/Test.csv` | 2,223 | 80,622 | **Smartphone reviews** (facelock, TGDĐ/Thế Giới Di Động, vivo91c, pin/camera) |
| `chat/Train.csv` | 7,784 | 282,727 | **Smartphone reviews** (thegioididong, oppo/iphone/realme, "pin trâu") |
| `chat/history_export.csv` | 9 | 290 | **Genuine informal chat** (office/smalltalk) — the only real chat-domain file |

- Top tokens in all 3 review files: **máy** (8,195 total), mua, pin, hình, game — device vocabulary, zero conversational phatic text.
- `convert_chat_corpus.py`: converts `_raw/*.csv` (raw `comment` column; docstring says "raw comment dataset (e.g. UIT-ViSFD)") into no_diacritics/with_diacritics via synthetic NFD-strip + đ→d; filters min-words 3, dedup. `_raw/` contains only: `Dev.csv` (309,271 B), `Test.csv` (636,268 B), `Train.csv` (2,240,007 B). Content = **ViSFD-style smartphone feedback** (7,784+2,223+1,111 = 11,118 rows), **not student/course feedback and not chat**.
- First 3 rows (200c) per file are excerpted in the analysis transcript; representative: Train row 1 "Mới mua máy này Tại thegioididong thốt nốt…"; Test row 1 "Điện thoải ổn. Facelock cực nhanh…"; Dev row 1 "Máy ok, k chê điểm nào…".

## 2. Chat n-gram counts (with_diacritics column; ×3 = weighted contribution at ChatWeight 3)

| Item | Dev | Test | Train | hist | Chat total | **×3** | News (11.29M rows) | Asset bigram_freq |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| chúc bạn | 0 | 0 | 0 | 0 | **0** | **0** | 90 | **ABSENT** |
| mấy giờ | 0 | 0 | 0 | 0 | **0** | **0** | 81 | **ABSENT** |
| rồi bạn | 0 | 0 | 0 | 0 | **0** | **0** | 102 | 103 ✓ |
| tốt lắm | 7 | 8 | 27 | 0 | 42 | **126** | 150 | 267 ✓ |
| bận quá | 0 | 0 | 1 | 0 | 1 | **3** | 27 | **ABSENT** |
| bạn quá | 0 | 0 | 1 | 0 | 1 | **3** | 164 | 167 ✓ |
| ngủ ngon | 0 | 0 | 0 | 0 | **0** | **0** | 1,265 | 1,260 ✓ |
| hôm nay | 11 | 29 | 71 | 8 | 119 | **357** | 35,796 | ✓ |
| quá vậy | 1 | 1 | 6 | 0 | 8 | **24** | 49 | **ABSENT** |
| nhé (1g) | 24 | 62 | 186 | 6 | 278 | 834 | 5,443 | — |
| lắm (1g) | 99 | 211 | 686 | 0 | 996 | 2,988 | 12,651 | — |
| bận (1g) | 1 | 1 | 11 | 0 | 13 | 39 | 5,923 | — |
| chúc (1g) | 2 | 3 | 16 | 0 | 21 | 63 | 18,121 | — |
| mấy (1g) | 67 | 150 | 524 | 0 | 741 | 2,223 | 10,533 | — |
| chức (1g) | 18 | 30 | 98 | 0 | 146 | 438 | 232,198 | — |
| bán (1g) | 22 | 41 | 155 | 0 | 218 | 654 | 231,554 | — |
| máy (1g) | 781 | 1,673 | 5,741 | 0 | 8,195 | 24,585 | 230,866 | — |
| làm (1g) | 42 | 107 | 421 | 1 | 571 | 1,713 | 501,377 | — |

Chain-link bigrams (needed to assemble the trap sentences):

| Link | Chat total (×3) | News | Asset |
|---|---:|---:|---|
| bạn ngủ | 0 (0) | 211 | 209 ✓ |
| ngủ ngon nhé | 0 (0) | 5 | ABSENT |
| ngon nhé | 0 (0) | 10 | ABSENT |
| mấy giờ rồi | 0 (0) | 3 | ABSENT |
| giờ rồi | 2 (6) | 56 | ABSENT |
| sao mấy | 8 (24) | 10 | ABSENT |
| mấy hôm | 24 (72) | 261 | 330 ✓ |
| nay bạn | 2 (6) | 202 | 211 ✓ |
| chúc bạn ngủ (3-g) | 0 | 0 | n/a |
| bạn quá vậy (3-g) | 0 | 0 | n/a |

No-diacritics column counts (loose substring on token-joined text — may overcount, e.g. "máy giới hạn" matches "may gio"): chuc ban=0, may gio=6, roi ban=2, tot lam=47, ban qua=6. **All 4 trap phrases ('chuc ban ngu ngon nhe', 'may gio roi ban', 'tot lam', 'sao may hom nay ban qua vay') occur 0 times in every chat file (both columns).**

## 3. Live-asset cross-check (decisive; `backend/data/diacritic/`, manifest 2026-09-21, inputs = val+train+4 chat files, overwrite mode)

- `bigram_freq.json`: 200,000 entries; **cutoff count = 82.0** (200k-th value). ABSENT: `chúc_bạn`, `mấy_giờ`, `bận_quá`, `quá_vậy`, `ngon_nhé`, `giờ_rồi`, `sao_mấy` — none present in NFC **or** NFD key variants (not a Unicode-fragmentation artifact). Present: `tốt_lắm`=267, `rồi_bạn`=103, `bạn_quá`=167, `ngủ_ngon`=1,260, `bạn_ngủ`=209, `mấy_hôm`=330, `nay_bạn`=211.
  - Mechanics: during news processing, bigrams are **lossily pruned to top-300k at every 1M-line chunk** (L226–229); a bigram as rare as "chúc bạn" (~8 per chunk) is wiped mid-stream and cannot re-accumulate; final top-200k cutoff = 82 then drops the residue ("mấy_giờ" misses by **one**: 81 < 82). Chat files are processed **last** (manifest order: val, train, Dev, history_export, Test, Train) and never hit a chunk boundary, so a chat bigram only needs ≥82 weighted (≥28 raw rows ×3) to survive into the final asset.
- `word_map.json`: 7,170 entries. `chuc`→[chức, chục, **chúc**(3rd), chực, chuc]; `may`→[**máy**, may, **mấy**(3rd), mây, mày]; `ban`→[bản, **bán**, **bạn**(3rd), ban, bàn]; `qua`→**ABSENT** (bare "qua" is the top form ⇒ key dropped by the `forms[0] != nd_word` rule, L287 — so "qua→quá" has **no map entry at all**). `lam`→[làm, lâm, lãm, lạm, lầm] — **"lắm" is missing entirely**, although bigram_freq contains 51 `lắm_*`/`*_lắm` entries summing 10,162 from the same build: an asset-internal inconsistency (merge/provenance or top-10-candidate truncation) that needs a dedicated build-side investigation; corpus-side evidence for "lắm" (news 12,651 + chat 2,988 weighted) is ample.
- Keys whose bare form dominates are dropped **by design** (trong, nam, con, theo, xem, an, thi… all ABSENT) — this is why the map is small (7,170), not a bug per se.

## 4. history_export.csv (task 4)

9 rows, 290 words. Full with_diacritics text (all < 500 words, shown verbatim in transcript): "Hôm nay đi đk thẻ ngân hàng phải không" / "…pk" / "Sắp đèn đỏ an chuyên ngành rồi. Giờ mới bắt đầunâng cấpvà sửa lỗi hệ thống…" / 4 near-duplicate office variants ("Chuyện trong công ty hôm nay đã giải quyết sao rồi… khó tính đấy/dậy nhé… tiếp đãi/đại…") / "Hôm nay bạn đã ăn cơm chưa vậy" / "Hôm nay bạn đã an sáng chưa".
- **None of the 4 trap phrases appear** (all = 0). It contains "hôm nay bạn…" (nay bạn=2) but no "chúc bạn/mấy giờ/rồi bạn/tốt lắm/bận".
- `export_history_corpus.py`: `SELECT input_text, output_text FROM dbo.normalization_history ORDER BY created_at DESC OFFSET 0 FETCH NEXT :limit` with **limit default 200,000**, filters min-words 4 / max-words 120, dedup by output casefold. **No script-side limit explains 9 rows** — the table simply contained only 9 qualifying rows at export time (script prints "scanned N, wrote 9"; a 0-row table would print an explicit note). Rows 4–7 also retain imperfect system outputs ("dậy nhé", "tiếp đại", "Giờ thi") — near-duplicate noise.

## 5. VERDICT

**(a) Can chat + weight 3 flip any needed bigram? NO.**
Chat contributes **0** to `chúc bạn`, `mấy giờ`, `rồi bạn`, `ngủ ngon` — nothing to flip. Its only sizable item, `tốt lắm` (126 weighted vs news 150), *reinforces* a bigram both corpora already agree on (46% share, no polarity flip). No needed item has chat×3 > news (máy 9.6% share, mấy 17.4%, lắm 19.1%, bạn 0.9%). Moreover the asset layer discards the evidence the corpora *do* contain: `chúc_bạn` (90) and `mấy_giờ` (81) are absent from live bigram_freq due to the lossy per-chunk prune + 82-count cutoff — the regression gate failed on evidence that exists in the corpus but cannot reach the asset at current weights/pruning.

**(b) Does the content actively boost WRONG candidates? YES.**
News priors: chức 232,198 (12.8:1 vs chúc), bán 231,554 (> bạn; even +2,043 chat-weighted bạn loses, 225,134 vs 232,208), máy 230,866 (13.4:1 vs mấy), làm 501,377 (32:1 vs lắm). The "chat" corpus is **smartphone reviews**, so it *worsens* the ratio where it speaks loudest: it adds máy 24,585 vs mấy 2,223 (11:1) — pushing máy:mấy to **14.9:1** — and chức 438 vs chúc 63 (7:1). word_map ordering is exactly backwards for the traps: máy(1st)/mấy(3rd), chức(1st)/chúc(3rd), bán(2nd)/bạn(3rd), and `qua` has no entry. Only genuine chat (`history_export.csv`, 290 words) points the right way — ~0.07% of chat weight.

**(c) Minimum additional evidence needed.**
1. **Missing entirely from BOTH corpora (unbuildable today):** the 3-gram chains "chúc bạn ngủ" and "bạn quá vậy" — and from chat, **every** trap bigram (chúc bạn, mấy giờ, rồi bạn, ngủ ngon = 0; bận quá/bạn quá = 1).
2. **Missing from the asset despite corpus presence:** chúc_bạn, mấy_giờ, bận_quá, quá_vậy, ngon_nhé, giờ_rồi, sao_mấy (all < 82 or chunk-pruned).
3. **Minimum seed:** since chat files are processed last (no chunk prune) at weight 3, each needed bigram needs **≥ 82 weighted = ≥ 28 raw chat rows** to enter `bigram_freq` (vs min-freq 2 for word_map candidacy). Seed real conversational rows containing: "chúc bạn (ngủ ngon nhé)", "mấy giờ (rồi) bạn", "bận quá", "(bạn) quá vậy", "ngon nhé" — ~30–100 rows per pattern; `tốt lắm` and `ngủ ngon` already survive via news.
4. **Non-corpus blockers found en route:** word_map["lam"] lacks "lắm" (asset inconsistency despite bigram evidence), `qua` key dropped entirely, and `mấy_giờ` missed the cutoff by 1 — these need build-side fixes (protect/bucket chat bigrams, merge-mode audit), not just more data.

## Caveats
- ND-column counts use substring matching on token-joined text (loose; can overcount). WD bigram counts are strict adjacent-token counts; builder's tokenizer (whitespace + edge-punct strip + isalpha-only) explains ±0.3–4% deltas vs asset values (e.g. tốt_lắm 276 vs 267).
- Restorer scoring internals were not inspected (out of scope); "rồi_bạn"=103 exists in the asset yet `may gio roi ban` failed — that points at restorer-side thresholds or the missing first links (`mấy_giờ`, `giờ_rồi`).
