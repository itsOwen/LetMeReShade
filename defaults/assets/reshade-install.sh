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
AUTOHDR_ENABLED=${AUTOHDR_ENABLED:-0}
SELECTED_SHADERS=${SELECTED_SHADERS:-"all"}

# Get the correct path to the bin directory - check both possible locations
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Check if we're in defaults/assets (development)
if [[ "$SCRIPT_DIR" == */defaults/assets ]]; then
    PLUGIN_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two directories from defaults/assets
    log_message() { echo "[DEBUG] Using defaults/assets path: $1" >&2; }
# Check if we're in assets (decky store)
elif [[ "$SCRIPT_DIR" == */assets ]]; then
    PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"  # Go up one directory from assets
    log_message() { echo "[DEBUG] Using assets path: $1" >&2; }
else
    # Fallback - assume we're in assets
    PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
    log_message() { echo "[DEBUG] Using fallback path: $1" >&2; }
fi

BIN_PATH="$PLUGIN_ROOT/bin"

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
    # NEW: Create AutoHDR addon storage directory
    mkdir -p "$MAIN_PATH/AutoHDR_addons"
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
    
    # Check if bin directory and file exist
    if [[ ! -d "$BIN_PATH" ]]; then
        log_message "Error: Bin directory not found at $BIN_PATH"
        log_message "Script directory: $SCRIPT_DIR"
        log_message "Plugin root: $PLUGIN_ROOT"
        exit 1
    fi
    
    if [[ ! -f "$BIN_PATH/d3dcompiler_47.dll" ]]; then
        log_message "Error: d3dcompiler_47.dll not found in bin directory"
        exit 1
    fi
    
    # Copy the bundled DLL
    cp "$BIN_PATH/d3dcompiler_47.dll" "$target_file"
    
    if [[ ! -f "$target_file" ]]; then
        log_message "Error: Failed to set up d3dcompiler_47.dll for $arch-bit"
        exit 1
    fi
}

is_shader_selected() {
    local shader_id="$1"
    
    # If SELECTED_SHADERS is "all", install all shaders
    if [[ "$SELECTED_SHADERS" == "all" ]]; then
        return 0
    fi
    
    # If SELECTED_SHADERS is empty, install none
    if [[ -z "$SELECTED_SHADERS" ]]; then
        return 1
    fi
    
    # Check if shader_id is in the comma-separated list
    local IFS=','
    for selected_shader in $SELECTED_SHADERS; do
        if [[ "$selected_shader" == "$shader_id" ]]; then
            return 0
        fi
    done
    
    return 1
}

