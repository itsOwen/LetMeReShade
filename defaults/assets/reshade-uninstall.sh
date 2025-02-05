#!/bin/bash

RESHADE_PATH="$HOME/.local/share/reshade"
COMMON_OVERRIDES="d3d8 d3d9 d3d11 ddraw dinput8 dxgi opengl32"

log_message() {
    echo "[DEBUG] $1" >&2
}

remove_game_reshade() {
    local game_path="$1"
    
    log_message "Removing ReShade from: $game_path"
    log_message "Current files in game directory:"
    ls -la "$game_path" >&2
    
    # Remove all potential ReShade links
    for override in $COMMON_OVERRIDES; do
        if [[ -L "$game_path/${override}.dll" ]]; then
            log_message "Removing link: ${override}.dll"
            rm -fv "$game_path/${override}.dll"
        fi
    done
    
    local extras=("ReShade.ini" "ReShade32.json" "ReShade64.json" 
                 "d3dcompiler_47.dll" "ReShade_shaders" "ReShadePreset.ini")
    
    for extra in "${extras[@]}"; do
        if [[ -L "$game_path/$extra" ]]; then
            log_message "Removing link: $extra"
            rm -fv "$game_path/$extra"
        fi
    done
    
    if [[ -f "$game_path/ReShade.log" ]]; then
        log_message "Removing ReShade.log"
        rm -f "$game_path/ReShade.log"
    fi
    
    log_message "Removal completed"
    return 0
}

main() {
    if [[ $# -eq 0 ]]; then
        # Global uninstall
        if [[ ! -d "$RESHADE_PATH" ]]; then
            echo "ReShade is not installed"
            exit 0
        fi
        echo "Removing ReShade installation..."
        rm -rf "$RESHADE_PATH"
        echo "ReShade uninstalled successfully"
    else
        # Game-specific uninstall
        local game_path="$1"
        if [[ ! -d "$game_path" ]]; then
            echo "Error: Invalid game path: $game_path"
            exit 1
        fi
        remove_game_reshade "$game_path"
        echo "ReShade removed from game directory"
    fi
}

main "$@"