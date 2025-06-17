#!/bin/bash

SEPERATOR="------------------------------------------------------------------------------------------------"
COMMON_OVERRIDES="d3d8 d3d9 d3d11 ddraw dinput8 dxgi opengl32"
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
MAIN_PATH=${MAIN_PATH:-"$XDG_DATA_HOME/reshade"}
RESHADE_PATH="$MAIN_PATH/reshade"
WINE_MAIN_PATH="$(echo "$MAIN_PATH" | sed "s#/home/$USER/##" | sed 's#/#\\\\#g')"
VULKAN_SUPPORT=${VULKAN_SUPPORT:-0}
GLOBAL_INI=${GLOBAL_INI:-"ReShade.ini"}
DELETE_RESHADE_FILES=${DELETE_RESHADE_FILES:-0}

log_message() {
    echo "[DEBUG] $1" >&2
}

detect_game_arch_and_api() {
    local game_path="$1"
    local arch="32"
    local detected_api="d3d9"
    
    log_message "Analyzing game directory: $game_path"
    
    # Find all exe files in root directory
    local exes=()
    while IFS= read -r -d '' exe; do
        exes+=("$exe")
    done < <(find "$game_path" -maxdepth 1 -name "*.exe" -print0)
    
    for exe in "${exes[@]}"; do
        log_message "Checking EXE: $exe"
        
        # Skip launchers and utilities
        if [[ "$exe" =~ [Ll]auncher|[Cc]rash|[Ss]etup|[Uu]nins|[Rr]edist ]]; then
            log_message "Skipping utility executable: $exe"
            continue
        fi
        
        # Get file info
        local file_info=$(file "$exe")
        log_message "File info: $file_info"
        
        # Check for 64-bit (PE32+ or x86-64)
        if echo "$file_info" | grep -Eq "x86-64|PE32\+"; then
            log_message "Detected 64-bit executable: $exe"
            arch="64"
            detected_api="dxgi"
            break
        fi
    done

    # Secondary check for common DLLs
    if [[ "$arch" == "64" ]]; then
        [[ -f "$game_path/dxgi.dll" || -f "$game_path/d3d11.dll" ]] && detected_api="dxgi"
        [[ -f "$game_path/d3d9.dll" ]] && detected_api="d3d9"
    else
        [[ -f "$game_path/d3d9.dll" ]] && detected_api="d3d9"
        [[ -f "$game_path/d3d11.dll" ]] && detected_api="d3d11"
    fi

    echo "${arch},${detected_api}"
}

