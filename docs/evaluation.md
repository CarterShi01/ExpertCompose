# Evaluation contract

ExpertCompose distinguishes three questions:

1. **Is it well formed?** Provenance resolves, the graph is navigable, required
   Tools are bound, and Contexture compiles it.
2. **Can an agent use it?** A real Host runs held-out tasks and returns neutral
   observations.
3. **Is it better and safe enough?** Domain owners compare baselines, inspect
   errors, and approve policy thresholds.

The MVP fully automates the first question and defines a portable receipt for
the second. It does not pretend those answer the third.

Run `expertcompose suite PROJECT` to create task cases and an observation
template. A Host should execute only the published/generated ExpertNet surface,
record which Contexture refs it opened or invoked, list evidence refs appearing
in the result, score its rubric, and preserve notes or metrics. Then pass the
completed file to:

```bash
expertcompose evaluate PROJECT --observations observations.json --require-behavioral
```

An observation set passes only when it contains every expected case, no unknown
case, and every case is marked passed. The current schema intentionally does
not trust a particular runner. Production deployments should sign receipts,
pin Host/model/tool versions, include cost/latency/tokens, compare a no-ExpertNet
baseline, and define minimum sample sizes and regression thresholds.

Structural warnings, such as a selected source contributing no evidence, are
visible but do not fail v0.1. Organizations can harden policy by promoting
warnings to failures before approving a release.
