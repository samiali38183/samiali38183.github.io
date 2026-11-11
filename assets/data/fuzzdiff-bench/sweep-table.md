Inputs: 2000000 (999999 request, 500001 response, 500000 header block). All three parsers did the same thing on 1390722 (69.54%); they disagreed on 609278.

picohttpparser and fuzzdiff differed on 0 inputs (a non-zero number would be a bug and fail the tests). Disagreements explained by no known feature: 0. Disagreements that are only httparse rejecting an invalid prefix earlier: 36905.

Disagreements by entry point and outcome pattern (picohttpparser, fuzzdiff, httparse; `C` complete, `P` partial, `R` reject, `!` all complete but fields differ):

| Entry point | Pattern | Inputs |
|---|---|---|
| headers | CCR | 64870 |
| headers | PPR | 8272 |
| request | CCR | 270686 |
| request | PPR | 68826 |
| request | RRC | 46 |
| request | RRP | 1351 |
| response | CCC! | 13344 |
| response | CCR | 129628 |
| response | PPR | 45589 |
| response | RRC | 6132 |
| response | RRP | 534 |

Disagreements by attributed feature. Each disagreeing input is attributed to the smallest set of features whose removal (a rewrite of just that feature) makes all three parsers agree; an input attributed to two features counts under both, and "alone" counts the inputs where this feature is the whole explanation:

| Feature | Inputs attributed | Alone | Patterns (count) |
|---|---|---|---|
| obs-fold | 258293 | 116039 | CCR 233016, PPR 25277 |
| multi-space-start-line | 104350 | 24524 | CCC! 10136, CCR 85708, PPR 8477, RRC 29 |
| version-digits | 404441 | 219612 | CCR 338185, PPR 66256 |
| high-byte-start-line | 16527 | 11475 | CCC! 3406, CCR 10572, PPR 2431, RRC 118 |
| bare-lf | 213 | 213 | PPR 213 |
| bare-cr | 442 | 434 | PPR 358, RRP 84 |
| leading-empty-lines | 1492 | 1467 | RRC 123, RRP 1369 |
| header-line-without-colon | 1 | 1 | RRP 1 |
| status-code-range | 6495 | 6353 | RRC 6065, RRP 430 |
