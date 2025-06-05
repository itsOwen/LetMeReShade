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
            'RESHADE_ADDON_SUPPORT': '0'
        }
        # Separate base paths for ReShade and VkBasalt
        self.main_path = os.path.join(self.environment['XDG_DATA_HOME'], 'reshade')
        self.vkbasalt_base_path = os.path.join(self.environment['XDG_DATA_HOME'], 'vkbasalt')
        self.vkbasalt_path = os.path.join(self.vkbasalt_base_path, 'installation')
        
        # Create necessary directories
        os.makedirs(self.main_path, exist_ok=True)
        os.makedirs(self.vkbasalt_path, exist_ok=True)

    async def _main(self):
        assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
        for script in assets_dir.glob("*.sh"):
            script.chmod(0o755)
        decky.logger.info("ReShade plugin loaded")

    async def _unload(self):
        decky.logger.info("ReShade plugin unloaded")

    async def check_reshade_path(self) -> dict:
        path = Path(os.path.expanduser("~/.local/share/reshade"))
        marker_file = path / ".installed"
        addon_marker = path / ".installed_addon"
        return {
            "exists": marker_file.exists() or addon_marker.exists(),
            "is_addon": addon_marker.exists()
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

    async def run_install_reshade(self, with_addon: bool = False) -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
            script_path = assets_dir / "reshade-install.sh"

            if not script_path.exists():
                decky.logger.error(f"Install script not found: {script_path}")
                return {"status": "error", "message": "Install script not found"}

            # Create a new environment dictionary for this installation
            install_env = self.environment.copy()
            
            # Explicitly set RESHADE_ADDON_SUPPORT based on the with_addon parameter
            install_env['RESHADE_ADDON_SUPPORT'] = '1' if with_addon else '0'
            
            # Add other necessary environment variables
            install_env.update({
                'LD_LIBRARY_PATH': '/usr/lib',
                'XDG_DATA_HOME': os.path.expandvars('$HOME/.local/share')
            })

            decky.logger.info(f"Installing ReShade with addon support: {with_addon}")
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

            return {"status": "success", "output": f"ReShade installed successfully!{'(with Addon Support)' if with_addon else ''}"}
        except Exception as e:
            decky.logger.error(f"Install error: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def run_install_vkbasalt(self) -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
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
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
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

            # Remove installation marker
            marker_file = Path(self.main_path) / ".installed"
            if marker_file.exists():
                marker_file.unlink()
                
            return {"status": "success", "output": "ReShade uninstalled"}
        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def run_uninstall_vkbasalt(self) -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
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

    async def manage_game_reshade(self, appid: str, action: str, dll_override: str = "dxgi", vulkan_mode: str = "") -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
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

            filtered_games = [g for g in games if "Proton" not in g["name"] and "Steam Linux Runtime" not in g["name"]]
            return {"status": "success", "games": filtered_games}

        except Exception as e:
            decky.logger.error(str(e))
            return {"status": "error", "message": str(e)}

    async def find_heroic_games(self) -> dict:
        """Find games installed through Heroic Launcher with improved detection"""
        try:
            # Common locations for Heroic games
            heroic_paths = [
                os.path.expanduser("~/Games/Heroic"),
                os.path.expanduser("~/Games/Heroic Games Launcher"),
                os.path.expanduser("~/heroic"),
                os.path.expanduser("~/HeroicGamesLauncher"),
                os.path.expanduser("~/.local/share/heroic/games")
            ]
            
            config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig/")
            
            # First check if any of the paths exist
            existing_paths = [path for path in heroic_paths if os.path.exists(path)]
            
            if not existing_paths:
                return {"status": "error", "message": "Heroic games directory not found"}
                
            games = []
            
            # Look for game directories in all possible locations
            for heroic_path in existing_paths:
                for game_dir in os.listdir(heroic_path):
                    game_path = os.path.join(heroic_path, game_dir)
                    if os.path.isdir(game_path) and game_dir.lower() not in ["prefixes", "temp", "legendary", "gog", "state", "logs"]:
                        # This is likely a game directory
                        game_info = {
                            "name": game_dir,
                            "path": game_path
                        }
                        
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
                        
                        # Find main executable to help with matching
                        exe_files = self._find_game_executables(game_path)
                        if exe_files:
                            main_exe = exe_files[0]  # Largest executable
                            game_info["main_exe"] = os.path.basename(main_exe["path"])
                        
                        games.append(game_info)
            
            # Try to match with config files if they exist
            if os.path.exists(config_path):
                config_matches = {}
                
                # First pass: Build a mapping of all config entries for easier access
                for config_file in os.listdir(config_path):
                    if config_file.endswith(".json"):
                        config_file_path = os.path.join(config_path, config_file)
                        try:
                            with open(config_file_path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                                for key in config_data:
                                    if key != "version" and key != "explicit":
                                        config_entry = config_data[key]
                                        # Store this config entry for later matching
                                        config_matches[(config_file, key)] = config_entry
                        except Exception as e:
                            decky.logger.error(f"Error reading config file {config_file}: {str(e)}")
                
                # Second pass: Try to match each game with its config
                for game in games:
                    best_match = None
                    best_score = 0
                    game_name_norm = self._normalize_string(game["name"])
                    
                    for (config_file, config_key), config_entry in config_matches.items():
                        match_score = 0
                        
                        # Check install path (most reliable)
                        if "installPath" in config_entry and game["path"].lower() == config_entry["installPath"].lower():
                            match_score += 15  # Direct path match is very strong
                        
                        # Check wine prefix
                        if "winePrefix" in config_entry:
                            prefix_game_name = os.path.basename(config_entry["winePrefix"])
                            prefix_norm = self._normalize_string(prefix_game_name)
                            
                            if game_name_norm == prefix_norm:
                                match_score += 10
                            elif game_name_norm in prefix_norm or prefix_norm in game_name_norm:
                                match_score += 5
                        
                        # Check app ID if available
                        if "app_id" in game and "gameId" in config_entry:
                            if game["app_id"] == str(config_entry["gameId"]):
                                match_score += 15  # App ID match is very strong
                        
                        # Check executable name if available
                        if "main_exe" in game and "targetExe" in config_entry:
                            game_exe = os.path.basename(game["main_exe"])
                            target_exe = os.path.basename(config_entry["targetExe"])
                            
                            if self._normalize_string(game_exe) == self._normalize_string(target_exe):
                                match_score += 10
                        
                        # Check title or name fields
                        name_fields = ["title", "name", "gameName"]
                        for field in name_fields:
                            if field in config_entry and isinstance(config_entry[field], str):
                                field_norm = self._normalize_string(config_entry[field])
                                if game_name_norm == field_norm:
                                    match_score += 8
                                elif game_name_norm in field_norm or field_norm in game_name_norm:
                                    match_score += 4
                        
                        # Update best match if this is better
                        if match_score > best_score:
                            best_score = match_score
                            best_match = (config_file, config_key)
                    
                    # If we found a good match, add the config info to the game
                    if best_match and best_score >= 5:
                        game["config_file"] = best_match[0]
                        game["config_key"] = best_match[1]
            
            # Sort games alphabetically by name
            games.sort(key=lambda g: g["name"].lower())
            
            return {"status": "success", "games": games}
        except Exception as e:
            decky.logger.error(f"Error finding Heroic games: {str(e)}")
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
                
            # Check if enviromentOptions exists
            if "enviromentOptions" not in config_data[config_key]:
                config_data[config_key]["enviromentOptions"] = []
            
            # Special case for VkBasalt
            if dll_override == "vkbasalt":
                # Remove any existing ENABLE_VKBASALT
                config_data[config_key]["enviromentOptions"] = [
                    env for env in config_data[config_key]["enviromentOptions"] 
                    if env.get("key") != "ENABLE_VKBASALT"
                ]
                
                # Add ENABLE_VKBASALT=1
                config_data[config_key]["enviromentOptions"].append({
                    "key": "ENABLE_VKBASALT",
                    "value": "1"
                })
            else:
                # Normal ReShade case - handle WINEDLLOVERRIDES
                # Remove any existing WINEDLLOVERRIDES
                config_data[config_key]["enviromentOptions"] = [
                    env for env in config_data[config_key]["enviromentOptions"] 
                    if env.get("key") != "WINEDLLOVERRIDES"
                ]
                
                # Add new WINEDLLOVERRIDES if not removing
                if dll_override != "remove":
                    config_data[config_key]["enviromentOptions"].append({
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

    async def find_heroic_game_config(self, game_path: str, game_name: str) -> dict:
        """
        Find the config file and key for a Heroic game using multiple robust detection strategies.
        This enhanced version handles edge cases like spaces, special characters, and unusual naming conventions.
        """
        try:
            decky.logger.info(f"Finding config for Heroic game: {game_name} at {game_path}")
            config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig/")
            
            if not os.path.exists(config_path):
                return {"status": "error", "message": "Heroic config directory not found"}
            
            # STRATEGY 0: Collect all game identifiers from various sources
            game_identifiers = set()
            
            # Normalize and add game name
            game_name_norm = self._normalize_string(game_name)
            game_identifiers.add(game_name_norm)
            
            # Add directory name
            game_dir_name = os.path.basename(game_path)
            game_dir_norm = self._normalize_string(game_dir_name)
            game_identifiers.add(game_dir_norm)
            
            # Find parent directory name (sometimes more accurate)
            parent_dir = os.path.basename(os.path.dirname(game_path))
            if parent_dir and parent_dir not in ["Games", "Heroic", "Home", "deck"]:
                parent_dir_norm = self._normalize_string(parent_dir)
                game_identifiers.add(parent_dir_norm)
            
            # Extract individual words for partial matching
            all_words = set()
            for identifier in game_identifiers:
                words = identifier.split()
                all_words.update(words)
            
            # Remove common words that might cause false matches
            common_words = {"the", "a", "an", "of", "and", "for", "in", "on", "to", "with", "game"}
            significant_words = {word for word in all_words if len(word) > 2 and word not in common_words}
            
            decky.logger.info(f"Game identifiers: {game_identifiers}")
            decky.logger.info(f"Significant words: {significant_words}")
            
            # Collect executable names
            exe_details = self._find_game_executables(game_path)
            for exe in exe_details:
                # Add executable names without extension
                exe_name = os.path.splitext(os.path.basename(exe["path"]))[0]
                exe_name_norm = self._normalize_string(exe_name)
                game_identifiers.add(exe_name_norm)
                
                # Add individual words from executable names
                exe_words = exe_name_norm.split()
                significant_words.update(word for word in exe_words if len(word) > 2 and word not in common_words)
                
            # Check for appinfo.json which might contain additional identifiers
            appinfo_paths = [
                os.path.join(game_path, "appinfo.json"),
                os.path.join(game_path, ".egstore", "appinfo.json"),
                os.path.join(os.path.dirname(game_path), ".egstore", "appinfo.json")
            ]
            
            for appinfo_path in appinfo_paths:
                if os.path.exists(appinfo_path):
                    try:
                        with open(appinfo_path, 'r', encoding='utf-8') as f:
                            appinfo = json.load(f)
                            if "AppName" in appinfo:
                                app_name_norm = self._normalize_string(appinfo["AppName"])
                                game_identifiers.add(app_name_norm)
                            if "DisplayName" in appinfo:
                                display_name_norm = self._normalize_string(appinfo["DisplayName"])
                                game_identifiers.add(display_name_norm)
                            if "AppId" in appinfo:
                                app_id = str(appinfo["AppId"])
                                game_identifiers.add(app_id)
                    except Exception as e:
                        decky.logger.error(f"Error reading appinfo.json: {str(e)}")
            
            # Store potential matches with scores
            potential_matches = []
            
            # STRATEGY 1: Scan all config files
            for config_file in os.listdir(config_path):
                if not config_file.endswith(".json"):
                    continue
                    
                config_file_path = os.path.join(config_path, config_file)
                try:
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        
                        # Look through each key in the config
                        for key in config_data:
                            if key in ["version", "explicit"]:
                                continue
                            
                            config_entry = config_data[key]
                            match_score = 0
                            match_details = []
                            match_strings = set()
                            
                            # Collect all potential identifiers from the config entry
                            self._extract_config_identifiers(config_entry, match_strings)
                            
                            # Normalize all strings from config
                            config_identifiers = {self._normalize_string(s) for s in match_strings if s}
                            
                            # Direct match with any game identifier
                            for game_id in game_identifiers:
                                for config_id in config_identifiers:
                                    if game_id == config_id:
                                        match_score += 10
                                        match_details.append(f"Direct match: {game_id} == {config_id}")
                                    elif game_id in config_id:
                                        match_score += 5
                                        match_details.append(f"Contained match: {game_id} in {config_id}")
                                    elif config_id in game_id:
                                        match_score += 5
                                        match_details.append(f"Contained match: {config_id} in {game_id}")
                            
                            # Check for word-level matches with significant words
                            for config_id in config_identifiers:
                                config_words = config_id.split()
                                matching_words = significant_words.intersection(config_words)
                                if matching_words:
                                    match_score += len(matching_words) * 2
                                    match_details.append(f"Word matches: {', '.join(matching_words)}")
                            
                            # Check key directly (often contains game ID or name)
                            key_norm = self._normalize_string(key)
                            for game_id in game_identifiers:
                                if game_id == key_norm:
                                    match_score += 8
                                    match_details.append(f"Key match: {key}")
                                elif game_id in key_norm:
                                    match_score += 4
                                    match_details.append(f"Key contains game ID: {key}")
                                elif key_norm in game_id:
                                    match_score += 3
                                    match_details.append(f"Game ID contains key: {key}")
                            
                            # Path matching is very reliable when it exists
                            if "installPath" in config_entry:
                                install_path = config_entry["installPath"]
                                if game_path.lower() == install_path.lower():
                                    match_score += 15  # Perfect path match is strongest
                                    match_details.append(f"Perfect installPath match")
                                elif game_path.lower() in install_path.lower():
                                    match_score += 7
                                    match_details.append(f"Game path contained in installPath")
                                elif install_path.lower() in game_path.lower():
                                    match_score += 7
                                    match_details.append(f"installPath contained in game path")
                            
                            # Check for executable matches with main executables
                            if "targetExe" in config_entry and exe_details:
                                target_exe = config_entry["targetExe"]
                                target_name = os.path.splitext(os.path.basename(target_exe))[0]
                                target_norm = self._normalize_string(target_name)
                                
                                for exe in exe_details:
                                    exe_name = os.path.splitext(os.path.basename(exe["path"]))[0]
                                    exe_norm = self._normalize_string(exe_name)
                                    
                                    if exe_norm == target_norm:
                                        match_score += 10
                                        match_details.append(f"Executable match: {exe_name} == {target_name}")
                                    elif exe_norm in target_norm or target_norm in exe_norm:
                                        match_score += 5
                                        match_details.append(f"Partial executable match: {exe_name} and {target_name}")
                            
                            # If we have a decent match, add it to potential matches
                            if match_score > 0:
                                potential_matches.append({
                                    "config_file": config_file,
                                    "config_key": key,
                                    "score": match_score,
                                    "details": match_details
                                })
                except Exception as e:
                    decky.logger.error(f"Error processing config file {config_file}: {str(e)}")
            
            # Sort potential matches by score (highest first)
            potential_matches.sort(key=lambda x: x["score"], reverse=True)
            
            # Log what we found
            for match in potential_matches:
                decky.logger.info(f"Potential config match: {match['config_file']} / {match['config_key']} (Score: {match['score']})")
                for detail in match['details']:
                    decky.logger.info(f"  - {detail}")
            
            # Return the best match if we have one
            if potential_matches:
                best_match = potential_matches[0]
                decky.logger.info(f"Best config match: {best_match['config_file']} / {best_match['config_key']} (Score: {best_match['score']})")
                return {
                    "status": "success",
                    "config_file": best_match["config_file"],
                    "config_key": best_match["config_key"],
                    "score": best_match["score"],
                    "details": best_match["details"]
                }
                        
            return {"status": "error", "message": f"Could not find config for game: {game_name}"}
        except Exception as e:
            decky.logger.error(f"Error finding Heroic game config: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _normalize_string(self, text):
        """Normalize a string for consistent comparison"""
        if not text or not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace common separators with spaces
        for char in ["-", "_", ".", ","]:
            text = text.replace(char, " ")
        
        # Remove special characters
        text = ''.join(c for c in text if c.isalnum() or c.isspace())
        
        # Collapse multiple spaces
        while "  " in text:
            text = text.replace("  ", " ")
        
        # Trim leading/trailing spaces
        return text.strip()

    def _extract_config_identifiers(self, config_entry, match_strings):
        """Extract all potential identifiers from a config entry"""
        # Fields that might contain game identifiers
        identifier_fields = [
            "title", "name", "gameName", "game_name", "displayName", "displayTitle",
            "appName", "appTitle", "shortName", "gameID", "gameId", "appID", "appId"
        ]
        
        # Recursively extract strings from nested structure
        if isinstance(config_entry, dict):
            # First check known identifier fields
            for field in identifier_fields:
                if field in config_entry and isinstance(config_entry[field], str):
                    match_strings.add(config_entry[field])
            
            # Also check wine prefix for game name
            if "winePrefix" in config_entry and isinstance(config_entry["winePrefix"], str):
                prefix_game_name = os.path.basename(config_entry["winePrefix"])
                match_strings.add(prefix_game_name)
            
            # Look through all other fields
            for key, value in config_entry.items():
                if isinstance(value, str):
                    # Add all string values as potential matches
                    match_strings.add(value)
                    
                    # Extract substrings that might be paths
                    if "/" in value or "\\" in value:
                        parts = value.replace("\\", "/").split("/")
                        for part in parts:
                            if part and not part.startswith("$") and len(part) > 3:
                                match_strings.add(part)
                
                elif isinstance(value, (dict, list)):
                    self._extract_config_identifiers(value, match_strings)
                    
        elif isinstance(config_entry, list):
            for item in config_entry:
                self._extract_config_identifiers(item, match_strings)

    def _find_game_executables(self, game_path):
        """Find and analyze executable files in the game directory"""
        exe_files = []
        
        # Walk through the directory looking for executables
        for root, _, files in os.walk(game_path):
            for file in files:
                if not file.lower().endswith(".exe"):
                    continue
                    
                # Skip utility executables
                if any(skip in file.lower() for skip in ["unins", "launcher", "crash", "setup", "config", "redist"]):
                    continue
                    
                exe_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(exe_path)
                    # Only consider executables of reasonable size
                    if file_size > 100 * 1024:  # Larger than 100KB
                        exe_files.append({
                            "path": exe_path,
                            "size": file_size,
                            "name": file
                        })
                except Exception:
                    pass
        
        # Sort by file size (largest first) as main executables tend to be larger
        exe_files.sort(key=lambda x: x["size"], reverse=True)
        
        return exe_files

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

    async def search_heroic_config_by_identifier(self, identifier: str) -> dict:
        """
        Search for a Heroic config by any identifier (game ID, name, path, etc.)
        This is useful as a fallback when other methods fail.
        """
        try:
            config_path = os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig/")
            
            if not os.path.exists(config_path):
                return {"status": "error", "message": "Heroic config directory not found"}
                
            identifier_norm = self._normalize_string(identifier)
            potential_matches = []
            
            # Check each config file
            for config_file in os.listdir(config_path):
                if not config_file.endswith(".json"):
                    continue
                    
                config_file_path = os.path.join(config_path, config_file)
                try:
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        
                        # Look through each game entry
                        for key in config_data:
                            if key in ["version", "explicit"]:
                                continue
                                
                            config_entry = config_data[key]
                            match_score = 0
                            match_details = []
                            
                            # Try direct key match
                            key_norm = self._normalize_string(key)
                            if identifier_norm == key_norm:
                                match_score += 10
                                match_details.append(f"Key match: {key}")
                            elif identifier_norm in key_norm:
                                match_score += 5
                                match_details.append(f"Key contains identifier: {key}")
                            
                            # Check all string values recursively
                            all_strings = self._extract_all_strings(config_entry)
                            
                            for s in all_strings:
                                s_norm = self._normalize_string(s)
                                if s_norm and identifier_norm == s_norm:
                                    match_score += 10
                                    match_details.append(f"Direct match: {s}")
                                elif s_norm and identifier_norm in s_norm:
                                    match_score += 3
                                    match_details.append(f"Contained match: {identifier} in {s}")
                                elif s_norm and s_norm in identifier_norm:
                                    match_score += 2
                                    match_details.append(f"Contained match: {s} in {identifier}")
                            
                            # If we have a decent match, add it to potential matches
                            if match_score > 0:
                                potential_matches.append({
                                    "config_file": config_file,
                                    "config_key": key,
                                    "score": match_score,
                                    "details": match_details
                                })
                except Exception as e:
                    decky.logger.error(f"Error processing config file {config_file}: {str(e)}")
            
            # Sort potential matches by score (highest first)
            potential_matches.sort(key=lambda x: x["score"], reverse=True)
            
            # Return the best match if we have one
            if potential_matches:
                best_match = potential_matches[0]
                return {
                    "status": "success",
                    "config_file": best_match["config_file"],
                    "config_key": best_match["config_key"],
                    "score": best_match["score"],
                    "details": best_match["details"]
                }
            
            return {"status": "error", "message": f"No config found for identifier: {identifier}"}
        except Exception as e:
            decky.logger.error(f"Error searching Heroic config: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _extract_all_strings(self, obj, max_depth=5):
        """Extract all string values from a nested object"""
        if max_depth <= 0:
            return []
            
        result = []
        
        if isinstance(obj, str):
            result.append(obj)
        elif isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, str):
                    result.append(value)
                elif isinstance(value, (dict, list)) and max_depth > 1:
                    result.extend(self._extract_all_strings(value, max_depth - 1))
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, (dict, list)) and max_depth > 1:
                    result.extend(self._extract_all_strings(item, max_depth - 1))
        
        return result

    async def log_error(self, error: str) -> None:
        decky.logger.error(f"FRONTEND: {error}")