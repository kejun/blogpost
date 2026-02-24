# antirez 全文翻译：用 Claude Code 实现“净室”Z80 / ZX Spectrum 模拟器

> 原文链接: https://antirez.com/news/160  
> 参考技术原稿: https://github.com/antirez/ZOT/blob/main/README.md  
> 翻译时间: 2026-02-24

---

## ZOT：一个 Z80、ZX Spectrum 48K 与 CP/M 2.2 模拟器

ZOT 项目包含三部分：Z80 CPU 模拟器、ZX Spectrum 48K 模拟器，以及运行在同一 Z80 内核之上的 CP/M 2.2 模拟器。项目全部使用 C 语言编写，除标准库外无依赖（SDL 前端是可选的）。Z80 内核足够小，可运行在 RP2040 这类微控制器上，同时精度足够高，能够通过 ZEXALL 套件中所有已记录与未记录的 Z80 指令测试。

Spectrum 模拟器由大约 3500 行 C 构成，分布于 4 个文件：`z80.c`（Z80 内核）、`spectrum.c`（Spectrum 模拟）、`tzx.c`（磁带播放器）和 `zxsdl.c`（SDL 前端）。CP/M 模拟器在 `cpm.c` 及其前端基础上额外增加约 2000 行代码。

**这个项目最初是一次使用 AI 工具进行净室开发（clean room development）的实验**，最终质量足够好，因此公开发布。

---

## AI 说明（AI Disclaimer）

该模拟器在“净室环境”中由 Claude Code Opus 4.6 实现。为避免受到其他实现污染，采用了如下流程：

- Agent 不可访问任何其他模拟器源码。
- 由人类编写设计文档，给出模拟器的主要架构和目标。
- Agent 先对 Z80、CP/M 规范，以及 ZX Spectrum 内部结构、ULA、磁带/镜像文件类型做资料研究；收集完成后，重启 agent 会话并清除旧会话上下文，避免把已有实现带入最终编码上下文。
- 实现过程中由人类持续反馈，指导关键设计决策。实现阶段 agent 无互联网访问权限。人类不手写代码，只提供提示与设计文档。

---

## Z80 内核

Z80 CPU 模拟器位于 `z80.h` 与 `z80.c`。核心设计是：`z80_step()` 一次执行一条完整指令，并返回消耗的 T-state（时钟周期）数。

这属于“按指令步进（instruction-stepping）”，而不是“按周期步进（cycle-stepping）”。后者能模拟“写内存过程中的中间总线状态”等细粒度行为，但对 ZX Spectrum 软件而言通常并不必要——真正关键的是每条指令总周期正确、标志位正确。按指令步进更简单、更快、内存占用更低，尤其适合 264KB RAM 的微控制器目标。

CPU 状态使用普通 C 结构体：

- 各 8 位寄存器（A/F/B/C/D/E/H/L 及其影子寄存器）使用 `uint8_t`
- IX/IY/SP/PC 使用 `uint16_t`
- 内存访问与 I/O 访问通过函数指针回调

函数指针使 Z80 内核与具体系统解耦：Spectrum 可提供自身的 ROM/RAM 布局和 ULA 端口解码回调，而同一内核也可接入 CP/M、MSX 等其他系统。

### 指令覆盖

实现了完整 Z80 指令集：

- 256 条非前缀指令
- CB 前缀（位操作/旋转/移位）
- ED 前缀（扩展组：块传输、16 位算术、I/O 块操作）
- DD/FD 前缀（IX/IY 变体）
- DDCB/FDCB 双前缀索引位操作
- 已知未文档化指令（如 SLL、IX/IY 半寄存器操作、`RLC (IX+d)` 结果写回寄存器等）

### 标志位与细节

标志位计算遵循真实芯片，包括未文档化的 X（bit3）与 Y（bit5）标志位。多数指令把 X/Y 设为结果对应位；但 `CP` 以及 `CPI/CPIR/CPD/CPDR` 等指令需要从操作数或中间值推导。这个细节对通过 ZEXALL 至关重要。

使用 256 字节预计算表 `sz53p_table` 提供常见的 S/Z/Y/X/P 标志，大多数 ALU 指令只需查表并补上 H/N/C 即可。

R 寄存器（刷新计数器）也被正确更新：

- 非前缀指令取指时 +1
- 前缀字节同样计入
- 仅低 7 位递增，高位保持 `LD R,A` 设置值

这对部分利用 R 作为伪随机源的拷贝保护很重要。

### 测试

Z80 内核包含 154 个单元测试，覆盖指令组、标志位边界与时序要求。并且通过：

- ZEXDOC（文档化标志）
- ZEXALL（含未文档化 X/Y 标志）

二者均 100% 通过。

运行方式：

```bash
make test
./z80_test --zexdoc
./z80_test --zexall
```

---

## Spectrum 模拟器

