#!/usr/bin/env bash
# Build a clean public copy of the repo (single commit, no history).
# Usage: scripts/public_export.sh <out_dir>
# Removes raw Kalodata dumps, the API probe (the dated probe stays: test fixture), review logs (contain local paths
# and an e-mail), old screenshots with unblurred video frames, and the copied
# Kalodata API docs. Blurs the real video frames used by the pitch deck.
set -euo pipefail
out=${1:?out dir}
src=$(git rev-parse --show-toplevel)
rm -rf "$out"; mkdir -p "$out"
git -C "$src" archive HEAD | tar -x -C "$out"
cd "$out"
rm -rf data/raw reports/agy/media_analysis_*.json reports/api_probe.json \
  reports/*.log docs/kalodata_api docs/build/shots docs/build/logs \
  reports/audit/shots docs/shots/v2_web docs/shots/v2_web2 .claude
for f in docs/pitch/assets/frame_*.webp; do
  [ -e "$f" ] && magick "$f" -blur 0x14 "$f"
done
mail=$(git -C "$src" config user.email || echo none@invalid)
if grep -rIlF -e "$mail" . || grep -rIl -E "sk-or-v1-[a-f0-9]{20}|AIza[0-9A-Za-z_-]{30}" . ; then
  echo "private data found above; stop" >&2; exit 1
fi
echo "export ok: $(find . -type f | wc -l) files, $(du -sh . | cut -f1)"
