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
    
    # NEW: Copy AutoHDR addon files if available (addons can't be symlinked)
    if [ -f "$RESHADE_PATH/latest/addon_version" ]; then
        log_message "ReShade has addon support, checking for AutoHDR components"
        
        # Copy AutoHDR addon files if they exist
        if [ -f "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon$arch" ]; then
            log_message "Copying AutoHDR addon files to game directory"
            cp "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon$arch" "$game_path/" || {
                log_message "Warning: Failed to copy AutoHDR addon file"
            }
            
            # Also copy the other architecture if present (some games may need both)
            if [[ "$arch" == "64" && -f "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon32" ]]; then
                cp "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon32" "$game_path/" || {
                    log_message "Warning: Failed to copy AutoHDR.addon32"
                }
            elif [[ "$arch" == "32" && -f "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon64" ]]; then
                cp "$MAIN_PATH/AutoHDR_addons/AutoHDR.addon64" "$game_path/" || {
                    log_message "Warning: Failed to copy AutoHDR.addon64"
                }
            fi
        else
            log_message "AutoHDR addon files not found in storage directory"
        fi
    else
        log_message "ReShade addon support not available, skipping AutoHDR addon installation"
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
    
    log_message "Setup completed successfully"
    return 0
}

remove_game_reshade() {
    local game_path="$1"
    
    log_message "Removing ReShade from: $game_path"
    
    # Remove DLL overrides
    for override in $COMMON_OVERRIDES; do
        if [ -L "$game_path/${override}.dll" ]; then
            log_message "Removing link: ${override}.dll"
            rm -fv "$game_path/${override}.dll"
        fi
    done
    
    # NEW: Remove AutoHDR addon files
    if [ -f "$game_path/AutoHDR.addon32" ]; then
        log_message "Removing AutoHDR.addon32"
        rm -fv "$game_path/AutoHDR.addon32"
    fi
    
    if [ -f "$game_path/AutoHDR.addon64" ]; then
        log_message "Removing AutoHDR.addon64"
        rm -fv "$game_path/AutoHDR.addon64"
    fi
    
    # Remove other ReShade files
    local reshade_files="ReShade.ini ReShade32.json ReShade64.json d3dcompiler_47.dll ReShade_shaders ReShadePreset.ini"
    
    for file in $reshade_files; do
        if [ -L "$game_path/$file" ]; then
            log_message "Removing link: $file"
            rm -fv "$game_path/$file"
        fi
    done

    if [ "$DELETE_RESHADE_FILES" = "1" ]; then
        log_message "Removing additional ReShade files"
        rm -f "$game_path/ReShade.log" "$game_path/ReShadePreset.ini"
    fi
    
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