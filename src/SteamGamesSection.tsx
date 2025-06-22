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
const manageGameReShade = callable<[string, string, string, string, string], ReShadeResponse>("manage_game_reshade");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const listInstalledGames = callable<[], GameListResponse>("list_installed_games");
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

interface ExecutableInfo {
  path: string;
  directory_path: string;
  filename: string;
  relative_path?: string;
  score?: number;
  size_mb?: number;
}

interface DetectionResult {
  status: string;
  method?: string;
  executable_path?: string;
  directory_path?: string;
  filename?: string;
  all_executables?: ExecutableInfo[];
  confidence?: string;
  message?: string;
  // Integrated Linux detection fields
  is_linux_game?: boolean;
  linux_confidence?: string;
  linux_reasons?: string[];
  linux_indicators?: any;
  scan_summary?: {
    total_files_scanned: number;
    windows_executables: number;
    main_windows_executables: number;
    so_files: number;
    sh_files: number;
    linux_indicators_found: number;
  };
}

interface ExecutableDetectionResponse {
  status: string;
  steam_logs_result?: DetectionResult;
  enhanced_detection_result?: DetectionResult;
  recommended_method?: string;
  message?: string;
  linux_game_warning?: boolean;
}

const SteamGamesSection = () => {
  const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
  const [selectedDll, setSelectedDll] = useState<DllOverride | null>(null);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [result, setResult] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [executableDetection, setExecutableDetection] = useState<ExecutableDetectionResponse | null>(null);
  const [checkingExecutable, setCheckingExecutable] = useState<boolean>(false);
  const [selectedExecutablePath, setSelectedExecutablePath] = useState<string>('');

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

  // Unified detection - one call for both executable and Linux detection
  useEffect(() => {
    const checkExecutableDetection = async () => {
      if (!selectedGame) {
        setExecutableDetection(null);
        setSelectedExecutablePath('');
        return;
      }

      try {
        setCheckingExecutable(true);
        const detection = await findGameExecutablePath(selectedGame.appid);
        setExecutableDetection(detection);
        
        // Set default selected executable path based on recommended method
        if (detection.status === "success") {
          if (detection.recommended_method === "steam_logs" && 
              detection.steam_logs_result?.status === "success") {
            setSelectedExecutablePath(detection.steam_logs_result.executable_path || '');
          } else if (detection.enhanced_detection_result?.status === "success") {
            setSelectedExecutablePath(detection.enhanced_detection_result.executable_path || '');
          }
        }
      } catch (error) {
        await logError(`Executable detection error: ${String(error)}`);
        setExecutableDetection(null);
        setSelectedExecutablePath('');
      } finally {
        setCheckingExecutable(false);
      }
    };

    checkExecutableDetection();
  }, [selectedGame]);

  // Helper function to extract Linux detection info from integrated result
  const getLinuxDetectionInfo = () => {
    if (!executableDetection) return null;
    
    // Check enhanced detection result for Linux info
    const enhancedResult = executableDetection.enhanced_detection_result;
    if (enhancedResult && (enhancedResult.is_linux_game || enhancedResult.status === "linux_game_detected")) {
      return {
        is_linux_game: enhancedResult.is_linux_game || enhancedResult.status === "linux_game_detected",
        confidence: enhancedResult.linux_confidence || "medium",
        reasons: enhancedResult.linux_reasons || [],
        scan_summary: enhancedResult.scan_summary
      };
    }
    
    // Check Steam logs result for Linux info
    const steamResult = executableDetection.steam_logs_result;
    if (steamResult && (steamResult.is_linux_game || steamResult.status === "linux_game_detected")) {
      return {
        is_linux_game: steamResult.is_linux_game || steamResult.status === "linux_game_detected",
        confidence: steamResult.linux_confidence || "medium",
        reasons: steamResult.linux_reasons || [],
        scan_summary: steamResult.scan_summary
      };
    }
    
    return null;
  };

  const handlePatch = async () => {
    if (!selectedGame) {
      setResult('Please select a game.');
      return;
    }

    if (!selectedDll) {
      setResult('Please select a DLL override or "Automatic".');
      return;
    }

    // Check integrated Linux detection
    const linuxInfo = getLinuxDetectionInfo();
    if (linuxInfo?.is_linux_game && linuxInfo.confidence !== "low") {
      // Create enhanced Linux game warning modal
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
        
        if (selectedExecutablePath) {
          const fileName = selectedExecutablePath.split('/').pop();
          info += `\n\nSelected executable: ${fileName}`;
          info += `\nLocation: ${selectedExecutablePath}`;
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
              dllValue,
              "",
              selectedExecutablePath
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
                  
                  if (selectedExecutablePath) {
                    const fileName = selectedExecutablePath.split('/').pop();
                    successMessage += `\n\nInstalled to: ${fileName}`;
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
              selectedDll?.value || 'dxgi',
              "",
              selectedExecutablePath
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

  // Updated rendering function for integrated detection info
  const renderDetectionInfo = () => {
    if (!executableDetection || executableDetection.status !== "success") return null;

    const enhancedResult = executableDetection.enhanced_detection_result;
    const linuxInfo = getLinuxDetectionInfo();

    return (
      <>
        {/* Show Linux warning if detected */}
        {linuxInfo?.is_linux_game && linuxInfo.confidence !== "low" && (
          <PanelSectionRow>
            <div style={{
              padding: '12px',
              marginTop: '8px',
              backgroundColor: linuxInfo.confidence === "high" ? "#ff6b6b" : "#ffa726",
              borderRadius: '4px',
              color: 'white'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                ⚠️ Linux Game Detected ({linuxInfo.confidence} confidence)
              </div>
              <div style={{ fontSize: '0.9em', marginBottom: '8px' }}>
                This appears to be a Linux version. ReShade requires Windows version through Proton.
              </div>
              <div style={{ fontSize: '0.85em' }}>
                <strong>Fix:</strong> Properties → Compatibility → Force Proton → Reinstall game
              </div>
              {linuxInfo.reasons && linuxInfo.reasons.length > 0 && (
                <div style={{ fontSize: '0.8em', marginTop: '8px', opacity: 0.9 }}>
                  <strong>Detected:</strong> {linuxInfo.reasons.slice(0, 2).join(', ')}
                </div>
              )}
              {linuxInfo.scan_summary && (
                <div style={{ fontSize: '0.8em', marginTop: '4px', opacity: 0.9 }}>
                  Found: {linuxInfo.scan_summary.so_files} .so files, {linuxInfo.scan_summary.sh_files} .sh files
                </div>
              )}
            </div>
          </PanelSectionRow>
        )}

        {/* Show scan summary if available */}
        {enhancedResult?.scan_summary && (
          <PanelSectionRow>
            <div style={{
              padding: '8px',
              marginTop: '8px',
              backgroundColor: 'var(--decky-highlighted-ui-bg)',
              borderRadius: '4px',
              border: '1px solid var(--decky-subtle-border)',
              fontSize: '0.85em'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                📊 Scan Results: {enhancedResult.scan_summary.total_files_scanned} files analyzed
              </div>
              <div>
                Windows: {enhancedResult.scan_summary.main_windows_executables} executables • 
                Linux: {enhancedResult.scan_summary.so_files} .so files, {enhancedResult.scan_summary.sh_files} .sh files
              </div>
            </div>
          </PanelSectionRow>
        )}

        {renderExecutableSelection()}
      </>
    );
  };

  const renderExecutableSelection = () => {
    if (!executableDetection || executableDetection.status !== "success") return null;

    const steamLogsResult = executableDetection.steam_logs_result;
    const enhancedResult = executableDetection.enhanced_detection_result;
    const recommendedMethod = executableDetection.recommended_method;

    // Skip if we detected a Linux game
    if (enhancedResult?.status === "linux_game_detected") return null;

    const executableOptions: Array<{
      path: string;
      filename: string;
      method: string;
      isRecommended: boolean;
      score?: number;
      relative_path?: string;
      displayLabel: string;
    }> = [];

    // Add Steam logs result if available
    if (steamLogsResult?.status === "success" && steamLogsResult.executable_path) {
      const isRecommended = recommendedMethod === 'steam_logs';
      executableOptions.push({
        path: steamLogsResult.executable_path,
        filename: steamLogsResult.filename || steamLogsResult.executable_path.split('/').pop() || 'Unknown',
        method: 'Steam Console Logs',
        isRecommended,
        relative_path: 'Main directory',
        displayLabel: `${steamLogsResult.filename || steamLogsResult.executable_path.split('/').pop()} ${isRecommended ? '(RECOMMENDED)' : ''} - Steam Logs`
      });
    }

    // Add enhanced detection results if available
    if (enhancedResult?.status === "success" && enhancedResult.all_executables) {
      enhancedResult.all_executables.forEach((exe, index) => {
        // Check for duplicates more carefully - compare just the filename to be safer
        const steamLogsFilename = steamLogsResult?.filename || steamLogsResult?.executable_path?.split('/').pop();
        const isDuplicate = steamLogsFilename && steamLogsFilename === exe.filename;
        
        if (!isDuplicate) {
          const isRecommended = recommendedMethod === 'enhanced_detection' && exe.path === enhancedResult.executable_path;
          executableOptions.push({
            path: exe.path,
            filename: exe.filename,
            method: 'Enhanced Detection',
            isRecommended,
            score: exe.score,
            relative_path: exe.relative_path || `Directory ${index + 1}`,
            displayLabel: `${exe.filename} ${isRecommended ? '(RECOMMENDED)' : ''} - ${exe.relative_path || 'Enhanced'} (Score: ${exe.score || 0})`
          });
        }
      });
    }

    if (executableOptions.length === 0) return null;

    return (
      <>
        <PanelSectionRow>
          <div style={{
            padding: '12px',
            marginTop: '8px',
            backgroundColor: 'var(--decky-highlighted-ui-bg)',
            borderRadius: '4px',
            border: '1px solid var(--decky-subtle-border)'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '8px', fontSize: '0.95em' }}>
              🎯 Executable Detection Results ({executableOptions.length} found)
            </div>
          </div>
        </PanelSectionRow>
        
        <PanelSectionRow>
          <DropdownItem
            rgOptions={executableOptions.map(option => ({
              data: option.path,
              label: option.displayLabel
            }))}
            selectedOption={selectedExecutablePath}
            onChange={(option) => {
              setSelectedExecutablePath(option.data);
            }}
            strDefaultLabel="Select executable location..."
          />
        </PanelSectionRow>

        {/* Show details of currently selected executable */}
        {selectedExecutablePath && (() => {
          const selectedOption = executableOptions.find(opt => opt.path === selectedExecutablePath);
          if (!selectedOption) return null;

          return (
            <PanelSectionRow>
              <div style={{
                padding: '8px',
                backgroundColor: selectedOption.isRecommended ? 'rgba(76, 175, 80, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                borderRadius: '4px',
                border: selectedOption.isRecommended ? '1px solid rgba(76, 175, 80, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                fontSize: '0.85em'
              }}>
                <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                  Selected: {selectedOption.filename}
                  {selectedOption.isRecommended && (
                    <span style={{
                      backgroundColor: '#4CAF50',
                      color: 'white',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      fontSize: '0.8em',
                      fontWeight: 'normal',
                      marginLeft: '8px'
                    }}>
                      RECOMMENDED
                    </span>
                  )}
                </div>
                <div style={{ opacity: 0.8, marginBottom: '2px' }}>
                  Method: {selectedOption.method}
                  {selectedOption.score !== undefined && (
                    <span style={{ marginLeft: '8px' }}>
                      (Score: {selectedOption.score})
                    </span>
                  )}
                </div>
                <div style={{ opacity: 0.7, fontSize: '0.8em', wordBreak: 'break-all' }}>
                  Path: {selectedOption.relative_path}
                </div>
              </div>
            </PanelSectionRow>
          );
        })()}
        
        {steamLogsResult?.status !== "success" && (
          <PanelSectionRow>
            <div style={{
              padding: '8px',
              backgroundColor: 'rgba(33, 150, 243, 0.1)',
              borderRadius: '4px',
              border: '1px solid rgba(33, 150, 243, 0.3)',
              fontSize: '0.85em'
            }}>
              <div style={{ marginBottom: '4px', fontWeight: 'bold' }}>
                💡 Want Steam Console Logs detection?
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

          {selectedGame && checkingExecutable && (
            <PanelSectionRow>
              <div style={{ fontSize: '0.9em', opacity: 0.7 }}>
                🔍 Analyzing game directory (Windows/Linux detection + executable analysis)...
              </div>
            </PanelSectionRow>
          )}

          {renderDetectionInfo()}

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
                  onClick={handleUnpatch}
                >
                  🗑️ Remove ReShade
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