import decky
import os
import subprocess
import shutil
from pathlib import Path
import json
import glob
import re
import time

class Plugin:
    def __init__(self):
        self.environment = {
            'XDG_DATA_HOME': os.path.expandvars('$HOME/.local/share'),
            'UPDATE_RESHADE': '1',
            'MERGE_SHADERS': '1',
            'VULKAN_SUPPORT': '0',
            'GLOBAL_INI': 'ReShade.ini',
            'DELETE_RESHADE_FILES': '0',
            'FORCE_RESHADE_UPDATE_CHECK': '0',
            'RESHADE_ADDON_SUPPORT': '0',
            'RESHADE_VERSION': 'latest',
            'AUTOHDR_ENABLED': '0'
        }
        # Separate base paths for ReShade and VkBasalt
        self.main_path = os.path.join(self.environment['XDG_DATA_HOME'], 'reshade')
        self.vkbasalt_base_path = os.path.join(self.environment['XDG_DATA_HOME'], 'vkbasalt')
        self.vkbasalt_path = os.path.join(self.vkbasalt_base_path, 'installation')
        
        # Cache for executable paths
        self.executable_cache = {}
        
        # Create necessary directories
        os.makedirs(self.main_path, exist_ok=True)
        os.makedirs(self.vkbasalt_path, exist_ok=True)

    def _get_assets_dir(self) -> Path:
        """Get the assets directory, checking both possible locations"""
        plugin_dir = Path(decky.DECKY_PLUGIN_DIR)
        
        # Check defaults/assets first (development)
        defaults_assets = plugin_dir / "defaults" / "assets"
        if defaults_assets.exists():
            decky.logger.info(f"Using assets from: {defaults_assets}")
            return defaults_assets
            
        # Check assets (decky store installation)
        assets = plugin_dir / "assets"
        if assets.exists():
            decky.logger.info(f"Using assets from: {assets}")
            return assets
            
        # Fallback to defaults/assets even if it doesn't exist (for error reporting)
        decky.logger.warning(f"Neither {defaults_assets} nor {assets} exists, defaulting to {defaults_assets}")
        return defaults_assets

    async def _main(self):
        assets_dir = self._get_assets_dir()
        for script in assets_dir.glob("*.sh"):
            script.chmod(0o755)
        decky.logger.info("ReShade plugin loaded")

    async def _unload(self):
        decky.logger.info("ReShade plugin unloaded")

    async def parse_steam_logs_for_executable(self, appid: str) -> dict:
        """Parse Steam console logs to find the exact executable path Steam uses"""
        try:
            decky.logger.info(f"Parsing Steam logs for App ID: {appid}")
            
            # Check cache first
            cache_key = f"steam_log_{appid}"
            if cache_key in self.executable_cache:
                cached_result = self.executable_cache[cache_key]
                # Check if cache is less than 1 hour old
                if time.time() - cached_result.get('timestamp', 0) < 3600:
                    decky.logger.info(f"Using cached result for {appid}")
                    return cached_result
            
            # Steam log file locations
            log_files = [
                "/home/deck/.steam/steam/logs/console-linux.txt",
                "/home/deck/.steam/steam/logs/console_log.txt", 
                "/home/deck/.steam/steam/logs/console_log.previous.txt"
            ]
            
            executable_path = None
            launch_command = None
            
            for log_file in log_files:
                if not os.path.exists(log_file):
                    continue
                    
                decky.logger.info(f"Checking log file: {log_file}")
                
                try:
                    # Read the log file (check last 10000 lines for performance)
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Check recent lines first (Steam logs can be large)
                        recent_lines = lines[-10000:] if len(lines) > 10000 else lines
                        
                    # Look for game launch patterns
                    for line in recent_lines:
                        # Pattern 1: Direct executable in launch command
                        # Example: AppId=501300 -- ... '/path/to/game.exe'
                        if f"AppId={appid}" in line and ".exe" in line:
                            # Extract the executable path
                            exe_match = re.search(r"'([^']*\.exe)'", line)
                            if exe_match:
                                potential_exe = exe_match.group(1)
                                # Verify this is a real path and not a temp file
                                if "/steamapps/common/" in potential_exe and os.path.exists(potential_exe):
                                    executable_path = potential_exe
                                    launch_command = line.strip()
                                    decky.logger.info(f"Found executable from logs: {executable_path}")
                                    break
                        
                        # Pattern 2: Game process added/updated logs
                        # Example: Game process added : AppID 501300 "command with exe path"
                        if f"AppID {appid}" in line and (".exe" in line or "Game process" in line):
                            exe_match = re.search(r"'([^']*\.exe)'", line)
                            if not exe_match:
                                # Try different quote patterns
                                exe_match = re.search(r'"([^"]*\.exe)"', line)
                            if exe_match:
                                potential_exe = exe_match.group(1)
                                if "/steamapps/common/" in potential_exe and os.path.exists(potential_exe):
                                    executable_path = potential_exe
                                    launch_command = line.strip()
                                    decky.logger.info(f"Found executable from process log: {executable_path}")
                                    break
                    
                    if executable_path:
                        break
                        
                except Exception as e:
                    decky.logger.error(f"Error reading log file {log_file}: {str(e)}")
                    continue
            
            if executable_path:
                # Cache the result
                result = {
                    "status": "success",
                    "method": "steam_logs",
                    "executable_path": executable_path,
                    "directory_path": os.path.dirname(executable_path),
                    "filename": os.path.basename(executable_path),
                    "launch_command": launch_command,
                    "timestamp": time.time()
                }
                self.executable_cache[cache_key] = result
                
                return result
            else:
                decky.logger.info(f"No executable found in logs for App ID: {appid}")
                return {
                    "status": "not_found",
                    "method": "steam_logs", 
                    "message": "No executable path found in Steam logs"
                }
                
        except Exception as e:
            decky.logger.error(f"Error parsing Steam logs: {str(e)}")
            return {
                "status": "error",
                "method": "steam_logs",
                "message": str(e)
            }

    async def find_game_executable_enhanced(self, appid: str) -> dict:
        """Enhanced executable detection using discovered patterns"""
        try:
            decky.logger.info(f"Enhanced executable detection for App ID: {appid}")
            
            # Get the base game path using existing method - but use the BASE path, not the detected exe path
            try:
                # Get the raw base game installation path
                steam_root = Path(decky.HOME) / ".steam" / "steam"
                library_file = steam_root / "steamapps" / "libraryfolders.vdf"

                if not library_file.exists():
                    return {"status": "error", "message": "Steam library file not found"}

                library_paths = []
                with open(library_file, "r", encoding="utf-8") as file:
                    for line in file:
                        if '"path"' in line:
                            path = line.split('"path"')[1].strip().strip('"').replace("\\\\", "/")
                            library_paths.append(path)

                base_game_path = None
                for library_path in library_paths:
                    manifest_path = Path(library_path) / "steamapps" / f"appmanifest_{appid}.acf"
                    if manifest_path.exists():
                        with open(manifest_path, "r", encoding="utf-8") as manifest:
                            for line in manifest:
                                if '"installdir"' in line:
                                    install_dir = line.split('"installdir"')[1].strip().strip('"')
                                    base_game_path = str(Path(library_path) / "steamapps" / "common" / install_dir)
                                    break
                        break

                if not base_game_path:
                    return {"status": "error", "message": f"Could not find installation directory for AppID: {appid}"}
                    
                decky.logger.info(f"Base game path for detection: {base_game_path}")
                
            except Exception as e:
                return {"status": "error", "message": str(e)}
            
            # Find all executables in the game directory
            all_executables = []
            
            decky.logger.info(f"Walking directory tree starting from: {base_game_path}")
            for root, dirs, files in os.walk(base_game_path):
                for file in files:
                    if file.lower().endswith('.exe'):
                        exe_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(exe_path)
                            rel_path = os.path.relpath(exe_path, base_game_path)
                            
                            all_executables.append({
                                "path": exe_path,
                                "directory_path": os.path.dirname(exe_path),
                                "relative_path": rel_path,
                                "filename": file,
                                "size": file_size,
                                "size_mb": round(file_size / (1024 * 1024), 1)
                            })
                            decky.logger.debug(f"Found exe: {file} ({rel_path}) - {round(file_size / (1024 * 1024), 1)}MB")
                        except Exception as e:
                            decky.logger.warning(f"Error getting size for {exe_path}: {str(e)}")
                            continue
            
            if not all_executables:
                return {
                    "status": "error",
                    "method": "enhanced_detection",
                    "message": f"No executables found in game directory: {base_game_path}"
                }
            
            decky.logger.info(f"Found {len(all_executables)} total executables")
            
            # Enhanced filtering based on discovered patterns
            def score_executable(exe_info):
                score = 50  # Start with a base score instead of 0
                filename = exe_info["filename"].lower()
                rel_path = exe_info["relative_path"].lower()
                size_mb = exe_info["size_mb"]
                
                decky.logger.debug(f"Scoring {filename} at {rel_path}")
                
                # LESS aggressive utility filtering - only skip very obvious ones
                utility_keywords = ["unins", "setup", "vcredist", "directx", "redist"]
                if any(skip in filename for skip in utility_keywords):
                    decky.logger.debug(f"  Utility file detected: {filename}")
                    return 0  # Set to 0 instead of negative
                
                # Size-based scoring (more moderate)
                if size_mb > 50:      # Large games
                    score += 35
                elif size_mb > 20:    # Medium games  
                    score += 25
                elif size_mb > 5:     # Small games
                    score += 15
                elif size_mb > 1:     # Small but not tiny
                    score += 5
                elif size_mb < 0.5:   # Very small files (likely utilities)
                    score -= 20
                
                # Path-based scoring (more moderate)
                if "binaries/win64" in rel_path or "binaries\\win64" in rel_path:    # Unreal Engine pattern
                    score += 25
                elif "bin" in rel_path:             # Common bin directory
                    score += 15
                elif "game" in rel_path:            # Game subdirectory
                    score += 10
                elif rel_path.count("/") == 0 and rel_path.count("\\") == 0:  # Root directory
                    score += 8
                
                # Filename-based scoring (more moderate)
                if any(good in filename for good in [
                    "game", "main", "client", "app"
                ]):
                    score += 12
                
                # Special patterns from real data (more moderate)
                if "shipping" in filename:          # Unreal shipping builds
                    score += 20
                elif "win64" in filename:           # 64-bit indicator
                    score += 8
                elif "launcher" in filename:        # Launchers (lower score but don't exclude)
                    score -= 15
                
                # Moderate penalty for deep nesting
                path_depth = rel_path.count("/") + rel_path.count("\\")
                if path_depth > 4:  # Increased threshold
                    score -= (path_depth - 4) * 3
                
                # Cap score between 0 and 100
                score = max(0, min(100, score))
                
                decky.logger.debug(f"  Final score for {filename}: {score}")
                return score
            
            # Score all executables - use much lower threshold
            scored_executables = []
            for exe_info in all_executables:
                score = score_executable(exe_info)
                # Much more permissive threshold - only exclude very obvious utilities
                if score > 0:  # Changed from -50 to 0 for 0-100 scale
                    scored_executables.append({
                        **exe_info,
                        "score": score
                    })
                else:
                    decky.logger.debug(f"Filtered out {exe_info['filename']} with score {score}")
            
            if not scored_executables:
                # If we filtered everything out, include everything with any positive score
                decky.logger.warning("All executables filtered out, using less restrictive filtering")
                for exe_info in all_executables:
                    score = score_executable(exe_info)
                    if score >= 0:  # Even more permissive
                        scored_executables.append({
                            **exe_info,
                            "score": score
                        })
            
            if not scored_executables:
                # Last resort: include everything
                decky.logger.warning("Still no executables, including all found")
                for exe_info in all_executables:
                    scored_executables.append({
                        **exe_info,
                        "score": score_executable(exe_info)
                    })
            
            # Sort by score (highest first) and take top 5
            scored_executables.sort(key=lambda x: x["score"], reverse=True)
            top_executables = scored_executables[:5]
            
            best_executable = top_executables[0]
            
            decky.logger.info(f"Total executables after filtering: {len(scored_executables)}")
            decky.logger.info(f"Top 5 executables:")
            for i, exe in enumerate(top_executables):
                decky.logger.info(f"  {i+1}. {exe['filename']} (score: {exe['score']}) at {exe['relative_path']}")
            
            return {
                "status": "success",
                "method": "enhanced_detection", 
                "executable_path": best_executable["path"],
                "directory_path": best_executable["directory_path"],
                "filename": best_executable["filename"],
                "all_executables": top_executables,  # Top 5 for UI
                "confidence": "high" if best_executable["score"] > 100 else "medium"
            }
            
        except Exception as e:
            decky.logger.error(f"Enhanced detection error: {str(e)}")
            return {
                "status": "error",
                "method": "enhanced_detection", 
                "message": str(e)
            }

    async def find_game_executable_path(self, appid: str) -> dict:
        """
        Primary method that runs BOTH Steam logs and enhanced detection, returning both results
        """
        try:
            decky.logger.info(f"Finding executable path for App ID: {appid}")
            
            # Method 1: Steam console logs
            steam_logs_result = await self.parse_steam_logs_for_executable(appid)
            
            # Method 2: Enhanced detection (always run now)
            enhanced_result = await self.find_game_executable_enhanced(appid)
            
            # Determine recommended method
            recommended_method = "steam_logs"
            if steam_logs_result["status"] != "success":
                recommended_method = "enhanced_detection"
            
            return {
                "status": "success",
                "steam_logs_result": steam_logs_result,
                "enhanced_detection_result": enhanced_result,
                "recommended_method": recommended_method
            }
            
        except Exception as e:
            decky.logger.error(f"Error in find_game_executable_path: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def find_heroic_game_executable_path(self, game_path: str, game_name: str) -> dict:
        """
        Find executable paths for a Heroic game, similar to Steam game detection
        """
        try:
            decky.logger.info(f"Finding executable path for Heroic game: {game_name} at {game_path}")
            
            # Check cache first
            cache_key = f"heroic_{game_path}_{game_name}"
            if cache_key in self.executable_cache:
                cached_result = self.executable_cache[cache_key]
                # Check if cache is less than 1 hour old
                if time.time() - cached_result.get('timestamp', 0) < 3600:
                    decky.logger.info(f"Using cached result for {game_name}")
                    return cached_result
            
            # Verify game path exists
            if not os.path.exists(game_path):
                return {"status": "error", "message": f"Game path not found: {game_path}"}
            
            game_path_obj = Path(game_path)
            
            # Find all executables in the game directory
            all_executables = []
            
            decky.logger.info(f"Walking directory tree starting from: {game_path}")
            for root, dirs, files in os.walk(game_path):
                for file in files:
                    if file.lower().endswith('.exe'):
                        exe_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(exe_path)
                            rel_path = os.path.relpath(exe_path, game_path)
                            
                            all_executables.append({
                                "path": exe_path,
                                "directory_path": os.path.dirname(exe_path),
                                "relative_path": rel_path,
                                "filename": file,
                                "size": file_size,
                                "size_mb": round(file_size / (1024 * 1024), 1)
                            })
                            decky.logger.debug(f"Found exe: {file} ({rel_path}) - {round(file_size / (1024 * 1024), 1)}MB")
                        except Exception as e:
                            decky.logger.warning(f"Error getting size for {exe_path}: {str(e)}")
                            continue
            
            if not all_executables:
                return {
                    "status": "error",
                    "method": "heroic_enhanced_detection",
                    "message": f"No executables found in game directory: {game_path}"
                }
            
            decky.logger.info(f"Found {len(all_executables)} total executables")
            
            # Extract words from game name for better matching
            game_words = set(re.findall(r'\w+', game_name.lower()))
            
            decky.logger.info(f"Game words for matching: {game_words}")
            
            # Enhanced filtering based on discovered patterns
            def score_executable(exe_info):
                score = 50  # Start with a base score
                filename = exe_info["filename"].lower()
                rel_path = exe_info["relative_path"].lower()
                size_mb = exe_info["size_mb"]
                
                decky.logger.debug(f"Scoring {filename} at {rel_path}")
                
                # LESS aggressive utility filtering - only skip very obvious ones
                utility_keywords = ["unins", "setup", "vcredist", "directx", "redist"]
                if any(skip in filename for skip in utility_keywords):
                    decky.logger.debug(f"  Utility file detected: {filename}")
                    return 0
                
                # Name matching with game name
                name_words = set(re.findall(r'\w+', filename.lower()))
                
                # Calculate word match score based on intersection
                matching_words = game_words.intersection(name_words)
                
                # If there are matching words, they're worth more if they're a larger percentage of the game name
                if matching_words:
                    match_percentage = len(matching_words) / len(game_words) if game_words else 0
                    word_score = len(matching_words) * 1.5 * (1 + match_percentage)
                    decky.logger.debug(f"  Name match score: +{word_score:.2f} (words: {matching_words})")
                    score += word_score
                
                # If the exe name is a substring of the game name or vice versa, that's a good indicator
                if filename in game_name.lower() or any(word in filename for word in game_words):
                    name_substring_score = 2
                    decky.logger.debug(f"  Name substring match: +{name_substring_score}")
                    score += name_substring_score
                
                # Check for exact name match (normalized)
                norm_exe_name = re.sub(r'[^a-z0-9]', '', filename)
                norm_game_name = re.sub(r'[^a-z0-9]', '', game_name.lower())
                
                if norm_exe_name == norm_game_name or filename == game_name.lower():
                    exact_match_score = 3
                    decky.logger.debug(f"  Exact normalized name match: +{exact_match_score}")
                    score += exact_match_score
                
                # Size-based scoring (more moderate)
                if size_mb > 50:      # Large games
                    score += 35
                elif size_mb > 20:    # Medium games  
                    score += 25
                elif size_mb > 5:     # Small games
                    score += 15
                elif size_mb > 1:     # Small but not tiny
                    score += 5
                elif size_mb < 0.5:   # Very small files (likely utilities)
                    score -= 20
                
                # Path-based scoring (more moderate)
                if "binaries/win64" in rel_path or "binaries\\win64" in rel_path:    # Unreal Engine pattern
                    score += 25
                elif "bin" in rel_path:             # Common bin directory
                    score += 15
                elif "game" in rel_path:            # Game subdirectory
                    score += 10
                elif rel_path.count("/") == 0 and rel_path.count("\\") == 0:  # Root directory
                    score += 8
                
                # Filename-based scoring (more moderate)
                if any(good in filename for good in [
                    "game", "main", "client", "app"
                ]):
                    score += 12
                
                # Special patterns from real data (more moderate)
                if "shipping" in filename:          # Unreal shipping builds
                    score += 20
                elif "win64" in filename:           # 64-bit indicator
                    score += 8
                elif "launcher" in filename:        # Launchers (lower score but don't exclude)
                    score -= 15
                
                # Moderate penalty for deep nesting
                path_depth = rel_path.count("/") + rel_path.count("\\")
                if path_depth > 4:  # Increased threshold
                    score -= (path_depth - 4) * 3
                
                # Cap score between 0 and 100
                score = max(0, min(100, score))
                
                decky.logger.debug(f"  Final score for {filename}: {score}")
                return score
            
            # Score all executables
            scored_executables = []
            for exe_info in all_executables:
                score = score_executable(exe_info)
                if score > 0:
                    scored_executables.append({
                        **exe_info,
                        "score": score
                    })
                else:
                    decky.logger.debug(f"Filtered out {exe_info['filename']} with score {score}")
            
            if not scored_executables:
                # If we filtered everything out, include everything with any positive score
                decky.logger.warning("All executables filtered out, using less restrictive filtering")
                for exe_info in all_executables:
                    score = score_executable(exe_info)
                    if score >= 0:
                        scored_executables.append({
                            **exe_info,
                            "score": score
                        })
            
            if not scored_executables:
                # Last resort: include everything
                decky.logger.warning("Still no executables, including all found")
                for exe_info in all_executables:
                    scored_executables.append({
                        **exe_info,
                        "score": score_executable(exe_info)
                    })
            
            # Sort by score (highest first) and take top 5
            scored_executables.sort(key=lambda x: x["score"], reverse=True)
            top_executables = scored_executables[:5]
            
            best_executable = top_executables[0]
            
            decky.logger.info(f"Total executables after filtering: {len(scored_executables)}")
            decky.logger.info(f"Top 5 executables:")
            for i, exe in enumerate(top_executables):
                decky.logger.info(f"  {i+1}. {exe['filename']} (score: {exe['score']}) at {exe['relative_path']}")
            
            result = {
                "status": "success",
                "heroic_enhanced_detection_result": {
                    "status": "success",
                    "method": "heroic_enhanced_detection",
                    "executable_path": best_executable["path"],
                    "directory_path": best_executable["directory_path"],
                    "filename": best_executable["filename"],
                    "all_executables": top_executables,
                    "confidence": "high" if best_executable["score"] > 70 else "medium"
                },
                "recommended_method": "heroic_enhanced_detection",
                "timestamp": time.time()
            }
            
            # Cache the result
            self.executable_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            decky.logger.error(f"Heroic executable detection error: {str(e)}")
            return {
                "status": "error",
                "method": "heroic_enhanced_detection",
                "message": str(e)
            }

    async def save_shader_preferences(self, selected_shaders: list) -> dict:
        """Save user's shader preferences to a file"""
        try:
            preferences_file = os.path.join(self.main_path, "user_preferences.json")
            
            # Load existing preferences to preserve other settings
            existing_preferences = {}
            if os.path.exists(preferences_file):
                try:
                    with open(preferences_file, 'r') as f:
                        existing_preferences = json.load(f)
                except:
                    pass  # If file is corrupted, start fresh
            
            # Update shader preferences while preserving other settings
            existing_preferences.update({
                "selected_shaders": selected_shaders,
                "last_updated": int(time.time()),
                "version": "1.1"
            })
            
            # Ensure directory exists
            os.makedirs(self.main_path, exist_ok=True)
            
            with open(preferences_file, 'w') as f:
                json.dump(existing_preferences, f, indent=2)
            
            decky.logger.info(f"Saved shader preferences: {selected_shaders}")
            return {"status": "success", "message": "Shader preferences saved successfully"}
            
        except Exception as e:
            decky.logger.error(f"Error saving shader preferences: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def load_shader_preferences(self) -> dict:
        """Load user's shader preferences from file"""
        try:
            preferences_file = os.path.join(self.main_path, "user_preferences.json")
            
            # Also check old file for migration
            old_preferences_file = os.path.join(self.main_path, "shader_preferences.json")
            
            preferences = None
            
            # Try to load from new file first
            if os.path.exists(preferences_file):
                with open(preferences_file, 'r') as f:
                    preferences = json.load(f)
            # Migrate from old file if exists
            elif os.path.exists(old_preferences_file):
                with open(old_preferences_file, 'r') as f:
                    old_prefs = json.load(f)
                    # Migrate to new format
                    preferences = {
                        "selected_shaders": old_prefs.get("selected_shaders", []),
                        "last_updated": old_prefs.get("last_updated", int(time.time())),
                        "version": "1.1",
                        "autohdr_enabled": False  # Default for migrated preferences
                    }
                    # Save in new format and remove old file
                    with open(preferences_file, 'w') as f:
                        json.dump(preferences, f, indent=2)
                    try:
                        os.remove(old_preferences_file)
                    except:
                        pass
            
            if not preferences:
                return {"status": "success", "preferences": None, "message": "No preferences file found"}
            
            # Validate the preferences structure
            if "selected_shaders" not in preferences:
                return {"status": "error", "message": "Invalid preferences file format"}
            
            decky.logger.info(f"Loaded shader preferences: {preferences['selected_shaders']}")
            return {
                "status": "success", 
                "preferences": preferences,
                "selected_shaders": preferences["selected_shaders"]
            }
            
        except Exception as e:
            decky.logger.error(f"Error loading shader preferences: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def has_shader_preferences(self) -> dict:
        """Check if user has saved shader preferences"""
        try:
            preferences_file = os.path.join(self.main_path, "user_preferences.json")
            old_preferences_file = os.path.join(self.main_path, "shader_preferences.json")
            
            exists = os.path.exists(preferences_file) or os.path.exists(old_preferences_file)
            
            if exists:
                # Also load and return a summary
                result = await self.load_shader_preferences()
                if result["status"] == "success" and result["preferences"]:
                    shader_count = len(result["selected_shaders"])
                    return {
                        "status": "success",
                        "has_preferences": True,
                        "shader_count": shader_count,
                        "last_updated": result["preferences"].get("last_updated", 0)
                    }
            
            return {"status": "success", "has_preferences": False}
            
        except Exception as e:
            decky.logger.error(f"Error checking shader preferences: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def save_autohdr_preference(self, autohdr_enabled: bool) -> dict:
        """Save user's AutoHDR preference"""
        try:
            preferences_file = os.path.join(self.main_path, "user_preferences.json")
            
            # Load existing preferences to preserve other settings
            existing_preferences = {}
            if os.path.exists(preferences_file):
                try:
                    with open(preferences_file, 'r') as f:
                        existing_preferences = json.load(f)
                except:
                    pass  # If file is corrupted, start fresh
            
            # Update AutoHDR preference while preserving other settings
            existing_preferences.update({
                "autohdr_enabled": autohdr_enabled,
                "last_updated": int(time.time()),
                "version": "1.1"
            })
            
            # Ensure selected_shaders exists if it doesn't
            if "selected_shaders" not in existing_preferences:
                existing_preferences["selected_shaders"] = []
            
            # Ensure directory exists
            os.makedirs(self.main_path, exist_ok=True)
            
            with open(preferences_file, 'w') as f:
                json.dump(existing_preferences, f, indent=2)
            
            decky.logger.info(f"Saved AutoHDR preference: {autohdr_enabled}")
            return {"status": "success", "message": "AutoHDR preference saved successfully"}
            
        except Exception as e:
            decky.logger.error(f"Error saving AutoHDR preference: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def load_autohdr_preference(self) -> dict:
        """Load user's AutoHDR preference"""
        try:
            preferences_file = os.path.join(self.main_path, "user_preferences.json")
            
            if not os.path.exists(preferences_file):
                return {"status": "success", "autohdr_enabled": False, "message": "No preferences file found"}
            
            with open(preferences_file, 'r') as f:
                preferences = json.load(f)
            
            autohdr_enabled = preferences.get("autohdr_enabled", False)
            
            decky.logger.info(f"Loaded AutoHDR preference: {autohdr_enabled}")
            return {
                "status": "success", 
                "autohdr_enabled": autohdr_enabled
            }
            
        except Exception as e:
            decky.logger.error(f"Error loading AutoHDR preference: {str(e)}")
            return {"status": "error", "message": str(e), "autohdr_enabled": False}

    async def save_installed_configuration(self, with_addon: bool, version: str, with_autohdr: bool, selected_shaders: list) -> dict:
        """Save the configuration that was actually installed"""
        try:
            config_file = os.path.join(self.main_path, "installed_config.json")
            
            installed_config = {
                "with_addon": with_addon,
                "version": version,
                "with_autohdr": with_autohdr,
                "selected_shaders": selected_shaders or [],
                "installed_at": int(time.time())
            }
            
            os.makedirs(self.main_path, exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(installed_config, f, indent=2)
            
            decky.logger.info(f"Saved installed configuration: {installed_config}")
            return {"status": "success"}
            
        except Exception as e:
            decky.logger.error(f"Error saving installed configuration: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def load_installed_configuration(self) -> dict:
        """Load the configuration that was actually installed"""
        try:
            config_file = os.path.join(self.main_path, "installed_config.json")
            
            if not os.path.exists(config_file):
                return {"status": "success", "config": None}
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            return {"status": "success", "config": config}
            
        except Exception as e:
            decky.logger.error(f"Error loading installed configuration: {str(e)}")
            return {"status": "error", "message": str(e), "config": None}

    async def clear_installed_configuration(self) -> dict:
        """Clear the installed configuration (called on uninstall)"""
        try:
            config_file = os.path.join(self.main_path, "installed_config.json")
            
            if os.path.exists(config_file):
                os.remove(config_file)
            
            return {"status": "success"}
            
        except Exception as e:
            decky.logger.error(f"Error clearing installed configuration: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def get_available_shaders(self) -> dict:
        """Get list of available shader packages for selection"""
        try:
            # Get the bin directory path
            plugin_dir = Path(decky.DECKY_PLUGIN_DIR)
            
            # Check both possible locations for bin directory
            defaults_bin = plugin_dir / "defaults" / "bin"
            assets_bin = plugin_dir / "bin"
            
            bin_path = None
            if defaults_bin.exists():
                bin_path = defaults_bin
            elif assets_bin.exists():
                bin_path = assets_bin
            else:
                return {"status": "error", "message": "Bin directory not found"}

            # Define available shader packages with descriptions
            shader_packages = [
                {
                    "id": "reshade_shaders",
                    "name": "ReShade Community Shaders",
                    "description": "Official ReShade community shader collection",
                    "file": "reshade_shaders.tar.gz",
                    "size_mb": "~15MB",
                    "enabled": True
                },
                {
                    "id": "sweetfx_shaders", 
                    "name": "SweetFX Shaders",
                    "description": "Popular SweetFX shader effects collection",
                    "file": "sweetfx_shaders.tar.gz",
                    "size_mb": "~8MB",
                    "enabled": True
                },
                {
                    "id": "martymc_shaders",
                    "name": "MartyMcFly's RT Shaders",
                    "description": "High-quality ray tracing and lighting effects",
                    "file": "martymc_shaders.tar.gz", 
                    "size_mb": "~12MB",
                    "enabled": True
                },
                {
                    "id": "astrayfx_shaders",
                    "name": "AstrayFX Shaders",
                    "description": "Performance-focused shader collection",
                    "file": "astrayfx_shaders.tar.gz",
                    "size_mb": "~5MB", 
                    "enabled": True
                },
                {
                    "id": "prod80_shaders",
                    "name": "Prod80's Shaders",
                    "description": "Professional color grading and enhancement shaders",
                    "file": "prod80_shaders.tar.gz",
                    "size_mb": "~6MB",
                    "enabled": True
                },
                {
                    "id": "retroarch_shaders",
                    "name": "RetroArch Shaders",
                    "description": "Retro gaming and CRT emulation effects",
                    "file": "retroarch_shaders.tar.gz",
                    "size_mb": "~10MB",
                    "enabled": True
                }
            ]

            # Check which shader packages actually exist
            available_shaders = []
            for shader in shader_packages:
                shader_file = bin_path / shader["file"]
                if shader_file.exists():
                    # Get actual file size
                    file_size = shader_file.stat().st_size
                    size_mb = round(file_size / (1024 * 1024), 1)
                    shader["size_mb"] = f"{size_mb}MB"
                    available_shaders.append(shader)
                else:
                    decky.logger.warning(f"Shader package not found: {shader_file}")

            return {
                "status": "success",
                "shaders": available_shaders,
                "total_count": len(available_shaders)
            }

        except Exception as e:
            decky.logger.error(f"Error getting available shaders: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def detect_steam_deck_model(self) -> dict:
        """Detect Steam Deck model (OLED vs LCD) using board name"""
        try:
            decky.logger.info("Detecting Steam Deck model...")
            
            # First check if we can read system info at all
            is_steam_deck = False
            product_name = ""
            
            try:
                with open('/sys/devices/virtual/dmi/id/product_name', 'r') as f:
                    product_name = f.read().strip()
                decky.logger.info(f"DMI Product name: '{product_name}'")
                
                # More flexible Steam Deck detection
                if any(term in product_name.lower() for term in ["steam deck", "steamdeck", "jupiter", "galileo"]):
                    is_steam_deck = True
                    decky.logger.info("Confirmed this is a Steam Deck")
                else:
                    decky.logger.warning(f"Product name '{product_name}' doesn't indicate Steam Deck")
            except (FileNotFoundError, PermissionError) as e:
                decky.logger.warning(f"Could not read DMI product name: {e}")
            
            # If we can't confirm it's a Steam Deck through product name, 
            # let's assume it is and try board detection anyway
            if not is_steam_deck:
                decky.logger.info("Could not confirm Steam Deck via product name, proceeding with board detection")
            
            # Check board name - most reliable method for Steam Deck OLED vs LCD
            board_name = ""
            try:
                with open('/sys/devices/virtual/dmi/id/board_name', 'r') as f:
                    board_name = f.read().strip()
                decky.logger.info(f"DMI Board name: '{board_name}'")
                
                # Check for OLED (Galileo)
                if "Galileo" in board_name:
                    decky.logger.info("Detected Steam Deck OLED (Galileo)")
                    return {
                        "status": "success",
                        "model": "OLED",
                        "is_oled": True
                    }
                # Check for LCD (Jupiter)
                elif "Jupiter" in board_name:
                    decky.logger.info("Detected Steam Deck LCD (Jupiter)")
                    return {
                        "status": "success",
                        "model": "LCD",
                        "is_oled": False
                    }
                else:
                    decky.logger.warning(f"Unknown board name: '{board_name}'")
                    
                    # If we confirmed it's a Steam Deck but unknown board, default to LCD
                    if is_steam_deck:
                        decky.logger.info("Confirmed Steam Deck but unknown board, defaulting to LCD")
                        return {
                            "status": "success",
                            "model": "LCD",
                            "is_oled": False
                        }
                    
            except (FileNotFoundError, PermissionError) as e:
                decky.logger.warning(f"Could not read DMI board name: {e}")
            
            # Additional fallback checks for Steam Deck detection
            try:
                # Check system manufacturer
                with open('/sys/devices/virtual/dmi/id/sys_vendor', 'r') as f:
                    vendor = f.read().strip()
                decky.logger.info(f"System vendor: '{vendor}'")
                
                if "Valve" in vendor:
                    is_steam_deck = True
                    decky.logger.info("Confirmed Steam Deck via vendor")
            except (FileNotFoundError, PermissionError) as e:
                decky.logger.debug(f"Could not read sys_vendor: {e}")
            
            # Final decision logic
            if is_steam_deck:
                # We know it's a Steam Deck but couldn't determine the model
                decky.logger.info("Confirmed Steam Deck, but model detection failed - defaulting to LCD")
                return {
                    "status": "success",
                    "model": "LCD", 
                    "is_oled": False
                }
            else:
                # We couldn't confirm this is a Steam Deck
                decky.logger.info("Could not confirm this is a Steam Deck")
                return {
                    "status": "success",
                    "model": "Not Steam Deck",
                    "is_oled": False
                }
                
        except Exception as e:
            decky.logger.error(f"Error detecting Steam Deck model: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "model": "Unknown",
                "is_oled": False
            }

    async def check_reshade_path(self) -> dict:
        path = Path(os.path.expanduser("~/.local/share/reshade"))
        marker_file = path / ".installed"
        addon_marker = path / ".installed_addon"
        
        # Check version information
        version_info = {"version": "unknown", "addon": False}
        if marker_file.exists() or addon_marker.exists():
            try:
                version_file = path / "reshade" / "LVERS"
                if version_file.exists():
                    with open(version_file, 'r') as f:
                        version_content = f.read().strip()
                        if "last" in version_content.lower():
                            version_info["version"] = "last"
                        else:
                            version_info["version"] = "latest"
                        version_info["addon"] = "addon" in version_content.lower()
            except Exception as e:
                decky.logger.error(f"Error reading version info: {str(e)}")
        
        return {
            "exists": marker_file.exists() or addon_marker.exists(),
            "is_addon": addon_marker.exists(),
            "version_info": version_info
        }

    async def check_vkbasalt_path(self) -> dict:
        marker_file = Path(self.vkbasalt_base_path) / ".installed"
        return {"exists": marker_file.exists()}

    async def run_install_reshade(self, with_addon: bool = False, version: str = "latest", with_autohdr: bool = False, selected_shaders: list = None) -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "reshade-install.sh"

            if not script_path.exists():
                decky.logger.error(f"Install script not found: {script_path}")
                return {"status": "error", "message": "Install script not found"}

            # Create a new environment dictionary for this installation
            install_env = self.environment.copy()
            
            # Explicitly set RESHADE_ADDON_SUPPORT, RESHADE_VERSION, and AUTOHDR_ENABLED based on parameters
            install_env['RESHADE_ADDON_SUPPORT'] = '1' if with_addon else '0'
            install_env['RESHADE_VERSION'] = version
            install_env['AUTOHDR_ENABLED'] = '1' if with_autohdr else '0'
            
            # Set selected shaders (if provided)
            if selected_shaders is not None:
                # Convert selected shaders list to comma-separated string
                selected_shader_ids = ','.join(selected_shaders) if selected_shaders else ''
                install_env['SELECTED_SHADERS'] = selected_shader_ids
                decky.logger.info(f"Selected shader packages: {selected_shader_ids}")
            else:
                # Install all shaders (default behavior)
                install_env['SELECTED_SHADERS'] = 'all'
            
            # Add other necessary environment variables
            install_env.update({
                'LD_LIBRARY_PATH': '/usr/lib',
                'XDG_DATA_HOME': os.path.expandvars('$HOME/.local/share')
            })

            install_description = f"Installing ReShade {version}"
            if with_addon:
                install_description += " with addon support"
            if with_autohdr:
                install_description += " and AutoHDR components"
            if selected_shaders and selected_shaders != ['all']:
                install_description += f" with {len(selected_shaders)} shader packages"
            
            decky.logger.info(install_description)
            decky.logger.info(f"Environment: {install_env}")

            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env={**os.environ, **install_env},
                capture_output=True,
                text=True,
                timeout=300
            )

            decky.logger.info(f"Install output:\n{process.stdout}")
            if process.stderr:
                decky.logger.error(f"Install errors:\n{process.stderr}")

            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}

            # Create appropriate installation marker
            if with_addon:
                marker_file = Path(self.main_path) / ".installed_addon"
                # Remove non-addon marker if it exists
                normal_marker = Path(self.main_path) / ".installed"
                if normal_marker.exists():
                    normal_marker.unlink()
            else:
                marker_file = Path(self.main_path) / ".installed"
                # Remove addon marker if it exists
                addon_marker = Path(self.main_path) / ".installed_addon"
                if addon_marker.exists():
                    addon_marker.unlink()

            marker_file.touch()

            # Save the installed configuration
            await self.save_installed_configuration(with_addon, version, with_autohdr, selected_shaders)

            # Clear executable cache since new installation might affect detection
            self.executable_cache.clear()

            # Create success message
            version_display = f"ReShade {version.title()}"
            if with_addon:
                version_display += ' (with Addon Support)'
            if with_autohdr:
                version_display += ' and AutoHDR components'
            if selected_shaders and selected_shaders != ['all']:
                version_display += f' with {len(selected_shaders)} shader packages'
            
            return {"status": "success", "output": f"{version_display} installed successfully!"}
        except Exception as e:
            decky.logger.error(f"Install error: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def run_install_vkbasalt(self) -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "vkbasalt-install.sh"
            
            if not script_path.exists():
                decky.logger.error(f"VkBasalt install script not found: {script_path}")
                return {"status": "error", "message": "VkBasalt install script not found"}

            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env={**os.environ, **self.environment, 'LD_LIBRARY_PATH': '/usr/lib', 'VKBASALT_PATH': self.vkbasalt_path},
                capture_output=True,
                text=True
            )

            decky.logger.info(f"VkBasalt install output:\n{process.stdout}")
            if process.stderr:
                decky.logger.error(f"VkBasalt install errors:\n{process.stderr}")

            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}

            marker_file = Path(self.vkbasalt_base_path) / ".installed"
            marker_file.touch()
            
            return {"status": "success", "output": "VkBasalt installed successfully!"}
        except Exception as e:
            decky.logger.error(f"VkBasalt install error: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def run_uninstall_reshade(self) -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "reshade-uninstall.sh"
            
            if not script_path.exists():
                return {"status": "error", "message": "Uninstall script not found"}

            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env={**os.environ, **self.environment, 'LD_LIBRARY_PATH': '/usr/lib'},
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}

            # Remove installation markers
            marker_file = Path(self.main_path) / ".installed"
            addon_marker = Path(self.main_path) / ".installed_addon"
            if marker_file.exists():
                marker_file.unlink()
            if addon_marker.exists():
                addon_marker.unlink()

            # Clear installed configuration and cache
            await self.clear_installed_configuration()
            self.executable_cache.clear()
                
            return {"status": "success", "output": "ReShade uninstalled"}
        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def run_uninstall_vkbasalt(self) -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "vkbasalt-uninstall.sh"
            
            if not script_path.exists():
                return {"status": "error", "message": "VkBasalt uninstall script not found"}

            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env={**os.environ, **self.environment, 'LD_LIBRARY_PATH': '/usr/lib', 'VKBASALT_PATH': self.vkbasalt_path},
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}

            marker_file = Path(self.vkbasalt_base_path) / ".installed"
            if marker_file.exists():
                marker_file.unlink()
                    
            return {"status": "success", "output": "VkBasalt uninstalled"}
        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def detect_linux_game(self, appid: str) -> dict:
        """Detect if a Steam game is running the Linux version instead of Windows version"""
        try:
            game_path = self._find_game_path(appid)
            decky.logger.info(f"Checking if game is Linux version: {game_path}")
            
            # Convert to Path object for easier handling
            game_path_obj = Path(game_path)
            
            # Check 1: Look for .exe files (Windows indicator)
            exe_files = list(game_path_obj.rglob("*.exe"))
            has_exe_files = len(exe_files) > 0
            
            # Filter out known utility/redistributable executables
            main_exe_files = []
            for exe in exe_files:
                exe_name = exe.name.lower()
                if not any(skip in exe_name for skip in ["unins", "redist", "vcredist", "directx", "setup", "install"]):
                    main_exe_files.append(exe)
            
            has_main_exe = len(main_exe_files) > 0
            
            # Check 2: Look for Linux-specific file patterns only (no directories)
            linux_file_indicators = [
                "*.x86_64", "*.x86", "*.bin", "*.sh",  # Linux executable patterns
                "*.so", "*.so.*"  # Linux shared libraries
            ]
            
            linux_files_found = []
            for pattern in linux_file_indicators:
                matches = list(game_path_obj.rglob(pattern))
                # Filter to only include files (not directories)
                file_matches = [m for m in matches if m.is_file()]
                if file_matches:
                    linux_files_found.extend([str(m.relative_to(game_path_obj)) for m in file_matches[:5]])  # Limit to 5 examples
            
            # Check 3: Look for Linux executables (files without extension that are ELF binaries)
            linux_executables = []
            for file in game_path_obj.iterdir():
                if file.is_file() and file.suffix == "":  # Files without extension
                    try:
                        # Check if file is executable
                        if file.stat().st_mode & 0o111:  # Has execute permission
                            # Use 'file' command to check if it's an ELF binary
                            process = subprocess.run(
                                ["file", str(file)],
                                capture_output=True,
                                text=True
                            )
                            if "ELF" in process.stdout:
                                linux_executables.append(file.name)
                    except Exception as e:
                        decky.logger.debug(f"Error checking file {file}: {str(e)}")
            
            # Check 4: Look for Unity Linux file indicators (files only)
            unity_linux_file_patterns = [
                "UnityPlayer.so",
                "*_Data/Plugins/x86_64/*.so",
                "*_Data/Mono/etc/mono/config"
            ]
            
            unity_linux_files = []
            for pattern in unity_linux_file_patterns:
                matches = list(game_path_obj.rglob(pattern))
                # Filter to only include files
                file_matches = [m for m in matches if m.is_file()]
                if file_matches:
                    unity_linux_files.extend([str(m.relative_to(game_path_obj)) for m in file_matches[:3]])
            
            # Check 5: Look for other Linux-specific files
            linux_specific_files = []
            for file in game_path_obj.rglob("*"):
                if file.is_file():
                    file_name = file.name.lower()
                    # Check for common Linux game files
                    if any(pattern in file_name for pattern in [
                        "start.sh", "run.sh", "launch.sh",  # Launch scripts
                        ".desktop",  # Desktop files
                        "libc.so", "libstdc++.so", "libgcc_s.so"  # Common Linux libraries
                    ]):
                        linux_specific_files.append(str(file.relative_to(game_path_obj)))
                        if len(linux_specific_files) >= 5:  # Limit examples
                            break
            
            # Decision logic
            is_linux_game = False
            confidence = "low"
            reasons = []
            
            # Strong indicators of Linux version
            if linux_executables:
                is_linux_game = True
                confidence = "high"
                reasons.append(f"Found Linux ELF executables: {', '.join(linux_executables[:3])}")
            
            if unity_linux_files:
                is_linux_game = True
                confidence = "high"
                reasons.append(f"Found Unity Linux files: {', '.join(unity_linux_files)}")
            
            # Medium indicators
            if not has_main_exe and len(linux_files_found) >= 3:
                is_linux_game = True
                confidence = "medium"
                reasons.append(f"No Windows .exe files found, but multiple Linux files present")
            
            if linux_specific_files:
                is_linux_game = True
                confidence = "medium" if confidence == "low" else confidence
                reasons.append(f"Found Linux-specific files: {', '.join(linux_specific_files[:3])}")
            
            # Weak indicators
            if not has_exe_files and len(linux_files_found) >= 1:
                is_linux_game = True
                confidence = "medium" if not reasons else confidence
                reasons.append("Linux files found, no Windows executables")
            
            # Additional context
            total_files = len([f for f in game_path_obj.rglob("*") if f.is_file()]) if game_path_obj.exists() else 0
            
            result = {
                "status": "success",
                "is_linux_game": is_linux_game,
                "confidence": confidence,
                "reasons": reasons,
                "details": {
                    "has_exe_files": has_exe_files,
                    "has_main_exe": has_main_exe,
                    "main_exe_count": len(main_exe_files),
                    "linux_executables": linux_executables,
                    "linux_files_count": len(linux_files_found),
                    "linux_specific_files": linux_specific_files,
                    "unity_linux_files": len(unity_linux_files),
                    "total_files": total_files,
                    "game_path": str(game_path)
                }
            }
            
            decky.logger.info(f"Linux game detection result: {result}")
            return result
            
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            decky.logger.error(f"Error detecting Linux game: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def manage_game_reshade(self, appid: str, action: str, dll_override: str = "dxgi", vulkan_mode: str = "", selected_executable_path: str = "") -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "reshade-game-manager.sh"
            
            # Track if user selected a specific executable path
            using_user_selected_path = bool(selected_executable_path and os.path.exists(selected_executable_path))
            
            try:
                # Use selected executable path if provided, otherwise use detection
                if using_user_selected_path:
                    game_path = os.path.dirname(selected_executable_path)
                    decky.logger.info(f"Using user-selected executable path: {selected_executable_path}")
                    decky.logger.info(f"Installing ReShade to directory: {game_path}")
                elif action == "install":
                    # Get the base game installation path (not executable-specific directory)
                    game_path = self._find_game_path(appid)
                    decky.logger.info(f"Using base game path for Bash detection: {game_path}")
                else:
                    # For uninstall, we still need to find where ReShade was installed
                    # Try to use our detection first, then fall back to base path
                    try:
                        exe_result = await self.find_game_executable_path(appid)
                        if (exe_result["status"] == "success" and 
                            exe_result.get("steam_logs_result", {}).get("status") == "success"):
                            game_path = os.path.dirname(exe_result["steam_logs_result"]["executable_path"])
                            decky.logger.info(f"Using detected executable directory for uninstall: {game_path}")
                        elif (exe_result["status"] == "success" and 
                              exe_result.get("enhanced_detection_result", {}).get("status") == "success"):
                            game_path = os.path.dirname(exe_result["enhanced_detection_result"]["executable_path"])
                            decky.logger.info(f"Using enhanced detection directory for uninstall: {game_path}")
                        else:
                            game_path = self._find_game_path(appid)
                            decky.logger.info(f"Using base game path for uninstall: {game_path}")
                    except:
                        game_path = self._find_game_path(appid)
                        decky.logger.info(f"Using base game path for uninstall (fallback): {game_path}")
                
                decky.logger.info(f"Final game path: {game_path}")
            except ValueError as e:
                return {"status": "error", "message": str(e)}

            # Build command - if user selected a specific path, don't pass appid to prevent bash script from overriding
            cmd = ["/bin/bash", str(script_path), action, game_path, dll_override]
            if vulkan_mode:
                cmd.extend([vulkan_mode, os.path.expanduser(f"~/.local/share/Steam/steamapps/compatdata/{appid}"), appid])
            else:
                # For non-Vulkan mode, add empty placeholders for vulkan_mode and wineprefix
                if using_user_selected_path:
                    # Don't pass appid when using user-selected path to prevent bash script from overriding
                    cmd.extend(["", "", ""])
                    decky.logger.info("Not passing App ID to bash script to prevent path override")
                else:
                    # Pass appid for automatic detection
                    cmd.extend(["", "", appid])
            
            decky.logger.info(f"Executing command: {' '.join(cmd)}")
            
            process = subprocess.run(
                cmd,
                cwd=str(assets_dir),
                env={**os.environ, **self.environment, 'LD_LIBRARY_PATH': '/usr/lib'},
                capture_output=True,
                text=True
            )
            
            decky.logger.info(f"Script output: {process.stdout}")
            if process.stderr:
                decky.logger.error(f"Script errors: {process.stderr}")
            
            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}
                
            return {"status": "success", "output": process.stdout}
        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def list_installed_games(self) -> dict:
        try:
            steam_root = Path(decky.HOME) / ".steam" / "steam"
            library_file = steam_root / "steamapps" / "libraryfolders.vdf"

            if not library_file.exists():
                return {"status": "error", "message": "libraryfolders.vdf not found"}

            library_paths = []
            with open(library_file, "r", encoding="utf-8") as file:
                for line in file:
                    if '"path"' in line:
                        path = line.split('"path"')[1].strip().strip('"').replace("\\\\", "/")
                        library_paths.append(path)

            games = []
            for library_path in library_paths:
                steamapps_path = Path(library_path) / "steamapps"
                if not steamapps_path.exists():
                    continue

                for appmanifest in steamapps_path.glob("appmanifest_*.acf"):
                    with open(appmanifest, "r", encoding="utf-8") as file:
                        game_info = {"appid": None, "name": None}
                        for line in file:
                            if '"appid"' in line:
                                game_info["appid"] = line.split('"appid"')[1].strip().strip('"')
                            if '"name"' in line:
                                game_info["name"] = line.split('"name"')[1].strip().strip('"')

                        if game_info["appid"] and game_info["name"]:
                            games.append(game_info)

            # Filter out system components and redistributables that shouldn't be modded with ReShade
            filtered_games = [g for g in games if not any(exclude in g["name"] for exclude in [
                "Proton", 
                "Steam Linux Runtime", 
                "Steamworks Common Redistributables",
                "DirectX",
                "Visual C++",
                "Microsoft Visual C++",
                ".NET Framework",
                "OpenXR"
            ])]
            
            return {"status": "success", "games": filtered_games}

        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def find_heroic_games(self) -> dict:
        """Find games installed through Heroic Launcher using the config file"""
        try:
            # Read the Heroic config file to get the default install path
            heroic_config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/store/config.json")
            
            if not os.path.exists(heroic_config_path):
                return {"status": "error", "message": "Heroic config file not found"}
                
            with open(heroic_config_path, 'r', encoding='utf-8') as f:
                heroic_config = json.load(f)
            
            # Get the install path from config
            default_install_path = heroic_config.get("settings", {}).get("defaultInstallPath")
            if not default_install_path:
                default_install_path = os.path.expanduser("~/Games/Heroic")  # Fallback
            
            decky.logger.info(f"Heroic games install path: {default_install_path}")
            
            # Get the list of recent games for quick reference
            recent_games = heroic_config.get("games", {}).get("recent", [])
            recent_games_map = {game.get("title"): game.get("appName") for game in recent_games if game.get("title") and game.get("appName")}
            
            # Find all game directories in the install path
            games = []
            if os.path.exists(default_install_path):
                for game_dir in os.listdir(default_install_path):
                    game_path = os.path.join(default_install_path, game_dir)
                    if os.path.isdir(game_path) and game_dir.lower() not in ["prefixes", "temp", "legendary", "gog", "state", "logs"]:
                        # This is likely a game directory
                        game_info = {
                            "name": game_dir,
                            "path": game_path
                        }
                        
                        # Check if this game is in the recent games list
                        if game_dir in recent_games_map:
                            game_info["app_id"] = recent_games_map[game_dir]
                        
                        # Try to find a better name from appinfo.json if it exists
                        appinfo_paths = [
                            os.path.join(game_path, "appinfo.json"),
                            os.path.join(game_path, ".egstore", "appinfo.json")
                        ]
                        
                        for appinfo_path in appinfo_paths:
                            if os.path.exists(appinfo_path):
                                try:
                                    with open(appinfo_path, 'r', encoding='utf-8') as f:
                                        appinfo = json.load(f)
                                        if "DisplayName" in appinfo:
                                            game_info["name"] = appinfo["DisplayName"]
                                        elif "AppName" in appinfo:
                                            game_info["name"] = appinfo["AppName"]
                                        if "AppId" in appinfo:
                                            game_info["app_id"] = str(appinfo["AppId"])
                                        break
                                except Exception as e:
                                    decky.logger.error(f"Error reading appinfo.json for {game_dir}: {str(e)}")
                        
                        # Find and cache the config file information if available
                        if "app_id" in game_info:
                            # Check if there's a direct config file match
                            games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
                            for config_file in os.listdir(games_config_dir):
                                if config_file.endswith(".json"):
                                    config_file_path = os.path.join(games_config_dir, config_file)
                                    try:
                                        with open(config_file_path, 'r', encoding='utf-8') as f:
                                            config_data = json.load(f)
                                            # Check if app_id is a key in this config file
                                            if game_info["app_id"] in config_data:
                                                game_info["config_file"] = config_file
                                                game_info["config_key"] = game_info["app_id"]
                                                break
                                    except Exception as e:
                                        decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
                        
                        games.append(game_info)
            
            # Sort games alphabetically by name
            games.sort(key=lambda g: g["name"].lower())
            
            return {"status": "success", "games": games}
        except Exception as e:
            decky.logger.error(f"Error finding Heroic games: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def find_heroic_game_config(self, game_path: str, game_name: str) -> dict:
        """
        Find the config file and key for a Heroic game using the config.json file
        """
        try:
            decky.logger.info(f"Finding config for Heroic game: {game_name} at {game_path}")
            
            # Normalize game name for more flexible matching
            normalized_game_name = game_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            normalized_game_path = os.path.normpath(game_path)
            base_folder_name = os.path.basename(normalized_game_path).lower()
            
            decky.logger.info(f"Normalized game name: {normalized_game_name}")
            decky.logger.info(f"Base folder name: {base_folder_name}")
            
            # First, try to read the Heroic config file
            heroic_config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/store/config.json")
            if os.path.exists(heroic_config_path):
                with open(heroic_config_path, 'r', encoding='utf-8') as f:
                    heroic_config = json.load(f)
                
                # Get the list of recent games
                recent_games = heroic_config.get("games", {}).get("recent", [])
                
                # Look for a match by title with flexible matching
                for game in recent_games:
                    game_title = game.get("title", "")
                    normalized_title = game_title.lower().replace(" ", "").replace("-", "").replace("_", "")
                    
                    # Try multiple matching approaches
                    if (game.get("title") == game_name or  # Exact match
                        normalized_title == normalized_game_name or  # Normalized match
                        normalized_game_name in normalized_title or  # Normalized game name is in title
                        normalized_title in normalized_game_name or  # Normalized title is in game name
                        base_folder_name.startswith(normalized_title) or  # Folder starts with title
                        normalized_title.startswith(base_folder_name)):  # Title starts with folder
                        
                        app_name = game.get("appName")
                        if app_name:
                            decky.logger.info(f"Found appName in config.json for '{game_title}': {app_name}")
                            
                            # Now look for this appName in the GamesConfig directory
                            games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
                            for config_file in os.listdir(games_config_dir):
                                if not config_file.endswith(".json"):
                                    continue
                                    
                                config_file_path = os.path.join(games_config_dir, config_file)
                                try:
                                    with open(config_file_path, 'r', encoding='utf-8') as f:
                                        config_data = json.load(f)
                                        
                                        if app_name in config_data:
                                            decky.logger.info(f"Found config file: {config_file}, key: {app_name}")
                                            return {
                                                "status": "success",
                                                "config_file": config_file,
                                                "config_key": app_name
                                            }
                                except Exception as e:
                                    decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
                
                # If direct matching failed, try checking winePrefix paths in all config files
                decky.logger.info("Trying to match using winePrefix paths...")
                games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
                
                for config_file in os.listdir(games_config_dir):
                    if not config_file.endswith(".json"):
                        continue
                        
                    config_file_path = os.path.join(games_config_dir, config_file)
                    try:
                        with open(config_file_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                            
                            # Check each game config
                            for app_key, app_config in config_data.items():
                                # Check winePrefix path
                                wine_prefix = app_config.get("winePrefix", "")
                                if wine_prefix:
                                    # Get both last part and parent part of path for more chances to match
                                    prefix_parts = wine_prefix.rstrip('/').split('/')
                                    last_part = prefix_parts[-1].lower()
                                    parent_part = prefix_parts[-2].lower() if len(prefix_parts) > 1 else ""
                                    
                                    # Normalize for matching
                                    last_part_norm = last_part.replace(" ", "").replace("-", "").replace("_", "")
                                    parent_part_norm = parent_part.replace(" ", "").replace("-", "").replace("_", "")
                                    
                                    # Enhanced matching for Wine prefix components
                                    if (last_part.lower() == game_name.lower() or
                                        last_part_norm == normalized_game_name or
                                        normalized_game_name in last_part_norm or
                                        last_part_norm in normalized_game_name or
                                        base_folder_name.startswith(last_part_norm) or
                                        last_part_norm.startswith(base_folder_name) or
                                        # Also check parent directory if it's not a common prefix folder
                                        (parent_part and parent_part not in ["prefixes", "wine", "pfx"] and (
                                            parent_part.lower() == game_name.lower() or
                                            parent_part_norm == normalized_game_name or
                                            normalized_game_name in parent_part_norm or
                                            parent_part_norm in normalized_game_name or
                                            base_folder_name.startswith(parent_part_norm) or
                                            parent_part_norm.startswith(base_folder_name)))):
                                        
                                        match_type = "last_part" if (last_part.lower() == game_name.lower() or 
                                                                    last_part_norm == normalized_game_name or
                                                                    normalized_game_name in last_part_norm or
                                                                    last_part_norm in normalized_game_name) else "parent_part"
                                        
                                        decky.logger.info(f"Found match via winePrefix {match_type}: {wine_prefix}")
                                        decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                        return {
                                            "status": "success",
                                            "config_file": config_file,
                                            "config_key": app_key
                                        }
                    except Exception as e:
                        decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
            
            # Improved executable name matching
            decky.logger.info("Trying enhanced matching using executable names...")
            
            # Find the executable directory
            exe_dir = self._find_heroic_game_executable_directory(game_path)
            if not exe_dir:
                exe_dir = game_path
                
            # Find executable files - get all to increase chances of a match
            exe_files = []
            try:
                for file in os.listdir(exe_dir):
                    if file.lower().endswith(".exe") and not any(skip in file.lower() for skip in 
                                                            ["unins", "launcher", "crash", "setup", "config", "redist"]):
                        exe_files.append(file)
                        
                # Try additional subdirectories if no EXEs found in main directory
                if not exe_files:
                    for subdir in ["bin", "binaries", "game", "win64", "x64"]:
                        subdir_path = os.path.join(exe_dir, subdir)
                        if os.path.exists(subdir_path) and os.path.isdir(subdir_path):
                            for file in os.listdir(subdir_path):
                                if file.lower().endswith(".exe") and not any(skip in file.lower() for skip in 
                                                                        ["unins", "launcher", "crash", "setup", "config", "redist"]):
                                    exe_files.append(file)
                                    decky.logger.info(f"Found exe in subdirectory {subdir}: {file}")
            except Exception as e:
                decky.logger.error(f"Error listing executable directory: {str(e)}")
                
            if exe_files:
                # Use all executable names for matching, not just the first one
                games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
                
                for exe_file in exe_files:
                    # Get name without .exe extension
                    exe_name = os.path.splitext(exe_file)[0].lower()
                    exe_name_norm = exe_name.replace(" ", "").replace("-", "").replace("_", "")
                    
                    decky.logger.info(f"Trying to match using executable: {exe_name}")
                    
                    # Check all config files for matches
                    for config_file in os.listdir(games_config_dir):
                        if not config_file.endswith(".json"):
                            continue
                            
                        config_file_path = os.path.join(games_config_dir, config_file)
                        try:
                            with open(config_file_path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                                
                                # Check all games in this config
                                for app_key, app_config in config_data.items():
                                    # Get game info and any other relevant fields that might contain the game name
                                    game_info = app_config.get("game", {})
                                    config_title = game_info.get("title", "").lower()
                                    config_title_norm = config_title.replace(" ", "").replace("-", "").replace("_", "")
                                    
                                    # Also check the app config directly for game name
                                    app_title = app_config.get("title", "").lower()
                                    app_title_norm = app_title.replace(" ", "").replace("-", "").replace("_", "")
                                    
                                    # Enhanced matching for executable names
                                    if (exe_name == config_title.lower() or
                                        exe_name_norm == config_title_norm or
                                        exe_name == app_title.lower() or
                                        exe_name_norm == app_title_norm or
                                        exe_name_norm in config_title_norm or
                                        exe_name_norm in app_title_norm or
                                        config_title_norm in exe_name_norm or
                                        app_title_norm in exe_name_norm):
                                        
                                        match_source = "game_info" if exe_name_norm in config_title_norm else "app_config"
                                        match_type = "exact" if (exe_name == config_title.lower() or exe_name == app_title.lower()) else "partial"
                                        
                                        decky.logger.info(f"Found match via executable name: {exe_name} matches '{config_title or app_title}' ({match_type} match from {match_source})")
                                        decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                        return {
                                            "status": "success",
                                            "config_file": config_file,
                                            "config_key": app_key
                                        }
                        except Exception as e:
                            decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
                        
            # Check install path as before
            decky.logger.info("Trying to match using install path...")
            games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
            for config_file in os.listdir(games_config_dir):
                if not config_file.endswith(".json"):
                    continue
                    
                config_file_path = os.path.join(games_config_dir, config_file)
                try:
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        
                        # Check all games in this config
                        for app_key, app_config in config_data.items():
                            install_path = app_config.get("installPath", "")
                            if install_path:
                                normalized_install_path = os.path.normpath(install_path)
                                install_folder = os.path.basename(normalized_install_path).lower()
                                install_folder_norm = install_folder.replace(" ", "").replace("-", "").replace("_", "")
                                
                                # Enhanced matching for install paths
                                if (normalized_install_path == normalized_game_path or
                                    install_folder == base_folder_name or
                                    (normalized_game_name in install_folder_norm) or
                                    (install_folder_norm in normalized_game_name) or
                                    base_folder_name.startswith(install_folder_norm) or
                                    install_folder_norm.startswith(base_folder_name)):
                                    
                                    decky.logger.info(f"Found match via install path: {install_path}")
                                    decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                    return {
                                        "status": "success",
                                        "config_file": config_file,
                                        "config_key": app_key
                                    }
                except Exception as e:
                    decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
            
            # NEW FALLBACK: Check store-specific installed.json files if all other methods fail
            decky.logger.info("Trying to find game in store-specific installed.json files...")
            
            # Define paths to different store installed.json files
            installed_json_paths = {
                "epic": os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/legendaryConfig/legendary/installed.json"),
                "gog": os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/gog_store/installed.json"),
                "amazon": os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/nile_config/nile/installed.json")
            }
            
            # Check each store's installed.json file
            for store, json_path in installed_json_paths.items():
                if not os.path.exists(json_path):
                    decky.logger.debug(f"{store.upper()} installed.json not found: {json_path}")
                    continue
                    
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        installed_data = json.load(f)
                    
                    decky.logger.info(f"Checking {store.upper()} installed.json file")
                    
                    # Handle Epic Games format (object with app IDs as keys)
                    if store == "epic":
                        for app_id, game_info in installed_data.items():
                            title = game_info.get("title", "").lower()
                            title_norm = title.replace(" ", "").replace("-", "").replace("_", "")
                            install_path = os.path.normpath(game_info.get("install_path", ""))
                            executable = game_info.get("executable", "").lower()
                            executable_name = os.path.splitext(executable)[0].lower() if executable else ""
                            
                            # Comprehensive matching
                            if (title.lower() == game_name.lower() or
                                title_norm == normalized_game_name or
                                normalized_game_name in title_norm or
                                title_norm in normalized_game_name or
                                install_path == normalized_game_path or
                                os.path.basename(install_path).lower() == base_folder_name or
                                (executable_name and (
                                    executable_name == normalized_game_name or
                                    normalized_game_name in executable_name or
                                    executable_name in normalized_game_name
                                ))):
                                
                                app_name = game_info.get("app_name", app_id)
                                if app_name:
                                    decky.logger.info(f"Found match in Epic installed.json: {app_name} for {title}")
                                    
                                    # Now search for this app_name in GamesConfig directory
                                    config_result = self._find_config_for_app_name(app_name)
                                    if config_result["status"] == "success":
                                        return config_result
                    
                    # Handle GOG format (installed array)
                    elif store == "gog":
                        installed_array = installed_data.get("installed", [])
                        for game_info in installed_array:
                            install_path = os.path.normpath(game_info.get("install_path", ""))
                            app_name = game_info.get("appName")
                            
                            # Match based on install path
                            if (install_path == normalized_game_path or
                                os.path.basename(install_path).lower() == base_folder_name):
                                
                                if app_name:
                                    decky.logger.info(f"Found match in GOG installed.json: {app_name}")
                                    
                                    # Search for this app_name in config files
                                    config_result = self._find_config_for_app_name(app_name)
                                    if config_result["status"] == "success":
                                        return config_result
                    
                    # Handle Amazon format (likely similar to others)
                    elif store == "amazon":
                        # Implementation would depend on exact structure
                        # This is a placeholder assuming similar structure to other stores
                        if isinstance(installed_data, dict) and "installed" in installed_data:
                            # Array format like GOG
                            for game_info in installed_data.get("installed", []):
                                app_name = game_info.get("appName") or game_info.get("app_name")
                                install_path = os.path.normpath(game_info.get("install_path", ""))
                                
                                if (install_path == normalized_game_path or
                                    os.path.basename(install_path).lower() == base_folder_name):
                                    
                                    if app_name:
                                        decky.logger.info(f"Found match in Amazon installed.json: {app_name}")
                                        
                                        # Search for this app_name in config files
                                        config_result = self._find_config_for_app_name(app_name)
                                        if config_result["status"] == "success":
                                            return config_result
                        else:
                            # Object format like Epic
                            for app_id, game_info in installed_data.items():
                                app_name = game_info.get("appName") or game_info.get("app_name")
                                install_path = os.path.normpath(game_info.get("install_path", ""))
                                
                                if (install_path == normalized_game_path or
                                    os.path.basename(install_path).lower() == base_folder_name):
                                    
                                    if app_name:
                                        decky.logger.info(f"Found match in Amazon installed.json: {app_name}")
                                        
                                        # Search for this app_name in config files
                                        config_result = self._find_config_for_app_name(app_name)
                                        if config_result["status"] == "success":
                                            return config_result
                        
                except Exception as e:
                    decky.logger.error(f"Error reading {store} installed.json: {str(e)}")
            
            # If we still couldn't find a match, look for appinfo.json
            return {"status": "error", "message": f"Could not find config for game: {game_name}"}
        except Exception as e:
            decky.logger.error(f"Error finding Heroic game config: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _find_config_for_app_name(self, app_name: str) -> dict:
        """Find config file containing the specified app_name as a key"""
        games_config_dir = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig")
        
        for config_file in os.listdir(games_config_dir):
            if not config_file.endswith(".json"):
                continue
                
            config_file_path = os.path.join(games_config_dir, config_file)
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                    if app_name in config_data:
                        decky.logger.info(f"Found config file for {app_name}: {config_file}")
                        return {
                            "status": "success",
                            "config_file": config_file,
                            "config_key": app_name
                        }
            except Exception as e:
                decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
        
        return {"status": "error", "message": f"No config file found for app name: {app_name}"}

    async def update_heroic_config(self, config_file: str, config_key: str, dll_override: str) -> dict:
        """Update Heroic game configuration with WINEDLLOVERRIDES for ReShade or ENABLE_VKBASALT for VkBasalt"""
        try:
            config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig/")
            config_file_path = os.path.join(config_path, config_file)
            
            if not os.path.exists(config_file_path):
                return {"status": "error", "message": f"Config file not found: {config_file}"}
                
            # Read the config file
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            if config_key not in config_data:
                return {"status": "error", "message": f"Game config key '{config_key}' not found in config file"}
                
            # Check if environmentOptions exists (note: it's "environmentOptions" in newer versions, not "enviromentOptions")
            env_key = "environmentOptions" if "environmentOptions" in config_data[config_key] else "enviromentOptions"
            
            if env_key not in config_data[config_key]:
                config_data[config_key][env_key] = []
            
            # Special case for VkBasalt
            if dll_override == "vkbasalt":
                # Remove any existing ENABLE_VKBASALT
                config_data[config_key][env_key] = [
                    env for env in config_data[config_key][env_key] 
                    if env.get("key") != "ENABLE_VKBASALT"
                ]
                
                # Add ENABLE_VKBASALT=1
                config_data[config_key][env_key].append({
                    "key": "ENABLE_VKBASALT",
                    "value": "1"
                })
            else:
                # Normal ReShade case - handle WINEDLLOVERRIDES
                # Remove any existing WINEDLLOVERRIDES
                config_data[config_key][env_key] = [
                    env for env in config_data[config_key][env_key] 
                    if env.get("key") != "WINEDLLOVERRIDES"
                ]
                
                # Add new WINEDLLOVERRIDES if not removing
                if dll_override != "remove":
                    config_data[config_key][env_key].append({
                        "key": "WINEDLLOVERRIDES",
                        "value": f"d3dcompiler_47=n;{dll_override}=n,b"
                    })
            
            # Write back the updated config
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
                
            return {"status": "success", "output": f"Updated Heroic config with {dll_override} override."}
        except Exception as e:
            decky.logger.error(f"Error updating Heroic config: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def install_reshade_for_heroic_game(self, game_path: str, dll_override: str = "d3d9", selected_executable_path: str = "") -> dict:
        """Install ReShade for a Heroic game by copying files instead of symlinks and properly configuring ReShade.ini"""
        try:
            decky.logger.info(f"Installing ReShade for Heroic game at: {game_path}")
            
            # Verify ReShade is installed
            marker_file = Path(self.main_path) / ".installed"
            addon_marker = Path(self.main_path) / ".installed_addon"
            if not marker_file.exists() and not addon_marker.exists():
                return {"status": "error", "message": "ReShade is not installed. Please install ReShade first."}
            
            # Verify game path exists
            if not os.path.exists(game_path):
                return {"status": "error", "message": f"Game path not found: {game_path}"}
            
            # Determine the target directory for ReShade installation
            if selected_executable_path and os.path.exists(selected_executable_path):
                # Use the directory of the selected executable
                exe_dir = os.path.dirname(selected_executable_path)
                decky.logger.info(f"Using user-selected executable directory: {exe_dir}")
            else:
                # Find the actual executable directory using smart detection
                exe_dir = self._find_heroic_game_executable_directory(game_path)
                if not exe_dir:
                    decky.logger.warning(f"Could not find executable directory, using provided path: {game_path}")
                    exe_dir = game_path
                else:
                    decky.logger.info(f"Found executable directory: {exe_dir}")
            
            # Find architecture by checking for .exe files
            arch = "64"  # Default to 64-bit
            exe_found = False
            
            for file in os.listdir(exe_dir):
                if file.lower().endswith(".exe"):
                    # Skip known utility executables
                    if any(skip in file.lower() for skip in ["unins", "launcher", "crash", "setup", "config", "redist"]):
                        continue
                        
                    exe_found = True
                    exe_path = os.path.join(exe_dir, file)
                    try:
                        # Check if 32-bit or 64-bit using the 'file' command
                        process = subprocess.run(
                            ["file", exe_path],
                            capture_output=True,
                            text=True
                        )
                        
                        if "PE32 executable" in process.stdout and "PE32+" not in process.stdout:
                            arch = "32"
                            decky.logger.info(f"Found 32-bit executable: {exe_path}")
                            break
                        elif "PE32+ executable" in process.stdout or "x86-64" in process.stdout:
                            decky.logger.info(f"Found 64-bit executable: {exe_path}")
                    except Exception as e:
                        decky.logger.error(f"Error checking EXE architecture: {str(e)}")
            
            decky.logger.info(f"Using architecture: {arch}-bit")
            
            # Source paths for DLLs
            reshade_dll_src = os.path.join(self.main_path, "reshade/latest", f"ReShade{arch}.dll")
            d3dcompiler_src = os.path.join(self.main_path, "reshade", f"d3dcompiler_47.dll.{arch}")
            
            if not os.path.exists(reshade_dll_src) or not os.path.exists(d3dcompiler_src):
                return {"status": "error", "message": "ReShade DLL files not found. Please reinstall ReShade."}
                
            # Destination paths
            reshade_dll_dst = os.path.join(exe_dir, f"{dll_override}.dll")
            d3dcompiler_dst = os.path.join(exe_dir, "d3dcompiler_47.dll")
            
            # Copy files instead of creating symlinks
            shutil.copy2(reshade_dll_src, reshade_dll_dst)
            shutil.copy2(d3dcompiler_src, d3dcompiler_dst)
            
            # Set proper permissions for DLL files (read/write for all)
            os.chmod(reshade_dll_dst, 0o666)
            os.chmod(d3dcompiler_dst, 0o666)
            
            # Copy shader directory if exists
            if os.path.exists(os.path.join(self.main_path, "ReShade_shaders")):
                shaders_dst = os.path.join(exe_dir, "ReShade_shaders")
                # Check if it already exists
                if os.path.exists(shaders_dst):
                    # Remove old link/directory
                    if os.path.islink(shaders_dst):
                        os.unlink(shaders_dst)
                    else:
                        shutil.rmtree(shaders_dst)
                # Create the directory and copy files
                shutil.copytree(os.path.join(self.main_path, "ReShade_shaders"), shaders_dst)
            
            # Fix ReShade.ini to use local paths instead of system paths
            reshade_ini_src = os.path.join(self.main_path, "ReShade.ini")
            reshade_ini_dst = os.path.join(exe_dir, "ReShade.ini")
            
            if os.path.exists(reshade_ini_src):
                # Read the original file
                with open(reshade_ini_src, 'r', encoding='utf-8') as f:
                    ini_content = f.read()
                    
                # Update paths to use local directories instead of system paths
                # This is critical for Wine/Proton compatibility
                
                # First, detect if we're using merged shaders
                merged_path = False
                if "ReShade_shaders\\Merged\\Shaders" in ini_content or "ReShade_shaders/Merged/Shaders" in ini_content:
                    merged_path = True
                    
                # Replace system paths with relative game paths (convert to Windows format for Wine)
                if merged_path:
                    # For merged shader setup
                    ini_content = re.sub(r'EffectSearchPaths=.*', r'EffectSearchPaths=.\\ReShade_shaders\\Merged\\Shaders', ini_content)
                    ini_content = re.sub(r'TextureSearchPaths=.*', r'TextureSearchPaths=.\\ReShade_shaders\\Merged\\Textures', ini_content)
                else:
                    # For individual shader repositories
                    ini_content = re.sub(r'EffectSearchPaths=.*', r'EffectSearchPaths=.\\ReShade_shaders', ini_content)
                    ini_content = re.sub(r'TextureSearchPaths=.*', r'TextureSearchPaths=.\\ReShade_shaders', ini_content)
                    
                # Update the PresetPath to use the local directory
                ini_content = re.sub(r'PresetPath=.*', r'PresetPath=.', ini_content)
                
                # Write the modified ini file with proper permissions
                with open(reshade_ini_dst, 'w', encoding='utf-8') as f:
                    f.write(ini_content)
                
                # Set proper permissions for ReShade.ini (read/write for all)
                os.chmod(reshade_ini_dst, 0o666)
                
            else:
                # If no ReShade.ini exists, create a basic one
                with open(reshade_ini_dst, 'w', encoding='utf-8') as f:
                    f.write("""[GENERAL]
    EffectSearchPaths=.\\ReShade_shaders
    TextureSearchPaths=.\\ReShade_shaders
    PresetPath=.
    PerformanceMode=0
    PreprocessorDefinitions=
    Effects=
    Techniques=

    [INPUT]
    KeyOverlay=36
    KeyNextPreset=0
    KeyPreviousPreset=0
    """)
                # Set proper permissions (read/write for all)
                os.chmod(reshade_ini_dst, 0o666)
            
            # Handle ReShadePreset.ini - preserve existing user settings
            reshade_preset_dst = os.path.join(exe_dir, "ReShadePreset.ini")
            
            # Only create the file if it doesn't already exist (preserve existing user settings)
            if not os.path.exists(reshade_preset_dst):
                game_name = os.path.basename(game_path)
                with open(reshade_preset_dst, 'w', encoding='utf-8') as f:
                    f.write(f"""# ReShade Preset Configuration for {game_name}
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
    """)
                
                # Set proper permissions for ReShadePreset.ini (read/write for all)
                os.chmod(reshade_preset_dst, 0o666)
                decky.logger.info("Created new ReShadePreset.ini with proper permissions")
            else:
                # File exists, just ensure it has proper permissions
                os.chmod(reshade_preset_dst, 0o666)
                decky.logger.info("ReShadePreset.ini already exists, updated permissions only")
            
            # Create a README file to help users with the configuration
            readme_path = os.path.join(exe_dir, "ReShade_README.txt")
            
            # Check if AutoHDR was actually installed
            autohdr_installed = os.path.exists(os.path.join(exe_dir, f"AutoHDR.addon{arch}"))
            autohdr_compatible = dll_override.lower() in ['dxgi', 'd3d11', 'd3d12']
            
            if autohdr_installed:
                autohdr_status = f"- AutoHDR.addon{arch}: AutoHDR addon (DirectX 10/11/12 compatible)"
            elif autohdr_compatible:
                autohdr_status = f"- AutoHDR.addon{arch}: Not installed (AutoHDR addon file missing)"
            else:
                autohdr_status = f"- AutoHDR.addon{arch}: Not compatible with {dll_override} (requires DirectX 10/11/12)"
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"""ReShade for {os.path.basename(game_path)}
    ------------------------------------
    Installed with LetMeReShade plugin for Heroic Games Launcher

    DLL Override: {dll_override}
    Architecture: {arch}-bit
    Executable Directory: {exe_dir}
    {f'Selected Executable: {os.path.basename(selected_executable_path)}' if selected_executable_path else 'Auto-detected executable location'}

    Press HOME key in-game to open the ReShade overlay.

    If shaders are not visible:
    1. Open the ReShade overlay with HOME key
    2. Go to Settings tab
    3. Check paths for "Effect Search Paths" and "Texture Search Paths"
    4. They should point to the ReShade_shaders folder in this game directory
    5. If not, update them to: ".\\ReShade_shaders"

    Shader preset files (.ini) will be saved in this game directory.

    Files created:
    - ReShade.ini: Main ReShade configuration
    - ReShadePreset.ini: Preset configurations (auto-populated when you save presets)
    - {dll_override}.dll: ReShade DLL
    - d3dcompiler_47.dll: DirectX shader compiler
    - ReShade_shaders/: Shader files directory
    {autohdr_status}

    AutoHDR Compatibility:
    - Compatible APIs: DXGI, D3D11, D3D12 (DirectX 10/11/12)
    - Incompatible APIs: D3D9, D3D8, OpenGL32, DDraw, DInput8
    - Current API: {dll_override} {'(✅ AutoHDR Compatible)' if autohdr_compatible else '(❌ AutoHDR Incompatible)'}

    Note: If ReShadePreset.ini already existed, your previous settings were preserved.
    """)
            
            # Set proper permissions for README (read/write for all)
            os.chmod(readme_path, 0o666)
            
            # Copy AutoHDR addon files if available AND compatible with the selected API
            autohdr_compatible = dll_override.lower() in ['dxgi', 'd3d11', 'd3d12']
            
            if autohdr_compatible:
                autohdr_addon_path = os.path.join(self.main_path, "AutoHDR_addons", f"AutoHDR.addon{arch}")
                if os.path.exists(autohdr_addon_path):
                    autohdr_dst = os.path.join(exe_dir, f"AutoHDR.addon{arch}")
                    try:
                        shutil.copy2(autohdr_addon_path, autohdr_dst)
                        os.chmod(autohdr_dst, 0o666)
                        decky.logger.info(f"AutoHDR addon copied successfully for {arch}-bit architecture (API: {dll_override})")
                    except Exception as e:
                        decky.logger.warning(f"Failed to copy AutoHDR addon: {str(e)}")
                else:
                    decky.logger.info(f"AutoHDR addon file not found: {autohdr_addon_path}")
            else:
                decky.logger.info(f"Skipping AutoHDR addon installation for API: {dll_override} (requires DirectX 10/11/12)")
                # Remove any existing AutoHDR addon files if they exist from previous installations
                for addon_arch in ['32', '64']:
                    existing_addon = os.path.join(exe_dir, f"AutoHDR.addon{addon_arch}")
                    if os.path.exists(existing_addon):
                        decky.logger.info(f"Removing existing AutoHDR addon (incompatible with {dll_override})")
                        os.remove(existing_addon)
                
            return {"status": "success", "output": f"ReShade installed successfully for Heroic game using {dll_override} override."}
        except Exception as e:
            decky.logger.error(f"Error installing ReShade for Heroic game: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _find_game_executable_directory(self, path: Path, game_name: str) -> tuple[Path, float]:
        """
        Unified function to find the game executable directory with smart detection
        
        Args:
            path: Base path to search for game executables
            game_name: Name of the game for matching
            
        Returns:
            tuple[Path, float]: The best executable directory and its score
        """
        try:
            if not path.exists() or not path.is_dir():
                return path, 0
                
            # Extract words from game name for better matching
            game_words = set(re.findall(r'\w+', game_name.lower()))
            
            decky.logger.info(f"Looking for executables for game: {game_name}")
            decky.logger.info(f"Game words for matching: {game_words}")
            
            def analyze_directory_content(dir_path: Path) -> float:
                """Score a directory based on its content"""
                if not dir_path.exists() or not dir_path.is_dir():
                    return 0
                    
                score = 0
                file_types = {'exe': 0, 'dll': 0, 'config': 0, 'asset': 0, 'setup': 0, 'redist': 0}
                
                try:
                    # Count file types
                    for file in dir_path.iterdir():
                        if file.is_file():
                            ext = file.suffix.lower()
                            
                            # Game binary files
                            if ext == '.exe':
                                file_types['exe'] += 1
                            elif ext == '.dll':
                                file_types['dll'] += 1
                                
                            # Game config and data files
                            elif ext in ['.ini', '.cfg', '.xml', '.json', '.txt']:
                                file_types['config'] += 1
                                
                            # Game asset files
                            elif ext in ['.pak', '.dat', '.bsa', '.ba2', '.dds', '.tga', '.png', '.jpg']:
                                file_types['asset'] += 1
                                
                            # Setup and redistributable files (negative indicators)
                            elif ext in ['.msi', '.cab', '.msm']:
                                file_types['setup'] += 1
                            
                            # Check file names for redistributable indicators
                            file_name = file.name.lower()
                            if any(term in file_name for term in ['redist', 'vcredist', 'directx', 'setup', 'install']):
                                file_types['redist'] += 1
                    
                    # Score based on file types
                    # Game directories usually have more DLLs and game-related files
                    score += file_types['dll'] * 0.5  # DLLs are good indicators
                    score += file_types['config'] * 0.3  # Config files are somewhat good indicators
                    score += file_types['asset'] * 0.4  # Asset files are good indicators
                    
                    # Too many EXEs might indicate a utility directory
                    if file_types['exe'] > 5:
                        score -= (file_types['exe'] - 5) * 0.2
                    
                    # Setup files are negative indicators
                    score -= file_types['setup'] * 1.0
                    score -= file_types['redist'] * 1.0
                    
                    # Check directory name
                    dir_name = dir_path.name.lower()
                    if dir_name in ['bin', 'bin64', 'bin32', 'binaries', 'game', 'main']:
                        score += 2
                    elif any(term in dir_name for term in ['redist', 'setup', 'support', 'tools', 'eadm']):
                        score -= 2
                    
                    # Analyze subdirectory names
                    subdirs = [d for d in dir_path.iterdir() if d.is_dir()]
                    subdir_names = [d.name.lower() for d in subdirs]
                    
                    # Game directories often have these subdirectories
                    game_subdir_indicators = ['data', 'config', 'save', 'content', 'assets', 'levels']
                    for indicator in game_subdir_indicators:
                        if any(indicator in name for name in subdir_names):
                            score += 0.5
                    
                    decky.logger.debug(f"Directory content score for {dir_path}: {score}")
                    return score
                    
                except (PermissionError, OSError) as e:
                    decky.logger.debug(f"Error analyzing directory {dir_path}: {e}")
                    return 0
            
            def score_executable(exe_path: Path) -> float:
                """Score an executable based on how likely it is to be the main game executable"""
                if not exe_path.is_file():
                    return 0
                    
                name = exe_path.stem.lower()
                score = 0
                
                # Skip utility executables
                if any(skip in name for skip in ["unins", "launcher", "crash", "setup", "config", "redist", "install"]):
                    return 0
                    
                decky.logger.debug(f"Scoring executable: {name}")
                
                # Name matching with game name
                name_words = set(re.findall(r'\w+', name.lower()))
                
                # Calculate word match score based on intersection
                matching_words = game_words.intersection(name_words)
                
                # If there are matching words, they're worth more if they're a larger percentage of the game name
                if matching_words:
                    match_percentage = len(matching_words) / len(game_words) if game_words else 0
                    word_score = len(matching_words) * 1.5 * (1 + match_percentage)
                    decky.logger.debug(f"  Name match score: +{word_score:.2f} (words: {matching_words})")
                    score += word_score
                
                # If the exe name is a substring of the game name or vice versa, that's a good indicator
                if name in game_name or any(word in name for word in game_words):
                    name_substring_score = 2
                    decky.logger.debug(f"  Name substring match: +{name_substring_score}")
                    score += name_substring_score
                
                # Check for exact name match (normalized)
                norm_exe_name = re.sub(r'[^a-z0-9]', '', name)
                norm_game_name = re.sub(r'[^a-z0-9]', '', game_name)
                
                if norm_exe_name == norm_game_name or name == game_name:
                    exact_match_score = 3
                    decky.logger.debug(f"  Exact normalized name match: +{exact_match_score}")
                    score += exact_match_score
                
                try:
                    # File size is still a factor, but less important than name matching
                    size = exe_path.stat().st_size
                    size_mb = size / (1024 * 1024)
                    
                    # Logarithmic scoring for size - diminishing returns for very large files
                    if size_mb > 0:
                        import math
                        size_score = min(1.5, math.log10(size_mb) / 2)  # Reduced weight for size
                        decky.logger.debug(f"  Size score: +{size_score:.2f} ({size_mb:.2f} MB)")
                        score += size_score
                    
                    # Penalize extremely small executables
                    if size_mb < 0.5:  # Less than 500KB
                        size_penalty = 1
                        decky.logger.debug(f"  Small size penalty: -{size_penalty}")
                        score -= size_penalty
                except Exception as e:
                    decky.logger.debug(f"  Error checking file size: {e}")
                
                # Bonus for common game executable names
                if name.lower() in ["game", "start", "play", "client", "app"]:
                    common_name_score = 0.5
                    decky.logger.debug(f"  Common name bonus: +{common_name_score} ({name})")
                    score += common_name_score
                
                # If the name contains "launcher" or "setup", reduce score significantly
                if "launcher" in name.lower() or "setup" in name.lower():
                    launcher_penalty = 3
                    decky.logger.debug(f"  Launcher/setup penalty: -{launcher_penalty}")
                    score -= launcher_penalty
                
                decky.logger.debug(f"  Final executable score: {score}")
                return score
            
            def find_best_exe_dir(path: Path, max_depth=3, current_depth=0) -> tuple[Path, float]:
                """Recursively find the best executable directory"""
                if not path.exists() or not path.is_dir():
                    return None, 0
                    
                best_exe_dir = None
                best_score = -1
                
                try:
                    # First check for executables in this directory
                    exes_in_dir = []
                    for exe in path.glob("*.exe"):
                        exe_score = score_executable(exe)
                        if exe_score > 0:
                            exes_in_dir.append((exe, exe_score))
                    
                    # Get directory content score
                    dir_content_score = analyze_directory_content(path)
                    
                    # Sort executables by score (highest first)
                    exes_in_dir.sort(key=lambda x: x[1], reverse=True)
                    
                    # Calculate combined score for this directory
                    if exes_in_dir:
                        best_exe_score = exes_in_dir[0][1]
                        combined_score = best_exe_score + dir_content_score
                        decky.logger.debug(f"Directory {path} - Best exe: {exes_in_dir[0][0].name} (score: {best_exe_score:.2f}), Dir content: {dir_content_score:.2f}, Combined: {combined_score:.2f}")
                        
                        if combined_score > best_score:
                            best_score = combined_score
                            best_exe_dir = path
                    else:
                        # If no executables, just use the directory content score
                        if dir_content_score > best_score:
                            best_score = dir_content_score
                            best_exe_dir = path
                    
                    # If we haven't found a good match and have depth remaining, check subdirectories
                    if (best_score < 4 or current_depth == 0) and current_depth < max_depth:
                        for subdir in path.iterdir():
                            if subdir.is_dir():
                                sub_exe_dir, sub_score = find_best_exe_dir(subdir, max_depth, current_depth + 1)
                                if sub_score > best_score:
                                    best_score = sub_score
                                    best_exe_dir = sub_exe_dir
                
                except (PermissionError, OSError) as e:
                    decky.logger.debug(f"Error accessing directory {path}: {e}")
                
                return best_exe_dir, best_score
                
            # Find the best executable directory
            best_dir, score = find_best_exe_dir(path)
            
            return best_dir, score
            
        except Exception as e:
            decky.logger.error(f"Error in _find_game_executable_directory: {str(e)}")
            return path, 0

    def _find_heroic_game_executable_directory(self, game_path: str) -> str:
        """Find the directory containing the game's main executable using smart detection"""
        try:
            game_path = Path(game_path)
            if not game_path.exists() or not game_path.is_dir():
                return None
                
            # Get name of the game directory for smarter exe matching
            game_name = game_path.name.lower().replace("_", " ").replace("-", " ")
            
            decky.logger.info(f"Finding executable directory for Heroic game: {game_name}")
            
            # Use the unified game executable detection function
            best_dir, score = self._find_game_executable_directory(game_path, game_name)
            
            if best_dir and score > 0:
                decky.logger.info(f"Found game executable directory: {best_dir} (score: {score:.2f})")
                return str(best_dir)
            
            # If we couldn't find anything, check some common subdirectories
            common_dirs = ["bin", "bin32", "bin64", "binaries", "game", "win64", "win32", "x64", "x86"]
            for common in common_dirs:
                test_path = game_path / common
                if test_path.exists() and test_path.is_dir():
                    exes = list(test_path.glob("*.exe"))
                    if exes:
                        decky.logger.info(f"Using common executable directory: {test_path}")
                        return str(test_path)
            
            # If we still didn't find anything, just use the original path
            decky.logger.info(f"No suitable executable directory found, using original path: {game_path}")
            return str(game_path)
        
        except Exception as e:
            decky.logger.error(f"Error finding game executable directory: {str(e)}")
            return None

    def _find_game_path(self, appid: str) -> str:
        steam_root = Path(decky.HOME) / ".steam" / "steam"
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"

        if not library_file.exists():
            raise ValueError(f"Steam library file not found: {library_file}")

        library_paths = []
        with open(library_file, "r", encoding="utf-8") as file:
            for line in file:
                if '"path"' in line:
                    path = line.split('"path"')[1].strip().strip('"').replace("\\\\", "/")
                    library_paths.append(path)

        for library_path in library_paths:
            manifest_path = Path(library_path) / "steamapps" / f"appmanifest_{appid}.acf"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as manifest:
                    for line in manifest:
                        if '"installdir"' in line:
                            install_dir = line.split('"installdir"')[1].strip().strip('"')
                            base_path = Path(library_path) / "steamapps" / "common" / install_dir
                            
                            # Get name of the game directory for smarter exe matching
                            game_name = install_dir.lower().replace("_", " ").replace("-", " ")
                            
                            decky.logger.info(f"Finding executable directory for Steam game: {game_name}")
                            
                            # Use the unified game executable detection function
                            best_dir, score = self._find_game_executable_directory(base_path, game_name)
                            
                            if best_dir and score > 0:
                                decky.logger.info(f"Found game executable directory: {best_dir} (score: {score:.2f})")
                                return str(best_dir)
                            
                            # If we couldn't find anything, check some common subdirectories
                            common_dirs = ["bin", "bin32", "bin64", "binaries", "game", "win64", "win32", "x64", "x86"]
                            for common in common_dirs:
                                test_path = base_path / common
                                if test_path.exists() and test_path.is_dir():
                                    exes = list(test_path.glob("*.exe"))
                                    if exes:
                                        decky.logger.info(f"Using common executable directory: {test_path}")
                                        return str(test_path)
                            
                            # If we still didn't find anything, just use the original path
                            decky.logger.info(f"No suitable executable directory found, using base path: {base_path}")
                            return str(base_path)

        raise ValueError(f"Could not find installation directory for AppID: {appid}")

    async def uninstall_reshade_for_heroic_game(self, game_path: str) -> dict:
        """Uninstall ReShade from a Heroic game while preserving user presets"""
        try:
            decky.logger.info(f"Uninstalling ReShade from Heroic game at: {game_path}")
            
            # Find the executable directory
            exe_dir = self._find_heroic_game_executable_directory(game_path)
            if not exe_dir:
                decky.logger.warning(f"Could not find executable directory, using provided path: {game_path}")
                exe_dir = game_path
            
            # Remove ReShade files (excluding ReShadePreset.ini to preserve user settings)
            reshade_files = [
                "d3d8.dll", "d3d9.dll", "d3d10.dll", "d3d11.dll", "d3d12.dll", 
                "dxgi.dll", "opengl32.dll", "dinput8.dll", "ddraw.dll",
                "d3dcompiler_47.dll", "ReShade.ini", "ReShade_README.txt",
                "AutoHDR.addon32", "AutoHDR.addon64"
                # Note: ReShadePreset.ini is intentionally excluded to preserve user settings
            ]
            
            for file in reshade_files:
                file_path = os.path.join(exe_dir, file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    decky.logger.info(f"Removed {file_path}")
            
            # Remove ReShade_shaders directory if it exists
            shaders_path = os.path.join(exe_dir, "ReShade_shaders")
            if os.path.exists(shaders_path):
                if os.path.islink(shaders_path):
                    os.unlink(shaders_path)
                else:
                    shutil.rmtree(shaders_path)
                decky.logger.info(f"Removed {shaders_path}")
            
            # Check if ReShadePreset.ini exists and inform user it's preserved
            preset_path = os.path.join(exe_dir, "ReShadePreset.ini")
            if os.path.exists(preset_path):
                decky.logger.info(f"ReShadePreset.ini preserved at {preset_path}")
                return {"status": "success", "output": "ReShade uninstalled successfully.\nYour shader presets (ReShadePreset.ini) have been preserved for future use."}
            else:
                return {"status": "success", "output": "ReShade uninstalled successfully."}
                
        except Exception as e:
            decky.logger.error(f"Error uninstalling ReShade: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def detect_heroic_game_api(self, game_path: str) -> dict:
        """Detect the best API/DLL override for a Heroic game"""
        try:
            decky.logger.info(f"Detecting API for Heroic game at: {game_path}")
            
            # Verify game path exists
            if not os.path.exists(game_path):
                return {"status": "error", "message": f"Game path not found: {game_path}"}
            
            # Default API is dxgi (DirectX 10/11/12)
            detected_api = "dxgi"
            arch = "64"  # Default to 64-bit
            
            # Find all executable files
            exe_files = []
            for root, _, files in os.walk(game_path):
                for file in files:
                    if file.lower().endswith(".exe"):
                        # Skip known utility executables
                        if any(skip in file.lower() for skip in ["unins", "launcher", "crash", "setup", "config", "redist"]):
                            continue
                        
                        exe_path = os.path.join(root, file)
                        file_size = os.path.getsize(exe_path)
                        
                        # Larger files are more likely to be the main executable
                        if file_size > 1024 * 1024:  # Files larger than 1MB
                            exe_files.append((exe_path, file_size))
            
            # Sort by file size (descending)
            exe_files.sort(key=lambda x: x[1], reverse=True)
            
            # Process the largest executable files first
            for exe_path, _ in exe_files[:3]:  # Check the top 3 largest executables
                decky.logger.info(f"Analyzing executable: {exe_path}")
                
                # Check architecture
                try:
                    process = subprocess.run(
                        ["file", exe_path],
                        capture_output=True,
                        text=True
                    )
                    
                    if "PE32 executable" in process.stdout and "PE32+" not in process.stdout:
                        arch = "32"
                        decky.logger.info(f"Detected 32-bit executable: {exe_path}")
                    elif "PE32+ executable" in process.stdout or "x86-64" in process.stdout:
                        arch = "64"
                        decky.logger.info(f"Detected 64-bit executable: {exe_path}")
                except Exception as e:
                    decky.logger.error(f"Error checking architecture: {str(e)}")
                
                # Look for DLL files in the same directory to determine API
                exe_dir = os.path.dirname(exe_path)
                
                # Check for specific DLLs to determine API
                if os.path.exists(os.path.join(exe_dir, "d3d9.dll")):
                    detected_api = "d3d9"
                    decky.logger.info(f"Detected D3D9 API from d3d9.dll")
                    break
                elif os.path.exists(os.path.join(exe_dir, "d3d11.dll")):
                    detected_api = "d3d11"
                    decky.logger.info(f"Detected D3D11 API from d3d11.dll")
                    break
                elif os.path.exists(os.path.join(exe_dir, "d3d8.dll")):
                    detected_api = "d3d8"
                    decky.logger.info(f"Detected D3D8 API from d3d8.dll")
                    break
                elif os.path.exists(os.path.join(exe_dir, "opengl32.dll")):
                    detected_api = "opengl32"
                    decky.logger.info(f"Detected OpenGL API from opengl32.dll")
                    break
                elif os.path.exists(os.path.join(exe_dir, "dxgi.dll")):
                    detected_api = "dxgi"
                    decky.logger.info(f"Detected DXGI API from dxgi.dll")
                    break
                
                # If no DLLs found, try to analyze the executable for imports
                try:
                    # Check imports using objdump (if available)
                    process = subprocess.run(
                        ["objdump", "-p", exe_path],
                        capture_output=True,
                        text=True
                    )
                    
                    output = process.stdout.lower()
                    
                    # Check for DLL imports
                    if "d3d9.dll" in output:
                        detected_api = "d3d9"
                        decky.logger.info(f"Detected D3D9 API from imports")
                        break
                    elif "d3d11.dll" in output:
                        detected_api = "d3d11"
                        decky.logger.info(f"Detected D3D11 API from imports")
                        break
                    elif "d3d8.dll" in output:
                        detected_api = "d3d8"
                        decky.logger.info(f"Detected D3D8 API from imports")
                        break
                    elif "opengl32.dll" in output:
                        detected_api = "opengl32"
                        decky.logger.info(f"Detected OpenGL API from imports")
                        break
                    elif "dxgi.dll" in output:
                        detected_api = "dxgi"
                        decky.logger.info(f"Detected DXGI API from imports")
                        break
                except Exception as e:
                    decky.logger.error(f"Error analyzing imports: {str(e)}")
            
            # For 32-bit executables, default to d3d9 if not detected
            if arch == "32" and detected_api == "dxgi":
                detected_api = "d3d9"
                decky.logger.info(f"Falling back to D3D9 for 32-bit executable")
                
            decky.logger.info(f"Final detection - API: {detected_api}, Architecture: {arch}")
            
            return {
                "status": "success", 
                "api": detected_api,
                "architecture": arch
            }
        except Exception as e:
            decky.logger.error(f"Error detecting API for Heroic game: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def log_error(self, error: str) -> None:
        decky.logger.error(f"FRONTEND: {error}")