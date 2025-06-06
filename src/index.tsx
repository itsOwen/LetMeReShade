import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  ToggleField,
  DropdownItem,
  ConfirmModal,
  showModal
} from "@decky/ui";
import { definePlugin, callable } from "@decky/api";
import { IoMdColorPalette } from "react-icons/io";
import HeroicGamesSection from "./HeroicGamesSection";
import SteamGamesSection from "./SteamGamesSection";

interface InstallResult {
  status: string;
  message?: string;
  output?: string;
}

interface PathCheckResponse {
  exists: boolean;
  is_addon: boolean;
  version_info?: {
    version: string;
    addon: boolean;
  };
}

interface VersionOption {
  label: string;
  value: string;
}

const runInstallReShade = callable<[boolean, string], InstallResult>("run_install_reshade");
const runUninstallReShade = callable<[], InstallResult>("run_uninstall_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const logError = callable<[string], void>("log_error");

// VkBasalt callables
const checkVkBasaltPath = callable<[], PathCheckResponse>("check_vkbasalt_path");
const runInstallVkBasalt = callable<[], InstallResult>("run_install_vkbasalt");
const runUninstallVkBasalt = callable<[], InstallResult>("run_uninstall_vkbasalt");

function ReShadeInstallerSection() {
  const [installing, setInstalling] = useState<boolean>(false);
  const [uninstalling, setUninstalling] = useState<boolean>(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);
  const [addonEnabled, setAddonEnabled] = useState<boolean>(false);
  const [selectedVersion, setSelectedVersion] = useState<VersionOption | null>(null);
  const [currentVersionInfo, setCurrentVersionInfo] = useState<{ version: string; addon: boolean } | null>(null);
  const [initialLoad, setInitialLoad] = useState<boolean>(true);
  const [showingAddonDialog, setShowingAddonDialog] = useState<boolean>(false);
  const [pendingAddonState, setPendingAddonState] = useState<boolean>(false);

  const versionOptions: VersionOption[] = [
    { label: 'ReShade Latest', value: 'latest' },
    { label: 'ReShade Last Version', value: 'last' }
  ];

  useEffect(() => {
    const checkPath = async () => {
      try {
        const result = await checkReShadePath();
        setPathExists(result.exists);
        
        if (result.version_info) {
          setCurrentVersionInfo(result.version_info);
        }

        if (initialLoad) {
          setAddonEnabled(result.is_addon);
          // Set version dropdown to match currently installed version
          if (!selectedVersion) {
            if (result.version_info && result.version_info.version) {
              // Find the matching version option based on installed version
              const installedVersion = result.version_info.version;
              const matchingOption = versionOptions.find(v => v.value === installedVersion);
              setSelectedVersion(matchingOption || versionOptions[0]); // Default to latest if not found
            } else {
              // No version info available, default to latest
              setSelectedVersion(versionOptions[0]);
            }
          }
          setInitialLoad(false);
        }
      } catch (e) {
        await logError(`useEffect -> checkPath: ${String(e)}`);
      }
    };
    checkPath();
    const intervalId = setInterval(checkPath, 3000);
    return () => clearInterval(intervalId);
  }, [initialLoad, selectedVersion]);

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
    if (!selectedVersion) {
      setInstallResult({ status: "error", message: "Please select a ReShade version" });
      return;
    }

    try {
      setInstalling(true);
      const result = await runInstallReShade(addonEnabled, selectedVersion.value);
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

  const getInstallButtonText = () => {
    if (installing) return "Installing...";
    
    let text = "🔧 Install";
    if (selectedVersion) {
      text += ` ${selectedVersion.label}`;
    }
    if (addonEnabled) {
      text += " with Addon Support";
    }
    return text;
  };

  const getVersionMismatchWarning = () => {
    if (!pathExists || !currentVersionInfo || !selectedVersion) return null;
    
    const currentVersion = currentVersionInfo.version;
    const selectedVersionValue = selectedVersion.value;
    const currentAddon = currentVersionInfo.addon;
    
    if (currentVersion !== selectedVersionValue || currentAddon !== addonEnabled) {
      return (
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginBottom: '12px',
            backgroundColor: 'var(--decky-warning)',
            borderRadius: '4px',
            color: 'white'
          }}>
            ⚠️ Configuration change detected - reinstallation required
          </div>
        </PanelSectionRow>
      );
    }
    
    return null;
  };

  return (
    <PanelSection title="ReShade Management">
      {pathExists !== null && (
        <PanelSectionRow>
          <div style={{ color: pathExists ? "green" : "red" }}>
            {pathExists ? (
              <>
                🟢 ReShade Is Installed
                {currentVersionInfo && (
                  <div style={{ fontSize: '0.9em', opacity: 0.8, marginTop: '4px' }}>
                    Version: {currentVersionInfo.version.charAt(0).toUpperCase() + currentVersionInfo.version.slice(1)}
                    {currentVersionInfo.addon ? " (with Addon Support)" : ""}
                  </div>
                )}
              </>
            ) : (
              "🔴 ReShade Not Installed"
            )}
          </div>
        </PanelSectionRow>
      )}

      {pathExists === false && (
        <>
          <PanelSectionRow>
            <DropdownItem
              rgOptions={versionOptions.map(version => ({
                data: version.value,
                label: version.label
              }))}
              selectedOption={selectedVersion ? selectedVersion.value : undefined}
              onChange={(option) => {
                const selected = versionOptions.find(v => v.value === option.data);
                if (selected) {
                  setSelectedVersion(selected);
                }
              }}
              strDefaultLabel="Select ReShade version..."
            />
          </PanelSectionRow>
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
            <ButtonItem 
              layout="below" 
              onClick={handleInstallClick} 
              disabled={installing || !selectedVersion}
            >
              {getInstallButtonText()}
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}

      {pathExists === true && (
        <>
          {getVersionMismatchWarning()}
          <PanelSectionRow>
            <DropdownItem
              rgOptions={versionOptions.map(version => ({
                data: version.value,
                label: version.label
              }))}
              selectedOption={selectedVersion ? selectedVersion.value : undefined}
              onChange={(option) => {
                const selected = versionOptions.find(v => v.value === option.data);
                if (selected) {
                  setSelectedVersion(selected);
                }
              }}
              strDefaultLabel="Select ReShade version..."
            />
          </PanelSectionRow>
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
            <ButtonItem 
              layout="below" 
              onClick={handleInstallClick} 
              disabled={installing || !selectedVersion}
            >
              {getInstallButtonText()}
            </ButtonItem>
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
              `✅ ${installResult.output || "ReShade installed successfully!"}` :
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

export default definePlugin(() => ({
  name: "LetMeReShade Plugin",
  titleView: <div>LetMeReShade Manager</div>,
  alwaysRender: true,
  content: (
    <>
      <ReShadeInstallerSection />
      <VkBasaltInstallerSection />
      <SteamGamesSection />
      <HeroicGamesSection />
    </>
  ),
  icon: <IoMdColorPalette />,
  onDismount() {
    console.log("Plugin unmounted");
  },
}));