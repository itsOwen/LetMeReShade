import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  DropdownItem,
  ToggleField,
  ConfirmModal,
  showModal
} from "@decky/ui";
import { definePlugin, callable } from "@decky/api";
import { IoMdColorPalette } from "react-icons/io";
import ManualPatchSection from "./ManualPatchSection";
import NonSteamManager from "./NonSteamManager";

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
  is_addon: boolean;
}

interface GameListResponse {
  status: string;
  games: GameInfo[];
}

const runInstallReShade = callable<[boolean], ReShadeResponse>("run_install_reshade");
const runUninstallReShade = callable<[], ReShadeResponse>("run_uninstall_reshade");
const manageGameReShade = callable<[string, string, string], ReShadeResponse>("manage_game_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const listInstalledGames = callable<[], GameListResponse>("list_installed_games");
const logError = callable<[string], void>("log_error");

// VkBasalt callables
const checkVkBasaltPath = callable<[], PathCheckResponse>("check_vkbasalt_path");
const runInstallVkBasalt = callable<[], ReShadeResponse>("run_install_vkbasalt");
const runUninstallVkBasalt = callable<[], ReShadeResponse>("run_uninstall_vkbasalt");

function ReShadeInstallerSection() {
  const [installing, setInstalling] = useState<boolean>(false);
  const [uninstalling, setUninstalling] = useState<boolean>(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);
  const [isAddon, setIsAddon] = useState<boolean>(false);
  const [addonEnabled, setAddonEnabled] = useState<boolean>(false);
  const [initialLoad, setInitialLoad] = useState<boolean>(true);
  const [showingAddonDialog, setShowingAddonDialog] = useState<boolean>(false);
  const [pendingAddonState, setPendingAddonState] = useState<boolean>(false);

  useEffect(() => {
    const checkPath = async () => {
      try {
        const result = await checkReShadePath();
        setPathExists(result.exists);
        setIsAddon(result.is_addon);

        if (initialLoad) {
          setAddonEnabled(result.is_addon);
          setInitialLoad(false);
        }
      } catch (e) {
        await logError(`useEffect -> checkPath: ${String(e)}`);
      }
    };
    checkPath();
    const intervalId = setInterval(checkPath, 3000);
    return () => clearInterval(intervalId);
  }, [initialLoad]);

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
      const result = await runInstallReShade(addonEnabled);
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
      setAddonEnabled(false);
    } catch (e) {
      setUninstallResult({ status: "error", message: String(e) });
      await logError(`Uninstall error: ${String(e)}`);
    } finally {
      setUninstalling(false);
    }
  };

  const handleAddonToggle = () => {
    if (!addonEnabled) {
      setShowingAddonDialog(true);
      setPendingAddonState(true);
      showModal(
        <ConfirmModal
          strTitle="Enable ReShade Addon Support?"
          strDescription={
            "Using ReShade with addon support is generally not recommended when playing online multiplayer games with anti-cheat systems, as the addon functionality can trigger anti-cheat detection due to its potential for modification beyond just visual post-processing, which could be interpreted as cheating; most anti-cheat systems only whitelist the basic ReShade functionality with limited addons support."
          }
          strOKButtonText="Enable Anyway"
          strCancelButtonText="Cancel"
          onOK={() => {
            setAddonEnabled(true);
            setShowingAddonDialog(false);
            setPendingAddonState(false);
          }}
          onCancel={() => {
            setShowingAddonDialog(false);
            setPendingAddonState(false);
          }}
        />
      );
    } else {
      setAddonEnabled(false);
    }
  };

  return (
    <PanelSection title="ReShade Management">
      {pathExists !== null && (
        <PanelSectionRow>
          <div style={{ color: pathExists ? "green" : "red" }}>
            {pathExists ? `🟢 ReShade Is Installed${isAddon ? " (with Addon Support)" : ""}` : "🔴 ReShade Not Installed"}
          </div>
        </PanelSectionRow>
      )}

      {pathExists === false && (
        <>
          <PanelSectionRow>
            <ToggleField
              label="Enable Addon Support"
              description="Install ReShade with addon support"
              checked={showingAddonDialog ? pendingAddonState : addonEnabled}
              onChange={handleAddonToggle}
              disabled={showingAddonDialog}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={handleInstallClick} disabled={installing}>
              {installing ? "Installing..." : `🔧 Install ReShade${addonEnabled ? " with Addon Support" : ""}`}
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}

      {pathExists === true && (
        <>
          {isAddon !== addonEnabled && (
            <PanelSectionRow>
              <div style={{
                padding: '12px',
                marginBottom: '12px',
                backgroundColor: 'var(--decky-warning)',
                borderRadius: '4px',
                color: 'white'
              }}>
                ⚠️ {addonEnabled ? "Addon support requires reinstallation" : "Switching to non-addon version requires reinstallation"}
              </div>
            </PanelSectionRow>
          )}
          <PanelSectionRow>
            <ToggleField
              label="Enable Addon Support"
              description="Changes require reinstallation"
              checked={showingAddonDialog ? pendingAddonState : addonEnabled}
              onChange={handleAddonToggle}
              disabled={showingAddonDialog}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={handleUninstallClick} disabled={uninstalling}>
              {uninstalling ? "Uninstalling..." : "🗑️ Uninstall ReShade"}
            </ButtonItem>
          </PanelSectionRow>
        </>
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

function VkBasaltInstallerSection() {
  const [installing, setInstalling] = useState<boolean>(false);
  const [uninstalling, setUninstalling] = useState<boolean>(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);

  useEffect(() => {
    const checkPath = async () => {
      try {
        const result = await checkVkBasaltPath();
        setPathExists(result.exists);
      } catch (e) {
        await logError(`VkBasalt useEffect -> checkPath: ${String(e)}`);
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
      const result = await runInstallVkBasalt();
      setInstallResult(result);
    } catch (e) {
      setInstallResult({ status: "error", message: String(e) });
      await logError(`VkBasalt Install error: ${String(e)}`);
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstallClick = async () => {
    try {
      setUninstalling(true);
      const result = await runUninstallVkBasalt();
      setUninstallResult(result);
    } catch (e) {
      setUninstallResult({ status: "error", message: String(e) });
      await logError(`VkBasalt Uninstall error: ${String(e)}`);
    } finally {
      setUninstalling(false);
    }
  };

  return (
    <PanelSection title="VkBasalt Management">
      {pathExists !== null && (
        <PanelSectionRow>
          <div style={{ color: pathExists ? "green" : "red" }}>
            {pathExists ? "🟢 VkBasalt Is Installed" : "🔴 VkBasalt Not Installed"}
          </div>
        </PanelSectionRow>
      )}

      {pathExists === false && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleInstallClick} disabled={installing}>
            {installing ? "Installing..." : "🔧 Install VkBasalt"}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {pathExists === true && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleUninstallClick} disabled={uninstalling}>
            {uninstalling ? "Uninstalling..." : "🗑️ Uninstall VkBasalt"}
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
              "✅ VkBasalt installed successfully!" :
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
              "✅ VkBasalt uninstalled successfully!" :
              `❌ Error: ${uninstallResult.message || "Uninstallation failed"}`}
          </div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
}

function InstalledGamesSection() {
  const [games, setGames] = useState<{ appid: number; name: string }[]>([]);
  const [selectedGame, setSelectedGame] = useState<{ appid: number; name: string } | null>(null);
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

  const handleVkBasaltPatch = async () => {
    if (!selectedGame) return;

    try {
      const vkbasaltCheck = await checkVkBasaltPath();
      if (!vkbasaltCheck.exists) {
        setResult("Please install VkBasalt first before patching games.");
        return;
      }

      await SteamClient.Apps.SetAppLaunchOptions(selectedGame.appid, 'ENABLE_VKBASALT=1 %command%');
      setResult(`VkBasalt enabled for ${selectedGame.name}.\nPress Home key in-game to toggle effects.\nPlease follow the guide on GitHub or available YouTube videos for configuring VkBasalt settings and effects.`);

    } catch (error) {
      await logError(`handleVkBasaltPatch: ${String(error)}`);
      setResult(`Error enabling VkBasalt: ${String(error)}`);
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
        setResult(`ReShade and VkBasalt removed successfully from ${selectedGame.name}`);
      } else {
        setResult(`Failed to remove ReShade: ${response.message || 'Unknown error'}`);
      }
    } catch (error) {
      await logError(`handleUnpatchClick: ${String(error)}`);
      setResult(`Error removing ReShade: ${String(error)}`);
    }
  };

  return (
    <PanelSection title="Install Patch in Game">
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
              onClick={handleVkBasaltPatch}
            >
              🎨 Enable VkBasalt
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleUnpatchClick}
            >
              🗑️ Remove ReShade/VkBasalt
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
}

export default definePlugin(() => ({
  name: "LetMeReShade Plugin",
  titleView: <div>LetMeReShade Manager</div>,
  alwaysRender: true,
  content: (
    <>
      <ReShadeInstallerSection />
      <VkBasaltInstallerSection />
      <InstalledGamesSection />
      <NonSteamManager />
      <ManualPatchSection />
    </>
  ),
  icon: <IoMdColorPalette />,
  onDismount() {
    console.log("Plugin unmounted");
  },
}));