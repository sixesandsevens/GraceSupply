#!/usr/bin/env bash
# Usage: ./backup_db.sh [label]
# Example: ./backup_db.sh pre-migration
set -euo pipefail

LABEL=${1:-backup}
DB=instance/gracesupply.db
DEST="instance/gracesupply-${LABEL}-$(date +%Y%m%d-%H%M).db"

if [ ! -f "$DB" ]; then
  echo "No database found at $DB"
  exit 1
fi

cp "$DB" "$DEST"
echo "Backed up to $DEST"