Spectrum 模拟位于 `spectrum.h` 与 `spectrum.c`。它在 Z80 内核外包裹 Spectrum 硬件：

- 16KB ROM
- 48KB RAM
- ULA 芯片（视频、键盘、蜂鸣器、磁带 I/O）
- 内存争用（contention）

### 内存映射与 I/O

64KB 地址空间：

- `0x0000-0x3FFF`：ROM（只读，写入被忽略）
- `0x4000-0xFFFF`：RAM

屏幕内存从 `0x4000` 开始，因此 ULA 与 CPU 会竞争同一段 RAM。

I/O 方面，Spectrum 只做部分地址解码：

- ULA 响应所有偶数端口（A0=0）
- 读端口返回键盘状态（高位地址选择半行，支持多行并选并按位 AND）
- bit0-4 为按键（低有效），bit6 为磁带 EAR 输入，bit5/7 恒为 1
- 写端口：bit0-2 边框色，bit3 MIC（忽略），bit4 蜂鸣器

Kempston 摇杆在 A7-A5 全 0 时响应，按 active-high 返回方向与开火位。

### 内存争用

ULA 与 CPU 共享 `0x4000-0x7FFF`。显示期（192 条扫描线）ULA 抢占读取屏幕数据，CPU 会等待。等待周期取决于 ULA 8T 取数周期中的位置：

```text
Cycle position:  0  1  2  3  4  5  6  7
CPU wait states: 6  5  4  3  2  1  0  0
```

许多模拟器会用 69888 字节查表（每帧每 T-state 一项）。本实现改用算术计算：根据当前帧 T-state 推导扫描线与线内位置，判断是否处于争用区（显示区 64-255 行前 128T），再查 8 字节模式表。以 8 字节替代约 68KB，适合 MCU。

争用逻辑在内存回调内部处理，Z80 内核无需感知。访问争用区地址时，回调按当前帧位置补充等待状态。

### 帧时序

ULA 生成 50.08 Hz PAL：

- 每帧 69888 T-state
- 312 行，每行 224 T-state
- 8 行垂直同步 + 56 行上边框 + 192 行显示 + 56 行下边框
- 每帧 T-state=0 触发可屏蔽中断

`zx_tick()` 是核心执行原语，可按不同粒度运行：

- `zx_tick(zx, 0)`：单指令（磁带加载必须）
- `zx_tick(zx, 224)`：约一条扫描线
- `zx_frame()`：循环 `zx_tick()` 直到帧边界

帧边界优先：即使还没达到 `min_tstates`，跨帧时也立刻返回，确保调用者不会错过帧事件。

### 视频渲染

Spectrum 屏幕位图（`0x4000-0x57FF`）是非线性布局；属性区（`0x5800-0x5AFF`）线性存储，每个 8x8 字符单元一个属性字节（ink/paper/bright/flash）。

支持两种渲染模式：

1. **自动渲染模式**：通过 `zx_set_framebuffer()` 提供 RGB 帧缓冲，随着扫描线推进即时渲染，可正确呈现中途改色/分屏等效果。
2. **按需渲染模式**：调用 `zx_render_screen()` 获取当前屏幕快照，结构更简单但无法表现帧中动态变化。

### 音频

Spectrum 音频为 1-bit beeper。写 ULA 端口会切换电平。模拟器在一帧内记录 `(T-state, level)` 事件，帧结束时转换为 44100Hz 下每帧 882 个 16 位 PCM 样本。

SDL 前端用音频队列做“时钟源”：当音频缓冲超过约 3 帧时主循环休眠。无需 `usleep()` 或额外帧定时器。

---

## 磁带播放器（TZX/TAP）

磁带播放器在 `tzx.h` / `tzx.c` 中实现。它把 TZX/TAP 数据转换成脉冲序列，并按正确 T-state 时序驱动 EAR 位。

### Spectrum 磁带加载原理

ROM 在 `0x056B` 附近的加载例程通过紧循环测量 EAR 信号边沿间隔。标准格式：

1. **导频音（pilot tone）**：大量同宽脉冲（2168T）用于同步。
2. **两个同步脉冲**：667T 与 735T。
3. **数据位**：每 bit 由两段同宽脉冲构成（0=855T，1=1710T）。
4. **块间停顿**：通常约 1 秒。

ROM 只关心边沿时序，不关心信号来源（磁带、WAV、模拟器生成）。

### TAP

TAP 仅是数据块串联（每块前有 2 字节小端长度），不含时序信息；播放器按标准 ROM 常量自行合成脉冲。

### TZX

TZX 可表达更复杂录音：turbo loader、自定义脉冲、保护格式、原始录音等。支持块包括：

- 0x10 标准速数据
- 0x11 Turbo 数据
- 0x12 纯音
- 0x13 脉冲序列
- 0x14 纯数据
- 0x15 直接录音
- 0x20 暂停/停止
- 0x21/0x22 分组开始/结束
- 0x24/0x25 循环开始/结束
- 0x2B 设置信号电平
- 0x30/0x32 文本与归档信息

