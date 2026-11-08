# Desktop compatibility

Installed desktop build, not the docs checkout:

- Process: `apps/desktop/release/win-unpacked/Hermes.exe`
- Build stamp: `2026-11-05T00:57:01.555Z`
- Source hash: `5ec8e41fdc8d683e0ddc95633439cacbeb5bfd0cf9be5c6205b58d495886d5aa`
- The unpacked renderer contains `ROUTES_AREA`, `SIDEBAR_NAV_AREA`, and `@hermes/plugin-sdk`.
- The unpacked main process contains `desktop-plugins`.

The package ships `desktop/plugin.js` plus a hidden dashboard API. The API is read-only. Sending stays on `/salespilot-send`.
