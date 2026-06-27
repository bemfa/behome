# BeHome Home Assistant 集成

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

_BeHome（原巴法云）智能家居设备的 Home Assistant 集成。_

**此集成通过 Home Assistant 提供基于云端的 BeHome/巴法云物联网设备控制功能。**

[English](README_en.md) | 简体中文

## 功能特性

- **多种登录方式**：支持微信扫码登录、OAuth2 和手动输入用户私钥
- **多平台设备支持**：控制各种设备类型，包括：
  - 开关和插座
  - 支持调光的灯具
  - 可变速风扇
  - 气候设备（空调）
  - 窗帘/百叶窗
  - 热水器
  - 媒体播放器（电视）
  - 空气净化器
  - 传感器
- **自动同步设备**：自动导入账号下所有支持的设备
- **实时状态更新**：每 5 秒轮询设备状态
- **区域集成**：自动映射到 Home Assistant 区域

## 安装方法

### HACS 安装（推荐）

1. 在 Home Assistant 中打开 HACS
2. 进入"集成"页面
3. 点击"浏览和下载存储库"
4. 搜索 "BeHome"
5. 下载并重启 Home Assistant

### 手动安装

1. 使用您选择的工具打开 Home Assistant 配置目录（包含 `configuration.yaml` 的目录）
2. 如果没有 `custom_components` 目录，请创建一个
3. 在 `custom_components` 目录中创建名为 `behome` 的新文件夹
4. 从此存储库的 `custom_components/behome/` 目录中下载所有文件
5. 将下载的文件放置在您创建的新目录中
6. 重启 Home Assistant

## 配置说明

BeHome 支持三种登录方式：

- **微信扫码登录**：推荐大多数用户使用，无需配置应用程序凭据。
- **OAuth2 登录**：需要在 Home Assistant 中配置应用程序凭据。
- **手动输入用户私钥**：适合已经知道 BeHome 用户私钥的用户。

### 可选：设置 OAuth2 应用程序凭据

只有 OAuth2 登录需要此步骤。微信扫码登录和用户私钥登录不需要配置应用程序凭据。

1. 进入 **设置** -> **设备与服务** -> **助手** 选项卡
2. 点击 **"创建助手"** -> **"应用程序凭据"**
3. 填写以下信息：
   - **名称**：`BeHome`（或您自定义的名称）
   - **域**：`behome`
   - **客户端 ID**：`88ac425b4558463aa813aed1690db730`
   - **客户端密钥**：输入您的自定义密钥（可以使用任何安全字符串）
4. 点击 **"创建"**

### 添加集成

1. 进入 **设置** -> **设备与服务** -> **集成**
2. 点击 **"+ 添加集成"** 并搜索 **"BeHome"**
3. 选择 BeHome 集成
4. 选择 **微信扫码登录**、**OAuth2** 或 **手动输入用户私钥**
5. 按照所选登录方式完成授权
6. 您的 BeHome 设备将被自动发现并添加

### 设备同步

身份验证完成后，账号下所有支持的 BeHome 设备都会自动导入并配置。配置流程不会让用户选择设备；如果用户不想在 Home Assistant 中使用某个设备，可以在 Home Assistant 中禁用对应设备或实体。

后续如果用户在 BeHome 账号中新增了支持的设备，集成会在轮询时自动发现并创建对应实体。

集成将：
- 根据设备类型为每个设备创建实体
- 将设备映射到相应的 Home Assistant 区域（如果区域名称匹配）
- 设置每 5 秒自动状态轮询

## 设备类型

集成会自动将 BeHome 设备类型映射到相应的 Home Assistant 平台：

| BeHome 类型 | Home Assistant 平台 | 描述 |
|-------------|-------------------|------|
| outlet      | switch            | 智能插座和开关 |
| light       | light             | 支持调光的智能灯具 |
| fan         | fan               | 可变速风扇 |
| aircondition| climate           | 空调设备 |
| curtain     | cover             | 窗帘和百叶窗 |
| waterheater | water_heater      | 热水器 |
| television  | media_player      | 电视和媒体设备 |
| airpurifier | air_purifier      | 空气净化器 |
| sensor      | sensor            | 各种传感器 |

## 支持与反馈

- [GitHub Issues](https://github.com/bemfa/behome/issues)
- [Home Assistant 中文社区论坛](https://bbs.hassbian.com/)
- [Home Assistant 官方社区论坛](https://community.home-assistant.io/)

## 贡献

欢迎贡献！请阅读我们的贡献指南并提交拉取请求以帮助改进此集成。

## 许可证

本项目使用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 常见问题

### Q: 设备不显示或无法控制怎么办？
A: 请检查：
1. BeHome 云端账户是否正常
2. 设备在 BeHome 应用中是否在线
3. OAuth2 凭据配置是否正确
4. Home Assistant 日志中是否有错误信息

### Q: 支持哪些 BeHome 设备？
A: 集成支持所有通过 BeHome 云端 API 提供的设备类型，包括开关、灯具、风扇、空调、窗帘、热水器、电视、空气净化器和传感器等。

### Q: 设备状态更新频率是多少？
A: 集成每 5 秒轮询一次设备状态，确保状态信息的及时性。

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
