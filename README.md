# LetMeReShade 🎮✨

[![Decky Plugin](https://img.shields.io/badge/Decky-Plugin-brightgreen.svg)](https://github.com/SteamDeckHomebrew/decky-loader)
[![License](https://img.shields.io/badge/license-BSD--3-blue.svg)](LICENSE)

> Transform your Steam Deck gaming experience with advanced shader customization and graphics enhancements! 🚀

![LetMeReShade Banner](assets/shade.jpg)

## 🌟 Features

- 🎨 Easy ReShade installation and management
- 🎯 One-click game-specific shader application
- 🔄 Seamless shader updates and synchronization
- 💾 Global preset management
- 🎮 Compatible with most Steam games
- 🔍 Automatic game detection and configuration

## 📋 Prerequisites

- Decky Loader installed on your Steam Deck
- An internet connection for initial setup and shader downloads
- Some free space for shader storage

## 🚀 Installation

**Note:** ReShade conflicts with FGMOD as both use some of the same DLL files. I might be able to implement a workaround, but for now, you must choose between them. If you want to use FGMOD, uninstall/unpatch the game from the ReShade plugin (which will remove all ReShade files), then patch the game using FGMOD. To switch back to ReShade, reverse the process.

### Installation Steps

1. Download the latest release.
2. Extract the files to `homebrew/plugins/(foldername)`.
3. Restart your Steam Deck.
4. Done! Enjoy your enhanced graphics!

## 📷 Video Guide

[![Watch the video](https://img.youtube.com/vi/4uTVz7deH6E/maxresdefault.jpg)](https://youtu.be/4uTVz7deH6E)

## 🎮 Usage

### Initial Setup

1. Open the Quick Access Menu (...).
2. Navigate to the LetMeReShade plugin.
3. Click "Install ReShade" to set up the base components.

### Adding ReShade to Games

1. Select a game from your library within the plugin interface.
2. Click "Install ReShade" next to the game.
3. Wait for the installation to complete.
4. Launch your game and press **HOME** to access the ReShade overlay.

## ⚙️ Advanced Configuration

The plugin supports various advanced settings:

```bash
# Environment Variables (automatically managed)
XDG_DATA_HOME=~/.local/share
UPDATE_RESHADE=1
MERGE_SHADERS=1
VULKAN_SUPPORT=0
GLOBAL_INI=ReShade.ini
DELETE_RESHADE_FILES=0
```

## 🔧 Troubleshooting

### Common Issues

1. **ReShade overlay not appearing**
   - Verify the correct DLL override is selected.
   - Check if the HOME key is properly mapped.
   - Ensure launch options are correctly set.
   - Confirm that the game supports ReShade.

2. **Game crashes on launch**
   - Try a different DLL override (manual patching options will be added soon).
   - Verify shader compatibility.
   - Check the game's compatibility with ReShade.

3. **Performance issues**
   - Disable resource-intensive shaders.
   - Ensure you are using the latest version.

## 📝 Contributing

We welcome contributions! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests
- Share shader presets

## 🔄 Updates

The plugin automatically checks for:

- ReShade updates
- New shader repositories
- Plugin updates

## ⚖️ License

This project is licensed under the BSD-3-Clause License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ZigmA** for inspiring this plugin and assisting with testing.
- **xXJSONDeruloXx** for his brilliant plugin, *Decky Framegen*, which serves as the foundation for this plugin.
- **kevinlekiller** for his *reshade-steam-proton* repository.

## 📞 Support

For assistance:

1. Check the troubleshooting guide.
2. Search existing issues.
3. Create a new issue if needed.

---

<p align="center">Made with ❤️ for the Steam Deck Community</p>