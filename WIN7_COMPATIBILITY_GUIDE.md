# Windows 7 兼容性改造指南

> 基于 AionUI + AionCore (Electron + Rust) 的 Win7 移植实践，总结通用改造方法论。

---

## 一、问题定位框架

### 1.1 依赖层级分析

```
应用层 (UI Framework)        <- Electron / Tauri Webview
运行时层 (Runtime)           <- Node.js / Rust std
系统层 (Win32 API)           <- kernel32 / bcrypt / winrt
硬件层 (CPU / Instruction Set) <- SSE4.2, AVX (较少问题)
```

### 1.2 常见问题模式

| 层级 | 典型症状 | 诊断方法 |
|------|---------|---------|
| 链接阶段 | `LNK1181: cannot open file` | 检查 `.lib` 路径、SDK 版本 |
| 链接阶段 | `LNK2019: unresolved external symbol ProcessPrng` | `dumpbin /dependents` 查看导入表 |
| 运行时 | `DLL not found` | 在 Win7 机器抓取加载日志 |
| 运行时 | `API not found` | `api-ms-win-*` 前缀检查 |
| Electron | `STATUS_ACCESS_VIOLATION` | 检查 Electron 版本是否为 Win7 build |
| Native Module | `Module version mismatch` | `npm rebuild --build-from-source` |

---

## 二、核心解决方法

### 2.1 Rust: Tier 3 目标 + 自编译标准库

适用场景: Rust 项目依赖的 crate 调用了 Win10+ API (如 `bcryptprimitives.dll`, `ProcessPrng`).

```bash
# Step 1: 安装 nightly toolchain 和 rust-src 组件
rustup install nightly
rustup component add rust-src --toolchain nightly

# Step 2: 使用 Tier 3 目标编译
cargo +nightly build --release \
  --target x86_64-win7-windows-msvc \
  -Zbuild-std \
  -p <binary-crate>
```

原理:
- `x86_64-pc-windows-msvc` (Tier 1) 编译的 std 包含 Win10+ API 调用
- `x86_64-win7-windows-msvc` (Tier 3) 定义了 `_WIN32_WINNT=0x0601`，限制 API 不超过 Win7 SDK
- `-Zbuild-std` 从源码编译标准库，确保不引入 Tier 1 std 中的 Win10+ 调用

关键验证:
```bash
# 检查 PE 子系统版本 (Win7 = 6.00)
dumpbin /headers app.exe | findstr "6.00"

# 检查是否引用 Win10+ API (应无输出)
dumpbin /dependents app.exe | findstr "ProcessPrng bcryptprimitives"
```

### 2.2 修复链接器库路径

适用场景: Tier 3 目标的 `.lib` 文件不在默认路径，MSVC linker 找不到 (LNK1181).

```toml
# .cargo/config.toml
[target.x86_64-win7-windows-msvc]
rustflags = ["-C", "link-arg=/LIBPATH:C:\\Users\\<user>\\.rustup\\toolchains\\nightly-x86_64-pc-windows-msvc\\lib\\rustlib\\x86_64-win7-windows-msvc\\lib"]
```

验证路径存在:
```bash
ls ~/.rustup/toolchains/nightly-x86_64-pc-windows-msvc/lib/rustlib/x86_64-win7-windows-msvc/lib/windows.0.*.lib
```

### 2.3 替换问题依赖 (源码级)

适用场景: 第三方 crate 引入了 Win10+ API (如 `trash` crate 使用 WinRT).

#### 识别问题依赖

```bash
# 查看二进制导入的所有 DLL
dumpbin /dependents target/x86_64-win7-windows-msvc/release/app.exe

# 搜索 Win10+ 特有 API
dumpbin /imports target/x86_64-win7-windows-msvc/release/app.exe | findstr "ProcessPrng"
```

#### 替换策略

方案 A: 条件编译 (推荐)
```rust
#[cfg(target_os = "windows")]
fn trash_delete(path: &Path) -> Result<()> {
    if is_win7_or_older() {
        // Win7 fallback: 使用标准库
        if path.is_dir() {
            std::fs::remove_dir_all(path)?;
        } else {
            std::fs::remove_file(path)?;
        }
    } else {
        // Win10+: 使用 trash crate
        trash::delete(path).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    }
    Ok(())
}
```

方案 B: feature flag 替换整个 crate
```toml
# Cargo.toml
[dependencies]
trash = { version = "5", optional = true }

[features]
default = ["trash"]
win7-compat = []  # 启用时禁用 trash，使用 std::fs
```

#### 识别 Win10+ API 的方法

```bash
# 1. dumpbin 检查导入表
dumpbin /imports app.exe | findstr /i "api-ms-win-core-winrt"

# 2. 在依赖树中搜索 WinRT / WindowsApp
cargo tree --edges normal -p <crate> | findstr -i "winrt"

# 3. grep 源码搜索可疑 API 调用
rg "ProcessPrng|BCryptGenRandom|WinRT|IUnknown" --type rust target/
```

### 2.4 替换运行时 (Electron / Node.js)

