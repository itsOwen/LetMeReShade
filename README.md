# LetMeReShade 🎮✨

[![Decky Plugin](https://img.shields.io/badge/Decky-Plugin-brightgreen.svg)](https://github.com/SteamDeckHomebrew/decky-loader)
[![License](https://img.shields.io/badge/license-BSD--3-blue.svg)](LICENSE)

> Transform your Steam Deck gaming experience with advanced shader customization and graphics enhancement! 🚀

![LetMeReShade Banner](assets/shade.jpg)

## 🌟 Features

- 🎨 Easy ReShade installation and management
- 🎯 One-click game-specific shader application
- 🔄 Seamless shader updates and synchronization
- 🛠️ Advanced configuration options
- 💾 Global preset management
- 🎮 Compatible with most Steam games
- 🔍 Automatic game detection and configuration
- ⚡ Vulkan support (experimental)

## 📋 Prerequisites

- Decky Loader installed on your Steam Deck
- Internet connection for initial setup and shader downloads
- Some free space for shader storage

## 🚀 Installation

1. Download the Latest Releases
2. Extract the files to to homebrew/plugins/(foldername)
3. Restart your Steam Deck.
4. Done, Enjoy!

## 🎮 Usage

### Initial Setup

1. Open the Quick Access Menu (...)
2. Navigate to the LetMeReShade plugin
3. Click "Install ReShade" to set up the base components

### Adding ReShade to Games

1. Select a game from your library in the plugin interface
2. Click "Install ReShade" next to the game
3. Wait for the installation to complete
4. Launch your game and press INSERT/Home to access the ReShade overlay

### Managing Settings

- Toggle Vulkan Support for compatible games
- Enable/disable shader merging
- Configure global presets
- Manage installation options

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

1. ReShade overlay not appearing

   - Verify the correct DLL override is selected
   - Check if INSERT or Home key is properly mapped
   - Ensure launch options are correctly set

2. Game crashes on launch

   - Try a different DLL override (will add manual patching options soon)
   - Verify shader compatibility
   - Check game compatibility with ReShade

3. Performance Issues

   - Disable intensive shaders
   - Update to the latest version
   - Check GPU compatibility

## 📝 Contributing

We welcome contributions! Please feel free to:

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

This project is licensed under the BSD-3-Clause License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Will add as soon as the plugin is fully operational

## 📞 Support

For support, please:

1. Check the troubleshooting guide
2. Search existing issues
3. Create a new issue if needed

---

<p align="center">Made with ❤️ for the Steam Deck Community</p>

