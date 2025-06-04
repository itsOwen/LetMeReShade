#!/bin/bash

SEPERATOR="------------------------------------------------------------------------------------------------"
COMMON_OVERRIDES="d3d8 d3d9 d3d11 ddraw dinput8 dxgi opengl32"
REQUIRED_EXECUTABLES="7z grep"
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
MAIN_PATH=${MAIN_PATH:-"$XDG_DATA_HOME/reshade"}
RESHADE_PATH="$MAIN_PATH/reshade"
WINE_MAIN_PATH="$(echo "$MAIN_PATH" | sed "s#/home/$USER/##" | sed 's#/#\\\\#g')"
UPDATE_RESHADE=${UPDATE_RESHADE:-1}
MERGE_SHADERS=${MERGE_SHADERS:-1}
VULKAN_SUPPORT=${VULKAN_SUPPORT:-0}
GLOBAL_INI=${GLOBAL_INI:-"ReShade.ini"}
RESHADE_VERSION=${RESHADE_VERSION:-"latest"}
RESHADE_ADDON_SUPPORT=${RESHADE_ADDON_SUPPORT:-0}
# Get the path to the bin directory containing bundled files
BIN_PATH="$(dirname "$(realpath "$0")")/../bin"

log_message() {
    echo "[DEBUG] $1" >&2
}

check_dependencies() {
    for cmd in $REQUIRED_EXECUTABLES; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "Error: Required program '$cmd' is missing."
            exit 1
        fi
    done
}

setup_directories() {
    mkdir -p "$RESHADE_PATH"
    mkdir -p "$MAIN_PATH/ReShade_shaders"
    mkdir -p "$MAIN_PATH/External_shaders"
}

# Creates a temporary directory for downloads
createTempDir() {
    tmpDir=$(mktemp -d)
    cd "$tmpDir" || echo "Failed to create temp directory."
}

removeTempDir() {
    cd "$MAIN_PATH" || exit
    [[ -d $tmpDir ]] && rm -rf "$tmpDir"
}

setup_d3dcompiler() {
    local arch=$1
    local target_file="$RESHADE_PATH/d3dcompiler_47.dll.$arch"
    
    [[ -f $target_file ]] && return
    
    log_message "Setting up d3dcompiler_47.dll for $arch bits"
    
    # Copy the bundled DLL
    cp "$BIN_PATH/d3dcompiler_47.dll" "$target_file"
    
    if [[ ! -f "$target_file" ]]; then
        log_message "Error: Failed to set up d3dcompiler_47.dll for $arch-bit"
        exit 1
    fi
}

