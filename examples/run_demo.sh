#!/usr/bin/env bash
set -euo pipefail

demo_root="${1:-.expertcompose-demo}"
uv run expertcompose --workspace "$demo_root" init
uv run expertcompose --workspace "$demo_root" project create literature-review \
  --title "Literature Review" \
  --objective "Produce evidence-traceable reviews without hiding conflicting results"
uv run expertcompose --workspace "$demo_root" ingest literature-review \
  examples/sources/review.md examples/sources/session.json \
  --authorization "Repository-owned examples authorized for local demonstration"
uv run expertcompose --workspace "$demo_root" compose literature-review
uv run expertcompose --workspace "$demo_root" build literature-review
uv run expertcompose --workspace "$demo_root" evaluate literature-review
uv run expertcompose --workspace "$demo_root" approve literature-review --approved-by demo-reviewer
uv run expertcompose --workspace "$demo_root" publish literature-review --published-by demo-reviewer
