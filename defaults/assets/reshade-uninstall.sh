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
    
    # Remove ReShade files (excluding ReShadePreset.ini to preserve user settings)
    local extras=("ReShade.ini" "ReShade32.json" "ReShade64.json" 
                 "d3dcompiler_47.dll" "ReShade_shaders" "ReShade_README.txt")
    # Note: ReShadePreset.ini is intentionally excluded to preserve user settings
    
    for extra in "${extras[@]}"; do
        if [[ -L "$game_path/$extra" ]]; then
            log_message "Removing link: $extra"
            rm -fv "$game_path/$extra"
        elif [[ -f "$game_path/$extra" ]]; then
            log_message "Removing file: $extra"
            rm -fv "$game_path/$extra"
        fi
    done
    
    if [[ -f "$game_path/ReShade.log" ]]; then
        log_message "Removing ReShade.log"
        rm -f "$game_path/ReShade.log"
    fi
    
    # Check if ReShadePreset.ini exists and inform user it's preserved
    if [[ -f "$game_path/ReShadePreset.ini" ]]; then
        log_message "ReShadePreset.ini preserved to keep user shader presets"
    fi
    
    log_message "Removal completed - ReShadePreset.ini preserved if it existed"
    return 0
}

main() {
    if [[ $# -eq 0 ]]; then
        # Global uninstall
        if [[ ! -d "$RESHADE_PATH" ]]; then
            echo "ReShade is not installed"
            exit 0
        fi
        
        # Before removing the global installation, inform about preserved presets
        echo "Removing ReShade installation..."
        echo "Note: Any ReShadePreset.ini files in game directories will be preserved."
        
        rm -rf "$RESHADE_PATH"
        echo "ReShade uninstalled successfully"
        echo "Individual game ReShadePreset.ini files have been preserved to maintain your shader configurations."
    else
        # Game-specific uninstall
        local game_path="$1"
        if [[ ! -d "$game_path" ]]; then
            echo "Error: Invalid game path: $game_path"
            exit 1
        fi
        remove_game_reshade "$game_path"
        echo "ReShade removed from game directory"
        if [[ -f "$game_path/ReShadePreset.ini" ]]; then
            echo "Your shader presets (ReShadePreset.ini) have been preserved."
        fi
    fi
}

main "$@"