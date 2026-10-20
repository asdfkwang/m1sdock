# Boot Sequence

BL808 · from power-on to Linux

Follow code execution and memory operations on one fixed board diagram.
The first two scenes are playable. Each runs once, then waits for **Next**,
**Previous** or **Replay**. Pause to inspect an address; the diagram supports
panning and zooming. Left / right keys work while the player has focus.

<div id="boot-sequence-root"><p>The interactive player loads here. The complete text storyboard and address reference are available below.</p></div>

## The complete storyboard

The animation follows vendor **low_load** startup. M0 and D0 initialization
can overlap: the first two scenes explain their dependencies rather than
claiming a cycle-accurate reset trace. Animation speed is illustrative.

| Scene | What moves or changes | Preview |
|---|---|---|
| **1 · M0 runtime** | Boot headers → M0 XIP; set the stack; copy initialized sections; clear BSS; initialize platform memory and the heap | Playable |
| **2 · D0 synchronization** | D0 XIP and stack; wait on two XRAM words; M0 publishes readiness; D0 clears the flags and initializes its C runtime | Playable |
| 3 · Load U-Boot | D0 reads the compressed U-Boot payload at NOR `0x000F_2000` through XIP `0x580A_0000` and expands it into PSRAM `0x5000_0000` | Storyboard |
| 4 · Load the kernel | Extend the loader to unpack a separate kernel from the Flash slot starting at `0x0095_2000` into PSRAM `0x5100_0000`; payload metadata is not finalized | Storyboard · packaging / loader work pending |
| 5 · Copy DTB and OpenSBI | DTB: NOR `0x000D_2000` → PSRAM `0x51FF_8000`; OpenSBI: NOR `0x0085_2000` → PSRAM `0x53F0_0000` | Storyboard |
| 6 · Enter OpenSBI | Cache maintenance and PMP configuration; D0 jumps to `0x53F0_0000` in M-mode with hart ID 0 and the DTB pointer | Storyboard |
| 7 · Enter U-Boot | OpenSBI hands control to S-mode U-Boot at `0x5000_0000`; U-Boot establishes its runtime and reservations | Storyboard |
| 8 · Enter Linux | U-Boot `booti` prepares the kernel at `0x5100_0000`, relocates it to `0x5020_0000`, chooses the final DTB location and enters Linux | Storyboard |
| 9 · Linux early initialization | Kernel memory, traps, interrupt controller, timers and console become active | Storyboard |
| 10 · Root filesystem and init | Load or mount the intended root filesystem, start init and reach userspace | Storyboard · end-to-end acceptance pending |

The dedicated Flash-kernel path and a complete Linux login are not established
by this preview. Only scenes 1 and 2 have animation timelines; the later
scenes define the sequence to extend. Zephyr startup requires its own linked
image and dual-core startup contract.

## Scene 1 · M0 runtime

1. Boot metadata at NOR `0x0000_0000` / `0x0000_1000` establishes the group mappings.
2. M0 executes its low_load image at CPU XIP entry `0x5800_0000`, backed by
   physical NOR body offset `0x0000_2000`.
3. `Reset_Handler` sets `sp = __StackTop = 0x6203_0000` and aligns it to 16 bytes.
4. `System_Init()` configures access protection, caches and 160 KiB MCU WRAM.
5. `start_load()` copies initialized ITCM / DTCM / RAM sections from their
   Flash load addresses, then clears `[__bss_start__, __bss_end__)`.
6. `System_Post_Init()` powers the MM domain and makes its SRAM available.
   In `main()`, `bflb_platform_init()` calls `board_init()` to initialize
   clocks, pins and UHS PSRAM before initializing the heap.
7. `mmheap_init()` receives `[__HeapBase, __HeapLimit)`; M0 is ready for the
   synchronization handshake in scene 2.

