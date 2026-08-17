#!/usr/bin/env bash
set -euo pipefail
SCIENCE_BRANCH="${ATLAS_SCIENCE_BRANCH:-morocco26-b2}"
SCIENCE_DIR="${ATLAS_SCIENCE_DIR:-/tmp/atlas395-science}"
RELEASE_MANIFEST="morocco26/atlas395/release_manifest.json"
INTAKE_DIR="morocco26/atlas395/intake"
rm -rf "$SCIENCE_DIR"
git fetch origin "$SCIENCE_BRANCH:refs/remotes/origin/$SCIENCE_BRANCH"
git worktree add --detach "$SCIENCE_DIR" "origin/$SCIENCE_BRANCH" >/dev/null
cleanup(){ git worktree remove --force "$SCIENCE_DIR" >/dev/null 2>&1 || true; }
trap cleanup EXIT
GOAL100="$SCIENCE_DIR/morocco26/data/goal100"
SNAPSHOT="$(python morocco26/scripts/atlas395_daily.py select-snapshot --goal100-root "$GOAL100" | tail -n 1)"
SCIENCE_REF="$(git -C "$SCIENCE_DIR" rev-parse HEAD)"
echo "Atlas Daily source: branch=$SCIENCE_BRANCH ref=$SCIENCE_REF snapshot=$SNAPSHOT"

# Product-side autonomous watch. It is deliberately quarantined from science
# and cannot alter any forecast value.
python morocco26/scripts/atlas395_intake.py \
  --surface "$GOAL100/b2_deterministic_acquisition_surface.json" \
  --out "$INTAKE_DIR" --days-back 4 --max-per-source 30

mkdir -p "$SCIENCE_DIR/morocco26/scripts"
cp morocco26/scripts/atlas395_export.py "$SCIENCE_DIR/morocco26/scripts/atlas395_export.py"
python "$SCIENCE_DIR/morocco26/scripts/atlas395_export.py" --snapshot "$SNAPSHOT"
rm -rf morocco26/web/data
mkdir -p morocco26/web/data
cp -R "$SCIENCE_DIR/morocco26/web/data/." morocco26/web/data/

# Merge detections into the reader-facing watch layer only. Forecast impact is
# hard-coded NONE until a later certified scientific snapshot admits evidence.
python morocco26/scripts/atlas395_apply_intake.py \
  --intake "$INTAKE_DIR/latest.json" \
  --evidence morocco26/web/data/evidence_index.json

python morocco26/scripts/atlas395_daily.py build-edition \
  --data-dir morocco26/web/data \
  --editions-dir morocco26/web/editions \
  --science-ref "$SCIENCE_REF" \
  --release-manifest "$RELEASE_MANIFEST"
python morocco26/scripts/validate_atlas395_views.py --require-daily
echo "ATLAS395_DAILY_PUBLISH_OK"
