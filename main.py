import decky
import os
import subprocess
import shutil
from pathlib import Path

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
        # Ensure the main path exists
        self.main_path = os.path.join(self.environment['XDG_DATA_HOME'], 'reshade')
        os.makedirs(self.main_path, exist_ok=True)

    async def _main(self):
        assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
        for script in assets_dir.glob("*.sh"):
            script.chmod(0o755)
        decky.logger.info("ReShade plugin loaded")

    async def _unload(self):
        decky.logger.info("ReShade plugin unloaded")

    async def check_reshade_path(self) -> dict:
        path = Path(os.path.expanduser("~/.local/share/reshade"))
        return {"exists": path.exists()}

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
                            return str(Path(library_path) / "steamapps" / "common" / install_dir)

        raise ValueError(f"Could not find installation directory for AppID: {appid}")

    async def run_install_reshade(self) -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
            script_path = assets_dir / "reshade-install.sh"

            if not script_path.exists():
                decky.logger.error(f"Install script not found: {script_path}")
                return {"status": "error", "message": "Install script not found"}

            env = os.environ.copy()
            env.update(self.environment)
            env['LD_LIBRARY_PATH'] = '/usr/lib'
            
            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )

            decky.logger.info(f"Install output:\n{process.stdout}")
            if process.stderr:
                decky.logger.error(f"Install errors:\n{process.stderr}")

            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}

            return {"status": "success", "output": "ReShade installed successfully!"}
        except Exception as e:
            decky.logger.error(f"Install error: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def run_uninstall_reshade(self) -> dict:
        try:
            assets_dir = Path(decky.DECKY_PLUGIN_DIR) / "defaults" / "assets"
            script_path = assets_dir / "reshade-uninstall.sh"
            
            if not script_path.exists():
                return {"status": "error", "message": "Uninstall script not found"}

            env = os.environ.copy()
            env.update(self.environment)
            env['LD_LIBRARY_PATH'] = '/usr/lib'
            
            process = subprocess.run(
                ["/bin/bash", str(script_path)],
                cwd=str(assets_dir),
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                return {"status": "error", "message": process.stderr}
                
            return {"status": "success", "output": "ReShade uninstalled"}
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

            env = os.environ.copy()
            env.update(self.environment)
            env['LD_LIBRARY_PATH'] = '/usr/lib'

            cmd = ["/bin/bash", str(script_path), action, game_path, dll_override]
            if vulkan_mode:
                cmd.extend([vulkan_mode, os.path.expanduser(f"~/.local/share/Steam/steamapps/compatdata/{appid}")])
            
            process = subprocess.run(
                cmd,
                cwd=str(assets_dir),
                env=env,
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

    async def log_error(self, error: str) -> None:
        decky.logger.error(f"FRONTEND: {error}")