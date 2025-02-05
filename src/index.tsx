import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  ToggleField,
  Field,
} from "@decky/ui";
import { definePlugin, callable } from "@decky/api";
import { VscSymbolColor } from "react-icons/vsc";

interface GameInfo {
  appid: string;
  name: string;
}

interface AdvancedSettings {
  vulkanSupport: boolean;
  mergeShaders: boolean;
  deleteFiles: boolean;
}

interface InstallationResult {
  status: string;
  message?: string;
  output?: string;
  launchOptions?: string;
}

const runInstallReShade = callable<[], { status: string; message?: string; output?: string }>("run_install_reshade");
const runUninstallReShade = callable<[], { status: string; message?: string; output?: string }>("run_uninstall_reshade");
const manageGameReShade = callable<[string, string, string, string?], { status: string; message?: string; output?: string }>("manage_game_reshade");
const checkReShadePath = callable<[], { exists: boolean }>("check_reshade_path");
const listInstalledGames = callable<[], { status: string; games: GameInfo[] }>("list_installed_games");
const logError = callable<[string], void>("log_error");

function StatusMessage({ type, message }: { type: "success" | "error"; message: string }) {
  return (
    <div style={{ 
      padding: '12px',
      marginTop: '8px',
      backgroundColor: type === "success" ? "rgba(0,255,0,0.1)" : "rgba(255,0,0,0.1)",
      borderRadius: '4px',
      fontSize: '14px'
    }}>
      {message}
    </div>
  );
}

function AdvancedSettingsSection({ settings, onSettingsChange }: { 
  settings: AdvancedSettings; 
  onSettingsChange: (settings: AdvancedSettings) => void 
}) {
  return (
    <PanelSection title="Advanced Settings">
      <PanelSectionRow>
        <ToggleField
          label="Vulkan Support"
          description="Enable experimental Vulkan support"
          checked={settings.vulkanSupport}
          onChange={(checked) => onSettingsChange({ ...settings, vulkanSupport: checked })}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Merge Shaders"
          description="Combine shaders from all repositories"
          checked={settings.mergeShaders}
          onChange={(checked) => onSettingsChange({ ...settings, mergeShaders: checked })}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Delete Files on Uninstall"
          description="Remove ReShade files when uninstalling"
          checked={settings.deleteFiles}
          onChange={(checked) => onSettingsChange({ ...settings, deleteFiles: checked })}
        />
      </PanelSectionRow>
    </PanelSection>
  );
}

