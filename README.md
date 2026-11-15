# GINKA · REDMI Watch 5 移植版 (`ginka-rw5`)

《GINKA》面向 **REDMI Watch 5**（小米 Vela QuickApp，屏幕分辨率 `432×514`）的纯图文剧情阅读与 CG 鉴赏移植工程。

- **包名**：`com.antigravity.ginka.rw5`
- **当前最新版本**：`0.1.2`（`versionCode: 3`）
- **交付包下载**：前往 [Releases (v0.1.2)](https://github.com/xuanyide01/ginka-rw5/releases/tag/v0.1.2) 或直接查看 [`dist/`](./dist) 目录：
  - `com.antigravity.ginka.rw5.debug.0.1.2.rpk`（`9,652,897` 字节，约 `9.21 MiB`）
  - `com.antigravity.ginka.rw5.debug.0.1.2.bin`（`9,652,897` 字节，约 `9.21 MiB`）

---

## 功能特性

- **完整剧本与章节分支**：
  - 覆盖本篇剧情（`scn000 – scn015`）、`NEXT` 篇章（`scn101 – scn114`）、分支结局（`scn901 – scn904`）及 `AFTER` 篇章，保留关键选项与渐进式解锁逻辑。
  - 支持在菜单中执行 **下一章** 跳转，且停在选项节点时同步对齐对应背景 CG 与人物立绘；`EXTRA` 内提供分级 **篇章选择 / 章节选择** 目录试读（不修改主线解锁进度）。
- **轻量纯图文适配（< 10 MB）**：
  - 去除全部音视频文件与音量 UI 开关，保留 32 组 / 134 张基础 CG 与差分、432×243 背景图及角色立绘缓存管理（有限块缓存与离开清理）。
- **标题界面与存档系统**：
  - 适配手表竖屏布局的标题视觉裁切、应用封面图标及随通关进度切换的标题背景；
  - 提供 **30 个存档位**，支持覆盖确认以及长按 / 600ms 触控保持删除确认（滑动取消误触发）。
- **阅读体验与交互**：
  - 支持 **逐字 / 即时** 两种文本显示速度与多档自动播放速度、标准（`24px`）/ 大号（`28px`）字号切换。
  - 文本框内滑动后提供防误触保护；当文本内容超出 156px 显示区域时，姓名栏右侧自动出现紧凑 `上` / `下` 滚动控制按钮。
- **CG 鉴赏画廊**：
  - 支持 32 组 / 134 张基础 CG 及其差分浏览，点击大图可切换差分；
  - 右侧原生垂直 `<slider>` 滑块与 `+` / `-` 按钮支持 **`1.0x – 2.5x`** 缩放，放大后可在视口内手指拖动看图并带有边界钳制与防误切差分保护。

---

## 目录结构

```text
ginka-rw5/
├── src/                  # QuickApp 前端页面与资源（index.ux、manifest.json、图像与子集字体）
├── tests/                # 剧情引擎与 UI 逻辑单元测试（engine.test.mjs、ui.test.mjs）
├── tools/                # 剧本编译、资源预处理、打包构建与校验脚本
├── converted/            # 转换映射与资源清单数据
├── reports/              # 资源预算与布局规划报告
├── dist/                 # 最终构建产物（.rpk / .bin）
├── HANDOFF.md            # 阶段 0 解密与资源盘点交接说明
└── package.json
```

---

## 本地测试与构建

> 构建工具链要求：`Node.js`、`Python 3` 与 **`aiot-toolkit 1.1.0`**。

```bash
# 运行引擎与 UI 自动化测试
node --test tests/engine.test.mjs tests/ui.test.mjs

# 编译并重打包输出 .rpk 与 .bin 至 dist/
node tools/build.cjs

# 校验包体积、签名、ZIP CRC 与资源完整性
python tools/audit_package.py
```

### `0.1.2` 构建实测记录
- **自动化测试**：`20 pass / 0 fail / 0 skipped`。
- **包体积**：`9,652,897` 字节（展开后 `11,157,774` 字节，`1,123` 个条目，`1,090` 个签名文件）。
- **包校验**：ZIP CRC、内外签名与文件摘要校验全部通过（SHA-256: `cc5eb438f3f98e445a29c17104e8577f4049254c875813b9346e397676a57af0`）。
- **说明**：交互与界面渲染主要在 REDMI Watch 5 规格的 Vela 模拟器中验证，尚未在物理手表真机上实测。

---

## 安装说明

请根据你的手表刷入方式选择 [Releases](https://github.com/xuanyide01/ginka-rw5/releases/tag/v0.1.2) 或 [`dist/`](./dist) 中的 `.rpk` / `.bin` 包安装。若覆盖安装或升级后出现异常，可先卸载旧版 `com.antigravity.ginka.rw5` 后重新安装。
