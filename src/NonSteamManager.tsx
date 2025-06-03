import { useState } from "react";
import {
    PanelSection,
    PanelSectionRow,
    ButtonItem,
    Dropdown,
    showModal,
    ConfirmModal,
    ToggleField
} from "@decky/ui";
import { callable } from "@decky/api";

// Type definitions
interface GameInfo {
    name: string;
    launcher: string;
    path: string;
    exe: string;
    app_name?: string;
}

interface NonSteamGamesResponse {
    status: string;
    games: GameInfo[];
    message?: string;
}

interface AddToSteamResponse {
    status: string;
    app_id?: string;
    message: string;
}

interface RestartResponse {
    status: string;
    message?: string;
}

interface RemoveReShadeResponse {
    status: string;
    message: string;
}

const scanNonSteamGames = callable<[], NonSteamGamesResponse>("scan_non_steam_games");
const addToSteamWithReShade = callable<[GameInfo], AddToSteamResponse>("add_to_steam_with_reshade");
const restartSteamClient = callable<[], RestartResponse>("restart_steam_client");
const removeReShadeFromGame = callable<[GameInfo, boolean], RemoveReShadeResponse>("remove_reshade_from_game");

function NonSteamManager() {
    const [games, setGames] = useState<GameInfo[]>([]);
    const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
    const [loading, setLoading] = useState(false);
    const [scanning, setScanning] = useState(false);
    const [removing, setRemoving] = useState(false);

    const scanForGames = async () => {
        setScanning(true);
        try {
            const result = await scanNonSteamGames();
            console.log("Scan result:", result);

            if (result.status === "success") {
                setGames(result.games.sort((a: GameInfo, b: GameInfo) =>
                    a.name.localeCompare(b.name)
                ));

                if (result.games.length === 0) {
                    showModal(
                        <ConfirmModal
                            strTitle="No Games Found"
                            strDescription="No games were found. Make sure you have games installed via Heroic, Lutris, or other supported launchers."
                            strOKButtonText="OK"
                        />
                    );
                }
            } else {
                showModal(
                    <ConfirmModal
                        strTitle="Scan Error"
                        strDescription={`Error: ${result.message}`}
                        strOKButtonText="OK"
                    />
                );
            }
        } catch (error) {
            console.error("Scan error:", error);
            showModal(
                <ConfirmModal
                    strTitle="Scan Error"
                    strDescription={`An error occurred while scanning: ${error}`}
                    strOKButtonText="OK"
                />
            );
        } finally {
            setScanning(false);
        }
    };

    const handleAddToSteam = async () => {
        if (!selectedGame) return;

        showModal(
            <ConfirmModal
                strTitle="Add to Steam with ReShade?"
                strDescription={
                    <div>
                        <p>This will:</p>
                        <ul style={{ textAlign: 'left', paddingLeft: '20px' }}>
                            <li>Add {selectedGame.name} to Steam</li>
                            <li>Install ReShade for the game</li>
                            <li>Configure launch options automatically</li>
                        </ul>
                        <p style={{ marginTop: '10px' }}>
                            <strong>Note:</strong> You'll need to manually set Proton compatibility after restarting Steam.
                        </p>
                        <p style={{ marginTop: '10px' }}>Continue?</p>
                    </div>
                }
                strOKButtonText="Add to Steam"
                strCancelButtonText="Cancel"
                onOK={async () => {
                    setLoading(true);
                    try {
                        console.log("Adding game to Steam:", selectedGame);
                        const result = await addToSteamWithReShade(selectedGame);
                        console.log("Add to Steam result:", result);

                        if (result.status === "success") {
                            showModal(
                                <ConfirmModal
                                    strTitle="Success!"
                                    strDescription={
                                        <div>
                                            <p>{selectedGame.name} has been added to Steam with ReShade!</p>
                                            <p style={{ marginTop: '10px' }}><strong>Next steps:</strong></p>
                                            <ol style={{ textAlign: 'left', paddingLeft: '20px' }}>
                                                <li>Steam will restart automatically</li>
                                                <li>Find the game in your library</li>
                                                <li>Right-click → Properties → Compatibility</li>
                                                <li>Enable "Force the use of a specific Steam Play compatibility tool"</li>
                                                <li>Select your preferred Proton version</li>
                                            </ol>
                                            <p style={{ marginTop: '10px' }}>
                                                <strong>Click OK to restart Steam now.</strong>
                                            </p>
                                        </div>
                                    }
                                    strOKButtonText="OK - Restart Steam"
                                    onOK={async () => {
                                        // Restart Steam when user clicks OK
                                        try {
                                            console.log("Restarting Steam...");
                                            await restartSteamClient();
                                        } catch (error) {
                                            console.error("Failed to restart Steam:", error);
                                        }
                                    }}
                                />
                            );
                            // Clear selection
                            setSelectedGame(null);
                        } else {
                            showModal(
                                <ConfirmModal
                                    strTitle="Error"
                                    strDescription={`Failed to add game: ${result.message}`}
                                    strOKButtonText="OK"
                                />
                            );
                        }
                    } catch (error) {
                        console.error("Add to Steam error:", error);
                        showModal(
                            <ConfirmModal
                                strTitle="Error"
                                strDescription={`An error occurred: ${error}`}
                                strOKButtonText="OK"
                            />
                        );
                    } finally {
                        setLoading(false);
                    }
                }}
            />
        );
    };

    const handleRemoveReShade = async () => {
        if (!selectedGame) return;

        let removeShortcut = true;

        showModal(
            <ConfirmModal
                strTitle="Remove ReShade?"
                strDescription={
                    <div>
                        <p>This will remove ReShade from {selectedGame.name}.</p>
                        <div style={{ marginTop: '15px' }}>
                            <ToggleField
                                label="Also remove Steam library shortcut"
                                checked={removeShortcut}
                                onChange={(checked) => {
                                    removeShortcut = checked;
                                }}
                            />
                        </div>
                    </div>
                }
                strOKButtonText="Remove ReShade"
                strCancelButtonText="Cancel"
                onOK={async () => {
                    setRemoving(true);
                    try {
                        console.log("Removing ReShade from game:", selectedGame, "Remove shortcut:", removeShortcut);
                        const result = await removeReShadeFromGame(selectedGame, removeShortcut);
                        console.log("Remove ReShade result:", result);

                        if (result.status === "success") {
                            showModal(
                                <ConfirmModal
                                    strTitle="Success!"
                                    strDescription={
                                        <div>
                                            <p>ReShade has been removed from {selectedGame.name}!</p>
                                            {removeShortcut && (
                                                <p style={{ marginTop: '10px' }}>
                                                    The Steam shortcut has also been removed.
                                                    Click OK to restart Steam.
                                                </p>
                                            )}
                                        </div>
                                    }
                                    strOKButtonText={removeShortcut ? "OK - Restart Steam" : "OK"}
                                    onOK={async () => {
                                        if (removeShortcut) {
                                            try {
                                                console.log("Restarting Steam...");
                                                await restartSteamClient();
                                            } catch (error) {
                                                console.error("Failed to restart Steam:", error);
                                            }
                                        }
                                    }}
                                />
                            );
                        } else {
                            showModal(
                                <ConfirmModal
                                    strTitle="Error"
                                    strDescription={`Failed to remove ReShade: ${result.message}`}
                                    strOKButtonText="OK"
                                />
                            );
                        }
                    } catch (error) {
                        console.error("Remove ReShade error:", error);
                        showModal(
                            <ConfirmModal
                                strTitle="Error"
                                strDescription={`An error occurred: ${error}`}
                                strOKButtonText="OK"
                            />
                        );
                    } finally {
                        setRemoving(false);
                    }
                }}
            />
        );
    };

    return (
        <PanelSection title="Non-Steam Games">
            <PanelSectionRow>
                <ButtonItem
                    layout="below"
                    onClick={scanForGames}
                    disabled={scanning}
                >
                    {scanning ? "Scanning..." : "🔍 Scan for Games"}
                </ButtonItem>
            </PanelSectionRow>

            {games.length > 0 && (
                <>
                    <PanelSectionRow>
                        <Dropdown
                            rgOptions={games.map(game => ({
                                data: game,
                                label: `${game.name} (${game.launcher})`
                            }))}
                            selectedOption={selectedGame}
                            onChange={(option) => setSelectedGame(option.data)}
                            strDefaultLabel="Select a game..."
                        />
                    </PanelSectionRow>

                    {selectedGame && (
                        <>
                            <PanelSectionRow>
                                <ButtonItem
                                    layout="below"
                                    onClick={handleAddToSteam}
                                    disabled={loading}
                                >
                                    {loading ? "Adding..." : "➕ Add to Steam with ReShade"}
                                </ButtonItem>
                            </PanelSectionRow>

                            <PanelSectionRow>
                                <ButtonItem
                                    layout="below"
                                    onClick={handleRemoveReShade}
                                    disabled={removing}
                                >
                                    {removing ? "Removing..." : "🗑️ Remove ReShade"}
                                </ButtonItem>
                            </PanelSectionRow>
                        </>
                    )}
                </>
            )}

            {games.length > 0 && (
                <PanelSectionRow>
                    <div style={{ fontSize: '0.9em', opacity: 0.8 }}>
                        Found {games.length} game{games.length !== 1 ? 's' : ''}
                    </div>
                </PanelSectionRow>
            )}
        </PanelSection>
    );
}

export default NonSteamManager;