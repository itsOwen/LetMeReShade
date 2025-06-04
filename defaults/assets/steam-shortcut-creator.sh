#!/bin/bash

GAME_NAME="$1"
EXE_PATH="$2"
GAME_DIR="$3"
DLL_OVERRIDE="${4:-dxgi}"  # Use provided DLL or default to dxgi

# Steam user detection
STEAM_USER_ID=$(ls -1 "$HOME/.steam/steam/userdata" 2>/dev/null | head -1)
if [[ -z "$STEAM_USER_ID" ]]; then
    echo "Error: Could not find Steam user ID" >&2
    exit 1
fi

SHORTCUTS_VDF="$HOME/.steam/steam/userdata/$STEAM_USER_ID/config/shortcuts.vdf"

# Detect architecture 
cd "$GAME_DIR"
ARCH=$(file "$EXE_PATH" | grep -q "x86-64" && echo "64" || echo "32")

echo "Using DLL override: $DLL_OVERRIDE"

# Generate unique app ID for non-Steam game
APP_ID=$(echo -n "$EXE_PATH" | md5sum | cut -c1-8)
APP_ID=$((0x02000000 + 0x$APP_ID % 0x01000000))

echo "Generated App ID: $APP_ID"

# Create backup
cp "$SHORTCUTS_VDF" "$SHORTCUTS_VDF.bak" 2>/dev/null || true

# Create the entry name with ReShade suffix
ENTRY_NAME="${GAME_NAME} (ReShade)"

# Add the shortcut
echo "Adding $ENTRY_NAME to Steam shortcuts..."

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

# Create new entry with the detected DLL override
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

echo ""
echo "=== Success! ==="
echo "Shortcut created: $ENTRY_NAME"
echo "App ID: $APP_ID"
echo "DLL Override: $DLL_OVERRIDE"
echo ""
echo "IMPORTANT: After restarting Steam, you'll need to:"
echo "1. Right-click the game in your library"
echo "2. Go to Properties > Compatibility"
echo "3. Enable 'Force the use of a specific Steam Play compatibility tool'"
echo "4. Select your preferred Proton version"
echo ""
echo "Please restart Steam to see the new shortcut"