setup_game_reshade() {
    local game_path="$1"
    local dll_override="$2"
    local arch="$3"
    
    log_message "Setting up ReShade:"
    log_message "Game path: $game_path"
    log_message "DLL override: $dll_override"
    log_message "Architecture: $arch-bit"
    
    # Verify ReShade installation
    if [ ! -d "$RESHADE_PATH/latest" ]; then
        log_message "Error: ReShade is not installed in $RESHADE_PATH/latest"
        return 1
    fi
    
    # Check ReShade DLL
    local reshade_dll="ReShade${arch}.dll"
    if [ ! -f "$RESHADE_PATH/latest/$reshade_dll" ]; then
        log_message "Error: Required ReShade DLL not found: $reshade_dll"
        return 1
    fi

    # Check d3dcompiler
    local d3dcompiler="$RESHADE_PATH/d3dcompiler_47.dll.${arch}"
    if [ ! -f "$d3dcompiler" ]; then
        log_message "Error: d3dcompiler_47.dll not found for $arch-bit"
        return 1
    fi

    # Create symbolic links
    log_message "Creating symbolic links..."
    
    # Link ReShade DLL
    log_message "Linking ReShade DLL: $reshade_dll -> $dll_override.dll"
    [ -L "$game_path/$dll_override.dll" ] && unlink "$game_path/$dll_override.dll"
    if ! ln -sfv "$RESHADE_PATH/latest/$reshade_dll" "$game_path/$dll_override.dll"; then
        log_message "Failed to create DLL symlink"
        return 1
    fi
    
    # Link d3dcompiler
    log_message "Linking d3dcompiler: $d3dcompiler"
    [ -L "$game_path/d3dcompiler_47.dll" ] && unlink "$game_path/d3dcompiler_47.dll"
    if ! ln -sfv "$d3dcompiler" "$game_path/d3dcompiler_47.dll"; then
        log_message "Failed to create d3dcompiler symlink"
        return 1
    fi
    
    # Link shader directory
    if [ -d "$MAIN_PATH/ReShade_shaders" ]; then
        log_message "Linking shader directory"
        [ -L "$game_path/ReShade_shaders" ] && unlink "$game_path/ReShade_shaders"
        if ! ln -sfv "$MAIN_PATH/ReShade_shaders" "$game_path/"; then
            log_message "Failed to create shaders symlink"
            return 1
        fi
    fi
    
    # Link ReShade.ini
    if [ "$GLOBAL_INI" != "0" ] && [ -f "$MAIN_PATH/$GLOBAL_INI" ]; then
        log_message "Linking ReShade.ini"
        [ -L "$game_path/ReShade.ini" ] && unlink "$game_path/ReShade.ini"
        if ! ln -sfv "$MAIN_PATH/$GLOBAL_INI" "$game_path/ReShade.ini"; then
            log_message "Failed to create ini symlink"
            return 1
        fi
    fi
    
    # Handle ReShadePreset.ini - preserve existing user settings
    log_message "Handling ReShadePreset.ini"
    local preset_file="$game_path/ReShadePreset.ini"
    
    # Only create the file if it doesn't already exist (preserve existing user settings)
    if [ ! -f "$preset_file" ]; then
        cat > "$preset_file" << EOF
# ReShade Preset Configuration for $(basename "$game_path")
# This file will be automatically populated when you save presets in ReShade
# Press HOME key in-game to open ReShade overlay
# Go to Settings -> General -> "Reload all shaders" if shaders don't appear

# Example preset configuration:
# [Preset1]
# Techniques=SMAA,Clarity,LumaSharpen
# PreprocessorDefinitions=

# Uncomment and modify the lines below to create a default preset:
# [Default]
# Techniques=
# PreprocessorDefinitions=
EOF
        
        # Set proper permissions (read/write for all)
        chmod 666 "$preset_file"
        log_message "Created new ReShadePreset.ini with proper permissions"
    else
        # File exists, just ensure it has proper permissions
        chmod 666 "$preset_file"
        log_message "ReShadePreset.ini already exists, updated permissions only"
    fi
    
    # Ensure ReShade.ini has proper permissions if it exists
    if [ -f "$game_path/ReShade.ini" ]; then
        chmod 666 "$game_path/ReShade.ini"
        log_message "Set proper permissions for ReShade.ini"
    fi
    
    # Create README file for Steam games
    local readme_file="$game_path/ReShade_README.txt"
    cat > "$readme_file" << EOF
ReShade for $(basename "$game_path")
------------------------------------
Installed with LetMeReShade plugin for Steam

DLL Override: $dll_override
Architecture: $arch-bit
Game Directory: $game_path

Press HOME key in-game to open the ReShade overlay.

If shaders are not visible:
1. Open the ReShade overlay with HOME key
2. Go to Settings tab
3. Check paths for "Effect Search Paths" and "Texture Search Paths"
4. They should point to the ReShade_shaders folder in this game directory
5. If not, update them to: ".\\ReShade_shaders"

Shader preset files (.ini) will be saved in this game directory.

Files created:
- ReShade.ini: Main ReShade configuration (symlinked to global)
- ReShadePreset.ini: Preset configurations (auto-populated when you save presets)
- $dll_override.dll: ReShade DLL (symlinked)
- d3dcompiler_47.dll: DirectX shader compiler (symlinked)
- ReShade_shaders/: Shader files directory (symlinked)

Note: If ReShadePreset.ini already existed, your previous settings were preserved.
EOF
    
    # Set proper permissions for README (read/write for all)
    chmod 666 "$readme_file"
    log_message "Created ReShade_README.txt with proper permissions"
    
    log_message "Setup completed successfully"
    return 0
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
    
    # Always remove ReShade.log as it's just a log file
    if [[ -f "$game_path/ReShade.log" ]]; then
        log_message "Removing ReShade.log"
        rm -f "$game_path/ReShade.log"
    fi
    
    # Check if ReShadePreset.ini exists and inform user it's preserved
    if [[ -f "$game_path/ReShadePreset.ini" ]]; then
        log_message "ReShadePreset.ini preserved to keep user shader presets"
        echo "ReShade uninstalled successfully. Your shader presets (ReShadePreset.ini) have been preserved."
    else
        echo "ReShade uninstalled successfully."
    fi
    
    if [ "$DELETE_RESHADE_FILES" = "1" ]; then
        log_message "DELETE_RESHADE_FILES is enabled, but ReShadePreset.ini will still be preserved"
        # Remove any additional preset files except ReShadePreset.ini
        find "$game_path" -name "*.ini" -type f ! -name "ReShadePreset.ini" -exec grep -l "ReShade" {} \; 2>/dev/null | while read -r preset_file; do
            log_message "Removing additional ReShade config file: $preset_file"
            rm -f "$preset_file"
        done
    fi
    
    log_message "Removal completed - ReShadePreset.ini preserved"
    return 0
}

