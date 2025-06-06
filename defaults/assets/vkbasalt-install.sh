#!/bin/bash
set -eo pipefail

# Configuration
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
VKBASALT_PATH=${VKBASALT_PATH:-"$XDG_DATA_HOME/vkbasalt/installation"}
VKBASALT_BASE=${VKBASALT_PATH%/*}  # Parent directory of installation

# Get the correct path to the bin directory - check both possible locations
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Check if we're in defaults/assets (development)
if [[ "$SCRIPT_DIR" == */defaults/assets ]]; then
    PLUGIN_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two directories from defaults/assets
# Check if we're in assets (decky store)
elif [[ "$SCRIPT_DIR" == */assets ]]; then
    PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"  # Go up one directory from assets
else
    # Fallback - assume we're in assets
    PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
fi

BIN_PATH="$PLUGIN_ROOT/bin"

log_message() {
    echo "[DEBUG] $1" >&2
}

setup_directories() {
    mkdir -p "$VKBASALT_PATH"
    mkdir -p "$HOME/.local/"{lib,lib32,share/vulkan/implicit_layer.d}
    mkdir -p "$HOME/.config/"{vkBasalt,reshade}
}

install_reshade_shaders() {
    log_message "Setting up ReShade shaders for VkBasalt..."
    
    # Check if bin directory exists
    if [[ ! -d "$BIN_PATH" ]]; then
        log_message "Error: Bin directory not found at $BIN_PATH"
        log_message "Script directory: $SCRIPT_DIR"
        log_message "Plugin root: $PLUGIN_ROOT"
        exit 1
    fi
    
    # Check if shader file exists
    if [[ ! -f "$BIN_PATH/vkbasalt_shaders.tar.gz" ]]; then
        log_message "Error: vkbasalt_shaders.tar.gz not found in bin directory"
        exit 1
    fi
    
    # Use bundled VkBasalt shaders
    log_message "Using bundled VkBasalt ReShade shaders"
    mkdir -p "$HOME/.config/reshade/"{Shaders,Textures}
    tar -xzf "$BIN_PATH/vkbasalt_shaders.tar.gz" -C "$HOME/.config/reshade/"
    
    log_message "ReShade shaders installed for VkBasalt"
}

install_vkbasalt() {
    log_message "Starting VkBasalt installation..."
    local vkbasalt_pkg="/tmp/vkbasalt.tar.zst"
    local vkbasalt_lib32_pkg="/tmp/vkbasalt32.tar.zst"

    # Check if bin directory exists
    if [[ ! -d "$BIN_PATH" ]]; then
        log_message "Error: Bin directory not found at $BIN_PATH"
        exit 1
    fi
    
    # Check if VkBasalt packages exist
    if [[ ! -f "$BIN_PATH/vkbasalt_package.tar.zst" ]]; then
        log_message "Error: vkbasalt_package.tar.zst not found in bin directory"
        exit 1
    fi
    
    if [[ ! -f "$BIN_PATH/vkbasalt_package_lib32.tar.zst" ]]; then
        log_message "Error: vkbasalt_package_lib32.tar.zst not found in bin directory"
        exit 1
    fi

    # Use bundled VkBasalt packages
    log_message "Using bundled VkBasalt packages"
    cp "$BIN_PATH/vkbasalt_package.tar.zst" "${vkbasalt_pkg}"
    cp "$BIN_PATH/vkbasalt_package_lib32.tar.zst" "${vkbasalt_lib32_pkg}"

    # Extract files
    tar xf "${vkbasalt_pkg}" --strip-components=2 \
        --directory="$HOME/.local/lib/" usr/lib/libvkbasalt.so
    tar xf "${vkbasalt_lib32_pkg}" --strip-components=2 \
        --directory="$HOME/.local/lib32/" usr/lib32/libvkbasalt.so

    # Configure VkBasalt
    tar xf "${vkbasalt_pkg}" --to-stdout usr/share/vulkan/implicit_layer.d/vkBasalt.json \
        | sed -e "s|libvkbasalt.so|$HOME/.local/lib/libvkbasalt.so|" \
              -e "s/ENABLE_VKBASALT/ENABLE_VKBASALT/" \
        > "$HOME/.local/share/vulkan/implicit_layer.d/vkBasalt.json"
    tar xf "${vkbasalt_lib32_pkg}" --to-stdout usr/share/vulkan/implicit_layer.d/vkBasalt.x86.json \
        | sed -e "s|libvkbasalt.so|$HOME/.local/lib32/libvkbasalt.so|" \
              -e "s/ENABLE_VKBASALT/ENABLE_VKBASALT/" \
        > "$HOME/.local/share/vulkan/implicit_layer.d/vkBasalt.x86.json"

    # Create default configuration
    cat > "$HOME/.config/vkBasalt/vkBasalt.conf" << 'EOL'
effects = cas:clarity
reshadeTexturePath = "/home/deck/.config/reshade/Textures"
reshadeIncludePath = "/home/deck/.config/reshade/Shaders"
clarity = /home/deck/.config/reshade/Shaders/Clarity.fx
depthCapture = off
toggleKey = Home
enableOnLaunch = False
casSharpness = 0.4
dlsSharpness = 0.5
dlsDenoise = 0.17
fxaaQualitySubpix = 0.75
fxaaQualityEdgeThreshold = 0.125
fxaaQualityEdgeThresholdMin = 0.0312
smaaEdgeDetection = luma
smaaThreshold = 0.05
smaaMaxSearchSteps = 32
smaaMaxSearchStepsDiag = 16
smaaCornerRounding = 25
EOL

    # Cleanup
    rm -f "${vkbasalt_pkg}" "${vkbasalt_lib32_pkg}"

    # Create installation marker in the base directory
    touch "$VKBASALT_BASE/.installed"
    log_message "VkBasalt installation complete"
}

main() {
    # Debug output for file paths
    log_message "Script directory: $SCRIPT_DIR"
    log_message "Plugin root: $PLUGIN_ROOT"
    log_message "Bin path: $BIN_PATH"
    
    if [ ! -f /etc/os-release ] || ! grep -q SteamOS /etc/os-release; then
        echo "This script should only be run on a Steam Deck running SteamOS"
        exit 1
    fi

    if [ "$EUID" -eq 0 ]; then
        echo "This script should not be run as root"
        exit 1
    fi

    setup_directories
    install_vkbasalt
    install_reshade_shaders
    echo "VkBasalt installed successfully!"
    echo "Use ENABLE_VKBASALT=1 %command% in Steam launch options to enable"
}

main "$@"