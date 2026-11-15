# 《GINKA》→ REDMI Watch 5 移植工程交接文档（HANDOFF）

> 生成时间：2026-10-30（阶段 0 盘点收尾）  
> 当前阶段：**阶段 0（资源解密与全量盘点）已完成，尚未进入阶段 1（未编写任何手表端应用代码）**

---

## 1. 目标与约束

### 1.1 目标设备与产物规格
- **包名**：`com.antigravity.ginka.rw5`
- **目标机型与分辨率**：仅适配 **REDMI Watch 5**，屏幕物理分辨率 **`432×514`**。
- **构建工具链**：固定使用 **`aiot-toolkit 1.1.0`**（严禁升级版本）。
- **移植范围**：基础版剧情与基础 CG 阅读器。
- **多媒体裁剪硬约束**：
  - **不做 OP/ED 动画**：不转码、不抽帧、不在应用内播放任何影片（`OP.wmv`、`ED1.wmv`、`ed2.wmv` 及 `AJPM` 动画均跳过）。
  - **不做任何音频**：不含标题曲、BGM、音效（SE）、角色语音（JP/EN）及系统语音；**应用 UI 中严禁出现任何声音/音量开关**。
- **包体与条目硬预算**：
  - **包体大小**：目标 **约 `10 MB`**；硬上限 **`25,000,000` 字节**。
  - **RPK 条目数**：目标 **`≤ 4,100` 条**（设备安装器实测：`4,156` 条可正常安装，`4,177` 条报 `rpkpackage -19`）。

### 1.2 工作区与只读红线
- **唯一可写工作区**：`E:\Antigravity`（所有脚本、下载工具、中间探针产物、报告与后续工程文件均必须位于此目录内）。
- **严格只读目录（严禁修改、移动或写入任何文件）**：
  - 原作目录：`G:\SteamLibrary\steamapps\common\GINKA`（**严禁运行 `GINKA.exe`、严禁执行任何 `.bat`、严禁改动存档**）。
  - 参考工程与产物：`D:\codex\2026-10-26\senren-rw5`（千恋＊万花 RW5 0.1.13）、`C:\Users\HP\Documents\Codex\2026-10-08\zhe\outputs`（含 ATRI / PARQUET / 千恋＊万花交付包与源码参考）。

---

## 2. 已完成的工作与产物路径

### 2.1 工作流里程碑总览
1. **XP3 原始索引探测**：扫描原作全部 9 个 `.xp3` 归档（共 **`17,099`** 条原始记录），确认全部采用 KiriKiri Z **CxdecV2 + `Hxv4`** 加密与文件名哈希混淆（标准解析下仅 `data.xp3` 索引 1 的诱饵 `startup.tjs` 为明文文件名，其余均为 `倀/倁/倂…` 私用区/CJK 单字符内部 ID）。
2. **`Hxv4` 索引区块提取与独立解密**：从 `lifegpc/msg-tool`（`crypt.json` + `cx.rs`）获取《GINKA》精确 `Hxv4` 参数，纯静态提取 9 个归档的 `Hxv4` 块（共约 `712 KB`）并在本地完成 Argon2i v1.3 + HChaCha20 + ChaCha20Legacy 派生与索引表解密，实现 `17,098 / 17,099` 原始条目一对一映射（唯一未入 `Hxv4` 表者即诱饵 `startup.tjs`）。
3. **全归档流解密、魔数分类与 Adler-32 校验**：编写并编译原生 C# 工具 `GinkaHxv4Tool.exe`（实现 `Xoroshiro128StarStar` 随机流过滤器与分块解密），完成全部 **9 个归档 `17,099` 条目**魔数探测与图像宽高/位深/透明通道提取；抽检并解包的 **`1,528 / 1,528` 条目 Adler-32 校验 100% 通过（0 误差）**，按需解包 **`1,429`** 个非音频/小体积关键文件。
4. **全量脚本/配置/字典/字节码解码**：对解包的 `1,429` 个文件执行二次解码（`SimpleCrypt \xfe\xfe` 文本、`TJS/ns0\0` UI 字典、`TJS/4s0\0` ChaCha+LZ4 立绘 `.pbd` 图层表、`TJS2100\0` 字节码字符串池、`MDF` 压缩壳、`PSB v3` `.ks.scn` 反编译）。
5. **目录与文件名哈希碰撞恢复**：基于全量解码语料 + 规则派生展开 SipHash-2-4（目录）与 BLAKE2s-256（文件名）碰撞：
   - **目录哈希（`path_hash`）**：**`31 / 31`（100.00%）全部恢复**（`explore_name_sources.py` 命中全部 31 个含 `anim/`；`resolve_hxv4_names.py` 命中 30 个 + 已知 `3e5e6fe060319f55 = anim/`）。
   - **真实 `Hxv4` 条目文件名**：**`16,579 / 17,089`（97.02%）已恢复真实文件名**（唯一文件哈希 `16,397 / 16,893`，97.06%）；其中**核心剧本 `.ks.scn`（100%）、事件 CG `cr_event.xp3`（100%）、立绘 `.pbd`（100%）、`fgimage.xp3`（100%）、`steam.xp3`（100%）均已 100% 还原**。

