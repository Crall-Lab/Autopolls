#!/bin/bash
# Replaces the placeholder username in all systemd service files with the
# current user (or a username passed as the first argument).

set -euo pipefail

SERVICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${1:-$USER}"

if ! id "$TARGET_USER" &>/dev/null; then
    echo "Error: user '$TARGET_USER' does not exist." >&2
    exit 1
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)

echo "Configuring service files for user: $TARGET_USER (home: $TARGET_HOME)"

SERVICE_FILES=(
    "$SERVICES_DIR/pcam@.service"
    "$SERVICES_DIR/pcam-ui.service"
    "$SERVICES_DIR/pcam-discover.service"
    "$SERVICES_DIR/pcam-overview.service"
    "$SERVICES_DIR/tfliteserve.service"
    "$SERVICES_DIR/pymicroclimate.service"
    "$SERVICES_DIR/run_discover.sh"
)

for f in "${SERVICE_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "Warning: $f not found, skipping." >&2
        continue
    fi
    # Replace User=<anything> and Group=<anything> (strips trailing comments too)
    sed -i \
        -e "s|^User=.*|User=$TARGET_USER|" \
        -e "s|^Group=.*|Group=$TARGET_USER|" \
        -e "s|home_dir/|/home/$TARGET_USER/|" \
        -e "s|chown user|chown $TARGET_USER|" \
        -e "s|chgrp user|chgrp $TARGET_USER|" \
        "$f"
    echo "  Updated: $(basename "$f")"
done

echo "Done. Reload systemd with: sudo systemctl daemon-reload"