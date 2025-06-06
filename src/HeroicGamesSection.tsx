// src/HeroicGamesSection.tsx
import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ButtonItem,
  DropdownItem,
  ConfirmModal,
  showModal
} from "@decky/ui";
import { callable } from "@decky/api";

// Define interfaces
interface HeroicGameInfo {
  name: string;
  path: string;
  app_id?: string;
  config_file?: string;
  config_key?: string;
}

interface DllOverride {
  label: string;
  value: string;
}

interface HeroicResponse {
  status: string;
  message?: string;
  output?: string;
  games?: HeroicGameInfo[];
  config_file?: string;
  config_key?: string;
  api?: string;
  architecture?: string;
  score?: number;
  details?: string[];
}

interface PathCheckResponse {
  exists: boolean;
  is_addon: boolean;
}

// Define callables
const findHeroicGames = callable<[], HeroicResponse>("find_heroic_games");
const installReshadeForHeroicGame = callable<[string, string], HeroicResponse>("install_reshade_for_heroic_game");
const uninstallReshadeForHeroicGame = callable<[string], HeroicResponse>("uninstall_reshade_for_heroic_game");
const updateHeroicConfig = callable<[string, string, string], HeroicResponse>("update_heroic_config");
const findHeroicGameConfig = callable<[string, string], HeroicResponse>("find_heroic_game_config");
const detectHeroicGameApi = callable<[string], HeroicResponse>("detect_heroic_game_api");
const checkReShadePath = callable<[], PathCheckResponse>("check_reshade_path");
const logError = callable<[string], void>("log_error");

