// src/ManualPatchSection.tsx
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
const listInstalledGames = callable<[], GameListResponse>("list_installed_games");

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

const ManualPatchSection = () => {
  const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
  const [selectedDll, setSelectedDll] = useState<DllOverride | null>(null);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [result, setResult] = useState<string>('');

  const dllOverrides: DllOverride[] = [
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
        const response = await listInstalledGames();
        if (response.status === "success") {
          const sortedGames = response.games
            .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
          setGames(sortedGames);
        }
      } catch (error) {
        console.error('Error fetching games:', error);
      }
    };
    fetchGames();
  }, []);

  const handlePatch = async () => {
    if (!selectedGame || !selectedDll) {
      setResult('Please select both a game and a DLL override.');
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
          strTitle="Confirm Manual Patch"
          strDescription={`Are you sure you want to patch ${selectedGame.name} with ${selectedDll.label}?`}
          strOKButtonText="Patch"
          strCancelButtonText="Cancel"
          onOK={async () => {
            const response = await manageGameReShade(
              selectedGame.appid,
              "install",
              selectedDll.value
            );

            if (response.status === "success") {
              const launchOption = `WINEDLLOVERRIDES="d3dcompiler_47=n;${selectedDll.value}=n,b" %command%`;
              await SteamClient.Apps.SetAppLaunchOptions(parseInt(selectedGame.appid), launchOption);
              setResult(`Successfully patched ${selectedGame.name} with ${selectedDll.label}.\nPress Home key in-game to open ReShade overlay.`);
            } else {
              setResult(`Failed to patch: ${response.message || 'Unknown error'}`);
            }
          }}
        />
      );
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      console.error('Patch error:', error);
    }
  };

  const handleUnpatch = async () => {
    if (!selectedGame) {
      setResult('Please select a game to unpatch.');
      return;
    }

    try {
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
    } catch (error) {
      setResult(`Error: ${error instanceof Error ? error.message : String(error)}`);
      console.error('Unpatch error:', error);
    }
  };

  return (
    <PanelSection title="Manual Game Patch">
      <PanelSectionRow>
        <DropdownItem
          rgOptions={games.map(game => ({
            data: game,
            label: game.name
          }))}
          selectedOption={selectedGame}
          onChange={(option) => {
            setSelectedGame(option.data);
            setResult('');
          }}
          strDefaultLabel="Select a game..."
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <DropdownItem
          rgOptions={dllOverrides.map(dll => ({
            data: dll,
            label: dll.label
          }))}
          selectedOption={selectedDll}
          onChange={(option) => {
            setSelectedDll(option.data);
            setResult('');
          }}
          strDefaultLabel="Select DLL override..."
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
              onClick={handlePatch}
              disabled={!selectedDll}
            >
              🔧 Apply Manual Patch
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleUnpatch}
            >
              🗑️ Remove Patch
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
};

export default ManualPatchSection;