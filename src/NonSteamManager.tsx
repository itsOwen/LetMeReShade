import { useState } from "react";
import {
    PanelSection,
    PanelSectionRow,
    ButtonItem,
    Dropdown,
    showModal,
    ConfirmModal
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

const scanNonSteamGames = callable<[], NonSteamGamesResponse>("scan_non_steam_games");
const addToSteamWithReShade = callable<[GameInfo], AddToSteamResponse>("add_to_steam_with_reshade");

function NonSteamManager() {
    const [games, setGames] = useState<GameInfo[]>([]);
    const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
    const [loading, setLoading] = useState(false);
    const [scanning, setScanning] = useState(false);

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
                            <li>Set Proton compatibility</li>
                        </ul>
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
                                    strDescription={`${selectedGame.name} has been added to Steam with ReShade!
                  
Steam will need to be restarted to see the new shortcut.`}
                                    strOKButtonText="OK"
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
                        <PanelSectionRow>
                            <ButtonItem
                                layout="below"
                                onClick={handleAddToSteam}
                                disabled={loading}
                            >
                                {loading ? "Adding..." : "➕ Add to Steam with ReShade"}
                            </ButtonItem>
                        </PanelSectionRow>
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