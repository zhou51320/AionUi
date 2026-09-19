# AionUi Agent Rules

本文件只定义仓库协作规则；Windows 7 的具体改造清单、构建命令、验证记录和上游同步步骤见 [WIN7_LOCAL_MAINTENANCE.md](WIN7_LOCAL_MAINTENANCE.md)。通用兼容性背景仍可参考 [WIN7_COMPATIBILITY_GUIDE.md](WIN7_COMPATIBILITY_GUIDE.md)。

## 基本要求

- 默认使用中文回复，除非用户明确要求其他语言。
- 回复简洁直接；开始长任务前说明当前阶段，完成后给出可复现的验证结果。
- 破坏性操作、修改共享环境、删除文件、推送远程或覆盖用户改动前，先确认范围；用户已明确授权的正常实现步骤可直接执行。
- 保留用户已有改动和未跟踪构建产物；不要使用 `git reset --hard`、`git checkout --` 或宽范围删除命令。
- 网络访问、拉取依赖或源码失败时，优先使用代理 `http://192.168.2.254:7890`，可设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`。
- 时间显示统一使用中国北京时间；在不受宿主机时区控制的命令中显式设置 `TZ=Asia/Shanghai`。
- 飞牛 NAS 通过 `/bin/bash` 登录 shell；NAS 地址与 fn-knock 运维约定见用户环境说明。

## 代码规范

- 新目录优先保持不超过 10 个直接子项；创建文件或模块时遵循 `.claude/skills/architecture/SKILL.md`。
- 组件使用 PascalCase，工具/Hook 使用 camelCase，常量值使用 `UPPER_SNAKE_CASE`；未使用参数以 `_` 开头。
- UI 使用 `@arco-design/web-react` 和 `@icon-park/react`，不得新增原生交互元素。
- 样式优先 UnoCSS；复杂样式使用 CSS Modules。颜色使用语义 token 或 CSS 变量。
- TypeScript 开启 strict：禁止 `any`、隐式返回和无意义类型断言；优先 `type` 而非 `interface`。
- 新增或修改用户可见文本必须使用 i18n；涉及 renderer、locales 或 i18n 配置时运行 i18n 类型生成和检查。
- Main 进程只能使用 Node/Rust 能力，Renderer 不得直接使用 Node.js；跨进程通信只能通过 preload IPC bridge。

## 测试与交付

- 修改运行时行为或修复 bug 必须补充/更新聚焦测试，并覆盖至少一个失败路径。
- 常规验证顺序：

  ```bash
  bun run lint:fix
  bun run format
  bunx tsc --noEmit
  bun run test
  ```

- 不要代替用户推送。用户明确要求推送时使用 `just push`，不要直接执行 `git push`。
- 提交信息遵循 Conventional Commits；不得添加 AI 署名。

## Windows 7 目标规则

- Win7 目标是 Windows 7 SP1 x64；不得把普通 Windows x64 构建冒充 Win7 构建。
- 桌面包必须使用仓库脚本选择的 Win7 Electron（`--win7`，当前版本由 `scripts/prepare-win7-electron.js` 固定），Rust AionCore 使用 `x86_64-win7-windows-msvc` 与 nightly `-Zbuild-std`。
- 内置 `officecli.exe` 必须随包放在 `resources/`，不得要求用户手动安装或手动填写路径。Win7 子进程需要 invariant globalization 与 NLS 环境变量。
- Windows 可执行文件必须使用仓库 `resources/app.ico` 的 AionUI 图标；禁止用 `signAndEditExecutable=false` 跳过 PE 资源编辑而产生 Electron 默认图标。具体校验和打包说明见 `WIN7_LOCAL_MAINTENANCE.md`。
- 内置 MCP 依赖托管 Node；Win7 包内必须包含真实 npm/npx CLI（`node_modules/npm/bin/npm-cli.js`、`npx-cli.js`），不得用只能返回版本号的 wrapper 冒充运行时。
- Win7 构建完成后必须运行 PE/导入表检查，并在真实 Win7 SP1 x64 环境验证启动、登录、会话、文件预览和 officecli。
- 详细命令、产物命名、当前相对官方上游的补丁和回归记录统一维护在 `WIN7_LOCAL_MAINTENANCE.md`；修改 Win7 行为时同步更新该文档。

## 上游同步规则

- 官方上游为 `https://github.com/iOfficeAI/AionUi.git`；当前 `origin` 可能是个人镜像，不得假定其等同官方。
- 拉取官方最新源码前先保存工作区状态、记录本地分支和 Win7 产物；优先在独立同步分支执行 `git fetch upstream`、合并或 rebase。
- 不得用官方版本覆盖本地 Win7 专用改动。至少保留并逐项复核：Win7 Electron 构建入口、Tier 3 Rust 目标、WinRT/combase 兼容修复、officecli 内置资源与解析、Win7 验证脚本、客户端 Win7 补丁。
- 解决冲突时以可运行的 Win7 目标和现有回归测试为验收标准；同步后重新运行普通测试、Win7 兼容检查和打包验证，再合并回工作分支。
- 上游同步不自动推送、不自动发布；需要删除旧产物或覆盖版本时先确认。

## 文档与文件变更

- `AGENTS.md` 只放规则和不可遗漏的约束；具体方案、命令、补丁清单和排障记录写入独立 Markdown 文档。
- `docs/superpowers/` 是本地忽略目录，不得强制加入提交。
- 修改前先查看 `git status --short`，完成后再次检查差异，确保未误改用户文件。