适用场景: 默认 Electron/Node.js 在 Win10+ 上编译，引用了 Win10+ API.

#### Electron

```bash
# 使用社区维护的 Win7 兼容 Electron
# 仓库: https://github.com/e3kskoy7wqk/Electron-for-windows-7
# 下载对应版本的 dist.zip

# 构建时指定自定义 Electron 路径
npx electron-builder --config.electronDist="../electron-win7/dist"
```

#### Node.js

```bash
# 使用 AionCore 内置的 managed-resources
cargo +nightly run --release --target x86_64-win7-windows-msvc -- prepare-managed-resources

# 或使用独立的 Win7 兼容 Node.js
# https://github.com/nicedoc/node-builds (node-win7-x64 分支)
```

关键: Electron/Node.js 自身不含 Win10+ 硬依赖，但 Chromium 引擎在 Win7 上需特殊构建。

### 2.5 Native Modules 重编译

适用场景: `.node` 动态库版本不匹配 (electron-rebuild) 或包含 Win10+ API 调用.

```bash
# electron-rebuild 根据目标 Electron 版本重编译所有 native modules
npx electron-rebuild --force --module-dir ./packages/desktop

# Node.js 原生模块 (如 better-sqlite3)
npm rebuild better-sqlite3 --build-from-source

# 验证生成的 .node 文件
dumpbin /dependents node_modules/.node/better_sqlite3.node | findstr "api-ms-win"
```

### 2.6 VC++ Redistributable 依赖

适用场景: MSVC 运行时 DLL 缺失 (`VCRUNTIME140.dll` 等).

```bash
# 方案 A: 静态链接 MSVC 运行时 (推荐)
# 在 .cargo/config.toml 中添加
# [target.x86_64-win7-windows-msvc]
# rustflags = ["-C", "target-feature=+crt-static"]
# 注意: 仅适用于纯 Rust 项目，与 C/C++ 混编时需额外配置

# 方案 B: 打包 VC++ Redistributable (推荐)
# 下载 vc_redist.x64.exe 并在安装包中捆绑
# https://aka.ms/vs/17/release/vc_redist.x64.exe

# 方案 C: 手动复制 DLL
copy C:\Windows\System32\VCRUNTIME140.dll .\dist\
```

---

## 三、验证清单

### 3.1 编译阶段验证

```bash
# [ ] PE 子系统版本检查 (Win7 = 6.00)
dumpbin /headers app.exe | findstr "6.00"

# [ ] 无 Win10+ API 导入
dumpbin /dependents app.exe | findstr "ProcessPrng bcryptprimitives WinRT"

# [ ] 所有 DLL 存在于 Win7 系统
dumpbin /dependents app.exe | findstr "api-ms-win"

# [ ] .lib 路径正确 (LNK1181)
# 编译时应无 LNK1181 错误
```

### 3.2 运行时验证

```bash
# [ ] 在 Win7 SP1 x64 机器实际运行
# [ ] 应用启动无 DLL 报错
# [ ] 核心功能正常 (数据库、文件操作、网络请求)
# [ ] 文件删除/回收站功能正常 (trash fallback)
# [ ] 子进程启动正常 (Electron + Node.js)
```

### 3.3 打包验证

```bash
# [ ] 安装包大小合理 (不应显著大于 Win10 版本)
# [ ] 安装过程无报错
# [ ] 安装后无需额外 DLL 文件
# [ ] 自动更新功能正常 (如已保留)
```

---

## 四、常见陷阱

| 陷阱 | 规避方法 |
|------|---------|
| `trust-cache.dll` 重定向系统 DLL | 确保所有依赖是原生 Win7 DLL，非重定向版本 |
| `VCRUNTIME140.dll` 缺失 | 打包 VC++ Redistributable 或使用 `crt-static` |
| `bcryptprimitives.dll` 崩溃 | Tier 3 target + `-Zbuild-std` 避免调用 |
| Electron 自动更新拉取新版 | 构建产物禁用自动更新，固定 Electron 版本 |
| Node.js 子进程加载不同 DLL | `managed-resources` 中的 Node 也需 Win7 兼容 |
| `workspace:*` 依赖无法 npm install | 使用 bun 或手动处理 workspace 协议 |
| `cargo tree` 显示正常但运行时崩溃 | `dumpbin` 检查实际 PE 导入表，非 Cargo.toml |
| 多个 crate 依赖不同版本的 `windows-rs` | 统一 `windows-rs` 版本，检查 `Cargo.lock` |
| `cargo build` 成功但 binary 不兼容 | 务必在 Win7 机器上实际运行测试 |

---

## 五、改造流程图

