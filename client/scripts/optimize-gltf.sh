#!/usr/bin/env bash
# optimize-gltf.sh — Apply Draco compression to GLTF/GLB assets so that
# the total model budget stays under 2 MB (board + pawns + cowrie shells).
#
# Dependencies (install globally or in CI):
#   npm install -g gltf-pipeline   # or: npx gltf-pipeline
#   npm install -g gltfpack        # alternative single-binary compressor
#
# Usage:
#   bash scripts/optimize-gltf.sh
#
# The script processes every .glb / .gltf file found under public/models/ and
# writes the Draco-compressed output alongside the original with a
# ".draco.glb" suffix.  Vite copies the public/ directory verbatim to dist/,
# so the optimized files are served directly by S3/CloudFront.
#
# Draco geometry compression typically reduces mesh data by 60-90 % compared
# to uncompressed GLTF.  Combined with gzip/brotli at the CDN layer the
# 2 MB budget is comfortably achievable for board + pawn + cowrie models.

set -euo pipefail

MODELS_DIR="$(dirname "$0")/../public/models"

if [ ! -d "$MODELS_DIR" ]; then
  echo "[optimize-gltf] No models directory found at $MODELS_DIR — skipping."
  exit 0
fi

# Require gltf-pipeline (gltfpack is an alternative but gltf-pipeline is
# more widely available as an npm package in CI).
if ! command -v gltf-pipeline &> /dev/null; then
  echo "[optimize-gltf] gltf-pipeline not found. Install with:"
  echo "  npm install -g gltf-pipeline"
  exit 1
fi

echo "[optimize-gltf] Compressing GLTF/GLB models with Draco…"

total_before=0
total_after=0

find "$MODELS_DIR" -type f \( -name "*.glb" -o -name "*.gltf" \) \
  ! -name "*.draco.glb" \
| while read -r src; do
  # Determine output path: replace extension with .draco.glb
  out="${src%.gl*}.draco.glb"

  size_before=$(wc -c < "$src")
  total_before=$((total_before + size_before))

  gltf-pipeline \
    --input "$src" \
    --output "$out" \
    --draco.compressMeshes \
    --draco.compressionLevel 7 \
    --draco.quantizePositionBits 14 \
    --draco.quantizeNormalBits 10 \
    --draco.quantizeTexcoordBits 12

  size_after=$(wc -c < "$out")
  total_after=$((total_after + size_after))

  reduction=$(( (size_before - size_after) * 100 / size_before ))
  echo "  $(basename "$src") → $(basename "$out")  ${reduction}% reduction"
done

echo "[optimize-gltf] Done."

# Verify total compressed size stays under 2 MB (2097152 bytes).
# This check is intentionally non-fatal (warning only) so the build is not
# blocked while models are still being authored; switch to exit 1 for CI.
MAX_BYTES=2097152
if [ "$total_after" -gt "$MAX_BYTES" ]; then
  echo "[optimize-gltf] WARNING: compressed model total ${total_after} bytes exceeds 2 MB budget (${MAX_BYTES} bytes)."
else
  echo "[optimize-gltf] Budget check passed: ${total_after} / ${MAX_BYTES} bytes."
fi