setup_shaders() {
    log_message "Setting up ReShade shaders..."
    
    # Create merged shader directories if needed
    if [[ $MERGE_SHADERS == 1 ]]; then
        mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/Shaders" 
        mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/Textures"
    fi
    
    # Extract shader archives
    log_message "Extracting bundled reshade_shaders.tar.gz"
    mkdir -p "$MAIN_PATH/ReShade_shaders/reshade-shaders"
    tar -xzf "$BIN_PATH/reshade_shaders.tar.gz" -C "$MAIN_PATH/ReShade_shaders/reshade-shaders"
    
    log_message "Extracting bundled sweetfx_shaders.tar.gz"
    mkdir -p "$MAIN_PATH/ReShade_shaders/sweetfx-shaders"
    tar -xzf "$BIN_PATH/sweetfx_shaders.tar.gz" -C "$MAIN_PATH/ReShade_shaders/sweetfx-shaders"
    
    log_message "Extracting bundled martymc_shaders.tar.gz"
    mkdir -p "$MAIN_PATH/ReShade_shaders/martymc-shaders"
    tar -xzf "$BIN_PATH/martymc_shaders.tar.gz" -C "$MAIN_PATH/ReShade_shaders/martymc-shaders"
    
    log_message "Extracting bundled astrayfx_shaders.tar.gz"
    mkdir -p "$MAIN_PATH/ReShade_shaders/astrayfx-shaders"
    tar -xzf "$BIN_PATH/astrayfx_shaders.tar.gz" -C "$MAIN_PATH/ReShade_shaders/astrayfx-shaders"
    
    log_message "Extracting bundled prod80_shaders.tar.gz"
    mkdir -p "$MAIN_PATH/ReShade_shaders/prod80-shaders"
    tar -xzf "$BIN_PATH/prod80_shaders.tar.gz" -C "$MAIN_PATH/ReShade_shaders/prod80-shaders"
    
    # Merge shaders if enabled
    if [[ $MERGE_SHADERS == 1 ]]; then
        log_message "Merging shaders..."
        # Copy from shader repositories to merged directory
        for repo_dir in "$MAIN_PATH/ReShade_shaders"/*-shaders; do
            if [[ -d "$repo_dir/Shaders" ]]; then
                cp -rf "$repo_dir/Shaders/"* "$MAIN_PATH/ReShade_shaders/Merged/Shaders/"
            fi
            if [[ -d "$repo_dir/Textures" ]]; then
                cp -rf "$repo_dir/Textures/"* "$MAIN_PATH/ReShade_shaders/Merged/Textures/"
            fi
        done
        
        # Handle external shaders
        if [[ -d "$MAIN_PATH/External_shaders" ]]; then
            for file in "$MAIN_PATH/External_shaders"/*; do
                [[ -f $file ]] && ln -sf "$file" "$MAIN_PATH/ReShade_shaders/Merged/Shaders/"
            done
        fi
    fi
}

setup_reshade() {
    local addon_support=${1:-0}
    createTempDir
    
    log_message "Setting up ReShade (addon_support=$addon_support)..."
    
    # Use bundled ReShade installer
    if [[ $addon_support -eq 1 ]]; then
        log_message "Using bundled ReShade addon installer"
        cp "$BIN_PATH/reshade_latest_addon.exe" "./ReShade_Setup.exe"
        local version="latest_Addon"
    else
        log_message "Using bundled ReShade installer"
        cp "$BIN_PATH/reshade_latest.exe" "./ReShade_Setup.exe"
        local version="latest"
    fi
    
    # Extract the installer
    7z -y e "./ReShade_Setup.exe" 1> /dev/null || {
        log_message "Failed to extract ReShade"
        removeTempDir
        exit 1
    }
    
    local target_dir="$RESHADE_PATH/$version"
    rm -rf "$target_dir"
    mkdir -p "$target_dir"
    mv ./* "$target_dir"
    removeTempDir
    
    # Create latest symlink and version file
    ln -sfn "$target_dir" "$RESHADE_PATH/latest"
    echo "$version" > "$RESHADE_PATH/LVERS"
    
    # Create version indicator file
    if [[ $addon_support -eq 1 ]]; then
        touch "$target_dir/addon_version"
    fi
}

setup_reshade_ini() {
    if [[ $GLOBAL_INI != 0 ]] && [[ $GLOBAL_INI == ReShade.ini ]] && [[ ! -f $MAIN_PATH/$GLOBAL_INI ]]; then
        cd "$MAIN_PATH" || exit
        
        # Use bundled template
        log_message "Using bundled ReShade.ini template"
        cp "$BIN_PATH/reshade_ini_template.ini" "$MAIN_PATH/$GLOBAL_INI"
        
        if [[ -f ReShade.ini ]]; then
            sed -i "s/_USERSED_/$USER/g" "$MAIN_PATH/$GLOBAL_INI"
            if [[ $MERGE_SHADERS == 1 ]]; then
                sed -i "s#_SHADSED_#$WINE_MAIN_PATH\\\ReShade_shaders\\\Merged\\\Shaders#g" "$MAIN_PATH/$GLOBAL_INI"
                sed -i "s#_TEXSED_#$WINE_MAIN_PATH\\\ReShade_shaders\\\Merged\\\Textures#g" "$MAIN_PATH/$GLOBAL_INI"
            fi
        fi
    fi
}

main() {
    echo -e "$SEPERATOR\nStarting ReShade installation...\n$SEPERATOR"
    
    check_dependencies
    setup_directories
    
    # Check update status
    if [[ -f "$MAIN_PATH/LASTUPDATED" ]]; then
        LASTUPDATED=$(cat "$MAIN_PATH/LASTUPDATED")
        [[ ! $LASTUPDATED =~ ^[0-9]+$ ]] && LASTUPDATED=0
        [[ $(($(date +%s)-LASTUPDATED)) -lt 14400 ]] && UPDATE_RESHADE=0
    fi
    [[ $UPDATE_RESHADE == 1 ]] && date +%s > "$MAIN_PATH/LASTUPDATED"
    
    # Ensure RESHADE_ADDON_SUPPORT is properly set
    RESHADE_ADDON_SUPPORT=${RESHADE_ADDON_SUPPORT:-0}
    log_message "Installing with addon support: $RESHADE_ADDON_SUPPORT"
    
    # Set up ReShade
    setup_reshade $RESHADE_ADDON_SUPPORT
    
    # Set up other components
    setup_d3dcompiler "32"
    setup_d3dcompiler "64"
    setup_shaders
    setup_reshade_ini
    
    echo -e "$SEPERATOR\nReShade installation completed successfully"
    echo "Shaders installed to: $MAIN_PATH/ReShade_shaders"
    [[ -f "$MAIN_PATH/$GLOBAL_INI" ]] && echo "ReShade.ini created at: $MAIN_PATH/$GLOBAL_INI"
    if [[ $RESHADE_ADDON_SUPPORT -eq 1 ]]; then
        echo "Installed with addon support"
    else
        echo "Installed without addon support"
    fi
}

main "$@"