```
开始
  |
  |-- 1. 分析项目技术栈
  |     |-- Rust? -> 使用 Tier 3 target
  |     |-- Electron? -> 下载 Win7 Electron
  |     +-- Node.js? -> 使用 managed-resources
  |
  |-- 2. 编译 (使用 Win7 目标)
  |     |-- 成功 -> 进入步骤 3
  |     +-- 失败 -> 检查 LNK 错误
  |           |-- LNK1181 (.lib 找不到) -> 修复 .cargo/config.toml
  |           |-- LNK2019 (未解析符号) -> 检查依赖引入的 Win10+ API
  |           +-- 其他 -> 查看完整错误信息
  |
  |-- 3. 验证二进制 (dumpbin)
  |     |-- 无 Win10+ API -> 进入步骤 4
  |     +-- 有 Win10+ API -> 替换问题依赖 (条件编译/feature flag)
  |
  |-- 4. 打包 (electron-builder + 自定义 Electron)
  |     |-- 成功 -> 进入步骤 5
  |     +-- 失败 -> 检查 electron-builder 日志
  |
  |-- 5. Win7 实际运行测试
  |     |-- 启动正常 -> 完成
  |     +-- 启动失败 -> 检查 DLL 依赖
  |           |-- 缺失 DLL -> 打包进安装包
  |           +-- API 不存在 -> 返步骤 3
  |
  +-- 完成
```

---

## 六、工具依赖

| 工具 | 用途 | 获取方式 |
|------|------|---------|
| rustup | Rust 工具链管理 | https://rustup.rs |
| nightly toolchain | Tier 3 target 支持 | `rustup install nightly` |
| rust-src | 自编译标准库 | `rustup component add rust-src` |
| VS Build Tools | MSVC linker | Visual Studio Installer |
| dumpbin | PE 文件分析 | VS Build Tools 自带 |
| electron-builder | 打包 Electron 应用 | `npm install -D electron-builder` |
| bun | workspace 依赖安装 | https://bun.sh |
| Win7 Electron | 兼容运行时 | https://github.com/e3kskoy7wqk/Electron-for-windows-7 |

---

## 七、追加:Win7 实测补充 (2026-09 回归)
> 本段由真实 Win7 机器实测反馈整理,逐项标注**凭据**(仓库内已有文件/命令)或**待补证**(尚未在真机二次确认)。
### 7.1 HTTP(S) 通道与本地服务商 (127.0.0.1:8080)
场景: 外部模型服务商 API 以本地回环地址运行 (如 `127.0.0.1:8080`),首个请求出现约 30 秒延迟、之后即时恢复。
- 凭据1 (前端通道自适应): `AionUi/packages/desktop/src/renderer/.../aionrs` 的发送盒与 bridge 依 `window.location.protocol` 在 `ws`/`wss` 间切换;`httpBridge.ts:63`。纯 HTTP 场景走 `127.0.0.1:8080` 时**不应**因 TLS/证书引发 30s——若有自签证书需求需另配 (`browser.ts:76` 同思路)。
- 待补证: 30s 归属后端 (build/stats/预热) 或首条 stream 的冷启动路径,文档不臆断。
- 检查命令:
  ```bash
  # 确认 AionUi 到本地服务的连接协议(非自签时 wss 会退化)
  rg "window.location.protocol" AionUi/packages/desktop/src/renderer
  ```
### 7.2 内置 officecli (办公能力内置)
仓库已内置 `officecli` 二进制 (`officecli-win-x64.exe`,仓库根),桌面端在启动管线中引导:
- 凭据2: `AionUi/packages/desktop/src/process/startup/officecliBootstrap.ts` — "Bootstrap bundled officecli binary"。
- 用途: 办公文件预览/转换 (Office 兼容) 的本地服务,不依赖外部云。
- Win7 注意:
  - `officecli-win-x64.exe` 必须通过 `dumpbin /dependents` 检查不含 Win10+ 导入 (参考第二章 2.3)。
  - 打包时必须把该二进制放入 `dist` 资源目录 (`electron-builder extraResources`),否则 Win7 上启动即缺失。
### 7.3 AionCore (Rust 后端) Win7 兼容点
- 凭据3 (构建/验证脚本已在仓库): `scripts/build-win7.ps1`、`scripts/verify-win7-compat.ps1`、`x86_64-win7-windows-msvc` 目标(`-Zbuild-std`)。
- 原则: 所有 Rust 后端 crate 一律用 Tier3 Win7 目标编译;错误定位用 `dumpbin /dependents` 而非仅看 Cargo.toml (第二章 2.1)。
- 待补证: 具体 crate 层 API 替换的最终清单,待真机全量回归后回填。
### 7.4 回归清单 (Win7 真机逐项勾选)
| # | 检查项 | 命令/凭据 |
|---|--------|----------|
| 1 | AionUi 启动无 DLL 缺失 | 见 3.2 |
| 2 | 本地 127.0.0.1:8080 首个请求计时 | 见 7.1 |
| 3 | officecli 内置服务可启动 | 见 7.2 |
| 4 | AionCore 二进制无 Win10+ 导入 | `dumpbin /dependents aioncore.exe` |
| 5 | 预览/转换办公文件成功 | 7.2 功能点 |
*追加版本: 0.1 | 2026-09-16*

### 7.5 agent只保留aioncli，其他agent选项都在ui删除
---

*文档版本: 1.0 | 基于 AionUI 2.1.59 + AionCore (2026-08-19)*
