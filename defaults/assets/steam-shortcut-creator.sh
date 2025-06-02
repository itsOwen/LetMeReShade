#!/bin/bash

GAME_NAME="$1"
EXE_PATH="$2"
GAME_DIR="$3"

# Steam user detection
STEAM_USER_ID=$(ls -1 "$HOME/.steam/steam/userdata" 2>/dev/null | head -1)
if [[ -z "$STEAM_USER_ID" ]]; then
    echo "Error: Could not find Steam user ID" >&2
    exit 1
fi

SHORTCUTS_VDF="$HOME/.steam/steam/userdata/$STEAM_USER_ID/config/shortcuts.vdf"
LOCALCONFIG="$HOME/.steam/steam/userdata/$STEAM_USER_ID/config/localconfig.vdf"

# Detect architecture and DLL override
cd "$GAME_DIR"
ARCH=$(file "$EXE_PATH" | grep -q "x86-64" && echo "64" || echo "32")

# Default to dxgi for most games
DLL_OVERRIDE="dxgi"

# Generate unique app ID for non-Steam game
APP_ID=$(echo -n "$EXE_PATH" | md5sum | cut -c1-8)
APP_ID=$((0x02000000 + 0x$APP_ID % 0x01000000))

echo "Generated App ID: $APP_ID"

# Create backup
cp "$SHORTCUTS_VDF" "$SHORTCUTS_VDF.bak" 2>/dev/null || true

# First, ensure Steam is not running
if pgrep -x "steam" > /dev/null; then
    echo "Steam is running. It will be closed to apply changes."
    killall -q steam || true
    sleep 2
fi

# Get available Proton version
PROTON_VERSION=""
STEAM_ROOT="$HOME/.steam/steam"
COMPAT_TOOLS_DIR="$STEAM_ROOT/steamapps/common"

# Check for Proton versions in order of preference
for proton_dir in "Proton - Experimental" "Proton 9.0 (Beta)" "Proton 8.0" "Proton 7.0" "Proton 6.3"; do
    if [[ -d "$COMPAT_TOOLS_DIR/$proton_dir" ]]; then
        # Get the internal name from compatibilitytool.vdf
        COMPAT_VDF="$COMPAT_TOOLS_DIR/$proton_dir/compatibilitytool.vdf"
        if [[ -f "$COMPAT_VDF" ]]; then
            # Extract the internal name
            PROTON_VERSION=$(grep -A5 '"compat_tools"' "$COMPAT_VDF" | grep -E '^\s+"[^"]+"\s*$' | head -1 | tr -d ' \t"')
            if [[ -n "$PROTON_VERSION" ]]; then
                echo "Found Proton: $PROTON_VERSION in $proton_dir"
                break
            fi
        fi
    fi
done

# If we couldn't find it that way, try the simple approach
if [[ -z "$PROTON_VERSION" ]]; then
    for proton in "proton_experimental" "proton_9" "proton_8" "proton_7" "proton_63"; do
        if [[ -d "$COMPAT_TOOLS_DIR/Proton"* ]] && [[ -d "$COMPAT_TOOLS_DIR/"*"$proton"* ]]; then
            PROTON_VERSION="$proton"
            echo "Found Proton (fallback): $PROTON_VERSION"
            break
        fi
    done
fi

# Create the entry name with ReShade suffix
ENTRY_NAME="${GAME_NAME} (ReShade)"

# Create a Python script to add the shortcut
python3 << EOF
import struct
import os

def create_shortcut_entry(index, app_name, exe_path, start_dir, launch_options):
    """Create a binary shortcut entry"""
    entry = b'\x00' + str(index).encode('ascii') + b'\x00'
    
    # Add fields
    fields = [
        (b'\x02appid\x00', struct.pack('<I', $APP_ID)),
        (b'\x01AppName\x00', app_name.encode('utf-8') + b'\x00'),
        (b'\x01Exe\x00', exe_path.encode('utf-8') + b'\x00'),
        (b'\x01StartDir\x00', start_dir.encode('utf-8') + b'\x00'),
        (b'\x01icon\x00', b'\x00'),
        (b'\x01ShortcutPath\x00', b'\x00'),
        (b'\x01LaunchOptions\x00', launch_options.encode('utf-8') + b'\x00'),
        (b'\x02IsHidden\x00', struct.pack('<I', 0)),
        (b'\x02AllowDesktopConfig\x00', struct.pack('<I', 1)),
        (b'\x02AllowOverlay\x00', struct.pack('<I', 1)),
        (b'\x02OpenVR\x00', struct.pack('<I', 0)),
        (b'\x02Devkit\x00', struct.pack('<I', 0)),
        (b'\x01DevkitGameID\x00', b'\x00'),
        (b'\x02DevkitOverrideAppID\x00', struct.pack('<I', 0)),
        (b'\x02LastPlayTime\x00', struct.pack('<I', 0)),
        (b'\x00tags\x00', b'\x08\x08')
    ]
    
    for field_name, field_value in fields:
        entry += field_name + field_value
    
    entry += b'\x08\x08'
    return entry

