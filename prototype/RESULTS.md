# XML-Run Merge Prototype — Final Results

## Test 1: python-docx-generated files (before Word editing)

| Template | Placeholders | 1-run | Multi-run | Lost |
|---|---|---|---|---|
| test_01_simple | 14 | 14 (100%) | 0 | 0 |
| test_02_formatting | 5 | 0 (0%) | 5 | 0 |
| test_03_table | 6 | 5 (83%) | 1 | 0 |
| test_04_real_layout | 17 | 17 (100%) | 0 | 0 |
| test_05_edge_cases | 11 | 11 (100%) | 0 | 0 |
| **TOTAL** | **53** | **47 (88%)** | **6 (12%)** | **0** |

## Test 2: After editing in Microsoft Word and re-saving

Word creates MORE fragmented XML-runs — 32% split rate vs 12%.

| Template | Placeholders | 1-run | Multi-run | Lost |
|---|---|---|---|---|
| test_01_simple | 14 | 14 (100%) | 0 | 0 |
| test_02_formatting | 5 | 0 (0%) | 5 | 0 |
| test_03_table | 6 | 5 (83%) | 1 | 0 |
| test_04_real_layout | 17 | 12 (70%) | 5 | 0 |
| test_05_edge_cases | 11 | 5 (45%) | 6 | 0 |
| **TOTAL** | **53** | **36 (67%)** | **17 (32%)** | **0** |

## Worst-case patterns observed

Word splits placeholders in various ways:

| Pattern | Example | Runs |
|---|---|---|
| {{  and }} in different runs | '{{ ', 'field', ' }}' | 3 |
| Extra fragmentation of }} | '{{ ', 'field', ' }', '}' | 4 |
| Underscore in field name triggers split | 'nds', '_20_', 'procentov' | 3 |
| Adjacent placeholder contamination | '{{ field1 }}{{ field2 }}' in one run | 2-3 |
| image: split from field name | '{{ ', 'image', ':field }}' | 3 |

**All patterns handled by merge-and-replace. 0 placeholders lost across all tests.**

## Merge-and-replace test on Word-edited files

| Input | Output | Remaining placeholders |
|---|---|---|
| test_02_formatting.docx | test_02_word_edited.docx | **0** ✅ |
| test_04_real_layout.docx | test_04_word_edited.docx | **0** ✅ |
| test_05_edge_cases.docx | test_05_word_edited.docx | **0** ✅ |

## Verdict

✅ **XML-run merge is VIABLE.** The prototype handles Word's aggressive run-splitting.

Next: open output files in Microsoft Word to verify that formatting (bold, italic, tables)
is preserved after merge-and-replace. If formatting is intact — we proceed to build the engine.
