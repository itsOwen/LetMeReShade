// src/SteamGamesSection.tsx
import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  DropdownItem,
  showModal,
  ConfirmModal
} from "@decky/ui";
import { callable } from "@decky/api";

// Import the callable functions
const manageGameReShade = callable<[string, string, string], ReShadeResponse>("manage_game_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const checkVkBasaltPath = callable<[], PathCheckResponse>("check_vkbasalt_path");
const listInstalledGames = callable<[], GameListResponse>("list_installed_games");
const detectLinuxGame = callable<[string], LinuxGameDetectionResponse>("detect_linux_game");
const findGameExecutablePath = callable<[string], ExecutableDetectionResponse>("find_game_executable_path");
const logError = callable<[string], void>("log_error");

interface GameInfo {
  appid: string;
  name: string;
}

interface DllOverride {
  label: string;
  value: string;
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
  message?: string;
}

interface LinuxGameDetectionResponse {
  status: string;
  is_linux_game: boolean;
  confidence: string;
  reasons: string[];
  details?: any;
  message?: string;
}

interface ExecutableDetectionResponse {
  status: string;
  method?: string;
  executable_path?: string;
  all_executables?: any[];
  confidence?: string;
  message?: string;
}

const SteamGamesSection = () => {
  const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
  const [selectedDll, setSelectedDll] = useState<DllOverride | null>(null);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [result, setResult] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [linuxGameDetection, setLinuxGameDetection] = useState<LinuxGameDetectionResponse | null>(null);
  const [checkingLinuxGame, setCheckingLinuxGame] = useState<boolean>(false);
  const [executableDetection, setExecutableDetection] = useState<ExecutableDetectionResponse | null>(null);
  const [checkingExecutable, setCheckingExecutable] = useState<boolean>(false);

  const dllOverrides: DllOverride[] = [
    { label: 'Automatic (Enhanced Detection)', value: 'auto' },
    { label: 'DXGI (DirectX 10/11/12)', value: 'dxgi' },
    { label: 'D3D9 (DirectX 9)', value: 'd3d9' },
    { label: 'D3D8 (DirectX 8)', value: 'd3d8' },
    { label: 'D3D11 (DirectX 11)', value: 'd3d11' },
    { label: 'DDraw (DirectDraw)', value: 'ddraw' },
    { label: 'DInput8 (DirectInput)', value: 'dinput8' },
    { label: 'OpenGL32 (OpenGL)', value: 'opengl32' }
  ];

  useEffect(() => {
    const fetchGames = async () => {
      try {
        setLoading(true);
        const response = await listInstalledGames();
        if (response.status === "success") {
          const sortedGames = response.games
            .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
          setGames(sortedGames);
        }
      } catch (error) {
        console.error('Error fetching games:', error);
        await logError(`SteamGamesSection -> fetchGames: ${String(error)}`);
      } finally {
        setLoading(false);
      }
    };
    fetchGames();
  }, []);

  // Check for Linux game when a game is selected
  useEffect(() => {
    const checkLinuxGame = async () => {
      if (!selectedGame) {
        setLinuxGameDetection(null);
        return;
      }

      try {
        setCheckingLinuxGame(true);
        const detection = await detectLinuxGame(selectedGame.appid);
        setLinuxGameDetection(detection);
      } catch (error) {
        await logError(`Linux game detection error: ${String(error)}`);
        setLinuxGameDetection(null);
      } finally {
        setCheckingLinuxGame(false);
      }
    };

    checkLinuxGame();
  }, [selectedGame]);

  // Check executable detection when a game is selected
  useEffect(() => {
    const checkExecutableDetection = async () => {
      if (!selectedGame) {
        setExecutableDetection(null);
        return;
      }

      try {
        setCheckingExecutable(true);
        const detection = await findGameExecutablePath(selectedGame.appid);
        setExecutableDetection(detection);
      } catch (error) {
        await logError(`Executable detection error: ${String(error)}`);
        setExecutableDetection(null);
      } finally {
        setCheckingExecutable(false);
      }
    };

    checkExecutableDetection();
  }, [selectedGame]);

  const handlePatch = async () => {
    if (!selectedGame) {
      setResult('Please select a game.');
      return;
    }

    if (!selectedDll) {
      setResult('Please select a DLL override or "Automatic".');
      return;
    }

    // Check if it's a Linux game and warn user
    if (linuxGameDetection?.is_linux_game && linuxGameDetection.confidence !== "low") {
      // Create a custom modal content with proper formatting
      const LinuxGameModalContent = () => (
        <div style={{ textAlign: 'left' }}>
          <p style={{ marginBottom: '16px' }}>
            This appears to be a Linux version of <strong>{selectedGame.name}</strong>. 
            ReShade only works with Windows games running through Proton.
          </p>
          
          <p style={{ marginBottom: '8px', fontWeight: 'bold' }}>To fix this:</p>
          <div style={{ marginBottom: '16px', paddingLeft: '8px' }}>
            <div style={{ marginBottom: '4px' }}>• Right-click the game in Steam</div>
            <div style={{ marginBottom: '4px' }}>• Go to Properties → Compatibility</div>
            <div style={{ marginBottom: '4px' }}>• Check "Force the use of a specific Steam Play compatibility tool"</div>
            <div style={{ marginBottom: '4px' }}>• Select "Proton Experimental" or latest Proton version</div>
            <div style={{ marginBottom: '4px' }}>• Reinstall the game to download the Windows version</div>
          </div>
          
          <p style={{ marginBottom: '0' }}>Do you want to continue anyway?</p>
        </div>
      );

      showModal(
        <ConfirmModal
          strTitle="Linux Game Detected"
          strDescription={<LinuxGameModalContent />}
          strOKButtonText="Continue Anyway"
          strCancelButtonText="Cancel"
          onOK={async () => {
            await proceedWithPatch();
          }}
        />
      );
      return;
    }

    await proceedWithPatch();
  };

  const proceedWithPatch = async () => {
    if (!selectedGame || !selectedDll) return;

    try {
      const reshadeCheck = await checkReShadePath();
      if (!reshadeCheck.exists) {
        setResult('Please install ReShade first before patching games.');
        return;
      }

      // Create enhanced confirmation dialog with detection info
      const getDetectionInfo = () => {
        let info = `Are you sure you want to patch ${selectedGame.name} with ${selectedDll.label}?`;
        
        if (executableDetection && executableDetection.status === "success") {
          info += `\n\nExecutable Detection:`;
          info += `\n• Method: ${executableDetection.method === 'steam_logs' ? 'Steam Console Logs' : 'Enhanced File Analysis'}`;
          if (executableDetection.executable_path) {
            const fileName = executableDetection.executable_path.split('/').pop();
            info += `\n• Found: ${fileName}`;
          }
          if (executableDetection.confidence) {
            info += `\n• Confidence: ${executableDetection.confidence}`;
          }
        }
        
        return info;
      };

      showModal(
        <ConfirmModal
          strTitle="Confirm Steam Game Patch"
          strDescription={getDetectionInfo()}
          strOKButtonText="Patch"
          strCancelButtonText="Cancel"
          onOK={async () => {
            const dllValue = selectedDll.value;
            
            const response = await manageGameReShade(
              selectedGame.appid,
              "install",
              dllValue
            );

            if (response.status === "success") {
              // Extract the launch option from the response if using auto
              if (selectedDll.value === 'auto' && response.output) {
                const launchOptionsMatch = response.output?.match(/Use this launch option: (.+)/);
                if (launchOptionsMatch) {
                  const launchOptions = launchOptionsMatch[1];
                  const detectedApi = launchOptions.match(/;(\w+)=n,b/)?.pop() || 'dxgi';
                  await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), launchOptions);
                  
                  let successMessage = `Successfully patched ${selectedGame.name}.\nDetected ${detectedApi.toUpperCase()} as the best API.\nPress HOME key in-game to open ReShade overlay.`;
                  
                  // Add detection method info
                  if (executableDetection && executableDetection.method) {
                    const methodName = executableDetection.method === 'steam_logs' ? 'Steam Console Logs' : 'Enhanced File Analysis';
                    successMessage += `\n\nDetection Method: ${methodName}`;
                  }
                  
                  setResult(successMessage);
                } else {
                  // Fallback if we can't extract from output
                  await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), `WINEDLLOVERRIDES="d3dcompiler_47=n;${dllValue}=n,b" %command%`);
                  setResult(`Successfully patched ${selectedGame.name} with ${dllValue.toUpperCase()}.\nPress HOME key in-game to open ReShade overlay.`);
                }
              } else {
                // Manual DLL selection
                await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), `WINEDLLOVERRIDES="d3dcompiler_47=n;${dllValue}=n,b" %command%`);
                setResult(`Successfully patched ${selectedGame.name} with ${dllValue.toUpperCase()}.\nPress HOME key in-game to open ReShade overlay.`);
              }
            } else {
              setResult(`Failed to patch: ${response.message || 'Unknown error'}`);
            }
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      await logError(`SteamGamesSection -> proceedWithPatch: ${String(error)}`);
    }
  };

  const handleUnpatch = async () => {
    if (!selectedGame) {
      setResult('Please select a game to unpatch.');
      return;
    }

    try {
      // Check if ReShade is installed first
      const reshadeCheck = await checkReShadePath();
      if (!reshadeCheck.exists) {
        setResult('ReShade is not installed.');
        return;
      }

      showModal(
        <ConfirmModal
          strTitle="Confirm Removal"
          strDescription={`Are you sure you want to remove ReShade from ${selectedGame.name}?`}
          strOKButtonText="Remove"
          strCancelButtonText="Cancel"
          onOK={async () => {
            const response = await manageGameReShade(
              selectedGame.appid,
              "uninstall",
              selectedDll?.value || 'dxgi'
            );

            if (response.status === "success") {
              await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), '');
              setResult(`Successfully removed ReShade from ${selectedGame.name}`);
            } else {
              setResult(`Failed to unpatch: ${response.message || 'Unknown error'}`);
            }
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      await logError(`SteamGamesSection -> handleUnpatch: ${String(error)}`);
    }
  };

  const handleVkBasaltPatch = async () => {
    if (!selectedGame) {
      setResult('Please select a game.');
      return;
    }

    try {
      // Check if VkBasalt is installed first
      const vkbasaltCheck = await checkVkBasaltPath();
      if (!vkbasaltCheck.exists) {
        setResult('Please install VkBasalt first before enabling it for games.');
        return;
      }

      showModal(
        <ConfirmModal
          strTitle="Enable VkBasalt"
          strDescription={`Are you sure you want to enable VkBasalt for ${selectedGame.name}?`}
          strOKButtonText="Enable"
          strCancelButtonText="Cancel"
          onOK={async () => {
            await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), 'ENABLE_VKBASALT=1 %command%');
            setResult(`VkBasalt enabled for ${selectedGame.name}.\nPress HOME key in-game to toggle effects.`);
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      await logError(`SteamGamesSection -> handleVkBasaltPatch: ${String(error)}`);
    }
  };

  const renderLinuxGameWarning = () => {
    if (!linuxGameDetection || !linuxGameDetection.is_linux_game) return null;
    
    if (linuxGameDetection.confidence === "low") return null; // Don't show warning for low confidence

    const confidenceColor = linuxGameDetection.confidence === "high" ? "#ff6b6b" : "#ffa726";
    
    return (
      <PanelSectionRow>
        <div style={{
          padding: '12px',
          marginTop: '8px',
          backgroundColor: confidenceColor,
          borderRadius: '4px',
          color: 'white'
        }}>
          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
            ⚠️ Linux Game Detected ({linuxGameDetection.confidence} confidence)
          </div>
          <div style={{ fontSize: '0.9em', marginBottom: '8px' }}>
            This appears to be a Linux version. ReShade requires Windows version through Proton.
          </div>
          <div style={{ fontSize: '0.85em' }}>
            <strong>Fix:</strong> Properties → Compatibility → Force Proton → Reinstall game
          </div>
        </div>
      </PanelSectionRow>
    );
  };

  const renderExecutableDetectionInfo = () => {
    if (!executableDetection || executableDetection.status !== "success") return null;

    const methodColor = executableDetection.method === 'steam_logs' ? "#4CAF50" : "#2196F3";
    const methodIcon = executableDetection.method === 'steam_logs' ? "📋" : "🔍";
    const methodName = executableDetection.method === 'steam_logs' ? 'Steam Console Logs' : 'Enhanced File Analysis';
    const isEnhancedDetection = executableDetection.method !== 'steam_logs';
    
    return (
      <>
        <PanelSectionRow>
          <div style={{
            padding: '10px',
            marginTop: '8px',
            backgroundColor: methodColor,
            borderRadius: '4px',
            color: 'white',
            fontSize: '0.9em'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
              {methodIcon} Executable Detection: {methodName}
            </div>
            {executableDetection.executable_path && (
              <div style={{ fontSize: '0.85em' }}>
                Found: {executableDetection.executable_path.split('/').pop()}
              </div>
            )}
            {executableDetection.confidence && (
              <div style={{ fontSize: '0.85em' }}>
                Confidence: {executableDetection.confidence}
              </div>
            )}
          </div>
        </PanelSectionRow>
        
        {isEnhancedDetection && (
          <PanelSectionRow>
            <div style={{
              padding: '8px',
              marginTop: '4px',
              backgroundColor: 'var(--decky-highlighted-ui-bg)',
              borderRadius: '4px',
              fontSize: '0.85em',
              opacity: 0.9,
              border: '1px solid var(--decky-subtle-border)'
            }}>
              <div style={{ marginBottom: '4px', fontWeight: 'bold' }}>
                💡 Want full confidence detection?
              </div>
              <div>
                Launch {selectedGame?.name} once, then close it and try again. 
                This will populate Steam logs for 100% accurate detection.
              </div>
            </div>
          </PanelSectionRow>
        )}
      </>
    );
  };

  return (
    <PanelSection title="Steam Games">
      {loading ? (
        <PanelSectionRow>
          <div>Loading Steam games...</div>
        </PanelSectionRow>
      ) : (
        <>
          <PanelSectionRow>
            <DropdownItem
              rgOptions={games.map(game => ({
                data: game,
                label: game.name
              }))}
              selectedOption={selectedGame ? selectedGame : undefined}
              onChange={(option) => {
                setSelectedGame(option.data);
                setResult('');
              }}
              strDefaultLabel="Select a game..."
            />
          </PanelSectionRow>

          {selectedGame && (checkingLinuxGame || checkingExecutable) && (
            <PanelSectionRow>
              <div style={{ fontSize: '0.9em', opacity: 0.7 }}>
                🔍 Analyzing game... {checkingLinuxGame && "Checking version"} {checkingExecutable && "Detecting executable"}
              </div>
            </PanelSectionRow>
          )}

          {renderLinuxGameWarning()}
          {renderExecutableDetectionInfo()}

          {selectedGame && (
            <PanelSectionRow>
              <DropdownItem
                rgOptions={dllOverrides.map(dll => ({
                  data: dll.value,
                  label: dll.label
                }))}
                selectedOption={selectedDll ? selectedDll.value : undefined}
                onChange={(option) => {
                  const selected = dllOverrides.find(dll => dll.value === option.data);
                  if (selected) {
                    setSelectedDll(selected);
                    setResult('');
                  }
                }}
                strDefaultLabel="Select API/DLL override..."
              />
            </PanelSectionRow>
          )}

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
                  onClick={handlePatch}
                  disabled={!selectedDll}
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
                  onClick={handleUnpatch}
                >
                  🗑️ Remove ReShade/VkBasalt
                </ButtonItem>
              </PanelSectionRow>
            </>
          )}
        </>
      )}
    </PanelSection>
  );
};

export default SteamGamesSection;