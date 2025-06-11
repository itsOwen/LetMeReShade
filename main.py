import decky
import os
import subprocess
import shutil
from pathlib import Path
import json
import glob
import re

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
            'RESHADE_VERSION': 'latest'  
        }
        # Separate base paths for ReShade and VkBasalt
        self.main_path = os.path.join(self.environment['XDG_DATA_HOME'], 'reshade')
        self.vkbasalt_base_path = os.path.join(self.environment['XDG_DATA_HOME'], 'vkbasalt')
        self.vkbasalt_path = os.path.join(self.vkbasalt_base_path, 'installation')
        
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
                            game_words = set(word.strip() for word in game_name.split())

                            def score_executable(exe_path: Path) -> float:
                                if not exe_path.is_file():
                                    return 0
                                    
                                name = exe_path.stem.lower()
                                score = 0

                                if any(skip in name for skip in ["unins", "launcher", "crash", "setup", "config", "redist"]):
                                    return 0

                                try:
                                    size = exe_path.stat().st_size
                                    if size > 1024 * 1024 * 10:  # Larger than 10MB
                                        score += 2
                                    elif size < 1024 * 1024:  # Smaller than 1MB
                                        score -= 1
                                except:
                                    pass

                                name_words = set(word.strip() for word in name.split())
                                matching_words = game_words.intersection(name_words)
                                score += len(matching_words) * 2

                                return score

                            def find_best_exe(path: Path, max_depth=4) -> tuple[Path, float]:
                                if not path.exists() or not path.is_dir():
                                    return None, 0

                                best_exe = None
                                best_score = -1

                                try:
                                    for exe in path.glob("*.exe"):
                                        score = score_executable(exe)
                                        if score > best_score:
                                            best_score = score
                                            best_exe = exe.parent

                                    if best_score < 3 and max_depth > 0:
                                        for subdir in path.iterdir():
                                            if subdir.is_dir():
                                                sub_exe, sub_score = find_best_exe(subdir, max_depth - 1)
                                                if sub_score > best_score:
                                                    best_score = sub_score
                                                    best_exe = sub_exe

                                except (PermissionError, OSError):
                                    pass

                                return best_exe, best_score

                            best_path, score = find_best_exe(base_path)
                            
                            if best_path and score > 0:
                                decky.logger.info(f"Found game executable directory: {best_path} (score: {score})")
                                return str(best_path)
                            
                            decky.logger.info(f"No suitable executable found, using base path: {base_path}")
                            return str(base_path)

        raise ValueError(f"Could not find installation directory for AppID: {appid}")

    async def run_install_reshade(self, with_addon: bool = False, version: str = "latest") -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "reshade-install.sh"

            if not script_path.exists():
                decky.logger.error(f"Install script not found: {script_path}")
                return {"status": "error", "message": "Install script not found"}

            # Create a new environment dictionary for this installation
            install_env = self.environment.copy()
            
            # Explicitly set RESHADE_ADDON_SUPPORT and RESHADE_VERSION based on parameters
            install_env['RESHADE_ADDON_SUPPORT'] = '1' if with_addon else '0'
            install_env['RESHADE_VERSION'] = version
            
            # Add other necessary environment variables
            install_env.update({
                'LD_LIBRARY_PATH': '/usr/lib',
                'XDG_DATA_HOME': os.path.expandvars('$HOME/.local/share')
            })

            decky.logger.info(f"Installing ReShade {version} with addon support: {with_addon}")
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

            version_display = f"ReShade {version.title()}" + (' (with Addon Support)' if with_addon else '')
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
            
            # Check 2: Look for Linux-specific files and directories
            linux_indicators = [
                # Common Linux executable patterns
                "*.x86_64", "*.x86", "*.bin", "*.sh",
                # Common Linux directories
                "lib", "lib64", "bin", "share",
                # Common Linux files
                "*.so", "*.so.*"
            ]
            
            linux_files_found = []
            for pattern in linux_indicators:
                matches = list(game_path_obj.rglob(pattern))
                if matches:
                    linux_files_found.extend([str(m.relative_to(game_path_obj)) for m in matches[:5]])  # Limit to 5 examples
            
            # Check 3: Look for specific Linux game files
            linux_executables = []
            for file in game_path_obj.iterdir():
                if file.is_file() and file.suffix == "":  # Files without extension (common for Linux executables)
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
            
            # Check 4: Look for Unity Linux indicators
            unity_linux_indicators = [
                "*_Data/Plugins/x86_64",
                "*_Data/Mono",
                "UnityPlayer.so"
            ]
            
            unity_linux_files = []
            for pattern in unity_linux_indicators:
                matches = list(game_path_obj.rglob(pattern))
                if matches:
                    unity_linux_files.extend([str(m.relative_to(game_path_obj)) for m in matches[:3]])
            
            # Check 5: Read Steam manifest to get platform info
            steam_root = Path(decky.HOME) / ".steam" / "steam"
            library_file = steam_root / "steamapps" / "libraryfolders.vdf"
            manifest_platform = None
            
            if library_file.exists():
                library_paths = []
                with open(library_file, "r", encoding="utf-8") as file:
                    for line in file:
                        if '"path"' in line:
                            path = line.split('"path"')[1].strip().strip('"').replace("\\\\", "/")
                            library_paths.append(path)
                
                for library_path in library_paths:
                    manifest_path = Path(library_path) / "steamapps" / f"appmanifest_{appid}.acf"
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, "r", encoding="utf-8") as manifest:
                                content = manifest.read()
                                # Look for tool information which might indicate platform
                                if '"tool"' in content and '"1"' in content:
                                    # This might be a tool/utility, not a game
                                    pass
                        except Exception as e:
                            decky.logger.debug(f"Error reading manifest: {str(e)}")
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
            if not has_main_exe and linux_files_found:
                is_linux_game = True
                confidence = "medium"
                reasons.append(f"No Windows .exe files found, but Linux files present")
            
            # Weak indicators
            if not has_exe_files and len(linux_files_found) > 10:
                is_linux_game = True
                confidence = "medium" if not reasons else confidence
                reasons.append("Many Linux-style files found, no .exe files")
            
            # Additional context
            total_files = len(list(game_path_obj.rglob("*"))) if game_path_obj.exists() else 0
            
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
                    "linux_files_found": len(linux_files_found),
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

    async def manage_game_reshade(self, appid: str, action: str, dll_override: str = "dxgi", vulkan_mode: str = "") -> dict:
        try:
            assets_dir = self._get_assets_dir()
            script_path = assets_dir / "reshade-game-manager.sh"
            
            try:
                game_path = self._find_game_path(appid)
                decky.logger.info(f"Found game path: {game_path}")
            except ValueError as e:
                return {"status": "error", "message": str(e)}

            cmd = ["/bin/bash", str(script_path), action, game_path, dll_override]
            if vulkan_mode:
                cmd.extend([vulkan_mode, os.path.expanduser(f"~/.local/share/Steam/steamapps/compatdata/{appid}")])
            
            process = subprocess.run(
                cmd,
                cwd=str(assets_dir),
                env={**os.environ, **self.environment, 'LD_LIBRARY_PATH': '/usr/lib'},
                capture_output=True,
                text=True
            )
            
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
            
            # First, try to read the Heroic config file
            heroic_config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/store/config.json")
            if os.path.exists(heroic_config_path):
                with open(heroic_config_path, 'r', encoding='utf-8') as f:
                    heroic_config = json.load(f)
                
                # Get the list of recent games
                recent_games = heroic_config.get("games", {}).get("recent", [])
                
                # Normalize game name by removing spaces, making lowercase
                normalized_game_name = game_name.lower().replace(" ", "")
                
                # Look for a match by title with flexible matching
                for game in recent_games:
                    game_title = game.get("title", "")
                    normalized_title = game_title.lower().replace(" ", "")
                    
                    # Try multiple matching approaches
                    if (game.get("title") == game_name or  # Exact match
                        normalized_title == normalized_game_name or  # Normalized match
                        game_name in game_title or  # Partial match
                        normalized_game_name in normalized_title):  # Normalized partial match
                        
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
                                    # Extract game name from winePrefix path
                                    prefix_game_name = os.path.basename(wine_prefix)
                                    
                                    # Compare with our game name
                                    if (prefix_game_name == game_name or
                                        prefix_game_name.lower().replace(" ", "") == normalized_game_name or
                                        game_name in prefix_game_name or
                                        normalized_game_name in prefix_game_name.lower().replace(" ", "")):
                                        
                                        decky.logger.info(f"Found match via winePrefix: {wine_prefix}")
                                        decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                        return {
                                            "status": "success",
                                            "config_file": config_file,
                                            "config_key": app_key
                                        }
                    except Exception as e:
                        decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
            
            # Fall back to checking for executable name matches
            decky.logger.info("Trying to match using executable names...")
            
            # Find the executable directory
            exe_dir = self._find_heroic_game_executable_directory(game_path)
            if not exe_dir:
                exe_dir = game_path
                
            # Find executable files
            exe_files = []
            for file in os.listdir(exe_dir):
                if file.lower().endswith(".exe") and not any(skip in file.lower() for skip in 
                                                        ["unins", "launcher", "crash", "setup", "config", "redist"]):
                    exe_files.append(file)
                    
            if exe_files:
                # Use the executable name for matching
                exe_name = os.path.splitext(exe_files[0])[0].lower()
                decky.logger.info(f"Using executable name for matching: {exe_name}")
                
                # Check all config files for matches
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
                                # Get game info from config
                                game_info = app_config.get("game", {})
                                config_title = game_info.get("title", "").lower()
                                
                                # Try to match by executable name
                                if (exe_name in config_title or
                                    exe_name.replace("_", "") in config_title.replace(" ", "") or
                                    config_title in exe_name):
                                    
                                    decky.logger.info(f"Found match via executable name: {exe_name} matches '{config_title}'")
                                    decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                    return {
                                        "status": "success",
                                        "config_file": config_file,
                                        "config_key": app_key
                                    }
                    except Exception as e:
                        decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
                        
            # As a last resort, check all config files and try to match install path
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
                            if install_path and (install_path == game_path or 
                                                os.path.basename(install_path) == os.path.basename(game_path)):
                                
                                decky.logger.info(f"Found match via install path: {install_path}")
                                decky.logger.info(f"Config file: {config_file}, key: {app_key}")
                                return {
                                    "status": "success",
                                    "config_file": config_file,
                                    "config_key": app_key
                                }
                except Exception as e:
                    decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
            
            # If we still couldn't find a match, look for appinfo.json
            return {"status": "error", "message": f"Could not find config for game: {game_name}"}
        except Exception as e:
            decky.logger.error(f"Error finding Heroic game config: {str(e)}")
            return {"status": "error", "message": str(e)}

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

    async def install_reshade_for_heroic_game(self, game_path: str, dll_override: str = "d3d9") -> dict:
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
                
                # Write the modified ini file
                with open(reshade_ini_dst, 'w', encoding='utf-8') as f:
                    f.write(ini_content)
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
                
            # Create a README file to help users with the configuration
            readme_path = os.path.join(exe_dir, "ReShade_README.txt")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"""ReShade for {os.path.basename(game_path)}
    ------------------------------------
    Installed with LetMeReShade plugin for Heroic Games Launcher

    DLL Override: {dll_override}
    Architecture: {arch}-bit
    Executable Directory: {exe_dir}

    Press HOME key in-game to open the ReShade overlay.

    If shaders are not visible:
    1. Open the ReShade overlay with HOME key
    2. Go to Settings tab
    3. Check paths for "Effect Search Paths" and "Texture Search Paths"
    4. They should point to the ReShade_shaders folder in this game directory
    5. If not, update them to: ".\\ReShade_shaders"

    Shader preset files (.ini) will be saved in this game directory.
    """)
                
            return {"status": "success", "output": f"ReShade installed successfully for Heroic game using {dll_override} override."}
        except Exception as e:
            decky.logger.error(f"Error installing ReShade for Heroic game: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _find_heroic_game_executable_directory(self, game_path: str) -> str:
        """Find the directory containing the game's main executable using smart detection"""
        try:
            game_path = Path(game_path)
            if not game_path.exists() or not game_path.is_dir():
                return None
                
            # Get name of the game directory for smarter exe matching
            game_name = game_path.name.lower().replace("_", " ").replace("-", " ")
            game_words = set(word.strip() for word in game_name.split())
            
            decky.logger.info(f"Looking for executables for game: {game_name}")
            decky.logger.info(f"Game words for matching: {game_words}")
            
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
                
                try:
                    # File size is a good indicator - main game executables tend to be larger
                    size = exe_path.stat().st_size
                    if size > 1024 * 1024 * 10:  # Larger than 10MB
                        score += 2
                        decky.logger.debug(f"  Large size bonus: +2 ({size} bytes)")
                    elif size > 1024 * 1024:  # Larger than 1MB
                        score += 1
                        decky.logger.debug(f"  Medium size bonus: +1 ({size} bytes)")
                    elif size < 1024 * 500:  # Smaller than 500KB
                        score -= 1
                        decky.logger.debug(f"  Small size penalty: -1 ({size} bytes)")
                except Exception as e:
                    decky.logger.debug(f"  Error checking file size: {e}")
                    
                # Word matching with game name is very useful
                name_words = set(word.strip() for word in re.split(r'[_\-\s]', name))
                matching_words = game_words.intersection(name_words)
                word_score = len(matching_words) * 2
                
                if word_score > 0:
                    decky.logger.debug(f"  Name match bonus: +{word_score} (words: {matching_words})")
                    score += word_score
                    
                # Some common executable names get bonus points
                if name.lower() in ["game", "start", "play", "client", "bin", "win64", "win32", "app"]:
                    score += 1
                    decky.logger.debug(f"  Common name bonus: +1 ({name})")
                    
                # Bonus for exact name match
                if name.lower() == game_name.lower() or name.lower().replace(" ", "") == game_name.lower().replace(" ", ""):
                    score += 3
                    decky.logger.debug(f"  Exact name match bonus: +3")
                    
                # If the name has "launcher" or "setup" in it, reduce score significantly
                if "launcher" in name.lower() or "setup" in name.lower():
                    score -= 3
                    decky.logger.debug(f"  Launcher/setup penalty: -3")
                    
                decky.logger.debug(f"  Final score: {score}")
                return score
            
            def find_best_exe(path: Path, max_depth=3, current_depth=0) -> tuple[Path, float]:
                """Recursively find the best executable directory"""
                if not path.exists() or not path.is_dir():
                    return None, 0
                    
                best_exe_dir = None
                best_score = -1
                
                try:
                    # First check for executables in this directory
                    exes_in_dir = []
                    for exe in path.glob("*.exe"):
                        score = score_executable(exe)
                        if score > 0:
                            exes_in_dir.append((exe, score))
                    
                    # Sort by score (highest first)
                    exes_in_dir.sort(key=lambda x: x[1], reverse=True)
                    
                    # If we found good executables, use this directory
                    if exes_in_dir and exes_in_dir[0][1] > best_score:
                        best_score = exes_in_dir[0][1]
                        best_exe_dir = path
                        decky.logger.debug(f"Found good executable in {path}: {exes_in_dir[0][0].name} (score: {best_score})")
                    
                    # If we didn't find a good match and have depth remaining, check subdirectories
                    if (best_score < 3 or current_depth == 0) and current_depth < max_depth:
                        for subdir in path.iterdir():
                            if subdir.is_dir():
                                sub_exe_dir, sub_score = find_best_exe(subdir, max_depth, current_depth + 1)
                                if sub_score > best_score:
                                    best_score = sub_score
                                    best_exe_dir = sub_exe_dir
                
                except (PermissionError, OSError) as e:
                    decky.logger.debug(f"Error accessing directory {path}: {e}")
                
                return best_exe_dir, best_score
            
            # Find the best executable directory
            best_dir, score = find_best_exe(game_path)
            
            if best_dir and score > 0:
                decky.logger.info(f"Found game executable directory: {best_dir} (score: {score})")
                return str(best_dir)
            
            # If we couldn't find anything, check some common subdirectories
            common_dirs = ["bin", "binaries", "game", "win64", "win32", "x64", "x86"]
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

    async def uninstall_reshade_for_heroic_game(self, game_path: str) -> dict:
        """Uninstall ReShade from a Heroic game"""
        try:
            decky.logger.info(f"Uninstalling ReShade from Heroic game at: {game_path}")
            
            # Find the executable directory
            exe_dir = self._find_heroic_game_executable_directory(game_path)
            if not exe_dir:
                decky.logger.warning(f"Could not find executable directory, using provided path: {game_path}")
                exe_dir = game_path
            
            # Remove ReShade files
            reshade_files = [
                "d3d8.dll", "d3d9.dll", "d3d10.dll", "d3d11.dll", "d3d12.dll", 
                "dxgi.dll", "opengl32.dll", "dinput8.dll", "ddraw.dll",
                "d3dcompiler_47.dll", "ReShade.ini", "ReShade_README.txt"
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