setup_vulkan_support() {
    local wineprefix="$1"
    local arch="$2"
    local action="$3"
    
    if [ "$VULKAN_SUPPORT" != "1" ]; then
        log_message "Vulkan support is disabled"
        return 1
    fi
    
    export WINEPREFIX="$wineprefix"
    
    case $action in
        "install")
            wine reg ADD "HKLM\\SOFTWARE\\Khronos\\Vulkan\\ImplicitLayers" /d 0 /t REG_DWORD /v "Z:\\home\\$USER\\$WINE_MAIN_PATH\\reshade\\latest\\ReShade$arch.json" -f /reg:"$arch"
            ;;
        "uninstall")
            wine reg DELETE "HKLM\\SOFTWARE\\Khronos\\Vulkan\\ImplicitLayers" -f /reg:"$arch"
            ;;
        *)
            log_message "Invalid Vulkan action: $action"
            return 1
            ;;
    esac
    
    return $?
}

main() {
    local action="$1"
    local game_path="$2"
    local dll_override="${3:-dxgi}"
    local vulkan_mode="$4"
    local wineprefix="$5"
    
    log_message "Starting game manager with:"
    log_message "Action: $action"
    log_message "Game path: $game_path"
    log_message "DLL override: $dll_override"
    log_message "Vulkan mode: $vulkan_mode"
    log_message "WINEPREFIX: $wineprefix"
    
    if [ ! -d "$RESHADE_PATH" ]; then
        log_message "Error: RESHADE_PATH does not exist: $RESHADE_PATH"
        echo "Error: ReShade path not found" >&2
        exit 1
    fi
    
    if [ "$vulkan_mode" = "vulkan" ]; then
        if [ -z "$wineprefix" ]; then
            log_message "Error: WINEPREFIX required for Vulkan mode"
            echo "Error: WINEPREFIX not provided for Vulkan mode" >&2
            exit 1
        fi
        
        local detection_result=$(detect_game_arch_and_api "$game_path")
        local arch=$(echo "$detection_result" | cut -d',' -f1)
        setup_vulkan_support "$wineprefix" "$arch" "$action"
        exit $?
    fi
    
    game_path="${game_path//\"}"  # Remove any quotes
    if [ ! -d "$game_path" ]; then
        log_message "Error: Invalid game path: $game_path"
        echo "Error: Invalid game path" >&2
        exit 1
    fi

    case $action in
        "install")
            local detection_result=$(detect_game_arch_and_api "$game_path")
            local arch=$(echo "$detection_result" | cut -d',' -f1)
            local detected_api=$(echo "$detection_result" | cut -d',' -f2)
            
            # Use detected API only when auto-detection is requested
            if [ "$dll_override" = "auto" ]; then
                dll_override="$detected_api"
                log_message "Using detected API: $dll_override"
            fi
            
            log_message "Setting executable permissions for game directory"
            chmod -R u+w "$game_path" 2>/dev/null || log_message "Warning: Could not set write permissions"
            
            if setup_game_reshade "$game_path" "$dll_override" "$arch"; then
                # Update the WINEDLLOVERRIDES based on detected API
                local override_cmd="WINEDLLOVERRIDES=\"d3dcompiler_47=n;${dll_override}=n,b\" %command%"
                echo "Successfully installed ReShade"
                if [ -f "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon$arch" ]; then
                    echo "AutoHDR components included (requires DirectX 10/11/12 games)"
                fi
                echo "Use this launch option: $override_cmd"
                echo "Press INSERT key in-game to open ReShade interface"
                return 0
            else
                echo "Failed to install ReShade" >&2
                return 1
            fi
            ;;
        "uninstall")
            if remove_game_reshade "$game_path"; then
                echo "Successfully removed ReShade"
                return 0
            else
                echo "Failed to remove ReShade" >&2
                return 1
            fi
            ;;
        *)
            log_message "Error: Invalid action: $action"
            echo "Invalid action. Use 'install' or 'uninstall'" >&2
            exit 1
            ;;
    esac
}

main "$@"