### 2.2 核心产物路径索引

| 类别 | 路径 | 说明 |
| :--- | :--- | :--- |
| **交接文档** | `E:\Antigravity\ginka-rw5\HANDOFF.md` | 本文档（阶段 0 收尾交接） |
| **阶段 0 正式报告** | `E:\Antigravity\reports\phase0\PHASE0_REPORT.md` | 阶段 0 全量盘点报告、体积预算与未命名资源替代方案 |
| **XP3 原始索引** | `E:\Antigravity\reports\phase0\raw_xp3_summary.json`<br>`E:\Antigravity\reports\phase0\<arc>.xp3.raw_entries.json` (×9)<br>`E:\Antigravity\reports\phase0\data__startup.tjs.bin` | 9 个归档标准 XP3 头部/索引块摘要、逐条目偏移/大小/Adler-32，以及 316 B 诱饵 `startup.tjs` |
| **Hxv4 密钥与解密表** | `E:\Antigravity\reports\phase0\ginka_hxv4_scheme.json`<br>`E:\Antigravity\reports\phase0\hxv4_index_summary.json`<br>`E:\Antigravity\reports\phase0\hxv4_decrypted_tables.json` | 派生的 `Hxv4` 密钥组（`key`/`iv`/`index_key1`/`index_key2`）与全部 `17,098` 条 `Hxv4` 记录（`pathHash`/`fileHash`/`id`/`key`） |
| **全量魔数与探测表** | `E:\Antigravity\reports\phase0\probed_archives_summary.json`<br>`E:\Antigravity\reports\phase0\<arc>.xp3.probed_entries.json` (×9) | 全 9 归档魔数分类、图像宽高/色深/Alpha、Adler-32 校验结果 |
| **二次解码统计与映射** | `E:\Antigravity\reports\phase0\decode_extracted_summary.json`<br>`E:\Antigravity\reports\phase0\bin_refine_map.json` | 文本/PSB/NS0/PBD/TJS2/MDF 解码统计及 130 个 `.bin` 细分类型表 |
| **未命名条目诊断表** | `E:\Antigravity\reports\phase0\unmatched_diagnostic.json` | 剩余未命中 `fileHash` 条目的按归档/目录/魔数分类样本 |
| **探针与解包缓存** | `E:\Antigravity\probe\`（详见 `E:\Antigravity\probe\README.md`） | `hxv4_chunks/`、`extracted/`（1,429 文件）、`decoded/`（解码后的 JSON/TXT/PSB） |
| **第三方参考与工具** | `E:\Antigravity\tools\downloads\`（详见 `E:\Antigravity\tools\downloads\README.md`） | `FreeMote` v4.9.0、`GARbro-Mod` 1.0.2.2、`msg-tool` 与 `hxv4_unhash_tools` 算法源码参考 |

---

## 3. 每个脚本的用途与复现命令

> **执行环境说明**：默认在 `E:\Antigravity` 工作区下使用 PowerShell 执行。除 **仅有的两步只读访问 `G:\SteamLibrary\steamapps\common\GINKA`**（及首次联网下载）在沙盒外需要读取权限外，其余所有解密、反编译、哈希碰撞脚本均 `100%` 仅读写 `E:\Antigravity` 内部文件。

### 3.1 `E:\Antigravity\tools\probe_xp3_headers.py`
- **用途**：只读扫描 `G:\SteamLibrary\steamapps\common\GINKA` 下 9 个 `.xp3` 的文件头、段落表与原始索引块，导出 `<arc>.xp3.raw_entries.json`、`raw_xp3_summary.json` 及明文诱饵 `data__startup.tjs.bin`。
- **复现命令**（需可读 `G:\`）：
  ```powershell
  python E:\Antigravity\tools\probe_xp3_headers.py
  ```

### 3.2 `E:\Antigravity\tools\query_github_hxv4.py` 与 `E:\Antigravity\tools\download_tools.py`
- **用途**：查询并下载开源逆向参考与离线工具至 `E:\Antigravity\tools\downloads\`（含 `GARbro-Mod-1.0.2.2.zip`、`Ulysses-FreeMoteToolkit-v4.9.0.zip`、`lifegpc/msg-tool` 的 `crypt.json`/`cx.rs`、`MLChinoo/hxv4_unhash_tools` 的 `krkr_hxv4_hash.py`），生成 SHA-256 清单 `download_manifest.json`。（文件已在本地就绪，无需重复运行。）
- **复现命令**（仅缺包重拉时需联网）：
  ```powershell
  python E:\Antigravity\tools\query_github_hxv4.py
  python E:\Antigravity\tools\download_tools.py
  ```

### 3.3 `E:\Antigravity\tools\hxv4_crypto.py`
- **用途**：纯 Python 实现完整的 `Hxv4` 密码学原语（Argon2i v1.3 3-lane 内存硬化、SHA3-224、SHAKE-256、FNV+BLAKE2s 轮转、`HChaCha20`、`ChaCha20Legacy`、SipHash-2-4 `calculate_path_hash`、BLAKE2s-256 `calculate_file_hash`、`TJS/ns0\0` 二进制序列化解析器），内置 `msg_tool_cx.rs` 官方测试向量自检，并输出 `ginka_hxv4_scheme.json`。
- **复现命令**：
  ```powershell
  python E:\Antigravity\tools\hxv4_crypto.py
  ```

### 3.4 `E:\Antigravity\tools\fetch_hxv4_chunks.py`
- **用途**：只读从 `G:\SteamLibrary\steamapps\common\GINKA` 提取全部 9 个 `.xp3` 尾部的原始 `Hxv4` 控制块（共约 `712 KB`）及两个微型归档（`fgimage.xp3`、`steam.xp3`）到 `E:\Antigravity\probe\hxv4_chunks\`。
- **复现命令**（需可读 `G:\`）：
  ```powershell
  python E:\Antigravity\tools\fetch_hxv4_chunks.py
  ```

### 3.5 `E:\Antigravity\tools\decrypt_all_hxv4_indices.py`
- **用途**：离线解密 `probe\hxv4_chunks\` 中全部 9 个归档的 `Hxv4` 索引表（自动处理 `flags=0` 使用 `index_key2`、`flags=1` 补丁包使用 `index_key1`），与标准 XP3 原始条目按 `id = ((flags << 16) | idx) + 0x5000` 关联，输出 `hxv4_decrypted_tables.json` 与 `hxv4_index_summary.json`，同时解密 `fgimage.xp3` / `steam.xp3` 的 5 个小文件至 `probe\tiny_decrypted\`。
- **复现命令**：
  ```powershell
  python E:\Antigravity\tools\decrypt_all_hxv4_indices.py
  ```

### 3.6 `E:\Antigravity\tools\inspect_tiny_decrypted.py` 与 `E:\Antigravity\tools\seed_unhash_check.py`
- **用途**：
  - `inspect_tiny_decrypted.py`：解码 `fgimage.xp3`（3 个 `SimpleCrypt` 文本：`emotion.txt`、`facezoom.csv`、`standPosition.txt`）与 `steam.xp3`（2 个 `TJS2100` 字节码）至 `probe\tiny_decoded\`。
  - `seed_unhash_check.py`：用 `GARbro-Mod/GameData/*.lst` 及参考工程词表做首轮哈希碰撞基线测试（命中 27/31 目录与首批 2,001 个通用文件名）。
- **复现命令**：
  ```powershell
  python E:\Antigravity\tools\inspect_tiny_decrypted.py
  python E:\Antigravity\tools\seed_unhash_check.py
  ```

### 3.7 `E:\Antigravity\tools\GinkaHxv4Tool.cs` 与 `E:\Antigravity\tools\GinkaHxv4Tool.exe`
- **用途**：高性能原生 C# 工具（实装完整 CxdecV2 `Hxv4` 流解密、`Xoroshiro128StarStar` 随机跳转表与 `filterKey=0x405a265e53a275d7` 头部异或还原）。只读遍历 `G:\` 全部 9 个 `.xp3` 的 `17,099` 个条目：探测魔数、解析 PNG/TLG5/JPEG 宽高与 Alpha 通道、校验 `1,528` 个条目的 `Adler-32`，并将 `1,429` 个脚本/配置/PSB/PBD/样张提取到 `E:\Antigravity\probe\extracted\<arc>\`，输出 `<arc>.xp3.probed_entries.json` 与 `probed_archives_summary.json`。
- **编译与复现命令**（运行 `probe` 需可读 `G:\`）：
  ```powershell
  C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /optimize+ /out:E:\Antigravity\tools\GinkaHxv4Tool.exe E:\Antigravity\tools\GinkaHxv4Tool.cs
  E:\Antigravity\tools\GinkaHxv4Tool.exe probe
  ```

### 3.8 `E:\Antigravity\tools\decode_all_extracted.py`
- **用途**：批量二次解码 `probe\extracted\` 中的全部文本/脚本/字典/PSB 资源：
  - 解密 `SimpleCrypt`（`\xfe\xfe\x00/\x01/\x02`）与 UTF-8/UTF-16 文本至 `probe\decoded\text\`；
  - 解析 `TJS/ns0\0` UI 布局 `.pbd` 与 `TJS/4s0\0`（ChaCha20+LZ4）立绘 `.pbd` 至 `probe\decoded\s0\`；
  - 提取 `TJS2100\0` 字节码字符串池至 `probe\decoded\tjs2\`；
  - 解压 `mdf\0` 封装的 PSB 至 `probe\decoded\mdf_psb\`；
  - 调用 `FreeMote\PsbDecompile.exe` 反编译全部 89 个 PSB（含 `.ks.scn`）至 `probe\decoded\psb\`；
  - 输出 `decode_extracted_summary.json` 与 `bin_refine_map.json`。
- **复现命令**：
  ```powershell
  python E:\Antigravity\tools\decode_all_extracted.py
  ```

### 3.9 `E:\Antigravity\tools\explore_name_sources.py` 与 `E:\Antigravity\tools\resolve_hxv4_names.py`
- **用途**：
  - `explore_name_sources.py`：扫描 `probe\decoded\` 全量明文与反编译 JSON，提取目录段与标识符候选，达成 **`31 / 31` 目录哈希全命中**。
  - `resolve_hxv4_names.py`：融合剧本 `storage`/`imageFile`/`voice` 引用、`.pbd` 图层号组合（`<stem>_<s|m|l|ll>_<layer_id>.tlg`）、语音前缀编号枚举、CG/背景/转场规则词根展开，达成 **`16,579 / 17,089`（97.02%）真实 `Hxv4` 条目文件名恢复**，并输出未命中诊断报告 `unmatched_diagnostic.json`。
- **复现命令**：
  ```powershell
  python E:\Antigravity\tools\explore_name_sources.py
  python E:\Antigravity\tools\resolve_hxv4_names.py
  ```

> **附注（保留的失败实验脚本）**：`E:\Antigravity\tools\inspect_garbro_schemes.ps1` 为早期尝试在 PowerShell 内通过 `AssemblyResolve` 加载 `GARbro-Mod` DLL 的测试脚本（因触发栈溢出已废弃，改用纯 Python `hxv4_crypto.py` + 原生 C# `GinkaHxv4Tool.cs`；详见第 6 节）。

---

## 4. 已确认结论

### 4.1 加密与文件名混淆机制
1. **归档保护**：全部 9 个 `.xp3` 均受 KiriKiri Z `CxdecV2` + `Hxv4` 保护，核心参数（来自 `PackinOne.dll` / `msg_tool_crypt.json`）：
   - `bootStrap = "GINKA (C)Frontwing"`（HEX `47494e4b412028432946726f6e7477696e67`）
   - `archiveUniqueKey = "{GinkaHimawariRinNazuna}"`
   - `mask = 409`, `offset = 390`, `randomType = 1` (`Xoroshiro128StarStar`), `filterKey = 0x405a265e53a275d7`
   - 基础归档（`flags = 0`）使用 `index_key2` 解密 `Hxv4` 表；补丁归档（`patch.xp3`、`patch_cr_data.xp3`，`flags = 1`）使用 `index_key1`。
2. **条目构成**：9 个归档原始 XP3 索引合计 **`17,099`** 条 = **9 条 `倀`（`U+5000` / `U+015000`）巨型随机尺寸防解包假条目**（每包索引 0 各 1 条） + **1 条明文诱饵 `startup.tjs`**（`data.xp3` 索引 1，316 B `TJS2100` 字节码，内部仅弹窗 `"startup failed: corrupted execution file"`） + **`17,089` 条真实受保护资源**。
3. **哈希算法**：
   - 目录名规范化（转小写、`/` 结尾、去首 `/`）后拼接 `"xp3hnp"` UTF-16LE，计算 **SipHash-2-4（`k0=0, k1=0`）** 64-bit `path_hash`（共 **31 个唯一目录，已 100% 还原**）。
   - 文件名转小写后拼接 `"xp3hnp"` UTF-16LE，计算 **BLAKE2s-256** 256-bit `file_hash`（已还原 **`16,579 / 17,089 = 97.02%`**）。

### 4.2 全局二次解码与特殊二进制细分结论
对解包的 `1,429` 个非音频/小体积关键条目执行 `decode_all_extracted.py` 的精确统计如下（见 `decode_extracted_summary.json`）：
- **文本解密（`textDecoded`）**：**`867`** 个（含 `SimpleCrypt \xfe\xfe` 模式 0/1/2 的 `.tjs`/`.ks`/`.asd`/`.sinfo`/`.stand`/`.csv`/`.ini`/`.txt` 及明文 `.vert`/`.frag`/`.sli`）。
- **TJS2 字节码解析（`tjs2Decoded`）**：**`230`** 个（`data.xp3` `223` 个［含诱饵 `startup.tjs`］ + `patch.xp3` `5` 个 + `steam.xp3` `2` 个）。
- **PSB 反编译（`psbDecompiled`）**：**`89`** 个（`cr_data.xp3` `47` 个 `.ks.scn` + `patch_cr_data.xp3` `38` 个 `.ks.scn` + `patch.xp3` `1` 个 `after.ks.scn` + `data.xp3` `2` 个标题动画纹理 PSB + `data.xp3` `1` 个 MDF 解压后的 `pro_tgs.ks.scn`）。
- **UI 布局字典（`ns0Decoded`，`TJS/ns0\0`）**：**`124`** 个（`data.xp3` `uipsd/` 下 **`78`** 个 + `patch.xp3` 下 **`46`** 个更新与 `_tw.pbd` 繁体 UI 布局字典，顶层键含 `packbase`、`packlist`、`names`、`order`、`result`）。
- **角色立绘图层字典（`pbdDecoded`，`TJS/4s0\0` ChaCha+LZ4）**：**`72`** 个（`cr_data.xp3` **`68`** 个［17 套模型 × `_s/_m/_l/_ll` 四档尺寸］ + `patch_cr_data.xp3` **`4`** 个更新版 `tginc01_{s,m,l,ll}.pbd`）。
- **MDF 压缩包解压（`mdfDecompressed`）**：**`1`** 个（`data.xp3` `scn/pro_tgs.ks.scn`，解压后 55,621 B 标准 `PSB v3`）。
- **各核心包关键组成核实**：
  - **`data.xp3`**（2,279 原始 = 1 假条目 + 1 诱饵 `startup.tjs` + 2,277 真实）：含 `1,124` `OGG_VORBIS`（`bgm/` 25、`voice/system/` 275、`sound/` 824）、`507` `PNG`、`223` `TJS2100`、`194` `SimpleCrypt`、**`78` `TJS_NS0`**、`74` `TLG5`（`uipsd/*__pack.tlg` 等 UI 图集，100% 命名恢复）、`41` `TEXT`、`16` `OTF` + `13` `TTF`、**`3` `AJPM`**（Alpha-JPEG 动画，位于 `image/` 2 个、`image/amv/` 1 个）、`2` `PSB`、**`1` `MDF_PSB`**、**`1` `TFT_FONT`**（`main/` 下 1,356 B `TVP pre-rendered font`）、`1` `JPEG`（`Loading.jpg`）。
  - **`patch.xp3`**（135 原始 = 1 假条目 + 134 真实，v1.06 引擎/UI/繁体补丁）：含 **`46` `TJS_NS0`** + **`27` `TLG5`**（UI 图集 100% 命名恢复）、`35` `PNG`（修正背景与中英本地化切入图 `CI024*_cn/en.png`、`sdcom002a_cn/en.png`）、`19` `SimpleCrypt`（含 `imagediffmap.csv`、`flagedit.ini`、开启 `"tw"` 与 `voiceTransEnabled` 的 `default.tjs`、`currev_patch.ini` `"534"`）、`5` `TJS2100`、`1` `PSB`（早期单语版 `after.ks.scn`）、`1` `JPEG`。
  - **`patch_cr_data.xp3`**（5,704 原始 = 1 假条目 + 5,703 真实，v1.06 剧本/CG/语音补丁）：含 `5,518` `OGG_VORBIS`（英文/AI 配音 `*_en.ogg` 及 `after` 语音）、`103` `TLG5`（更新 `tginc01` 立绘层，100% 恢复）、**`38` `PSB`**（更新版四语核心剧本 `.ks.scn`，100% 恢复）、`19` `PNG`（新增 `ev026`、`sdcom006`、`ev008b2` 等，100% 恢复）、`14` `TEXT`（`.ogg.sli`）、`6` `SimpleCrypt`（含入口 `start_vol1.ks`、更新版 `!scnlist.txt`、`cglist.csv`、`version` `1.06` 及 2 个开发者残留 `desktop.ini`）、`4` `TJS4s0`（`tginc01_{s,m,l,ll}.pbd`）、以及 **`1` `WIN_LNK`**（索引 2271，1,638 B 开发者误打包的 Windows 快捷方式，指向 `D:\Download\scn007\ElevenLabs_2024-04-09T10_41_36_銀花_gen_s34_sb76_se0_m2.mp3`）。

### 4.3 剧情与中文内嵌结论
- **剧本格式与总量**：编译态 **PSB v3**（`.ks.scn`）。补丁版 `!scnlist.txt` 共登记 **48 个 `.ks` 剧本**：
  - **正式可玩剧情 38 个**（恰好对应 `patch_cr_data.xp3` 中全部更新的 38 个 `.ks.scn`）：主线前篇 `scn000`–`scn015`（含分支 `scn013_a/b/c`，共 19 个） + 支线/Bad End `scn901`–`scn904`（4 个） + `NEXT` 真路线篇 `scn101`–`scn114`（14 个） + v1.06 新增 `AFTER` 后日谈 `after.ks`（1 个）。
  - **发售前倒计时/展会特典短剧 10 个**：`pro_1day`–`pro_7day`、`pro_master`、`pro_release`（位于 `cr_data.xp3`）及 `pro_tgs`（位于 `data.xp3` `scn/`，MDF 压缩），均为纯日文宣传语音小剧场，主流程不跳转。
- **中文直接内嵌确认**：全部 38 个正式剧情 `.ks.scn` 顶层均声明 `"languages": ["en", "cn", "tw"]`，每条台词/旁白数组均直接内嵌 **`[0: 日文, 1: 英文, 2: 简体中文, 3: 繁体中文]`** 四语槽位，无需外挂汉化补丁即可直接提取官方简体中文文本。

### 4.4 图像与分层结构结论
- **`fgimage.xp3` 仅 9.7 KB 的原因**：仅存 `emotion.txt`、`facezoom.csv`、`standPosition.txt` 三个立绘表情偏移与站位表；真正的 14 名角色（17 套模型 ID × `_s/_m/_l/_ll` 四档预缩放）立绘定义 `.stand`/`.sinfo`/`.pbd` 与 `2,032 + 103` 张 32-bit RGBA `TLG5` 局部图层全部存放在 **`cr_data.xp3`** 与 **`patch_cr_data.xp3`** 中。
- **CG 与背景**：画廊共登记 **32 组 CG**（26 组 `ev001`–`ev026`［缺号 `ev022`，含 `ev003b`］ + 6 组 Q 版合成 `sdcom001`–`sdcom006`）。基础背景/CG 为 `1280×720`（宽幅背景 `1680×720`），高清缩放版（`l` 后缀，如 `bgimage2.xp3` 及部分 `ev*l.png`）为 `2560×1440`。

---

## 5. 未解决问题与建议的下一步

### 5.1 已知收尾细节（非阻塞项）
1. **归档覆盖优先级固化**：KiriKiri Z 运行时挂载优先级为 **`patch_cr_data.xp3` / `patch.xp3` 高于 `cr_data.xp3` / `data.xp3` / `bgimage.xp3` / `cr_event.xp3`**。特别注意 `after.ks.scn` 同时存在于 `patch.xp3`（单语旧版）与 `patch_cr_data.xp3`（四语新版，含简体中文），阶段 1 提取剧本时**必须以 `patch_cr_data.xp3` 覆盖 `patch.xp3` 与 `cr_data.xp3`**。
2. **剩余 `2.98%`（510 条）未命中文件名条目**：主要为手表端不使用的音频（`OGG_VORBIS`）、桌面端着色器（`glsl/`）、旧版转场遮罩（`rule/old/`）、桌面 UI PSD 字典（`uipsd/`）、动态条带遮罩（`mask/`、`anim/`）及 `cr_data.xp3` 中 60 张 `TLG5` 图层。由于手表端仅按剧本实际引用的字符串取用资源，**任何被剧本引用的资源名均可直接用 `calculate_file_hash(name)` 在 `O(1)` 时间内定位到 XP3 条目，完全不构成阶段 1 阻塞**（详见 `PHASE0_REPORT.md` 第 6 节）。
3. **10 个纯日文倒计时短剧（`pro_*.ks`）范围裁定**：目标规格限定为“基础版剧情与基础 CG”，`pro_*` 无官方中文槽位且不在标题页 `START / NEXT / AFTER` 主线内，建议阶段 1 默认不纳入基础版阅读器（如需确认可在阶段 1 启动前向督导侧核实）。

### 5.2 建议的阶段 1 实施路线（待督导验收阶段 0 后启动）
1. **剧本编译器（`convert-story.py`）**：以 `patch_cr_data.xp3` 优先合并 `cr_data.xp3` 的 38 个正式 `.ks.scn`，提取 `texts[*][1][2]`（简体中文槽位）、选项分支（`selects`）、结局跳转与 `START`（`scn000`）→ `NEXT`（`scn101`）→ `AFTER`（`after`）解锁状态机，按 `≤ 32 KB/片` 切分为轻量 JSON/文本分片。
2. **图像烘焙管线（`prepare-images.py` / `plan-portraits.py`）**：
   - 背景、事件 CG、SD 合成 CG（按 `cglist.csv` 规则将 `sdcom*` 叠合至对应 `bg*`/`ev010_bg`，并按 `imagediffmap.csv` 选用 `*_cn` 简体差分图）统一离线合成为 **`432×286` JPEG `q22`**。
   - 立绘直接选取原包内置的紧凑档（`_s` 或 `_m` `.pbd` + `TLG5`），复用 `senren-rw5` / `parquet-rw5` 的 **“身体底图 + 表情小矩形透明 PNG 补丁”** 方案，避免全画布重复存储。
3. **字体子集化与 RPK 打包审计**：扫描全部简体中文剧本与 UI 字符集生成单文件子集字体，使用固定 **`aiot-toolkit 1.1.0`** 构建 `com.antigravity.ginka.rw5`，严格执行零音频/零视频、包体 `≤ 10 MB`（硬上限 `< 25,000,000 B`）及总条目 `≤ 4,100` 自动化审计。

---

## 6. 失败的尝试与原因

| 序号 | 失败尝试 | 报错现象与根因 | 最终解决方式 |
| :---: | :--- | :--- | :--- |
| 1 | 在 PowerShell 中通过 `Add-Type` + `AssemblyResolve` 加载 `GARbro-Mod` DLL（`tools\inspect_garbro_schemes.ps1`） | 触发 `StackOverflowException` 进程崩溃。根因：PowerShell 脚本块充当 `AppDomain.AssemblyResolve` 回调时，PowerShell 自身查找内部资源程序集再次触发该事件，形成无限递归。 | 彻底放弃在 PowerShell 内挂载 GARbro GUI/DLL，改从 `lifegpc/msg-tool` 提取公开算法与参数，编写零外部依赖的 `hxv4_crypto.py` 与原生 C# `GinkaHxv4Tool.cs`。 |
| 2 | `hxv4_crypto.py` 初版单元测试向量核对 | 初版存在一行冗余的 7 参数 `struct.pack("<IIIIIIII", ...)`，且对 `cx.rs` 测试用例里的虚构顺序字节 `00..0a` 套用了真实游戏才合法的逆置换，导致测试向量首轮未过。 | 删除无用代码并对合法置换范围加保护后，`msg_tool_cx.rs` 全套密钥派生、过滤器、SipHash 与 BLAKE2s 单元测试 100% 通过。 |
| 3 | PowerShell `-Command` 内联双引号运行 `python -c` | 外层 PowerShell 提前展开 `$dir` 变量或吞掉 `\"` 转义（报 `Missing ')' in function parameter list` / `Missing property name after reference operator`）。 | 所有解析、解密与统计逻辑一律写成 `E:\Antigravity\tools\` 下的独立 `.py` / `.cs` 脚本直接调用，不再拼接复杂内联单行命令。 |
| 4 | Windows 默认控制台编码打印日文/替换字符 | Python 默认按 `cp936/gbk` 输出含 `\ufffd` 或 `\u30fb`（`・`）的调试摘要时报 `UnicodeEncodeError`。 | 在所有 Python 工具入口统一配置 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，所有中间结果直接写 UTF-8 JSON 文件。 |
| 5 | 标准沙盒内直接读取 `G:\SteamLibrary\steamapps\common\GINKA` 或联网拉取 GitHub | 沙盒默认隔离工作区外盘符（`PermissionError`）与外网套接字（`WinError 10013`）。 | 遵循最小提权原则：仅对只读提取 `G:\` 的两步（`fetch_hxv4_chunks.py`、`GinkaHxv4Tool.exe probe`）及首次工具下载申请沙盒外只读执行；后续全部解码、反编译、碰撞均 100% 在沙盒内离线完成。 |
| 6 | `explore_name_sources.py` 首轮路径切分与全量台词枚举 | 遇到单斜杠 `"/"` 时 `parts` 为空触发 `IndexError`，且未过滤含空格/中文标点的长句导致候选词膨胀至 52.9 万条、耗时过长。 | 增加空列表守卫并过滤空白与中日文标点字符，运行时间收敛至约 90 秒内完成。 |
| 7 | `resolve_hxv4_names.py` 单段目录过滤导致 `anim/` 漏记 | `explore_name_sources.py` 已命中 `31/31` 目录（含 `3e5e6fe060319f55 = "anim/"`），而 `resolve_hxv4_names.py` 将候选收紧后显示 `30/31`。 | 交叉核验两份输出并验证 `calculate_path_hash("anim/") == "3e5e6fe060319f55"`，确认全部 **31/31** 个目录哈希均已 100% 精确还原。 |
