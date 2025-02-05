SEPERATOR="------------------------------------------------------------------------------------------------"
COMMON_OVERRIDES="d3d8 d3d9 d3d11 ddraw dinput8 dxgi opengl32"
REQUIRED_EXECUTABLES="7z curl git grep"
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
MAIN_PATH=${MAIN_PATH:-"$XDG_DATA_HOME/reshade"}
RESHADE_PATH="$MAIN_PATH/reshade"
WINE_MAIN_PATH="$(echo "$MAIN_PATH" | sed "s#/home/$USER/##" | sed 's#/#\\\\#g')"
UPDATE_RESHADE=${UPDATE_RESHADE:-1}
MERGE_SHADERS=${MERGE_SHADERS:-1}
VULKAN_SUPPORT=${VULKAN_SUPPORT:-0}
GLOBAL_INI=${GLOBAL_INI:-"ReShade.ini"}
SHADER_REPOS=${SHADER_REPOS:-"https://github.com/CeeJayDK/SweetFX|sweetfx-shaders;https://github.com/martymcmodding/qUINT|martymc-shaders;https://github.com/BlueSkyDefender/AstrayFX|astrayfx-shaders;https://github.com/prod80/prod80-ReShade-Repository|prod80-shaders;https://github.com/crosire/reshade-shaders|reshade-shaders|slim"}
RESHADE_VERSION=${RESHADE_VERSION:-"latest"}
RESHADE_ADDON_SUPPORT=${RESHADE_ADDON_SUPPORT:-0}
FORCE_RESHADE_UPDATE_CHECK=${FORCE_RESHADE_UPDATE_CHECK:-0}
RESHADE_URL="https://reshade.me"
RESHADE_URL_ALT="http://static.reshade.me"

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
    cd "$tmpDir" || printErr "Failed to create temp directory."
}

removeTempDir() {
    cd "$MAIN_PATH" || exit
    [[ -d $tmpDir ]] && rm -rf "$tmpDir"
}

download_d3dcompiler() {
    local arch=$1
    local target_file="$RESHADE_PATH/d3dcompiler_47.dll.$arch"
    
    [[ -f $target_file ]] && return
    
    log_message "Downloading d3dcompiler_47.dll for $arch bits"
    createTempDir
    
    curl -sLO "https://download-installer.cdn.mozilla.net/pub/firefox/releases/62.0.3/win$arch/ach/Firefox%20Setup%2062.0.3.exe" || {
        log_message "Failed to download Firefox"
        removeTempDir
        return 1
    }
    
    local expected_hash
    [[ $arch -eq 32 ]] && expected_hash="d6edb4ff0a713f417ebd19baedfe07527c6e45e84a6c73ed8c66a33377cc0aca" \
                       || expected_hash="721977f36c008af2b637aedd3f1b529f3cfed6feb10f68ebe17469acb1934986"
    
    local actual_hash=$(sha256sum Firefox*.exe | cut -d\  -f1)
    [[ "$actual_hash" != "$expected_hash" ]] && {
        log_message "Firefox integrity check failed"
        removeTempDir
        return 1
    }
    
    7z -y e Firefox*.exe 1> /dev/null || {
        log_message "Failed to extract Firefox"
        removeTempDir
        return 1
    }
    
    mv d3dcompiler_47.dll "$target_file"
    removeTempDir
}

