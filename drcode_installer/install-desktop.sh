#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$SCRIPT_DIR/drcode-installer.desktop"
ICONS_DIR="$HOME/.local/share/icons"
APPS_DIR="$HOME/.local/share/applications"

log_info() { echo "[INFO] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

if [ ! -f "$DESKTOP_FILE" ]; then
    log_error "Desktop file not found: $DESKTOP_FILE"
    exit 1
fi

log_info "Installing DR.CODE Installer to app drawer..."

mkdir -p "$ICONS_DIR"
mkdir -p "$APPS_DIR"

if [ -f "$SCRIPT_DIR/../frontend/public/favicon.svg" ]; then
    cp "$SCRIPT_DIR/../frontend/public/favicon.svg" "$ICONS_DIR/drcode.svg"
    sed -i 's|Icon=drcode|Icon='"$ICONS_DIR/drcode.svg"'|' "$DESKTOP_FILE"
    log_info "Icon installed"
fi

cp "$DESKTOP_FILE" "$APPS_DIR/drcode-installer.desktop"
chmod +x "$APPS_DIR/drcode-installer.desktop"

update-desktop-database "$APPS_DIR" 2>/dev/null || true

log_info "DR.CODE Installer installed successfully!"
log_info "Find it in your app drawer: 'DR.CODE Installer'"
