# AionUi Windows 7 本地维护说明

本文档记录当前 AionUi 相对官方上游的 Win7 专用目标、构建打包方式、已保留的本地改动和后续同步策略。它是操作文档，不替代根目录 `AGENTS.md` 的规则。

## 目标与产物

- 目标系统：Windows 7 SP1 x64。
- 桌面运行时：Win7 兼容 Electron，版本由 `scripts/prepare-win7-electron.js` 固定（当前为 `v37.2.2`）。
- 后端：AionCore 的 `aionui-app`，目标三元组 `x86_64-win7-windows-msvc`，nightly Rust + `-Zbuild-std`。
- 办公能力：`resources/officecli.exe` 与 `resources/officecli.runtimeconfig.json` 随桌面包发布。
- 主要本地包：`out/AionUi-*-win-x64.*`；独立 CLI 产物为 `aioncore-win7-x64.zip`。
- 图标：Windows 可执行文件必须使用仓库中的 `resources/app.ico`（AionUI 图标），禁止保留 Win7 Electron 默认图标。

未跟踪的 `aioncore.exe`、`officecli-win-x64.exe`、`aioncore-win7-x64.zip` 和 `resources/bundled-aioncore-local/` 属于本地构建产物，除非用户明确要求，不要删除或提交；发布源资源使用已纳入仓库的 `resources/officecli.exe`。

## 构建与打包

### 一键桌面 Win7 包

在仓库根目录执行：

```bash
TZ=Asia/Shanghai bun run build-win7
# 等价：TZ=Asia/Shanghai node scripts/build-with-builder.js x64 --win --x64 --win7
```

脚本会准备 Win7 Electron、构建前端、对齐 x64 native modules、把 officecli 复制到 `resources/`，再调用 electron-builder。首次运行需要下载 Win7 Electron；网络失败时按 `AGENTS.md` 使用代理重试。

### Windows PowerShell 全流程

在 Windows 构建机可执行：

```powershell
.\scripts\build-win7.ps1
```

只构建 Rust 或只打桌面包时使用 `-SkipDesktop` / `-SkipRust`。已有 Win7 Electron 解压目录时，用 `-ElectronDist <path>` 避免重复下载。

### AionCore 独立 CLI

```powershell
cd AionCore
cargo +nightly build --release `
  --target x86_64-win7-windows-msvc `
  -Zbuild-std=std,panic_abort `
  -p aionui-app
