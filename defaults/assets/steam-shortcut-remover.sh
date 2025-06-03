#!/bin/bash

GAME_NAME="$1"
EXE_PATH="$2"

# Steam user detection
STEAM_USER_ID=$(ls -1 "$HOME/.steam/steam/userdata" 2>/dev/null | head -1)
if [[ -z "$STEAM_USER_ID" ]]; then
    echo "Error: Could not find Steam user ID" >&2
    exit 1
fi

SHORTCUTS_VDF="$HOME/.steam/steam/userdata/$STEAM_USER_ID/config/shortcuts.vdf"

if [[ ! -f "$SHORTCUTS_VDF" ]]; then
    echo "Error: shortcuts.vdf not found" >&2
    exit 1
fi

# Create backup
cp "$SHORTCUTS_VDF" "$SHORTCUTS_VDF.bak" 2>/dev/null || true

echo "Removing shortcut for: $GAME_NAME"

# Use Python to remove the shortcut
python3 << EOF
import os

def remove_shortcut(game_name, exe_path):
    shortcuts_path = "$SHORTCUTS_VDF"
    
    if not os.path.exists(shortcuts_path):
        print("Error: shortcuts.vdf not found")
        return False
    
    with open(shortcuts_path, 'rb') as f:
        data = f.read()
    
    # Find and remove the entry
    removed = False
    output = b''
    pos = 0
    
    while pos < len(data):
        # Look for entry start
        if data[pos] == 0x00 and pos + 1 < len(data):
            entry_start = pos
            
            # Try to find the AppName in this entry
            app_name_marker = b'\\x01AppName\\x00'
            next_entry = data.find(b'\\x00', pos + 1)
            
            if next_entry > pos:
                # Check if this entry contains our game name
                entry_section = data[pos:pos+2000]  # Check next 2000 bytes
                
                if game_name.encode('utf-8') in entry_section:
                    # Found the entry, skip to the next one
                    # Find the end of this entry (look for the next \x00 digit \x00 pattern or end markers)
                    end_pos = pos + 1
                    bracket_count = 0
                    
                    while end_pos < len(data):
                        if data[end_pos] == 0x08:
                            if end_pos + 1 < len(data) and data[end_pos + 1] == 0x08:
                                # Found end marker
                                end_pos += 2
                                # Skip any additional end markers
                                while end_pos < len(data) and data[end_pos] == 0x08:
                                    end_pos += 1
                                break
                        elif data[end_pos] == 0x00 and end_pos + 2 < len(data):
                            # Check if this is the start of a new entry
                            try:
                                # Look for pattern like \x00[digit]\x00
                                if data[end_pos + 1] >= ord('0') and data[end_pos + 1] <= ord('9'):
                                    if end_pos + 2 < len(data) and data[end_pos + 2] == 0x00:
                                        break
                            except:
                                pass
                        end_pos += 1
                    
                    # Skip this entry
                    pos = end_pos
                    removed = True
                    print(f"Found and removed entry for {game_name}")
                    continue
        
        output += data[pos:pos+1]
        pos += 1
    
    if removed:
        # Write the modified data back
        with open(shortcuts_path, 'wb') as f:
            f.write(output)
        print("Successfully removed shortcut")
        return True
    else:
        print(f"Shortcut for {game_name} not found")
        return False

# Remove the shortcut
success = remove_shortcut("$GAME_NAME", "$EXE_PATH")
exit(0 if success else 1)
EOF

if [[ $? -eq 0 ]]; then
    echo "Shortcut removed successfully"
else
    echo "Failed to remove shortcut" >&2
    exit 1
fi