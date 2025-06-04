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

const SteamGamesSection = () => {
  const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
  const [selectedDll, setSelectedDll] = useState<DllOverride | null>(null);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [result, setResult] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

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

  const handlePatch = async () => {
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

      showModal(
        <ConfirmModal
          strTitle="Confirm Steam Game Patch"
          strDescription={`Are you sure you want to patch ${selectedGame.name} with ${selectedDll.label}?`}
          strOKButtonText="Patch"
          strCancelButtonText="Cancel"
          onOK={async () => {
            const dllValue = selectedDll.value === 'auto' ? 'dxgi' : selectedDll.value;
            
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
                  setResult(`Successfully patched ${selectedGame.name}.\nDetected ${detectedApi.toUpperCase()} as the best API.\nPress HOME key in-game to open ReShade overlay.`);
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
      await logError(`SteamGamesSection -> handlePatch: ${String(error)}`);
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