cd ..
```

GitHub Actions 的等价入口是 `.github/workflows/build-win7-cli.yml`。它会构建、执行 `scripts/verify-win7-compat.ps1`，然后生成 `aioncore-win7-x64.zip`。Actions 只用于生成构建产物，不替代本地 Win7 真机验收。

Linux 构建机如果缺少 `wine`，electron-builder 可能在 NSIS 安装器的最后阶段失败（`spawn wine ENOENT`），即使 `out/win-unpacked` 已完整生成。此时可以先确认资源校验通过，再用 7-Zip 将便携目录压成 ZIP：

```bash
SEVEN_ZIP=/home/zwh/.cache/electron-builder/7zip@1.0.0/7zip-linux-x64-16wjr/bin/7za
(cd out/win-unpacked && "$SEVEN_ZIP" a -tzip -mx=5 ../AionUi-2.2.2-win-x64.zip .)
```

该 ZIP 是便携包，不是 NSIS 安装器；安装器仍应在 Windows 构建机或安装了 wine 的 Linux 构建机生成。

本地 Linux 环境没有 MSVC/Windows SDK，不能重新链接 `x86_64-win7-windows-msvc` 的 AionCore；本轮 ZIP 使用现有 Win7 `aioncore.exe`，并已更新桌面迁移逻辑及 bundled Node/npm/npx 资源。要把 AionCore 中新增的旧配置兜底逻辑也编入后端，需在 Windows/MSVC 或 CI Win7 工作流重新编译后替换包内 `resources/bundled-aioncore/win32-x64/aioncore.exe`。

### 图标保护

`packages/desktop/electron-builder.yml` 的 `win.icon` 固定为 `resources/app.ico`。不要使用
`--config.win.signAndEditExecutable=false`：该参数会完全跳过 Windows PE 资源编辑，导致
`AionUi.exe` 回退为 Electron 默认图标。构建脚本会把这个旧参数自动转换为
`--config.win.signExecutable=false`，后者只跳过代码签名，仍会写入 AionUI 图标和版本元数据。

生成便携包后，在 Windows 资源查看器或 Win7 真机检查 `AionUi.exe` 的图标；Linux 构建机也可
用下面的 ICO 头检查确认源文件有效：

```bash
node - <<'NODE'
const fs = require('fs');
const b = fs.readFileSync('resources/app.ico');
if (b.readUInt16LE(0) !== 0 || b.readUInt16LE(2) !== 1 || b.readUInt16LE(4) < 7) {
  throw new Error('resources/app.ico is not a valid multi-size Windows ICO');
}
console.log(`AionUI ICO OK: ${b.readUInt16LE(4)} images`);
NODE
```

如果 PE 中仍出现 Electron 图标，先确认构建日志没有出现
`executable resource editing and code signing skipped`，并重新执行 `TZ=Asia/Shanghai bun run build-win7`。

图标基准是 AionUI 自有图标，不是 Electron 图标：源文件为 `resources/app.ico`，构建配置为
`packages/desktop/electron-builder.yml` 的 `win.icon`。`scripts/build-with-builder.js` 会强制保留
`win.signAndEditExecutable=true`；即使关闭签名，也必须保留 PE 资源编辑。发布前要在生成的
`AionUi.exe`、NSIS 快捷方式和 Win7 桌面上确认显示 AionUI 图标。

## 思考强度协议

聊天界面使用 `off/low/medium/high/xhigh`，但 AionCore 内嵌的 aionrs 只接受
`--thinking enabled|disabled`。后端边界必须把 `off` 映射为 `disabled`，把其他强度映射为
`enabled`，并分别用 `--thinking-budget` 保存 `0/2048/8192/16384/32768`；`auto` 表示不传思考参数。
禁止把 UI 的 `low`、`medium` 或 `high` 原样传给 aionrs，否则会触发
`Invalid --thinking value` 并导致会话启动失败。修改模型设置后要验证设置页能够勾选多个强度，
聊天输入框能显示并切换这些强度。

## 内置 MCP

- `aionui-browser` 的 MCP JSON 必须指向逻辑命令 `node` 和打包后的
  `builtin-mcp-browser.js`，由 AionCore 的托管 Node 解析器注入真实 Node、npm、npx 环境；不能
  把 Windows 的 `Electron.exe` 与 `ELECTRON_RUN_AS_NODE` 写回配置。
- `chrome-devtools` 默认配置固定为 `npx -y chrome-devtools-mcp@0.16.0`。Win7 包必须包含
  真实的 `node_modules/npm/bin/npm-cli.js` 和 `npx-cli.js`，仅能返回版本号的 wrapper 不足以完成
  MCP 握手。
- 报告“启动 npx 失败”时先检查 AionCore 是否用最新本地源码重新编译、托管 Node 文件是否随包
  更新，以及数据库中的旧 MCP JSON 是否已被启动迁移修复；不要只修改界面提示。

## 离线 PDF skill 运行时

Win7 便携包在构建阶段由 `scripts/prepare-pdf-runtime.js` 下载并校验以下固定组件：

- Python 3.8.10 embeddable x64（最后一代官方支持 Win7 的 Python）；
- `pypdf 5.9.0`、`reportlab 4.2.5`、`Pillow 10.4.0`、`pdf2image 1.17.0`；
- Poppler Windows x64 `23.11.0-0`。

组件会进入 `resources/pdf-runtime/win32-x64/`，并写入 `resources/pdf-runtime/manifest.json`。
manifest 对每个文件记录 SHA-256，`scripts/verify-pdf-runtime.js` 和 `afterPack.js` 会在打包前后
分别校验。Action 网络失败时构建应明确失败，不能生成缺少依赖的“伪离线包”；重跑时已有完整
runtime 会跳过重复下载。下载依赖时可设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`。

PDF skill 和所有 Agent/skill/script 子进程都会收到：
`AIONUI_PYTHON`、`AIONUI_PDF_RUNTIME`、`AIONUI_PDF_POPPLER`、`AIONUI_PYTHON_VERSION`。
因此脚本应优先调用 `$env:AIONUI_PYTHON`，`pdf2image` 应把
`poppler_path=$env:AIONUI_PDF_POPPLER` 传给转换函数，禁止离线包内执行 `pip install`。
OCR/Tesseract、`pdfplumber`、`pypdfium2`、`qpdf`、`pdftk` 等未列入 manifest 的高级能力必须
提示“离线运行时未提供”，不得静默联网下载或伪装成功。

本地验证命令：

```bash
node scripts/verify-pdf-runtime.js
```

Win7 Action 构建会在 `node scripts/build-with-builder.js x64 --win --x64 --win7` 中自动准备、校验并
将该目录放入最终 ZIP；便携包验收时应检查 `resources/pdf-runtime/python.exe`、四个 Python 包、
`poppler/pdftoppm.exe` 和 manifest 哈希均存在。

## 验证清单

在 Windows 构建机运行：

```powershell
.\scripts\verify-win7-compat.ps1 -ExePath .\AionCore\target\x86_64-win7-windows-msvc\release\aioncore.exe
```

至少确认：