### 每指令更新 EAR

播放磁带时，SDL 前端不再直接 `zx_frame()`，而是每条指令前更新 EAR：

```c
if (tzx_is_playing(&tape)) {
    do {
        zx_set_ear(zx, tzx_update(&tape, zx->cpu.clocks));
    } while (!zx_tick(zx, 0));
} else {
    zx_frame(zx);
}
```

这样可确保 ROM 加载器在每条指令之间都能看到准确电平变化。

---

## SDL 前端

`zxsdl.c` 提供最小桌面前端：PC 键盘映射到 Spectrum 40 键矩阵，方向键映射 Kempston 摇杆，支持 `.z80` 快照和 `.tzx/.tap` 磁带（命令行与拖放）。

```bash
./zxsdl
./zxsdl game.z80
./zxsdl game.tzx
./zxsdl game.tap
```

快捷键：

- F2 重置
- F3 从头播放磁带
- F4 停止磁带
- F5 切换 2x/3x 缩放
- F11 全屏
- ESC 退出

---

## CP/M 模拟器

`cpm.h` / `cpm.c` 在 C 里完整实现了 CP/M 2.2。与“跑真实 CCP/BDOS/BIOS 二进制”不同，这里采用“拦截系统调用并原生处理”方式，因此不依赖 CP/M 系统镜像即可自包含运行，可执行 Turbo Pascal、WordStar 等软件。

### 架构

CP/M 程序通过 `CALL 0005h` 调 BDOS（C=功能号，DE=参数）。模拟器在页零放置跳转到陷阱地址的指令；执行循环在每条指令前检查 PC，命中陷阱后：

1. 读取 C/DE
2. 在 C 代码中执行对应功能
3. 设置返回寄存器
4. 从栈弹返回地址并继续

BIOS 也用同样机制：F200h 的 17 项跳表指向 F240h 起始的陷阱入口。

### BDOS 功能

实现 CP/M 2.2 的 38 个 BDOS 功能：

- 控制台 I/O（1-12）
- 文件系统（13-23、30、33-36、40）
- 系统信息（24-32）

主机目录映射为 CP/M 盘符（A: 到 P:），并维护 16 槽打开文件表。

### CCP

CCP 也由 C 实现，提供 `A>` 交互提示和内建命令：`DIR`、`ERA`、`TYPE`、`REN`、`USER`、`SAVE`。无法匹配内建命令时会搜索 `.COM` 文件。

运行示例：

```bash
./cpmcon cpm-software/mbasic/
./cpmcon -A cpm-software/utils/ -B cpm-software/games/
```

控制键：Ctrl-C 热重启回 CCP，Ctrl-\ 退出模拟器。

### 终端翻译

很多 CP/M 程序面向 ADM-3A/Kaypro/VT52，而非 ANSI 终端。模拟器提供 `auto/adm3a/ansi` 三种翻译模式（`-t` 参数），并将方向键转换为常见 WordStar 控制键（如 Up -> Ctrl-E）。

---

## 构建与测试

外部依赖只有 SDL2（仅 Spectrum SDL 前端需要）。

```bash
make
make zxsdl
make cpmcon
```

测试分两层：

- `make test`：快速测试（154 Z80 + 49 Spectrum + 78 CP/M）
- `make fulltest`：快速测试 + ZEXDOC + ZEXALL

ZEXDOC/ZEXALL 来自 Frank Cringle，用于对比真实 Z80 行为 CRC，系统性验证 67 组指令及（在 ZEXALL 中）未文档化 X/Y 标志位。

---

## 文件结构（核心）

- `z80.c`：完整 Z80 指令实现
- `spectrum.c`：ULA、视频、音频、键盘、争用
- `tzx.c`：TZX/TAP 解析与脉冲生成
- `zxsdl.c`：SDL2 前端
- `cpm.c`：BDOS/BIOS/CCP/文件系统
- `cpmcon.c`：终端前端与转义翻译
- `z80_test.c` / `spectrum_test.c` / `cpm_test.c`：测试

---

## 许可证与 ROM 说明

项目代码为 MIT。`z80-specs/` 下文件使用不同许可证，需查看对应 README。

`rom.h` 包含 ZX Spectrum 48K ROM。历史上，Amstrad 在 1999 年公开声明允许模拟器作者分发 ROM（保留版权声明，不得单独售卖 ROM），该许可在社区沿用超过 25 年。如当前权利人提出要求，可联系作者移除。

---

## 译者注

本文为对 antirez 相关原文与同源技术文稿的完整中文翻译整理，保留了实现思路、架构决策、关键接口与测试方法，便于中文读者完整理解“净室 + AI 辅助系统编程”这一实践。