download_shaders() {
    log_message "Downloading ReShade shaders..."
    [[ $MERGE_SHADERS == 1 ]] && mkdir -p "$MAIN_PATH/ReShade_shaders/Merged/Shaders" "$MAIN_PATH/ReShade_shaders/Merged/Textures"
    
    for URI in $(echo "$SHADER_REPOS" | tr ';' '\n'); do
        local repoName=$(echo "$URI" | cut -d'|' -f2)
        local branch=$(echo "$URI" | cut -d'|' -f3)
        URI=$(echo "$URI" | cut -d'|' -f1)
        
        if [[ -d "$MAIN_PATH/ReShade_shaders/$repoName" ]]; then
            if [[ $UPDATE_RESHADE -eq 1 ]]; then
                cd "$MAIN_PATH/ReShade_shaders/$repoName" || continue
                git pull
            fi
        else
            cd "$MAIN_PATH/ReShade_shaders" || exit 1
            if [[ -n "$branch" ]]; then
                git clone --branch "$branch" "$URI" "$repoName"
            else
                git clone "$URI" "$repoName"
            fi
        fi
        
        # Handle shader merging if enabled
        if [[ $MERGE_SHADERS == 1 ]]; then
            if [[ -d "$MAIN_PATH/ReShade_shaders/$repoName/Shaders" ]]; then
                cp -rf "$MAIN_PATH/ReShade_shaders/$repoName/Shaders/"* "$MAIN_PATH/ReShade_shaders/Merged/Shaders/"
            fi
            if [[ -d "$MAIN_PATH/ReShade_shaders/$repoName/Textures" ]]; then
                cp -rf "$MAIN_PATH/ReShade_shaders/$repoName/Textures/"* "$MAIN_PATH/ReShade_shaders/Merged/Textures/"
            fi
        fi
    done

    # Handle external shaders
    if [[ $MERGE_SHADERS == 1 ]] && [[ -d "$MAIN_PATH/External_shaders" ]]; then
        for file in "$MAIN_PATH/External_shaders"/*; do
            [[ -f $file ]] && ln -sf "$file" "$MAIN_PATH/ReShade_shaders/Merged/Shaders/"
        done
    fi
}

get_latest_version() {
    local html
    local addon_support=${1:-0}
    local version_regex="[0-9][0-9.]*[0-9]"
    [[ $addon_support -eq 1 ]] && version_regex="${version_regex}_Addon"
    
    html=$(curl --max-time 10 -sL "$RESHADE_URL")
    if [[ $? != 0 || $html =~ '<h2>Something went wrong.</h2>' ]]; then
        log_message "Trying alternate URL..."
        html=$(curl -sL "$RESHADE_URL_ALT")
    fi
    
    local download_link=$(echo "$html" | grep -o "/downloads/ReShade_Setup_${version_regex}\.exe" | head -n1)
    if [[ -z $download_link ]]; then
        log_message "Could not find ReShade version"
        exit 1
    fi
    
    echo "$download_link"
}

download_reshade() {
    local version=$1
    local url=$2
    createTempDir
    
    log_message "Downloading ReShade version $version..."
    curl -sLO "$url" || {
        log_message "Failed to download ReShade"
        removeTempDir
        exit 1
    }
    
    local exe_file=$(find . -name "*.exe")
    7z -y e "$exe_file" 1> /dev/null || {
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
}

setup_reshade_ini() {
    if [[ $GLOBAL_INI != 0 ]] && [[ $GLOBAL_INI == ReShade.ini ]] && [[ ! -f $MAIN_PATH/$GLOBAL_INI ]]; then
        cd "$MAIN_PATH" || exit
        curl -sLO https://github.com/kevinlekiller/reshade-steam-proton/raw/ini/ReShade.ini
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
    
    # Download/Update ReShade
    if [[ $RESHADE_VERSION == "latest" ]]; then
        local download_link=$(get_latest_version $RESHADE_ADDON_SUPPORT)
        local version=$(echo "$download_link" | grep -o "[0-9][0-9.]*[0-9]")
        [[ $download_link =~ ^/ ]] && download_link="${RESHADE_URL}${download_link}"
        download_reshade "$version" "$download_link"
    else
        [[ $RESHADE_ADDON_SUPPORT -eq 1 ]] && RESHADE_VERSION="${RESHADE_VERSION}_Addon"
        download_reshade "$RESHADE_VERSION" "$RESHADE_URL/downloads/ReShade_Setup_$RESHADE_VERSION.exe"
    fi
    
    # Download components
    download_d3dcompiler "32"
    download_d3dcompiler "64"
    download_shaders
    setup_reshade_ini
    
    echo -e "$SEPERATOR\nReShade installation completed successfully"
    echo "Shaders installed to: $MAIN_PATH/ReShade_shaders"
    [[ -f "$MAIN_PATH/$GLOBAL_INI" ]] && echo "ReShade.ini created at: $MAIN_PATH/$GLOBAL_INI"
}

main "$@"