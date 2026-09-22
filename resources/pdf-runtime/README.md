# AionUI PDF runtime

The Win7 x64 build populates `win32-x64/` and `manifest.json` during the
Action/local packaging step with Python 3.8.10, the pinned PDF wheels, and
Poppler. Other architectures do not claim offline PDF support; the skill must
show an offline-runtime-unavailable message instead of downloading dependencies.


## 固定运行时路径

安装版固定目录为 `%LOCALAPPDATA%\\Programs\\AionUi\\resources\\pdf-runtime\\win32-x64`，便携版为 `AionUi.exe` 同级 `resources\\pdf-runtime\\win32-x64`。Python、Poppler、Tesseract 和 tessdata 均从该目录读取；环境变量只作为宿主注入的显式覆盖，不应触发全盘搜索。
