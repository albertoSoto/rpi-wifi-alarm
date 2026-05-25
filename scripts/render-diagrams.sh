#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

DIR=docs/diagrams
for f in "$DIR"/*.mmd; do
  name=$(basename "$f" .mmd)
  echo "rendering $name.svg"
  npx -y -p @mermaid-js/mermaid-cli mmdc -i "$f" -o "$DIR/$name.svg" -b transparent
done
