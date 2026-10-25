# Results Template (fill ONLY from real execution output)

## Dataset
| Item | Value |
|---|---|
| Name / source / licence | [..] |
| Original records | [..] |
| Usable records | [..] |
| Date range (UTC) | [..] -> [..] |
| Topic mode / granularity | [..] / [..] |

## Cleaning summary
| Metric | Value |
|---|---|
| Duplicates | [..] |
| Missing/invalid timestamps | [..] |
| Empty text | [..] |
| Records retained / rejected | [..] / [..] |

## MapReduce
| Item | Value |
|---|---|
| MongoDB version / PyMongo version | [..] / [..] |
| Job 1 input -> emit -> output | [..] |
| Job 2 input -> output | [..] |
| Independent validation | [valid / problems] |

## Detection
Parameters used: [paste detection_params.json]
| Topic | Earlier peak | Decline % | Quiet periods | Baseline | Current | Growth % | Status |
|---|---|---|---|---|---|---|---|
| [..] | | | | | | | potential comeback |

Threshold sensitivity (candidates found at different settings): [..]

## Tests
`python -m pytest -v` -> [N passed, M failed]
## Observations and caveats
[Write only what the data shows. Do not claim real-world popularity.]
