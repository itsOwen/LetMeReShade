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
import ShaderSelectionModal from "./ShaderSelectionModal";

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

interface DeckModelResponse {
  status: string;
  model: string;
  is_oled: boolean;
  message?: string;
}

const runInstallReShade = callable<[boolean, string, boolean, string[]], InstallResult>("run_install_reshade");
const runUninstallReShade = callable<[], InstallResult>("run_uninstall_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const detectSteamDeckModel = callable<[], DeckModelResponse>("detect_steam_deck_model");
const logError = callable<[string], void>("log_error");

// Shader preferences callables
const saveShaderPreferences = callable<[string[]], InstallResult>("save_shader_preferences");
const loadShaderPreferences = callable<[], any>("load_shader_preferences");
const hasShaderPreferences = callable<[], any>("has_shader_preferences");

// AutoHDR preferences callables
const saveAutoHdrPreference = callable<[boolean], InstallResult>("save_autohdr_preference");
const loadAutoHdrPreference = callable<[], any>("load_autohdr_preference");

// Configuration tracking callables
const loadInstalledConfiguration = callable<[], any>("load_installed_configuration");

function ReShadeInstallerSection() {
  const [installing, setInstalling] = useState<boolean>(false);
  const [uninstalling, setUninstalling] = useState<boolean>(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [uninstallResult, setUninstallResult] = useState<InstallResult | null>(null);
  const [pathExists, setPathExists] = useState<boolean | null>(null);
  const [addonEnabled, setAddonEnabled] = useState<boolean>(false);
  const [autoHdrEnabled, setAutoHdrEnabled] = useState<boolean>(false);
  const [selectedVersion, setSelectedVersion] = useState<VersionOption | null>(null);
  const [currentVersionInfo, setCurrentVersionInfo] = useState<{ version: string; addon: boolean } | null>(null);
  const [initialLoad, setInitialLoad] = useState<boolean>(true);
  const [showingAddonDialog, setShowingAddonDialog] = useState<boolean>(false);
  const [pendingAddonState, setPendingAddonState] = useState<boolean>(false);
  const [deckModel, setDeckModel] = useState<DeckModelResponse | null>(null);
  const [modelLoading, setModelLoading] = useState<boolean>(true);
  const [installedConfig, setInstalledConfig] = useState<any>(null);
  const [configChanged, setConfigChanged] = useState<boolean>(false);
  
  // State for shader preferences
  const [hasPreferences, setHasPreferences] = useState<boolean>(false);
  const [preferencesInfo, setPreferencesInfo] = useState<any>(null);

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
    const detectDeckModel = async () => {
      try {
        setModelLoading(true);
        const result = await detectSteamDeckModel();
        setDeckModel(result);
      } catch (e) {
        await logError(`Steam Deck model detection error: ${String(e)}`);
      } finally {
        setModelLoading(false);
      }
    };
    detectDeckModel();
  }, []);

  // Check for existing preferences
  useEffect(() => {
    const checkPreferences = async () => {
      try {
        const result = await hasShaderPreferences();
        if (result.status === "success") {
          setHasPreferences(result.has_preferences);
          setPreferencesInfo(result);
        }
      } catch (e) {
        await logError(`Error checking shader preferences: ${String(e)}`);
      }
    };
    
    checkPreferences();
  }, []);

  // Load AutoHDR preference on component mount
  useEffect(() => {
    const loadAutoHdrPref = async () => {
      try {
        const result = await loadAutoHdrPreference();
        if (result.status === "success") {
          setAutoHdrEnabled(result.autohdr_enabled);
        }
      } catch (e) {
        await logError(`Error loading AutoHDR preference: ${String(e)}`);
      }
    };
    
    loadAutoHdrPref();
  }, []);

  // Load installed configuration
  useEffect(() => {
    const loadInstalledConfig = async () => {
      try {
        const result = await loadInstalledConfiguration();
        if (result.status === "success" && result.config) {
          setInstalledConfig(result.config);
        }
      } catch (e) {
        await logError(`Error loading installed configuration: ${String(e)}`);
      }
    };
    
    loadInstalledConfig();
  }, [pathExists]);

  // Detect configuration changes
  useEffect(() => {
    if (!installedConfig || !pathExists) {
      setConfigChanged(false);
      return;
    }

    const currentConfig = {
      with_addon: addonEnabled,
      version: selectedVersion?.value || 'latest',
      with_autohdr: autoHdrEnabled,
      selected_shaders: [] // We'll need to load current shader preferences
    };

    // Load current shader preferences for comparison
    const checkConfigChange = async () => {
      try {
        const shaderPrefs = await loadShaderPreferences();
        if (shaderPrefs.status === "success" && shaderPrefs.selected_shaders) {
          currentConfig.selected_shaders = shaderPrefs.selected_shaders;
        }

        const hasChanged = 
          currentConfig.with_addon !== installedConfig.with_addon ||
          currentConfig.version !== installedConfig.version ||
          currentConfig.with_autohdr !== installedConfig.with_autohdr ||
          JSON.stringify(currentConfig.selected_shaders.sort()) !== JSON.stringify((installedConfig.selected_shaders || []).sort());

        setConfigChanged(hasChanged);
      } catch (e) {
        await logError(`Error checking config changes: ${String(e)}`);
      }
    };

    checkConfigChange();
  }, [addonEnabled, selectedVersion, autoHdrEnabled, installedConfig, pathExists]);

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

    // Always check for current preferences first
    try {
      const prefResult = await loadShaderPreferences();
      
      if (prefResult.status === "success" && prefResult.selected_shaders && prefResult.selected_shaders.length > 0) {
        // Use saved preferences directly - no popup
        setInstalling(true);
        const result = await runInstallReShade(
          addonEnabled, 
          selectedVersion.value, 
          autoHdrEnabled, 
          prefResult.selected_shaders
        );
        setInstallResult(result);
        
        // If installation was successful, reload installed config
        if (result.status === "success") {
          const configResult = await loadInstalledConfiguration();
          if (configResult.status === "success" && configResult.config) {
            setInstalledConfig(configResult.config);
          }
          setConfigChanged(false);
        }
        setInstalling(false);
      } else {
        // No preferences saved, show selection modal
        const modalResult = showModal(
          <ShaderSelectionModal
            onConfirm={async (selectedShaders: string[]) => {
              try {
                setInstalling(true);
                const result = await runInstallReShade(
                  addonEnabled, 
                  selectedVersion.value, 
                  autoHdrEnabled, 
                  selectedShaders
                );
                setInstallResult(result);
                
                // If installation was successful, reload installed config
                if (result.status === "success") {
                  const configResult = await loadInstalledConfiguration();
                  if (configResult.status === "success" && configResult.config) {
                    setInstalledConfig(configResult.config);
                  }
                  setConfigChanged(false);
                }
              } catch (e) {
                setInstallResult({ status: "error", message: String(e) });
                await logError(`Install error: ${String(e)}`);
              } finally {
                setInstalling(false);
              }
            }}
            onCancel={() => {
              // Cancel handler - modal will be closed via closeModal
            }}
            addonEnabled={addonEnabled}
            autoHdrEnabled={autoHdrEnabled}
            selectedVersion={selectedVersion.value}
            closeModal={() => modalResult.Close()}
          />
        );
      }
    } catch (e) {
      setInstallResult({ status: "error", message: String(e) });
      await logError(`Install error: ${String(e)}`);
    }
  };

  const handleUninstallClick = async () => {
    try {
      setUninstalling(true);
      const result = await runUninstallReShade();
      setUninstallResult(result);
      setAddonEnabled(false);
      setAutoHdrEnabled(false);
      
      // Clear installed configuration
      if (result.status === "success") {
        setInstalledConfig(null);
        setConfigChanged(false);
      }
    } catch (e) {
      setUninstallResult({ status: "error", message: String(e) });
      await logError(`Uninstall error: ${String(e)}`);
    } finally {
      setUninstalling(false);
    }
  };

  const handleManageShaders = async () => {
    // Load current preferences if they exist
    let currentPreferences: string[] = [];
    
    try {
      const loadResult = await loadShaderPreferences();
      if (loadResult.status === "success" && loadResult.selected_shaders) {
        currentPreferences = loadResult.selected_shaders;
      }
    } catch (e) {
      await logError(`Error loading preferences: ${String(e)}`);
    }

    const modalResult = showModal(
      <ShaderSelectionModal
        onConfirm={async (selectedShaders: string[]) => {
          try {
            const result = await saveShaderPreferences(selectedShaders);
            if (result.status === "success") {
              // Update the state variables immediately
              setHasPreferences(true);
              setPreferencesInfo({
                has_preferences: true,
                shader_count: selectedShaders.length,
                last_updated: Date.now()
              });
              setInstallResult({ 
                status: "success", 
                message: `Shader preferences saved! ${selectedShaders.length} packages selected.` 
              });
            } else {
              setInstallResult({ 
                status: "error", 
                message: result.message || "Failed to save preferences" 
              });
            }
          } catch (e) {
            setInstallResult({ status: "error", message: String(e) });
            await logError(`Save preferences error: ${String(e)}`);
          }
        }}
        onCancel={() => {
          // Cancel handler - modal will be closed via closeModal
        }}
        addonEnabled={addonEnabled}
        autoHdrEnabled={autoHdrEnabled}
        selectedVersion={selectedVersion?.value || 'latest'}
        mode="manage"
        initialSelectedShaders={currentPreferences}
        closeModal={() => modalResult.Close()}
      />
    );
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
      // Disable AutoHDR if addon support is disabled
      setAutoHdrEnabled(false);
    }
  };

  const handleAutoHdrToggle = async () => {
    if (!autoHdrEnabled) {
      // Create warning message based on detected model
      let warningTitle = "Enable AutoHDR Components?";
      let warningMessage = "AutoHDR components will be installed with ReShade. ";

      if (deckModel) {
        if (!deckModel.is_oled) {
          warningTitle = "LCD Model Warning";
          warningMessage += `⚠️ You have a Steam Deck ${deckModel.model}. AutoHDR is optimized for OLED displays and may not work properly or cause visual issues on LCD models. `;
        } else {
          warningMessage += `✅ Detected Steam Deck ${deckModel.model} - AutoHDR is optimized for your display. `;
        }
      } else if (!modelLoading) {
        warningMessage += "⚠️ Could not detect Steam Deck model. AutoHDR is optimized for OLED displays. ";
      }

      warningMessage += "AutoHDR only works with DirectX 10/11/12 games. Continue?";

      showModal(
        <ConfirmModal
          strTitle={warningTitle}
          strDescription={warningMessage}
          strOKButtonText="Enable AutoHDR"
          strCancelButtonText="Cancel"
          onOK={async () => {
            setAutoHdrEnabled(true);
            // Save preference
            try {
              await saveAutoHdrPreference(true);
            } catch (e) {
              await logError(`Error saving AutoHDR preference: ${String(e)}`);
            }
          }}
        />
      );
    } else {
      setAutoHdrEnabled(false);
      // Save preference
      try {
        await saveAutoHdrPreference(false);
      } catch (e) {
        await logError(`Error saving AutoHDR preference: ${String(e)}`);
      }
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
    if (autoHdrEnabled) {
      text += " + AutoHDR";
    }
    
    // Add indication if using saved preferences
    if (hasPreferences && preferencesInfo && preferencesInfo.shader_count > 0) {
      text += ` (${preferencesInfo.shader_count} shader packages)`;
    }
    
    return text;
  };

  const renderDeckModelInfo = () => {
    if (modelLoading) return null;

    if (deckModel && deckModel.status === "success") {
      // Handle the "Not Steam Deck" case properly
      if (deckModel.model === "Not Steam Deck") {
        return (
          <PanelSectionRow>
            <div style={{
              fontSize: '0.9em',
              color: "gray",
              marginBottom: '8px'
            }}>
              🔍 Non Steam Deck Device detected
            </div>
          </PanelSectionRow>
        );
      }

      // Handle normal Steam Deck cases
      const isOptimal = deckModel.is_oled;
      const statusColor = isOptimal ? "green" : "orange";
      const statusIcon = isOptimal ? "🟢" : "🟡";

      // Construct proper display text
      let displayText = "";
      if (deckModel.model === "OLED" || deckModel.model === "LCD") {
        displayText = `${statusIcon} Steam Deck ${deckModel.model} detected`;
      } else {
        // Fallback for any other model names
        displayText = `${statusIcon} ${deckModel.model} detected`;
      }

      return (
        <PanelSectionRow>
          <div style={{
            fontSize: '0.9em',
            color: statusColor,
            marginBottom: '8px'
          }}>
            {displayText}
            {!isOptimal && deckModel.model !== "Not Steam Deck" && (
              <div style={{ fontSize: '0.8em', opacity: 0.8, marginTop: '2px' }}>
                AutoHDR optimized for OLED
              </div>
            )}
          </div>
        </PanelSectionRow>
      );
    }

    return null;
  };

  const renderPreferencesInfo = () => {
    if (!hasPreferences || !preferencesInfo) return null;
    
    return (
      <PanelSectionRow>
        <div style={{
          padding: '8px',
          marginBottom: '8px',
          backgroundColor: 'rgba(0, 255, 0, 0.1)',
          borderRadius: '4px',
          border: '1px solid rgba(0, 255, 0, 0.3)',
          fontSize: '0.9em'
        }}>
          📋 Shader preferences saved ({preferencesInfo.shader_count} packages)
          <div style={{ fontSize: '0.8em', opacity: 0.8, marginTop: '2px' }}>
            Will be used automatically for installations
          </div>
        </div>
      </PanelSectionRow>
    );
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

      {addonEnabled && renderDeckModelInfo()}

      {/* Only show Select Packages to Install button when ReShade is not installed */}
      {pathExists === false && (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={handleManageShaders}
          >
            📦 Select Packages to Install
          </ButtonItem>
        </PanelSectionRow>
      )}

      {/* Show preferences info if they exist */}
      {renderPreferencesInfo()}

      {/* Version selection dropdown - always show */}
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

      {/* Addon support toggle - always show */}
      <PanelSectionRow>
        <ToggleField
          label="Enable Addon Support"
          description={pathExists ? "Changes require reinstallation" : "Install ReShade with addon support"}
          checked={showingAddonDialog ? pendingAddonState : addonEnabled}
          onChange={handleAddonToggle}
          disabled={showingAddonDialog}
        />
      </PanelSectionRow>

      {/* AutoHDR toggle - show when addon is enabled */}
      {addonEnabled && (
        <PanelSectionRow>
          <ToggleField
            label="Include AutoHDR Components"
            description="For Steam Deck OLED HDR gaming (DX10/11/12 only)"
            checked={autoHdrEnabled}
            onChange={handleAutoHdrToggle}
          />
        </PanelSectionRow>
      )}

      {/* Configuration change warning */}
      {pathExists === true && configChanged && (
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginBottom: '12px',
            backgroundColor: '#ffa726',
            borderRadius: '4px',
            color: 'white'
          }}>
            ⚠️ Configuration changed - Reinstallation required to apply changes
          </div>
        </PanelSectionRow>
      )}

      {/* Install button - show when not installed OR when config changed */}
      {selectedVersion && (pathExists === false || configChanged) && (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={handleInstallClick}
            disabled={installing}
          >
            {getInstallButtonText()}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {/* Uninstall button - only show when ReShade is installed */}
      {pathExists === true && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleUninstallClick} disabled={uninstalling}>
            {uninstalling ? "Uninstalling..." : "🗑️ Uninstall ReShade"}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {/* Install result */}
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
              `✅ ${installResult.output || installResult.message || "Operation completed successfully!"}` :
              `❌ Error: ${installResult.message || "Operation failed"}`}
          </div>
        </PanelSectionRow>
      )}

      {/* Uninstall result */}
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
          {addonEnabled && autoHdrEnabled && (
            <div style={{ fontSize: '0.9em', marginTop: '4px', opacity: 0.8 }}>
              AutoHDR works with DirectX 10/11/12 games only.
            </div>
          )}
        </div>
      </PanelSectionRow>
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
      <SteamGamesSection />
      <HeroicGamesSection />
    </>
  ),
  icon: <IoMdColorPalette />,
  onDismount() {
    console.log("Plugin unmounted");
  },
}));