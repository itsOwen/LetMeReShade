import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  DropdownItem
} from "@decky/ui";
import { definePlugin, callable } from "@decky/api";
import { IoMdColorPalette } from "react-icons/io";

interface InstallResult {
  status: string;
  message?: string;
  output?: string;
}

interface GameInfo {
  appid: string;
  name: string;
}

interface ReShadeResponse {
  status: string;
  message?: string;
  output?: string;
}

interface PathCheckResponse {
  exists: boolean;
}

interface GameListResponse {
  status: string;
  games: GameInfo[];
}

const runInstallReShade = callable<[], ReShadeResponse>("run_install_reshade");
const runUninstallReShade = callable<[], ReShadeResponse>("run_uninstall_reshade");
const manageGameReShade = callable<[string, string, string], ReShadeResponse>("manage_game_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const listInstalledGames = callable<[], GameListResponse>("list_installed_games");
const logError = callable<[string], void>("log_error");

function ReShadeInstallerSection() {
  const [installing, setInstalling] = useState<boolean>(false);
  const [uninstalling, setUninstalling] = useState<boolean>(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);

  useEffect(() => {
    const checkPath = async () => {
      try {
        const result = await checkReShadePath();
        setPathExists(result.exists);
      } catch (e) {
        await logError(`useEffect -> checkPath: ${String(e)}`);
      }
    };
    checkPath();
    const intervalId = setInterval(checkPath, 3000);
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (installResult) {
      const timer = setTimeout(() => setInstallResult(null), 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [installResult]);

  useEffect(() => {
    if (uninstallResult) {
      const timer = setTimeout(() => setUninstallResult(null), 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [uninstallResult]);

  const handleInstallClick = async () => {
    try {
      setInstalling(true);
      const result = await runInstallReShade();
      setInstallResult(result);
    } catch (e) {
      setInstallResult({ status: "error", message: String(e) });
      await logError(`Install error: ${String(e)}`);
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstallClick = async () => {
    try {
      setUninstalling(true);
      const result = await runUninstallReShade();
      setUninstallResult(result);
    } catch (e) {
      setUninstallResult({ status: "error", message: String(e) });
      await logError(`Uninstall error: ${String(e)}`);
    } finally {
      setUninstalling(false);
    }
  };

  return (
    <PanelSection>
      {pathExists !== null && (
        <PanelSectionRow>
          <div style={{ color: pathExists ? "green" : "red" }}>
            {pathExists ? "ReShade Is Installed" : "ReShade Not Installed"}
          </div>
        </PanelSectionRow>
      )}

      {pathExists === false && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleInstallClick} disabled={installing}>
            {installing ? "Installing..." : "🔧 Install ReShade"}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {pathExists === true && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleUninstallClick} disabled={uninstalling}>
            {uninstalling ? "Uninstalling..." : "🗑️ Uninstall ReShade"}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {installResult && (
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginTop: '16px',
            backgroundColor: 'var(--decky-selected-ui-bg)',
            borderRadius: '4px',
            color: installResult.status === "success" ? "green" : "red"
          }}>
            {installResult.status === "success" ? 
              "✅ ReShade installed successfully!" : 
              `❌ Error: ${installResult.message || "Installation failed"}`}
          </div>
        </PanelSectionRow>
      )}

      {uninstallResult && (
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginTop: '16px',
            backgroundColor: 'var(--decky-selected-ui-bg)',
            borderRadius: '4px',
            color: uninstallResult.status === "success" ? "green" : "red"
          }}>
            {uninstallResult.status === "success" ? 
              "✅ ReShade uninstalled successfully!" : 
              `❌ Error: ${uninstallResult.message || "Uninstallation failed"}`}
          </div>
        </PanelSectionRow>
      )}

      <PanelSectionRow>
        <div>
          Press HOME key in-game to access the ReShade overlay.
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
}

interface ProcessedGameInfo {
  appid: number;
  name: string;
}

function InstalledGamesSection() {
  const [games, setGames] = useState<ProcessedGameInfo[]>([]);
  const [selectedGame, setSelectedGame] = useState<ProcessedGameInfo | null>(null);
  const [result, setResult] = useState<string>('');

  useEffect(() => {
    const fetchGames = async () => {
      try {
        const response = await listInstalledGames();
        if (response.status === "success") {
          const sortedGames = response.games
            .map(game => ({
              appid: parseInt(game.appid, 10),
              name: game.name
            }))
            .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
          setGames(sortedGames);
        }
      } catch (error) {
        await logError(`Error fetching games: ${String(error)}`);
      }
    };
    fetchGames();
  }, []);

  const handlePatchClick = async () => {
    if (!selectedGame) return;

    try {
      const reshadeCheck = await checkReShadePath();
      if (!reshadeCheck.exists) {
        setResult("Please install ReShade first before patching games.");
        return;
      }

      const response = await manageGameReShade(
        selectedGame.appid.toString(),
        "install",
        "dxgi"
      );

      if (response.status === "success") {
        const launchOptionsMatch = response.output?.match(/Use this launch option: (.+)/);
        if (launchOptionsMatch) {
          const launchOptions = launchOptionsMatch[1];
          const detectedApi = launchOptions.match(/;(\w+)=n,b/)?.pop() || 'dxgi';
          await SteamClient.Apps.SetAppLaunchOptions(selectedGame.appid, launchOptions);
          setResult(`ReShade installed successfully for ${selectedGame.name} using ${detectedApi.toUpperCase()} API.\nPress Home key in-game to open ReShade overlay.`);
        } else {
          await SteamClient.Apps.SetAppLaunchOptions(selectedGame.appid, 'WINEDLLOVERRIDES="d3dcompiler_47=n;dxgi=n,b" %command%');
          setResult(`ReShade installed successfully for ${selectedGame.name}. Press Home key in-game to open ReShade overlay.`);
        }
      } else {
        setResult(`Failed to install ReShade: ${response.message || 'Unknown error'}`);
      }
    } catch (error) {
      await logError(`handlePatchClick: ${String(error)}`);
      setResult(`Error installing ReShade: ${String(error)}`);
    }
  };

  const handleUnpatchClick = async () => {
    if (!selectedGame) return;

    try {
      const reshadeCheck = await checkReShadePath();
      if (!reshadeCheck.exists) {
        setResult("ReShade is not installed.");
        return;
      }

      const response = await manageGameReShade(
        selectedGame.appid.toString(),
        "uninstall",
        "dxgi"
      );

      if (response.status === "success") {
        await SteamClient.Apps.SetAppLaunchOptions(selectedGame.appid, '');
        setResult(`ReShade removed successfully from ${selectedGame.name}`);
      } else {
        setResult(`Failed to remove ReShade: ${response.message || 'Unknown error'}`);
      }
    } catch (error) {
      await logError(`handleUnpatchClick: ${String(error)}`);
      setResult(`Error removing ReShade: ${String(error)}`);
    }
  };

  return (
    <PanelSection title="Select a game to patch:">
      <PanelSectionRow>
        <DropdownItem
          rgOptions={games.map(game => ({
            data: game.appid,
            label: game.name
          }))}
          selectedOption={selectedGame?.appid}
          onChange={(option) => {
            const game = games.find(g => g.appid === option.data);
            setSelectedGame(game || null);
            setResult('');
          }}
          strDefaultLabel="Select a game..."
          menuLabel="Installed Games"
        />
      </PanelSectionRow>

      {result && (
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginTop: '16px',
            backgroundColor: 'var(--decky-selected-ui-bg)',
            borderRadius: '4px'
          }}>
            {result}
          </div>
        </PanelSectionRow>
      )}

      {selectedGame && (
        <>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handlePatchClick}
            >
              🔧 Install ReShade
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleUnpatchClick}
            >
              🗑️ Remove ReShade
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
}

export default definePlugin(() => ({
  name: "LetMeReShade Plugin",
  titleView: <div>ReShade Manager</div>,
  alwaysRender: true,
  content: (
    <>
      <ReShadeInstallerSection />
      <InstalledGamesSection />
    </>
  ),
  icon: <IoMdColorPalette />,
  onDismount() {
    console.log("ReShade Plugin unmounted");
  },
}));