1. PE subsystem 不高于 Win7 支持范围。
2. 导入表没有 `ProcessPrng`、`bcryptprimitives.dll`、WinRT 或不兼容的 `combase.dll` 入口。
3. 包内存在 `resources\officecli.exe` 和 runtimeconfig。
4. Win7 SP1 x64 真机可以启动、登录、恢复会话、读写文件并打开 docx/xlsx/pptx 预览。
5. officecli 启动不再出现 `Could not load ICU data. UErrorCode: 2`。

本轮 Linux 便携包已生成：`out/AionUi-2.2.2-win-x64.zip`（SHA-256：`9a33ac7de3fe4995d8e8aba6e0a766a9963ae5bed1111f72f00585e1a4e98e4f`）。包内 AionCore 来自 Action `35503847266`（SHA-256：`b2307725c8f12a2b162ddaeb099a0197d43a184ddc879cccdf673a771b9a002a`）。

PDF runtime 验收记录：Action `35568895115`（提交 `bfa26f175`）生成并上传
`AionUi-windows-x64-portable.zip`；本地副本为
`AionUi-2.2.2-win-x64-pdf-runtime-portable.zip`，SHA-256：
`97e2a0f5f6c800c03f8030769c9666d3305669bb36ac1c887bbb523fc291ec5b`。
ZIP 内 manifest 的 453 个文件哈希全部通过，且包含 Python 3.8.10、四个固定 PDF 包、Poppler、
officecli、AionCore 和 AionUI `AionUi.exe`。

## 相对官方上游的本地改动

以下是需要在后续同步中保留并复核的本地改动；具体代码以当前工作树为准：

- `add01336e`：增加 Win7 兼容目标、lossless context compression 和 Win7 CLI workflow。
- `c17e2f031`：修复 Win7 CLI 的 WinRT `api-ms-win-core-winrt` 依赖。
- `23cdf3c0e`：将 native Win7 路径中的 `combase.dll` 映射到 `ole32.dll`，避免依赖 VxKex。
- `fb293c899`：Win7 下限制 assistant agent 到 aioncli、在 builder 中捆绑 officecli，并修复相关管理页面。
- `scripts/build-with-builder.js`：`--win7` 构建入口、Win7 Electron 自动准备、officecli 资源复制和 x64 打包逻辑。
- `scripts/prepare-win7-electron.js`：固定并下载 Win7 Electron 分发包。
- `scripts/build-win7.ps1`、`scripts/verify-win7-compat.ps1` 及 `.github/workflows/build-win7-cli.yml`：Win7 编译、PE 检查和 CLI 产物流程。
- `packages/desktop/src/process/index.ts`：Windows 进程启动时设置 .NET 的 NLS 兼容环境。
- `AionCore/crates/aionui-office/src/officecli_runtime.rs`：优先解析 PATH、AionUi `resources`、LOCALAPPDATA 安装目录和 Unix 本地目录，不再依赖旧 managed prefix。
- `AionCore/crates/aionui-app/assets/builtin-skills/auto-inject/officecli/SKILL.md`：要求 agent 优先定位 AionUi 内置 officecli，不让用户重复手动安装。
- `packages/desktop/src/process/utils/runBackendMigrations.ts`：内置浏览器 MCP 使用托管 `node` 运行时，`chrome-devtools-mcp` 固定为 `0.16.0`，避免 Windows 下裸 Electron/npx 启动和版本漂移导致握手失败。
- `packages/desktop/src/renderer/pages/settings/components/AddModelModal.tsx`、`useAionrsModelSelection.ts`：思考强度改为可控勾选，并在会话中合并最新模型设置。
- `scripts/build-with-builder.js`：无 Wine 的 Linux 构建也必须保留 PE 资源编辑，禁止因跳过签名而丢失 AionUI 图标。
- `AionCore/crates/aionui-mcp/`、`aionui-ai-agent/`、`aionui-runtime/`：识别旧版 `aionui-browser` Electron 路径并强制走托管 Node；Windows managed Node 必须包含真实 `npm-cli.js`/`npx-cli.js`，不能只保留版本探测 wrapper。
- `scripts/prepare-pdf-runtime.js`、`scripts/verify-pdf-runtime.js`：Action 下载并校验 Win7 Python 3.8.10、PDF wheels 与 Poppler，构建失败时阻止生成不完整离线包。
- `packages/desktop/electron-builder.yml`、`scripts/build-with-builder.js`、`scripts/afterPack.js`：将 PDF runtime 纳入 Windows 资源并在打包后验证文件哈希。
- `AionCore/crates/aionui-app/src/services.rs`、`aionui-conversation/src/service.rs`：把包内 Python/Poppler 路径注入所有 skill/script 子进程环境。
- `client-patches/0001-win7-auth-and-config-sync.patch`、`client-patches/0002-win7-market-and-logs.patch`：客户端 Win7 专用补丁；同步客户端代码时要重新应用并核对上下文。

