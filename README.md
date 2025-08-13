# BeHome Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

_Integration for BeHome (formerly Bemfa) smart home devices._

**This integration provides cloud-based control of BeHome/Bemfa IoT devices through Home Assistant.**

English | [简体中文](README_zh.md)

## Features

- **OAuth2 Authentication**: Secure authentication with BeHome cloud
- **Multi-Platform Support**: Control various device types including:
  - Switches and outlets
  - Lights with dimming support
  - Fans with speed control
  - Climate devices (air conditioners)
  - Covers (curtains/blinds)
  - Water heaters
  - Media players (TVs)
  - Air purifiers
  - Sensors
- **Real-time Updates**: Device state polling every minute
- **Area Integration**: Automatic mapping to Home Assistant areas

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click "Explore & Download Repositories"
4. Search for "BeHome"
5. Download and restart Home Assistant

### Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`)
2. If you do not have a `custom_components` directory (folder) there, you need to create it
3. In the `custom_components` directory (folder) create a new folder called `behome`
4. Download _all_ the files from the `custom_components/behome/` directory (folder) in this repository
5. Place the files you downloaded in the new directory (folder) you created
6. Restart Home Assistant

## Configuration

Only users who log in using OAuth2 need to configure this. Users who log in using their private key do not need to configure this.

### Step 1: Setup OAuth2 Application Credentials

Before adding the integration, you need to configure OAuth2 credentials in Home Assistant:

1. Go to **Settings** → **Devices & Services** → **Helpers** tab
2. Click **"Create Helper"** → **"Application Credentials"**
3. Fill in the following information:
   - **Name**: `BeHome` (or any custom name you prefer)
   - **Domain**: `behome`
   - **Client ID**: `88ac425b4558463aa813aed1690db730`
   - **Client Secret**: Enter your custom secret (you can use any secure string)
4. Click **"Create"**

### Step 2: Add the Integration

1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Click **"+ Add Integration"** and search for **"BeHome"**
3. Select the BeHome integration
4. Choose the application credentials you created in Step 1
5. Follow the OAuth2 authentication flow to authorize Home Assistant
6. Your BeHome devices will be automatically discovered and added

### Step 3: Device Configuration

Once authenticated, all your BeHome devices will be automatically imported and configured. The integration will:
- Create entities for each device based on their type
- Map devices to appropriate Home Assistant areas (if area names match)
- Set up automatic status polling every minute

## Device Types

The integration automatically maps BeHome device types to appropriate Home Assistant platforms:

| BeHome Type | Home Assistant Platform | Description |
|-------------|------------------------|-------------|
| outlet      | switch                 | Smart outlets and switches |
| light       | light                  | Smart lights with dimming |
| fan         | fan                    | Fans with speed control |
| aircondition| climate               | Air conditioners |
| curtain     | cover                  | Curtains and blinds |
| waterheater | water_heater          | Water heaters |
| television  | media_player          | TVs and media devices |
| airpurifier | air_purifier          | Air purifiers |
| sensor      | sensor                | Various sensors |

## Support

- [GitHub Issues](https://github.com/bemfa/behome/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to help improve this integration.

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/bemfa/behome.svg?style=for-the-badge
[commits]: https://github.com/bemfa/behome/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/bemfa/behome.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/bemfa/behome.svg?style=for-the-badge
[releases]: https://github.com/bemfa/behome/releases