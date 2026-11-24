# Owner-Harm v3 offline audit

Run with Python 3.11+ from the repository root. Both input paths are required.
An absolute script path also works from another directory.

```sh
python3 scripts/audit_owner_harm.py \
  --dataset data/owner_harm_heldout_v3.json \
  --gate-cache data/eval_v3_results.json > owner-harm-audit.json
```

The dataset is a JSON array of cases. The checkpoint contains a `mode` and
a `per_case_results` array with `id`, `label`, `category`, and boolean
`blocked` fields. The audit rejects repeated JSON object fields, duplicate
or unmatched case IDs, and label or category mismatches. It checks optional
cached count totals against the case flags. The JSON report identifies
inputs by SHA-256 digest and includes per-case flags and L4 rule IDs,
per-category and overall counts, and gate-versus-L4 overlaps by row.
A zero denominator means that the corresponding rate is undefined.

The gate flags are cached decisions. The script reruns L4 in standalone
mode using the historical tool-call bundling and ground-truth-dependent
mock file contents. It counts an L4 recommendation to require confirmation
as flagged. It computes the OR on each row before aggregating.
It then groups identical scenarios by exact prompt, tool calls, label,
and category. JSON object-key order is ignored. Tool-call order is
preserved. Each group contributes one vote under strict majority, any
copy, and all copies. Strict-majority ties count as unflagged. The first
row ID in a group is its scenario ID. The output also counts scenarios
with conflicting cached gate flags across copies.

These are diagnostic replay results. The cache documents combined gate
decisions and carries no per-row input fingerprint. Its IDs, labels, and
categories support the join, while provenance still depends on supplying
the paired dataset and cache. The true label determines which mock reader
serves the requested path, so the same path can produce different content
and a different V1 finding depending on the label. The resulting rates
describe this replay with oracle-supplied file contents. A label-blind
deployment would need to be evaluated with its own file contents.
