# AionUI PDF runtime

The Win7 x64 build populates `win32-x64/` and `manifest.json` during the
Action/local packaging step with Python 3.8.10, the pinned PDF wheels, and
Poppler. Other architectures do not claim offline PDF support; the skill must
show an offline-runtime-unavailable message instead of downloading dependencies.
