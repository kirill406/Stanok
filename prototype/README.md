# Prototype: XML-Run Merge for .docx {{ }} placeholders

## Purpose

Проверка ключевого технического риска: может ли движок надёжно находить и заменять {{ }}-плейсхолдеры в .docx-файлах после того, как Word разбил их на несколько XML-ранов.

## Files

| File | Purpose |
|---|---|
| generate_test_templates.py | Creates 5 test .docx with varied formatting |
| 	est_run_merge.py | Analyzes .docx: finds placeholders, counts split runs |
| 	est_merge_and_replace.py | Open .docx, merge runs, replace placeholders, save |

## Test Templates

| Template | Description | Risk |
|---|---|---|
| 	est_01_simple.docx | Plain placeholders, no formatting | Low |
| 	est_02_formatting.docx | Bold/italic BREAKS placeholders across 3 runs | **High** |
| 	est_03_table.docx | Table with placeholders | Medium |
| 	est_04_real_layout.docx | Realistic contract layout | Medium |
| 	est_05_edge_cases.docx | Adjacent, long names, line breaks | Low |

## Results (python-docx-generated files)

- **53 placeholders** in 5 templates
- **47 (88%)** — single XML run, no split
- **6 (12%)** — split across 3 runs (when formatting changes inside placeholder)
- **0 lost** — all found after merge
- **All replaced** — merge+replace produces valid .docx

## Critical Real-World Test

The python-docx library does NOT produce the same XML structure as Microsoft Word.
We need to:

1. Open 	est_02_formatting.docx, 	est_04_real_layout.docx, 	est_05_edge_cases.docx in **Microsoft Word**
2. Make minor formatting edits near placeholders
3. Save
4. Re-run python prototype/test_run_merge.py

Word will likely produce MORE split-placeholders than python-docx. This test
will reveal the true split rate and whether our merge approach handles it.
