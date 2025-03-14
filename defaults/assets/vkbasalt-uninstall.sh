#!/bin/bash
# Set strict error handling
set -euo pipefail

# Configuration
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
VKBASALT_PATH=${VKBASALT_PATH:-"$XDG_DATA_HOME/vkbasalt/installation"}
VKBASALT_BASE=${VKBASALT_PATH%/*}  # Parent directory of installation

log_message() {
    echo "[DEBUG] $1" >&2
}

remove_vkbasalt() {
    log_message "Removing VkBasalt installation..."
    
    # Remove libraries
    rm -f "$HOME/.local/lib/libvkbasalt.so"
    rm -f "$HOME/.local/lib32/libvkbasalt.so"
    
    # Remove JSON configuration files
    rm -f "$HOME/.local/share/vulkan/implicit_layer.d/vkBasalt.json"
    rm -f "$HOME/.local/share/vulkan/implicit_layer.d/vkBasalt.x86.json"
    
    # Remove configuration directory
    rm -rf "$HOME/.config/vkBasalt"
    
    # Don't remove reshade directory as it might be used by ReShade
    # Only remove if it's empty
    if [ -d "$HOME/.config/reshade" ]; then
        rmdir "$HOME/.config/reshade" 2>/dev/null || true
    fi
    
    # Remove VkBasalt paths and marker
    rm -rf "$VKBASALT_PATH"
    rm -f "$VKBASALT_BASE/.installed"
    
    log_message "VkBasalt removal completed"
    return 0
}

main() {
    if [[ ! -d "$VKBASALT_PATH" && ! -f "$VKBASALT_BASE/.installed" ]]; then
        echo "VkBasalt is not installed"
        exit 0
    fi
    
    log_message "Starting VkBasalt uninstallation..."
    remove_vkbasalt
    echo "VkBasalt uninstalled successfully"
}

main "$@"