const HeroicGamesSection = () => {
  const [heroicGames, setHeroicGames] = useState<HeroicGameInfo[]>([]);
  const [selectedGame, setSelectedGame] = useState<HeroicGameInfo | null>(null);
  const [selectedDll, setSelectedDll] = useState<DllOverride | null>(null);
  const [result, setResult] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [apiDetecting, setApiDetecting] = useState<boolean>(false);

  const dllOverrides: DllOverride[] = [
    { label: 'Automatic (Detect API)', value: 'auto' },
    { label: 'DXGI (DirectX 10/11/12)', value: 'dxgi' },
    { label: 'D3D9 (DirectX 9)', value: 'd3d9' },
    { label: 'D3D8 (DirectX 8)', value: 'd3d8' },
    { label: 'D3D11 (DirectX 11)', value: 'd3d11' },
    { label: 'DDraw (DirectDraw)', value: 'ddraw' },
    { label: 'DInput8 (DirectInput)', value: 'dinput8' },
    { label: 'OpenGL32 (OpenGL)', value: 'opengl32' }
  ];

  useEffect(() => {
    const loadHeroicGames = async () => {
      try {
        setLoading(true);
        const response = await findHeroicGames();
        if (response.status === "success" && response.games) {
          setHeroicGames(response.games);
        } else {
          setResult(`Failed to load Heroic games: ${response.message || 'Unknown error'}`);
        }
      } catch (error) {
        setResult(`Error loading Heroic games: ${error instanceof Error ? error.message : String(error)}`);
        await logError(`HeroicGamesSection -> loadHeroicGames: ${String(error)}`);
      } finally {
        setLoading(false);
      }
    };
    
    loadHeroicGames();
  }, []);

  const handleInstallReShade = async () => {
    if (!selectedGame) {
      setResult('Please select a game.');
      return;
    }

    if (!selectedDll) {
      setResult('Please select a DLL override or "Automatic".');
      return;
    }

    try {
      const reshadeCheck = await checkReShadePath();
      if (!reshadeCheck.exists) {
        setResult('Please install ReShade first before patching games.');
        return;
      }

      // If automatic is selected, detect the API
      let finalDllOverride = selectedDll.value;
      if (finalDllOverride === 'auto') {
        setApiDetecting(true);
        setResult('Detecting best API for your game...');
        
        const detectionResponse = await detectHeroicGameApi(selectedGame.path);
        
        if (detectionResponse.status === "success" && detectionResponse.api) {
          finalDllOverride = detectionResponse.api;
          setResult(`Detected ${finalDllOverride.toUpperCase()} as the best API for this game.`);
        } else {
          finalDllOverride = 'dxgi'; // Default to dxgi if detection fails
          setResult(`API detection failed: ${detectionResponse.message || 'Unknown error'}. Using DXGI as fallback.`);
        }
        setApiDetecting(false);
      }

      showModal(
        <ConfirmModal
          strTitle="Confirm Heroic Game Patch"
          strDescription={`Are you sure you want to install ReShade for ${selectedGame.name} with ${finalDllOverride.toUpperCase()} API?`}
          strOKButtonText="Install"
          strCancelButtonText="Cancel"
          onOK={async () => {
            setResult('Installing ReShade...');
            
            // Install ReShade files
            const installResponse = await installReshadeForHeroicGame(
              selectedGame.path,
              finalDllOverride
            );
            
            if (installResponse.status !== "success") {
              setResult(`Failed to install ReShade: ${installResponse.message || 'Unknown error'}`);
              return;
            }
            
            let configFound = false;
            
            // Try to update config if we already have config information
            if (selectedGame.config_file && selectedGame.config_key) {
              const configResponse = await updateHeroicConfig(
                selectedGame.config_file,
                selectedGame.config_key,
                finalDllOverride
              );
              
              if (configResponse.status === "success") {
                configFound = true;
                setResult(`ReShade installed successfully for ${selectedGame.name} with ${finalDllOverride.toUpperCase()} API.\nHeroic configuration has been updated. Press HOME key in-game to open ReShade overlay.`);
              }
            }
            
            // If config wasn't found or update failed, try to find config
            if (!configFound) {
              const configResponse = await findHeroicGameConfig(selectedGame.path, selectedGame.name);
              
              if (configResponse.status === "success" && configResponse.config_file && configResponse.config_key) {
                const updateResponse = await updateHeroicConfig(
                  configResponse.config_file,
                  configResponse.config_key,
                  finalDllOverride
                );
                
                if (updateResponse.status === "success") {
                  configFound = true;
                  setResult(`ReShade installed successfully for ${selectedGame.name} with ${finalDllOverride.toUpperCase()} API.\nHeroic configuration has been updated. Press HOME key in-game to open ReShade overlay.`);
                }
              }
            }
            
            // If config still wasn't found, show a message with manual instructions
            if (!configFound) {
              setResult(`ReShade installed successfully for ${selectedGame.name} with ${finalDllOverride.toUpperCase()} API, but could not update Heroic configuration.\nYou will need to manually add WINEDLLOVERRIDES="d3dcompiler_47=n;${finalDllOverride}=n,b" to the game's launch options in Heroic.`);
            }
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      await logError(`HeroicGamesSection -> handleInstallReShade: ${String(error)}`);
    }
  };

  const handleUninstallReShade = async () => {
    if (!selectedGame) {
      setResult('Please select a game to uninstall ReShade from.');
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
          strTitle="Confirm Uninstall"
          strDescription={`Are you sure you want to remove ReShade from ${selectedGame.name}?`}
          strOKButtonText="Uninstall"
          strCancelButtonText="Cancel"
          onOK={async () => {
            setResult('Uninstalling ReShade...');
            
            const uninstallResponse = await uninstallReshadeForHeroicGame(selectedGame.path);
            
            if (uninstallResponse.status === "success") {
              setResult(`ReShade uninstalled successfully from ${selectedGame.name}.`);
              
              // Try to update config if we have config information to remove the env var
              let configUpdated = false;
              
              if (selectedGame.config_file && selectedGame.config_key) {
                const updateResponse = await updateHeroicConfig(
                  selectedGame.config_file,
                  selectedGame.config_key,
                  "remove"
                );
                
                if (updateResponse.status === "success") {
                  configUpdated = true;
                }
              }
              
              // If config wasn't updated, try to find config
              if (!configUpdated) {
                const configResponse = await findHeroicGameConfig(selectedGame.path, selectedGame.name);
                
                if (configResponse.status === "success" && configResponse.config_file && configResponse.config_key) {
                  await updateHeroicConfig(
                    configResponse.config_file,
                    configResponse.config_key,
                    "remove"
                  );
                }
              }
            } else {
              setResult(`Failed to uninstall ReShade: ${uninstallResponse.message || 'Unknown error'}`);
            }
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      await logError(`HeroicGamesSection -> handleUninstallReShade: ${String(error)}`);
    }
  };

  return (
    <PanelSection title="Heroic Games ReShade">
      {loading ? (
        <PanelSectionRow>
          <div>Loading Heroic games...</div>
        </PanelSectionRow>
      ) : heroicGames.length === 0 ? (
        <PanelSectionRow>
          <div>No Heroic games found. Make sure Heroic is installed and you have games installed.</div>
        </PanelSectionRow>
      ) : (
        <>
          <PanelSectionRow>
            <DropdownItem
              rgOptions={heroicGames.map(game => ({
                data: game,
                label: game.name
              }))}
              selectedOption={selectedGame ? selectedGame : undefined}
              onChange={(option) => {
                setSelectedGame(option.data);
                setResult('');
              }}
              strDefaultLabel="Select a Heroic game..."
            />
          </PanelSectionRow>

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
                strDefaultLabel="Select DLL override..."
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
                  onClick={handleInstallReShade}
                  disabled={!selectedDll || apiDetecting}
                >
                  {apiDetecting ? "Detecting API..." : "🔧 Install ReShade"}
                </ButtonItem>
              </PanelSectionRow>
              <PanelSectionRow>
                <ButtonItem
                  layout="below"
                  onClick={handleUninstallReShade}
                >
                  🗑️ Uninstall ReShade
                </ButtonItem>
              </PanelSectionRow>
            </>
          )}
        </>
      )}
    </PanelSection>
  );
};

export default HeroicGamesSection;