| M0 allocation | Bounds / value |
|---|---|
| ITCM linker region | `0x6202_8000` · 28 KiB capacity |
| DTCM linker region | `0x6202_F000` · 4 KiB capacity |
| Bootstrap stack | `[0x6202_FC00, 0x6203_0000)` · **1 KiB** |
| WRAM / data / heap region | `[0x6203_0000, 0x6205_8000)` · 160 KiB |
| Heap | `[__HeapBase, 0x6205_8000)` · base depends on the linked image |

Setting `sp` assigns a CPU register; it does not copy a stack image from
Flash. Heap initialization prepares an allocator over the remaining RAM.
Section copy lengths, Flash load addresses and the exact heap base come
from linker symbols, so the animation does not invent measured occupancy.
Upper bounds in this chapter's `[start, end)` notation are **exclusive**.

## Scene 2 · D0 synchronization

1. D0 enters its low_load image at CPU XIP `0x5800_0000`, backed by physical
   NOR offset `0x0005_2000` through Group1.
2. Its `Reset_Handler` sets the bootstrap stack before calling `System_Init()`.
3. With the dual-core build enabled, D0 polls XRAM words `0x4000_0000` and
   `0x4000_0004`, waiting for both to equal `0x1234_5678`.
4. M0 disables its D-cache, writes both readiness words, performs the existing
   cache-clean operation and stays in its low_load wait loop.
5. D0 accepts the handshake, clears both words to zero and enables its caches.
6. D0 `start_load()` copies initialized sections and clears BSS. Interrupt
   setup follows; `bflb_platform_init()` initializes the heap before loading payloads.

| D0 allocation | Bounds / value |
|---|---|
| Initial stack pointer | `0x3F00_8000` |
| Bootstrap stack | `[0x3F00_7C00, 0x3F00_8000)` · **1 KiB** |
| Loader DTCM region | `[0x3F00_0400, 0x3F00_8000)` · 31 KiB |
| Loader ITCM region | `[0x3EFF_C000, 0x3F00_0400)` · 17 KiB, crossing DRAM into VRAM |
| Data / heap linker region | `[0x3EF8_0000, 0x3EF8_8000)` · 32 KiB |
| Heap | `[__HeapBase, 0x3EF8_8000)` |

The readiness flag is a software synchronization word. The animation does not
attribute an unverified direct D0 reset-release operation to M0. Initial XRAM
contents are shown as unknown, not assumed to be zero. The preview stops before
`linux_load()`; it does not claim later firmware or Linux execution.

## Visual language

CPU ownership follows the [memory map](./soc/memory-map.md): M0 is blue and
D0 is violet. Flash remains amber, PSRAM green and XRAM slate. Rose outlines
mark the operation being explained; data and pointer changes have explicit
labels. Node positions remain fixed throughout both scenes.

## Source of truth

| Source | What it establishes |
|---|---|
| SDK `drivers/bl808_driver/startup/{m0,d0}/source/GCC/startup.S` | Stack setup and calls to system initialization, `start_load` and `main` |
| SDK `drivers/bl808_driver/startup/{m0,d0}/source/GCC/start_load.c` | Initialized-section copies and BSS clearing |
| SDK `drivers/bl808_driver/startup/m0/bl808_flash.ld` | M0 stack, linker regions and heap limit |
| SDK `examples/low_load/bl808_flash_d0.ld` | D0 loader stack, linker regions and heap limit |
| SDK `drivers/bl808_driver/startup/{m0,d0}/source/system_bl808.c` | MM setup, shared-word polling and D0 cache-enable order |
| SDK `bsp/board/bl808/board.c` and `bsp/bsp_common/platform/bflb_platform.c` | M0 PSRAM initialization and heap allocator setup |
| SDK `examples/low_load/main.c` and `drivers/bl808_driver/regs/bl808.h` | Ready-word addresses, value, publication and loader handoff |
| `utils/prepare_blflash_low_load.py` | Both XIP entries and their distinct physical Flash body offsets |
| SDK `build.sh`, `utils/merge_linux_image.py` and `docs/src/flash-layout.md` | Whole-image packaging and the separate Flash-kernel storage plan |

SDK paths are relative to `M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/`, except
`build.sh`, which is at the SDK root. These sources define a software model;
no board is accessed by the player.