setup_shaders() {
    log_message "Setting up ReShade shaders..."
    log_message "Selected shaders: $SELECTED_SHADERS"
    
    # Create merged shader directories if needed
    if [[ $MERGE_SHADERS == 1 ]]; then
        mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/Shaders" 
        mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/Textures"
    fi
    
    # Check if bin directory exists
    if [[ ! -d "$BIN_PATH" ]]; then
        log_message "Error: Bin directory not found at $BIN_PATH"
        exit 1
    fi
    
    # Define shader packages and their corresponding IDs
    declare -A shader_packages=(
        ["reshade_shaders"]="reshade_shaders.tar.gz"
        ["sweetfx_shaders"]="sweetfx_shaders.tar.gz"
        ["martymc_shaders"]="martymc_shaders.tar.gz"
        ["astrayfx_shaders"]="astrayfx_shaders.tar.gz"
        ["prod80_shaders"]="prod80_shaders.tar.gz"
        ["retroarch_shaders"]="retroarch_shaders.tar.gz"
    )
    
    # ALWAYS extract ReShade core files first (essential dependencies)
    # This ensures ReShade.fxh and other core files are always available
    local core_archive="$BIN_PATH/reshade_shaders.tar.gz"
    if [[ -f "$core_archive" ]]; then
        log_message "Installing essential ReShade core files (always required)"
        mkdir -p "$MAIN_PATH/ReShade_shaders/reshade_shaders"
        tar -xzf "$core_archive" -C "$MAIN_PATH/ReShade_shaders/reshade_shaders"
        
        # Copy core files to merged directory immediately
        if [[ $MERGE_SHADERS == 1 ]]; then
            local core_repo_dir="$MAIN_PATH/ReShade_shaders/reshade_shaders"
            if [[ -d "$core_repo_dir/Shaders" ]]; then
                log_message "Copying essential ReShade core files to merged directory"
                # Copy essential .fxh files and core shaders
                find "$core_repo_dir/Shaders" -name "*.fxh" -exec cp {} "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" \; 2>/dev/null || true
                # Also copy any core .fx files if reshade_shaders is not explicitly selected
                if ! is_shader_selected "reshade_shaders"; then
                    log_message "ReShade core package not selected, copying essential core shaders too"
                    find "$core_repo_dir/Shaders" -name "*.fx" -exec cp {} "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" \; 2>/dev/null || true
                fi
            fi
            if [[ -d "$core_repo_dir/Textures" ]]; then
                log_message "Copying essential ReShade core textures to merged directory"
                cp -rf "$core_repo_dir/Textures"/* "$MAIN_PATH/ReShade_shaders/Merged/Textures/" 2>/dev/null || true
            fi
        fi
    else
        log_message "Warning: Core ReShade shaders package not found - shader compilation may fail"
    fi
    
    # Extract selected shader archives (skip reshade_shaders if already processed)
    for shader_id in "${!shader_packages[@]}"; do
        local archive_name="${shader_packages[$shader_id]}"
        local archive_path="$BIN_PATH/$archive_name"
        
        if is_shader_selected "$shader_id"; then
            if [[ "$shader_id" == "reshade_shaders" ]]; then
                log_message "ReShade core shaders already processed, skipping duplicate extraction"
                continue
            fi
            
            if [[ -f "$archive_path" ]]; then
                log_message "Extracting selected shader package: $archive_name"
                mkdir -p "$MAIN_PATH/ReShade_shaders/$shader_id"
                tar -xzf "$archive_path" -C "$MAIN_PATH/ReShade_shaders/$shader_id"
            else
                log_message "Warning: Selected shader package not found: $archive_path"
            fi
        else
            log_message "Skipping shader package: $shader_id (not selected)"
        fi
    done
    
    # Merge shaders if enabled
    if [[ $MERGE_SHADERS == 1 ]]; then
        log_message "Merging selected shaders..."
        # Copy from selected shader repositories to merged directory (skip reshade_shaders if already processed)
        for shader_id in "${!shader_packages[@]}"; do
            if is_shader_selected "$shader_id"; then
                if [[ "$shader_id" == "reshade_shaders" ]]; then
                    # Only merge the remaining files that weren't copied as core files
                    local repo_dir="$MAIN_PATH/ReShade_shaders/$shader_id"
                    if [[ -d "$repo_dir/Shaders" ]]; then
                        log_message "Merging remaining ReShade core shader files"
                        # Copy any .fx files (the .fxh files were already copied)
                        find "$repo_dir/Shaders" -name "*.fx" -exec cp {} "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" \; 2>/dev/null || true
                    fi
                    continue
                fi
                
                local repo_dir="$MAIN_PATH/ReShade_shaders/$shader_id"
                if [[ -d "$repo_dir" ]]; then
                    log_message "Merging all content from $shader_id"
                    
                    # Copy Shaders directory contents (all files)
                    if [[ -d "$repo_dir/Shaders" ]]; then
                        log_message "Copying all shader files from $shader_id/Shaders"
                        cp -rf "$repo_dir/Shaders"/* "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" 2>/dev/null || true
                    fi
                    
                    # Copy Textures directory contents (all files)
                    if [[ -d "$repo_dir/Textures" ]]; then
                        log_message "Copying all texture files from $shader_id/Textures"
                        cp -rf "$repo_dir/Textures"/* "$MAIN_PATH/ReShade_shaders/Merged/Textures/" 2>/dev/null || true
                    fi
                    
                    # Copy any root-level shader files directly to Shaders directory
                    if find "$repo_dir" -maxdepth 1 -name "*.fx" -o -name "*.fxh" -o -name "*.hlsl" -o -name "*.inc" | grep -q .; then
                        log_message "Copying root-level shader files from $shader_id"
                        find "$repo_dir" -maxdepth 1 \( -name "*.fx" -o -name "*.fxh" -o -name "*.hlsl" -o -name "*.inc" \) -exec cp {} "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" \; 2>/dev/null || true
                    fi
                    
                    # Copy any other directories that might contain shader resources
                    for subdir in "$repo_dir"/*; do
                        if [[ -d "$subdir" && "$(basename "$subdir")" != "Shaders" && "$(basename "$subdir")" != "Textures" ]]; then
                            subdir_name=$(basename "$subdir")
                            log_message "Copying additional directory: $subdir_name"
                            mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/$subdir_name"
                            cp -rf "$subdir"/* "$MAIN_PATH/ReShade_shaders/Merged/$subdir_name/" 2>/dev/null || true
                        fi
                    done
                fi
            fi
        done
        
        # Handle external shaders (copy ALL files)
        if [[ -d "$MAIN_PATH/External_shaders" ]]; then
            log_message "Copying external shader files"
            for file in "$MAIN_PATH/External_shaders"/*; do
                [[ -f $file ]] && cp "$file" "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" 2>/dev/null || true
            done
        fi
        
        # Copy any loose files from main ReShade_shaders directory to Merged/Shaders
        log_message "Copying any loose shader files to merged directory"
        find "$MAIN_PATH/ReShade_shaders" -maxdepth 1 -type f \( -name "*.fx" -o -name "*.fxh" -o -name "*.hlsl" -o -name "*.inc" -o -name "*.txt" -o -name "*.md" \) -exec cp {} "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" \; 2>/dev/null || true
    fi
    
    # Count installed shader packages for reporting
    local installed_count=0
    for shader_id in "${!shader_packages[@]}"; do
        if is_shader_selected "$shader_id"; then
            ((installed_count++))
        fi
    done
    
    if [[ $installed_count -eq 0 ]]; then
        log_message "Warning: No shader packages were selected, but core ReShade files were installed"
    else
        log_message "Successfully installed $installed_count shader packages plus essential ReShade core files"
    fi
}

setup_autohdr() {
    if [[ $AUTOHDR_ENABLED != 1 ]]; then
        return
    fi
    
    log_message "Setting up AutoHDR components..."
    
    # Extract AutoHDR addon files to addon storage directory (NOT to ReShade installation)
    if [[ -f "$BIN_PATH/autohdr_addon.tar.gz" ]]; then
        log_message "Extracting AutoHDR addon files to storage directory"
        tar -xzf "$BIN_PATH/autohdr_addon.tar.gz" -C "$MAIN_PATH/AutoHDR_addons/"
    else
        log_message "Warning: autohdr_addon.tar.gz not found in bin directory"
    fi
    
    # Extract AdvancedAutoHDR effect files
    if [[ -f "$BIN_PATH/advanced_autohdr_effect.tar.gz" ]]; then
        log_message "Extracting AdvancedAutoHDR effect files"
        # Create temporary directory for extraction
        temp_autohdr_dir=$(mktemp -d)
        tar -xzf "$BIN_PATH/advanced_autohdr_effect.tar.gz" -C "$temp_autohdr_dir"
        
        # Copy ALL files recursively to the main shader directory
        log_message "Copying all AutoHDR files to shader directory"
        if [[ -d "$temp_autohdr_dir" ]]; then
            # Copy all files and subdirectories
            cp -rf "$temp_autohdr_dir"/* "$MAIN_PATH/ReShade_shaders/" 2>/dev/null || true
        fi
        
        # If we're using merged shaders, also copy to merged directory
        if [[ $MERGE_SHADERS == 1 ]]; then
            log_message "Copying AutoHDR files to merged shaders directory"
            if [[ -d "$temp_autohdr_dir" ]]; then
                # Copy all files and subdirectories to merged directory
                cp -rf "$temp_autohdr_dir"/* "$MAIN_PATH/ReShade_shaders/Merged/" 2>/dev/null || true
                
                # Ensure proper structure for Shaders and Textures subdirectories
                if [[ -d "$temp_autohdr_dir/Shaders" ]]; then
                    cp -rf "$temp_autohdr_dir/Shaders"/* "$MAIN_PATH/ReShade_shaders/Merged/Shaders/" 2>/dev/null || true
                fi
                if [[ -d "$temp_autohdr_dir/Textures" ]]; then
                    cp -rf "$temp_autohdr_dir/Textures"/* "$MAIN_PATH/ReShade_shaders/Merged/Textures/" 2>/dev/null || true
                fi
            fi
        fi
        
        # Clean up temporary directory
        rm -rf "$temp_autohdr_dir"
    else
        log_message "Warning: advanced_autohdr_effect.tar.gz not found in bin directory"
    fi
    
    log_message "AutoHDR components setup completed"
}

setup_reshade() {
    local addon_support=${1:-0}
    createTempDir
    
    log_message "Setting up ReShade $RESHADE_VERSION (addon_support=$addon_support)..."
    
    # Check if bin directory exists
    if [[ ! -d "$BIN_PATH" ]]; then
        log_message "Error: Bin directory not found at $BIN_PATH"
        log_message "Current working directory: $(pwd)"
        log_message "Script directory: $SCRIPT_DIR"
        log_message "Plugin root: $PLUGIN_ROOT"
        exit 1
    fi
    
    # Select the correct installer based on version and addon support
    local installer_name=""
    local version_suffix=""
    
    if [[ "$RESHADE_VERSION" == "last" ]]; then
        version_suffix="_last"
        if [[ $addon_support -eq 1 ]]; then
            installer_name="reshade_last_addon.exe"
            version_suffix="${version_suffix}_Addon"
        else
            installer_name="reshade_last.exe"
        fi
    else
        # Default to latest
        version_suffix="_latest"
        if [[ $addon_support -eq 1 ]]; then
            installer_name="reshade_latest_addon.exe"
            version_suffix="${version_suffix}_Addon"
        else
            installer_name="reshade_latest.exe"
        fi
    fi
    
    # Check if the installer exists
    if [[ ! -f "$BIN_PATH/$installer_name" ]]; then
        log_message "Error: $installer_name not found in bin directory"
        exit 1
    fi
    
    log_message "Using installer: $installer_name"
    cp "$BIN_PATH/$installer_name" "./ReShade_Setup.exe"
    
    # Extract the installer
    7z -y e "./ReShade_Setup.exe" 1> /dev/null || {
        log_message "Failed to extract ReShade"
        removeTempDir
        exit 1
    }
    
    target_dir="$RESHADE_PATH/$RESHADE_VERSION$version_suffix"
    rm -rf "$target_dir"
    mkdir -p "$target_dir"
    mv ./* "$target_dir"
    removeTempDir
    
    # Create latest symlink and version file
    ln -sfn "$target_dir" "$RESHADE_PATH/latest"
    echo "$RESHADE_VERSION$version_suffix" > "$RESHADE_PATH/LVERS"
    
    # Create version indicator file
    if [[ $addon_support -eq 1 ]]; then
        touch "$target_dir/addon_version"
    fi
    
    # Set up AutoHDR components if enabled (must be after ReShade extraction)
    setup_autohdr
}

setup_reshade_ini() {
    if [[ $GLOBAL_INI != 0 ]] && [[ $GLOBAL_INI == ReShade.ini ]] && [[ ! -f $MAIN_PATH/$GLOBAL_INI ]]; then
        cd "$MAIN_PATH" || exit
        
        # Check if bin directory and template file exist
        if [[ ! -d "$BIN_PATH" ]]; then
            log_message "Error: Bin directory not found at $BIN_PATH"
            exit 1
        fi
        
        if [[ ! -f "$BIN_PATH/reshade_ini_template.ini" ]]; then
            log_message "Error: reshade_ini_template.ini not found in bin directory"
            exit 1
        fi
        
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
    echo -e "$SEPERATOR\nStarting ReShade $RESHADE_VERSION installation...\n$SEPERATOR"
    
    # Debug output for file paths
    log_message "Script directory: $SCRIPT_DIR"
    log_message "Plugin root: $PLUGIN_ROOT"
    log_message "Bin path: $BIN_PATH"
    log_message "ReShade version: $RESHADE_VERSION"
    log_message "AutoHDR enabled: $AUTOHDR_ENABLED"
    log_message "Selected shaders: $SELECTED_SHADERS"
    
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
    
    echo -e "$SEPERATOR\nReShade $RESHADE_VERSION installation completed successfully"
    echo "Shaders installed to: $MAIN_PATH/ReShade_shaders"
    
    # Report installed shader packages
    if [[ "$SELECTED_SHADERS" != "all" ]]; then
        local IFS=','
        local installed_packages=()
        for selected_shader in $SELECTED_SHADERS; do
            case "$selected_shader" in
                "reshade_shaders") installed_packages+=("ReShade Community Shaders") ;;
                "sweetfx_shaders") installed_packages+=("SweetFX Shaders") ;;
                "martymc_shaders") installed_packages+=("MartyMcFly's RT Shaders") ;;
                "astrayfx_shaders") installed_packages+=("AstrayFX Shaders") ;;
                "prod80_shaders") installed_packages+=("Prod80's Shaders") ;;
                "retroarch_shaders") installed_packages+=("RetroArch Shaders") ;;
            esac
        done
        
        if [[ ${#installed_packages[@]} -gt 0 ]]; then
            echo "Selected shader packages:"
            printf '  - %s\n' "${installed_packages[@]}"
        else
            echo "No shader packages were installed"
        fi
    else
        echo "All available shader packages installed"
    fi
    
    [[ -f "$MAIN_PATH/$GLOBAL_INI" ]] && echo "ReShade.ini created at: $MAIN_PATH/$GLOBAL_INI"
    if [[ $RESHADE_ADDON_SUPPORT -eq 1 ]]; then
        echo "Installed with addon support"
    else
        echo "Installed without addon support"
    fi
    if [[ $AUTOHDR_ENABLED -eq 1 ]]; then
        echo "AutoHDR components installed for Steam Deck OLED"
        echo "AutoHDR addon files stored at: $MAIN_PATH/AutoHDR_addons"
        echo "Note: AutoHDR only works with DirectX 10/11/12 games"
    fi
    echo "Version: $RESHADE_VERSION"
}

main "$@"