# Read existing shortcuts
shortcuts_path = "$SHORTCUTS_VDF"
if os.path.exists(shortcuts_path):
    with open(shortcuts_path, 'rb') as f:
        data = f.read()
    
    # Find the highest index
    max_index = -1
    pos = 0
    while pos < len(data):
        if data[pos] == 0x00 and pos + 1 < len(data):
            # Try to read index
            end_pos = data.find(b'\x00', pos + 1)
            if end_pos > pos + 1:
                try:
                    index = int(data[pos+1:end_pos])
                    if index > max_index:
                        max_index = index
                except:
                    pass
        pos += 1
    
    next_index = max_index + 1
else:
    # Create new shortcuts file
    data = b'\x00shortcuts\x00'
    next_index = 0

# Create new entry
new_entry = create_shortcut_entry(
    next_index,
    "$ENTRY_NAME",
    "$EXE_PATH",
    "$GAME_DIR",
    'WINEDLLOVERRIDES="d3dcompiler_47=n;$DLL_OVERRIDE=n,b" %command%'
)

# Insert new entry before the final closing bytes
if data.endswith(b'\x08\x08'):
    data = data[:-2] + new_entry + b'\x08\x08'
else:
    data = data + new_entry + b'\x08\x08'

# Write back
with open(shortcuts_path, 'wb') as f:
    f.write(data)

print(f"Successfully added shortcut with index {next_index}")
print(f"App ID: $APP_ID")
EOF

# Now update localconfig.vdf to set Proton compatibility
if [[ -f "$LOCALCONFIG" && -n "$PROTON_VERSION" ]]; then
    echo "Setting Proton compatibility for App ID $APP_ID to $PROTON_VERSION"
    
    # Create a Python script to modify localconfig properly
    python3 << EOFPY
import re
import os

app_id = "$APP_ID"
proton_version = "$PROTON_VERSION"
localconfig_path = "$LOCALCONFIG"

# Read the file
with open(localconfig_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# First, let's find the CompatToolMapping section
# Look for the pattern more carefully
pattern = r'("CompatToolMapping"\s*{[^}]*})'
match = re.search(pattern, content, re.DOTALL)

if match:
    # Extract the existing mapping content
    mapping_section = match.group(1)
    
    # Check if our app_id already exists
    if f'"{app_id}"' in mapping_section:
        print(f"App ID {app_id} already has compatibility set")
    else:
        # Add our new entry
        # Find the last closing brace of CompatToolMapping
        insert_pos = mapping_section.rfind('}')
        
        new_entry = f'''
				"{app_id}"
				{{
					"name"		"{proton_version}"
					"config"		""
					"priority"		"250"
				}}'''
        
        # Insert the new entry
        new_mapping = mapping_section[:insert_pos] + new_entry + '\n\t\t\t' + mapping_section[insert_pos:]
        
        # Replace in the original content
        content = content.replace(mapping_section, new_mapping)
        
        print(f"Added compatibility entry for {app_id}")
else:
    # CompatToolMapping doesn't exist, we need to create it
    # Find the Steam section
    steam_pattern = r'("Steam"\s*{)'
    steam_match = re.search(steam_pattern, content)
    
    if steam_match:
        insert_pos = steam_match.end()
        
        new_section = f'''
				"CompatToolMapping"
				{{
					"{app_id}"
					{{
						"name"		"{proton_version}"
						"config"		""
						"priority"		"250"
					}}
				}}'''
        
        # Find a good place to insert (after the opening brace of Steam section)
        # Look for the next line after "Steam" {
        next_line_pos = content.find('\n', insert_pos)
        if next_line_pos != -1:
            content = content[:next_line_pos] + new_section + content[next_line_pos:]
            print(f"Created CompatToolMapping section with entry for {app_id}")

# Write the file back
with open(localconfig_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Proton compatibility set successfully")
EOFPY

else
    if [[ -z "$PROTON_VERSION" ]]; then
        echo "Warning: No Proton version found. You'll need to set compatibility manually."
    else
        echo "Warning: localconfig.vdf not found"
    fi
fi

echo ""
echo "=== Success! ==="
echo "Shortcut created: $ENTRY_NAME"
echo "App ID: $APP_ID"
if [[ -n "$PROTON_VERSION" ]]; then
    echo "Proton version: $PROTON_VERSION"
else
    echo "Note: Proton compatibility needs to be set manually in Steam"
fi
echo ""
echo "Please restart Steam to see the new shortcut"