本轮回归还要求 AionCore 启动 officecli 子进程时显式注入：

```text
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
DOTNET_SYSTEM_GLOBALIZATION_USENLS=1
```

这是为 Win7 缺少 ICU 数据的环境提供的子进程级兜底，不应无审查地扩散到所有平台进程。

桌面主进程也在 Windows 入口设置同样的变量，作为旧版/预编译 AionCore 的继承兜底；重新编译 AionCore 后，Rust 子进程级设置仍是最终作用域。

## 2026-09 回归修复记录

- `AionCore/crates/aionui-office/src/watch_manager.rs`：只给 officecli 子进程注入 ICU invariant 与 NLS 环境变量。
- `resources/officecli.runtimeconfig.json`：开启 `System.Globalization.Invariant`，避免直接启动内置 officecli 时加载 ICU。
- `AionCore/crates/aionui-app/assets/builtin-skills/auto-inject/officecli/SKILL.md`：增加 PowerShell 自动路径解析，不再要求用户手动配置。
- 内置 MCP 回归：Windows `aionui-browser` 通过托管 `node` 启动，`chrome-devtools-mcp` 锁定 `0.16.0`；思考强度设置和会话选择器支持实时同步。
- MCP 启动迁移会修复已有 `chrome-devtools` 数据库记录中的 `@latest` 或旧 JSON，不要求用户手动删除并重新导入。
- aionrs 思考参数回归：`off/low/medium/high` 在后端分别转换为 `disabled/enabled + thinking_budget`，不再把 UI 值直接传给严格的 `--thinking` 解析器。
- MCP Node 回归：补齐 Win32 managed Node 的 npm/npx CLI 文件，并在连接检测、ACP、AionRS 和统一 session 注入入口统一识别浏览器 wrapper。
- Aionrs 上下文用量回归：每轮结束上报当前上下文占用、窗口上限、输入/输出 token 和耗时；桌面指示器只显示环形进度，详情弹层显示平均输出速度（tokens/s）。
- 验证：`cargo test -p aionui-office` 的 104 个单元测试通过；代理集成测试因当前 Linux 环境端口/代理返回 503，未作为本次回归判定依据。

## 同步官方最新源码

## Provider API Key 脱敏回归

- `/api/providers` 的 `api_key` 只返回 `***`，并附带 `api_key_configured` 与 `api_key_count`；明文仅通过受认证的 `/api/providers/:id/credentials` 供运行时使用。
- 编辑 Provider 时提交空值或 `***` 表示保留原 Key，只有主动输入新 Key 才替换；云端 `/api/config` 拉取的 Key 在设置表单中也只显示占位符。
- 已保存 Provider 的模型列表使用 `/api/providers/:id/models`，不把占位符当作真实 Key 发给匿名接口；图像生成 MCP 在同步环境变量时按 Provider ID 解析真实凭据。
- 回归验证：`cargo test -p aionui-system --test provider_routes`、`bunx tsc --noEmit`、`bunx vitest run tests/unit/common-config/modelCapabilities.dom.test.tsx`。

当前仓库的 `origin` 是个人镜像时，先添加官方只读 remote：

```bash
git remote add upstream https://github.com/iOfficeAI/AionUi.git
git fetch upstream --tags
git status --short
git branch --show-current
```

推荐流程：

1. 保留当前工作分支和本地提交，创建 `sync/upstream-<date>` 分支。
2. 在同步分支合并或 rebase `upstream/main`，不要直接改写工作分支历史。
3. 优先解决 Win7 文件和构建脚本的冲突；不能确认语义时保留两侧内容并停下来人工判断。
4. 重新检查本节列出的本地改动，运行普通测试、AionCore office 测试、Win7 兼容检查和打包流程。
5. 记录上游基线、冲突解决和新的 Win7 验证结果，再由用户决定是否合并或推送。

禁止用 `git checkout upstream/main -- <file>` 批量覆盖本地 Win7 文件，也禁止在未验证前删除 `client-patches/`、Win7 workflow 或本地构建脚本。

## 常见故障

- `Could not load ICU data. UErrorCode: 2`：确认 officecli 子进程环境变量和 runtimeconfig，重新打包后再测。
- Electron 启动即崩溃：确认使用 `--win7` 生成的 Electron，而不是普通 Electron x64。
- `LNK1181` 或标准库链接错误：确认 nightly、rust-src、Win7 target 和 MSVC Developer Command Prompt。
- 预览提示找不到 officecli：先检查包内 `resources/officecli.exe`，再检查 `officecli_runtime.rs` 的解析顺序和 packaged backend 的 current executable 路径。
- 包能编译但 Win7 不能启动：以真实 Win7 的 DLL/API 诊断为准，不要只根据 Cargo 或 electron-builder 成功下结论。