function ReShadeInstallerSection() {
  const [installing, setInstalling] = useState(false);
  const [uninstalling, setUninstalling] = useState(false);
  const [installResult, setInstallResult] = useState<InstallationResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallationResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);
  const [advancedSettings, setAdvancedSettings] = useState<AdvancedSettings>({
    vulkanSupport: false,
    mergeShaders: true,
    deleteFiles: false
  });

  useEffect(() => {
    const checkPath = async () => {
      try {
        const result = await checkReShadePath();
        setPathExists(result.exists);
      } catch (e) {
        logError('useEffect -> checkPath: ' + String(e));
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
      logError("Starting ReShade installation...");
      const result = await runInstallReShade();
      logError(`Installation result: ${JSON.stringify(result)}`);
      setInstalling(false);
      setInstallResult(result);
    } catch (e) {
      logError('handleInstallClick error: ' + String(e));
      setInstalling(false);
      setInstallResult({ status: "error", message: String(e) });
    }
  };

  const handleUninstallClick = async () => {
    try {
      setUninstalling(true);
      logError("Starting ReShade uninstallation...");
      const result = await runUninstallReShade();
      logError(`Uninstallation result: ${JSON.stringify(result)}`);
      setUninstalling(false);
      setUninstallResult(result);
    } catch (e) {
      logError('handleUninstallClick error: ' + String(e));
      setUninstalling(false);
      setUninstallResult({ status: "error", message: String(e) });
    }
  };

  return (
    <>
      <PanelSection>
        {pathExists !== null && (
          <PanelSectionRow>
            <Field
              label="ReShade Status"
              bottomSeparator="none"
              icon={<div style={{ color: pathExists ? "green" : "red" }}>●</div>}
            >
              {pathExists ? "Installed" : "Not Installed"}
            </Field>
          </PanelSectionRow>
        )}
        
        {pathExists === false && (
          <PanelSectionRow>
            <ButtonItem 
              layout="below" 
              onClick={handleInstallClick} 
              disabled={installing}
            >
              {installing ? "Installing..." : "Install ReShade"}
            </ButtonItem>
          </PanelSectionRow>
        )}
        
        {pathExists === true && (
          <PanelSectionRow>
            <ButtonItem 
              layout="below" 
              onClick={handleUninstallClick} 
              disabled={uninstalling}
            >
              {uninstalling ? "Uninstalling..." : "Uninstall ReShade"}
            </ButtonItem>
          </PanelSectionRow>
        )}

        {installResult && (
          <PanelSectionRow>
            <StatusMessage 
              type={installResult.status === "success" ? "success" : "error"}
              message={installResult.output || installResult.message || installResult.status}
            />
          </PanelSectionRow>
        )}

        {uninstallResult && (
          <PanelSectionRow>
            <StatusMessage 
              type={uninstallResult.status === "success" ? "success" : "error"}
              message={uninstallResult.output || uninstallResult.message || uninstallResult.status}
            />
          </PanelSectionRow>
        )}
      </PanelSection>
      <AdvancedSettingsSection settings={advancedSettings} onSettingsChange={setAdvancedSettings} />
    </>
  );
}

function InstalledGamesSection() {
  const [games, setGames] = useState<GameInfo[]>([]);
  const [processingGames, setProcessingGames] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, { message: string; type: "success" | "error" }>>({});

  useEffect(() => {
    const fetchGames = async () => {
      try {
        logError("Fetching games list...");
        const response = await listInstalledGames();
        logError(`Games response: ${JSON.stringify(response)}`);
        if (response.status === "success") {
          const sortedGames = [...response.games]
            .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
            .filter(game => !game.name.includes("Runtime") && !game.name.includes("Proton"));
          setGames(sortedGames);
        }
      } catch (error) {
        logError("Error fetching games: " + String(error));
      }
    };
    fetchGames();
  }, []);

  const handlePatchClick = async (game: GameInfo) => {
    logError(`Installing ReShade for game: ${game.name} (AppID: ${game.appid})`);
    setProcessingGames(prev => ({ ...prev, [game.appid]: true }));
    
    try {
      const response = await manageGameReShade(game.appid, "install", "dxgi");
      logError(`Game manager response: ${JSON.stringify(response)}`);

      if (response.status === "success") {
        const launchOptionsMatch = response.output?.match(/Use this launch option: (.+)/);
        const launchOptions = launchOptionsMatch ? 
          launchOptionsMatch[1] : 
          'WINEDLLOVERRIDES="d3dcompiler_47=n;dxgi=n,b" %command%';
        
        const detectedApi = launchOptions.match(/;(\w+)=n,b/)?.pop() || 'dxgi';
        
        await SteamClient.Apps.SetAppLaunchOptions(parseInt(game.appid), launchOptions);
        
        setResults(prev => ({
          ...prev,
          [game.appid]: {
            type: "success",
            message: `ReShade installed successfully using ${detectedApi.toUpperCase()} API.
Press Home key in-game to open ReShade overlay.
Launch options set: ${launchOptions}`
          }
        }));
      } else {
        setResults(prev => ({
          ...prev,
          [game.appid]: {
            type: "error",
            message: `Installation failed: ${response.message || "Unknown error"}`
          }
        }));
      }
    } catch (error) {
      const errorMsg = String(error);
      logError(`Error during installation: ${errorMsg}`);
      setResults(prev => ({
        ...prev,
        [game.appid]: {
          type: "error",
          message: `Error: ${errorMsg}`
        }
      }));
    } finally {
      setProcessingGames(prev => ({ ...prev, [game.appid]: false }));
    }
  };

  const handleUnpatchClick = async (game: GameInfo) => {
    logError(`Removing ReShade from game: ${game.name} (AppID: ${game.appid})`);
    setProcessingGames(prev => ({ ...prev, [game.appid]: true }));
    
    try {
      const response = await manageGameReShade(game.appid, "uninstall", "dxgi");
      logError(`Game manager response: ${JSON.stringify(response)}`);

      if (response.status === "success") {
        await SteamClient.Apps.SetAppLaunchOptions(parseInt(game.appid), '');
        setResults(prev => ({
          ...prev,
          [game.appid]: {
            type: "success",
            message: "ReShade removed successfully"
          }
        }));
      } else {
        setResults(prev => ({
          ...prev,
          [game.appid]: {
            type: "error",
            message: `Removal failed: ${response.message || "Unknown error"}`
          }
        }));
      }
    } catch (error) {
      const errorMsg = String(error);
      logError(`Error during removal: ${errorMsg}`);
      setResults(prev => ({
        ...prev,
        [game.appid]: {
          type: "error",
          message: `Error: ${errorMsg}`
        }
      }));
    } finally {
      setProcessingGames(prev => ({ ...prev, [game.appid]: false }));
    }
  };

  return (
    <PanelSection title="Games">
      {games.map(game => (
        <PanelSectionRow key={game.appid}>
          <div style={{ 
            backgroundColor: 'var(--main-bg)',
            padding: '12px',
            borderRadius: '8px',
            width: '100%'
          }}>
            <div style={{ 
              fontWeight: 'bold', 
              fontSize: '1.1em',
              marginBottom: '12px'
            }}>
              {game.name}
            </div>
            <div style={{
              display: 'flex',
              gap: '8px',
              marginBottom: results[game.appid] ? '8px' : '0'
            }}>
              <ButtonItem 
                layout="below" 
                onClick={() => handlePatchClick(game)}
                disabled={processingGames[game.appid]}
              >
                {processingGames[game.appid] ? "Installing..." : "Install ReShade"}
              </ButtonItem>
              <ButtonItem 
                layout="below" 
                onClick={() => handleUnpatchClick(game)}
                disabled={processingGames[game.appid]}
              >
                {processingGames[game.appid] ? "Removing..." : "Remove ReShade"}
              </ButtonItem>
            </div>
            {results[game.appid] && (
              <StatusMessage 
                type={results[game.appid].type}
                message={results[game.appid].message}
              />
            )}
          </div>
        </PanelSectionRow>
      ))}
    </PanelSection>
  );
}

export default definePlugin(() => ({
  name: "LetMeReShade Plugin",
  titleView: (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <VscSymbolColor />
      <span>LetMeReShade Manager</span>
    </div>
  ),
  content: (
    <>
      <ReShadeInstallerSection />
      <InstalledGamesSection />
    </>
  ),
  icon: <VscSymbolColor />,
}));