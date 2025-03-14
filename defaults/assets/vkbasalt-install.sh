#!/bin/bash
set -eo pipefail

# Configuration
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
VKBASALT_PATH=${VKBASALT_PATH:-"$XDG_DATA_HOME/vkbasalt/installation"}
VKBASALT_BASE=${VKBASALT_PATH%/*}  # Parent directory of installation
RESHADE_REPO="https://github.com/gripped/vkBasalt-working-reshade-shaders.git"
RESHADE_BRANCH="master"
RESHADE_PATH="allshaders/reshade-shaders-working"

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
    
    local temp_dir=$(mktemp -d)
    /usr/bin/git clone --depth 1 -b ${RESHADE_BRANCH} ${RESHADE_REPO} "${temp_dir}"
    
    mkdir -p "$HOME/.config/reshade/"{Shaders,Textures}
    cp -r "${temp_dir}/${RESHADE_PATH}/Shaders/"* "$HOME/.config/reshade/Shaders/"
    cp -r "${temp_dir}/${RESHADE_PATH}/Textures/"* "$HOME/.config/reshade/Textures/"
    
    rm -rf "${temp_dir}"
    log_message "ReShade shaders installed for VkBasalt"
}

install_vkbasalt() {
    log_message "Starting VkBasalt installation..."
    local vkbasalt_pkg="/tmp/vkbasalt.tar.zst"
    local vkbasalt_lib32_pkg="/tmp/vkbasalt32.tar.zst"

    # Download packages
    wget -q "https://builds.garudalinux.org/repos/chaotic-aur/x86_64/vkbasalt-0.3.2.10-1.1-x86_64.pkg.tar.zst" -O "${vkbasalt_pkg}"
    wget -q "https://builds.garudalinux.org/repos/chaotic-aur/x86_64/lib32-vkbasalt-0.3.2.10-1.1-x86_64.pkg.tar.zst" -O "${vkbasalt_lib32_pkg}"

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