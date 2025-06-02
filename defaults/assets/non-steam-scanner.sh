#!/bin/bash

# Common game installation directories
HEROIC_DIRS=(
    "$HOME/Games/Heroic"
    "$HOME/.local/share/games/heroic"
    "/mnt/*/Games/Heroic"
    "/run/media/*/Games/Heroic"
)

LUTRIS_DIRS=(
    "$HOME/Games"
    "$HOME/.local/share/lutris/games"
    "/mnt/*/Games"
    "/run/media/*/Games"
)

BOTTLES_DIRS=(
    "$HOME/.var/app/com.usebottles.bottles/data/bottles/bottles"
    "$HOME/.local/share/bottles/bottles"
)

LEGENDARY_DIRS=(
    "$HOME/.config/legendary/installed"
    "$HOME/Games/legendary"
)

# NonSteamLaunchers paths
NSL_PREFIX="$HOME/.local/share/Steam/steamapps/compatdata/NonSteamLaunchers/pfx/drive_c"

FOUND_GAMES='[]'

# Function to find executables in a directory
find_executables() {
    local dir="$1"
    local launcher="$2"
    local max_depth="${3:-3}"
    
    if [[ ! -d "$dir" ]]; then
        return
    fi
    
    # Find .exe files, excluding common launcher/installer executables
    find "$dir" -maxdepth "$max_depth" -name "*.exe" -type f 2>/dev/null | \
    grep -v -E "(unins|setup|install|launcher|updater|crash|report|helper|redis|node|python|ruby|java|UnityCrashHandler)" | \
    while read -r exe; do
        # Get the game directory (parent of the exe)
        local game_dir=$(dirname "$exe")
        local game_name=$(basename "$game_dir")
        
        # Skip if it looks like a system directory
        if [[ "$game_name" =~ ^(bin|lib|tools|engine|sdk|_CommonRedist|DirectX|vcredist)$ ]]; then
            continue
        fi
        
        # For deeply nested exes, try to get a better game name
        if [[ "$exe" =~ /Binaries/ ]] || [[ "$exe" =~ /bin/ ]]; then
            # Go up two directories for Unreal/Unity games
            game_name=$(basename "$(dirname "$(dirname "$exe")")")
        fi
        
        # Clean up the game name
        game_name=$(echo "$game_name" | sed 's/_/ /g' | sed 's/  */ /g')
        
        echo "{\"name\": \"$game_name\", \"launcher\": \"$launcher\", \"path\": \"$game_dir\", \"exe\": \"$exe\"}"
    done
}

# Scan Heroic games
echo "Scanning Heroic directories..." >&2
HEROIC_GAMES=""
for dir in "${HEROIC_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "Found Heroic dir: $dir" >&2
        while IFS= read -r game; do
            [[ -n "$game" ]] && HEROIC_GAMES="${HEROIC_GAMES}${game},"
        done < <(find_executables "$dir" "Heroic" 4)
    fi
done

# Scan Lutris games
echo "Scanning Lutris directories..." >&2
LUTRIS_GAMES=""
for dir in "${LUTRIS_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "Found Lutris dir: $dir" >&2
        while IFS= read -r game; do
            [[ -n "$game" ]] && LUTRIS_GAMES="${LUTRIS_GAMES}${game},"
        done < <(find_executables "$dir" "Lutris" 3)
    fi
done

# Scan Bottles
echo "Scanning Bottles directories..." >&2
BOTTLES_GAMES=""
for dir in "${BOTTLES_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "Found Bottles dir: $dir" >&2
        # Bottles has a specific structure
        for bottle in "$dir"/*; do
            [[ -d "$bottle/drive_c" ]] || continue
            while IFS= read -r game; do
                [[ -n "$game" ]] && BOTTLES_GAMES="${BOTTLES_GAMES}${game},"
            done < <(find_executables "$bottle/drive_c/Program Files" "Bottles" 3)
            while IFS= read -r game; do
                [[ -n "$game" ]] && BOTTLES_GAMES="${BOTTLES_GAMES}${game},"
            done < <(find_executables "$bottle/drive_c/Program Files (x86)" "Bottles" 3)
        done
    fi
done

# Scan NonSteamLaunchers
echo "Scanning NonSteamLaunchers..." >&2
NSL_GAMES=""
if [[ -d "$NSL_PREFIX" ]]; then
    echo "Found NSL prefix: $NSL_PREFIX" >&2
    # Epic Games
    if [[ -d "$NSL_PREFIX/Program Files/Epic Games" ]]; then
        while IFS= read -r game; do
            [[ -n "$game" ]] && NSL_GAMES="${NSL_GAMES}${game},"
        done < <(find_executables "$NSL_PREFIX/Program Files/Epic Games" "Epic (NSL)" 3)
    fi
    
    # EA Games
    if [[ -d "$NSL_PREFIX/Program Files/EA Games" ]]; then
        while IFS= read -r game; do
            [[ -n "$game" ]] && NSL_GAMES="${NSL_GAMES}${game},"
        done < <(find_executables "$NSL_PREFIX/Program Files/EA Games" "EA (NSL)" 3)
    fi
fi

# Combine all games
ALL_GAMES="${HEROIC_GAMES}${LUTRIS_GAMES}${BOTTLES_GAMES}${NSL_GAMES}"

# Remove trailing comma and wrap in array
if [[ -n "$ALL_GAMES" ]]; then
    ALL_GAMES="[${ALL_GAMES%,}]"
else
    ALL_GAMES="[]"
fi

echo "$ALL_GAMES"