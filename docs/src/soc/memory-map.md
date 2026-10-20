# Memory Map

BL808 M1s Dock · M0 / E907 (RV32) and D0 / C906 (RV64)

The current boot chain uses vendor M0 and the vendor D0 loader with a small
Rust probe. Generic OpenSBI runs in M-mode; U-Boot runs in S-mode. The future
design replaces M0 with Zephyr, moves OpenSBI into internal SRAM and loads
Linux from SD. That design has not been applied or validated.

<div class="memory-map" data-view="compare">
<div class="map-controls" hidden>
<div class="map-control-row" role="group" aria-label="Memory map view">
<span class="map-control-label">View</span>
<button type="button" data-control="view" data-value="current" aria-pressed="false">Current</button>
<button type="button" data-control="view" data-value="future" aria-pressed="false">Future</button>
<button type="button" data-control="view" data-value="compare" aria-pressed="true">Compare</button>
</div>
<div class="map-control-row" role="group" aria-label="Memory map topic">
<span class="map-control-label">Region</span>
<button type="button" data-control="topic" data-value="overview" aria-pressed="true">Overview</button>
<button type="button" data-control="topic" data-value="m0" aria-pressed="false">M0</button>
<button type="button" data-control="topic" data-value="d0" aria-pressed="false">D0</button>
<button type="button" data-control="topic" data-value="flash" aria-pressed="false">Flash &amp; SD</button>
</div>
<span class="map-status" data-status role="status" aria-live="polite"></span>
</div>
<p class="map-note">Read addresses from bottom to top. A labelled upper boundary is exclusive: <code>[start, end)</code>. Sizes use KiB / MiB. Diagrams are not to scale. CPU addresses and physical Flash offsets are separate coordinate systems.</p>


<section data-topic="m0" aria-labelledby="m0-map">
<h2 id="m0-map">M0 · RV32 E907</h2>
<p>Code executes from Flash through XIP. Internal MCU SRAM holds relocated code, data, stacks and heap. OCRAM (64 KiB) plus WRAM (160 KiB) provides 224 KiB when WRAM is assigned to the MCU.</p>

<div class="map-pair">
<article class="map-panel" data-era="current" aria-label="Current · implemented">
<h3>Current · implemented</h3>
<pre><code>0x62058000 +---------------------------+
           | WRAM: 160 KiB             |
           | data / BSS / heap         |
0x62030000 +---------------------------+
           | DTCM: 4 KiB / stack       |
0x6202F000 +---------------------------+
           | ITCM: 28 KiB              |
0x62028000 +---------------------------+
           | Remaining OCRAM: 32 KiB   |
           | Not assigned by this LD  |
0x62020000 +---------------------------+

Flash XIP entry: 0x58000000
Physical Flash body: 0x002000</code></pre>
<p>This is the vendor M0 linker allocation, not measured section usage. ITCM/DTCM are linker region names within MCU SRAM. The Rust M0 experiment was discarded.</p>
</article>
<article class="map-panel" data-era="future" aria-label="Future · proposed, not applied">
<h3>Future · proposed, not applied</h3>
<pre><code>0x62058000 +---------------------------+
           |                           |
           | Zephyr SRAM: 224 KiB      |
           | data / BSS / stacks       |
           | heap / selected code      |
           |                           |
           | Exact allocation: TBD     |
           | IPC carve-out: TBD        |
0x62020000 +---------------------------+

Zephyr code: Flash XIP
Image must fit its Flash slot.</code></pre>
<p>Proposed ownership, not a linked Zephyr image. A shared IPC carve-out must be reserved consistently on both cores. Do not count aliases or IPC as extra capacity.</p>
</article>
</div>

<h3>What M0 configures today</h3>
<ol>
<li><code>System_Init()</code> assigns WRAM as 160 KiB MCU RAM / 0 KiB BLE EM, sets PSRAM access-control barriers and installs a locked, no-access PMP region at <code>[0x80000000, 0x90000000)</code> for prefetch protection.</li>
<li>Startup enables I/D cache; <code>System_Post_Init()</code> powers the multimedia subsystem and configures available D0 L2 SRAM. <code>board_init()</code> initializes clocks, pins and UHS PSRAM, then releases the PSRAMA access barrier.</li>
<li>M0 low_load disables its D-cache, writes synchronization flags at <code>0x40000000</code> and <code>0x40000004</code>, performs the existing cache-clean operation and waits. D0 startup waits for and clears these flags.</li>
</ol>
<p>The non-cacheable MCU SRAM alias is <code>[0x22020000, 0x22058000)</code>. It refers to the same 224 KiB as the <code>0x62020000</code> cacheable alias. Selecting an alias alone does not establish the live cache state.</p>
<p>Future Zephyr must supply the initialization and D0 startup contract. Its present SoC startup halts D0 and LP; the existence of M0 board support does not establish this dual-core boot path.</p>
</section>

<section data-topic="d0" aria-labelledby="d0-map">
<h2 id="d0-map">D0 · RV64 C906</h2>
<h3>Internal SRAM: MM DRAM and MM VRAM</h3>
<p>MM DRAM is on-chip SRAM despite the SDK name “DRAM”. It is separate from external PSRAM. MM VRAM is another 32 KiB; neither should be counted as part of the 64 MiB PSRAM.</p>

<div class="map-pair">
<article class="map-panel" data-era="current" aria-label="Current · implemented">
<h3>Current · implemented</h3>
<pre><code>0x3F008000 +---------------------------+
           | MM VRAM: 32 KiB           |
           | Loader DTCM + ITCM tail   |
0x3F000000 +---------------------------+
           | MM DRAM: 512 KiB          |
           |                           |
           | Upper part: loader ITCM   |
           | Lower 32 KiB: data / heap |
           | Other space: not assigned |
           | by this loader LD         |
0x3EF80000 +---------------------------+

OpenSBI lives in PSRAM today.</code></pre>
<p>The loader uses selected regions, not all 512 KiB. Its 17 KiB ITCM region crosses from MM DRAM into the first 1 KiB of MM VRAM.</p>
</article>
<article class="map-panel" data-era="future" aria-label="Future · proposed, not applied">
<h3>Future · proposed, not applied</h3>
<pre><code>0x3F008000 +---------------------------+
           | MM VRAM: 32 KiB           |
           | Outside Linux RAM at first|
0x3F000000 +---------------------------+
           | OpenSBI: tentative 256 KiB |
           | firmware / BSS / scratch  |
           | stack / heap              |
0x3EFC0000 +---------------------------+
           | Linux SRAM pool:          |
           | tentative 256 KiB          |
0x3EF80000 +---------------------------+

Illustrative split, not finalized.</code></pre>
<p>Measure complete OpenSBI runtime requirements and loader lifetimes first. The proposed upper half overlaps current loader ITCM; the lower half overlaps its data/heap. Relocation, reservations and safe reuse must be resolved before applying this split.</p>
</article>
</div>

<table>
<thead><tr><th>Current loader linker region</th><th>CPU address range [start, end)</th><th>Capacity</th></tr></thead>
<tbody>
<tr><td>RAM / data / heap</td><td><code>0x3EF80000–0x3EF88000</code></td><td>32 KiB</td></tr>
<tr><td>ITCM</td><td><code>0x3EFFC000–0x3F000400</code></td><td>17 KiB</td></tr>
<tr><td>DTCM / stack</td><td><code>0x3F000400–0x3F008000</code></td><td>31 KiB</td></tr>
<tr><td>XRAM</td><td><code>0x40004000–0x40008000</code></td><td>16 KiB</td></tr>
</tbody></table>
<p>MM DRAM aliases: <code>0x3EF80000</code> and cacheable <code>0x7EF80000</code>. MM VRAM aliases: <code>0x3F000000</code> and cacheable <code>0x7F000000</code>. Each pair refers to one physical memory. Alias choice, cache maintenance and cross-core ownership require a single consistent policy.</p>
<h3>External PSRAM: 64 MiB</h3>

<div class="map-pair">
<article class="map-panel" data-era="current" aria-label="Current · implemented">
<h3>Current · implemented</h3>
<pre><code>0x54000000 +---------------------------+
           | OpenSBI reservation: 1 MiB |
           | runtime / BSS / scratch   |
           | stack / heap              |
0x53F00000 +---------------------------+
           | U-Boot / Linux budget     |
           | 63 MiB                    |
           |                           |
           | DTB copy: 0x51FF8000       |
           | Payload: 0x50000000        |
0x50000000 +---------------------------+</code></pre>
<p>Current U-Boot DT exposes 63 MiB; its OpenSBI reservation has <code>no-map</code>. The SDK Linux DT describes 64 MiB with the top 1 MiB reserved. DTB and payload occupy parts of the remaining budget.</p>
</article>
<article class="map-panel" data-era="future" aria-label="Future · proposed, not applied">
<h3>Future · proposed, not applied</h3>
<pre><code>0x54000000 +---------------------------+
           | Linux main-memory target  |
           | 64 MiB                    |
           |                           |
           | kernel / allocator        |
           | page cache / userspace    |
           |                           |
           | U-Boot uses PSRAM first   |
0x50000000 +---------------------------+</code></pre>
<p>Conditional on moving OpenSBI into internal SRAM. DTB placement, boot-time allocations and any IPC reservations must still be accounted for; 64 MiB does not mean 64 MiB of free memory.</p>
</article>
</div>

<h3>What D0 configures today</h3>
<ol>
<li>Wait for M0 synchronization, then enable cache and configure prefetch.</li>
<li>Execute the Rust probe after vendor platform initialization. It prints <code>D0 Rust OK</code> through the vendor UART callback.</li>
<li>Read the compressed length at <code>0x5809FFFC</code>; decompress the payload from <code>0x580A0000</code> to <code>0x50000000</code>. In the current U-Boot package this payload is U-Boot, despite the loader's Linux-oriented names.</li>
<li>Copy 64 KiB of DTB from <code>0x58080000</code> to <code>0x51FF8000</code> and 1 MiB of OpenSBI slot data from <code>0x58800000</code> to <code>0x53F00000</code>.</li>
<li>Clean/invalidate cache, perform the vendor <code>mcor</code> operation, install the loader PMP table and enter OpenSBI with hart ID 0 and the DTB address.</li>
</ol>
<details><summary>D0 loader PMP policy before OpenSBI</summary>
<table><thead><tr><th>Region [start, end)</th><th>Permissions</th></tr></thead><tbody>
<tr><td><code>0x20000000–0x20010000</code></td><td>RW</td></tr>
<tr><td><code>0x30000000–0x30100000</code></td><td>RW</td></tr>
<tr><td><code>0x53F00000–0x54000000</code></td><td>RWX</td></tr>
<tr><td><code>0x40000000–0x40004000</code></td><td>RWX</td></tr>
<tr><td><code>0x50000000–0x54000000</code></td><td>RWX</td></tr>
<tr><td><code>0x58000000–0x5C000000</code></td><td>RW</td></tr>
<tr><td><code>0xE0000000–0xE8000000</code></td><td>RW</td></tr>
</tbody></table>
<p>These are the seven NAPOT entries in <code>pmp_entry_tab</code>. The eighth entry is a no-permission TOR rule with the source bound <code>0xFFFFFFFFFF</code>. PMP is per-hart, not a map of allocated RAM. Generic OpenSBI later configures hart protection for its domains; this table does not establish the final S-mode policy. DT <code>no-map</code> and PMP permissions are different mechanisms. Reserving 1 MiB in DT does not by itself prove that exactly 1 MiB is PMP-protected.</p>
</details>
</section>

<section data-topic="flash" aria-labelledby="flash-map">
<h2 id="flash-map">SPI NOR Flash &amp; SD</h2>
<p>The board has 16 MiB NOR: physical offsets <code>[0x000000, 0x1000000)</code>. Flash stores images; copying or decompressing them creates a separate RAM allocation. A 1 MiB Flash slot does not imply a 1 MiB firmware runtime.</p>

<div class="map-pair">
<article class="map-panel" data-era="current" aria-label="Current · implemented">
<h3>Current · implemented</h3>
<pre><code>0x1000000  +---------------------------+
           | Remaining NOR             |
0x952000   +---------------------------+
           | OpenSBI slot: 1 MiB        |
0x852000   +---------------------------+
           | Gap: 512 KiB              |
0x7D2000   +---------------------------+
           | Rootfs slot: 2.5 MiB      |
0x552000   +---------------------------+
           | Compressed payload        |
           | slot: 0x460000 bytes       |
0x0F2000   +---------------------------+
           | Gap + 8-byte load header   |
0x0E2000   +---------------------------+
           | DTB slot: 64 KiB          |
0x0D2000   +---------------------------+
           | Boot reserve: 192 KiB      |
0x0A2000   +---------------------------+
           | D0 slot: 320 KiB          |
0x052000   +---------------------------+
           | M0 slot: 320 KiB          |
0x002000   +---------------------------+
           | Group0 / Group1 headers   |
0x000000   +---------------------------+</code></pre>
<p>The whole-image container is <code>[0x0D2000, 0x952000)</code>. The U-Boot package reuses the compressed-payload slot and carries the rootfs file for packaging compatibility; that does not establish Linux boot.</p>
</article>
<article class="map-panel" data-era="future" aria-label="Future · proposed, not applied">
<h3>Future · proposed, not applied</h3>
<pre><code>0x1000000  +---------------------------+
           | Config / metadata: 1 MiB  |
0xF00000   +---------------------------+
           | Recovery / backup: 7 MiB  |
0x800000   +---------------------------+
           | Recovery kernel: 4 MiB    |
0x400000   +---------------------------+
           | DTB / settings: SEE BELOW |
0x3D2000   +---------------------------+
           | OpenSBI slot: 1 MiB       |
0x2D2000   +---------------------------+
           | U-Boot slot: 2 MiB        |
0x0D2000   +---------------------------+
           | Boot reserve: 192 KiB      |
0x0A2000   +---------------------------+
           | D0 loader slot: 320 KiB   |
0x052000   +---------------------------+
           | M0 Zephyr slot: 320 KiB   |
0x002000   +---------------------------+
           | Group0 / Group1 headers   |
0x000000   +---------------------------+

DTB proposal: [0x3D2000, 0x412000)
256 KiB; overlaps recovery by 72 KiB.</code></pre>
<p>This is an unresolved proposal, not a valid partition manifest. The drawn space before recovery is only 184 KiB. Choose a smaller DTB/settings slot or move a boundary before implementation. Measure image sizes, update loader sources and rebuild packaging/headers together.</p>
</article>
</div>

<h3>Same XIP entry, different Flash offsets</h3>
<pre><code>M0 CPU address                 physical NOR offset
0x58000000  -----------------&gt; 0x002000 (M0 body)

D0 CPU address                 physical NOR offset
0x58000000  -----------------&gt; 0x052000 (D0 body)
0x58080000  -----------------&gt; 0x0D2000 (DTB)
0x580A0000  -----------------&gt; 0x0F2000 (compressed payload)
0x58800000  -----------------&gt; 0x852000 (OpenSBI slot)</code></pre>
<p>These are current group mappings. For these D0 source addresses, physical offset = CPU address − <code>0x58000000</code> + <code>0x52000</code>. Do not generalize this to every bus alias or future mapping. Both low_load entries are <code>0x58000000</code>, not <code>0x58002000</code> / <code>0x58052000</code>. The SoC primary XIP aperture is 64 MiB (<code>[0x58000000, 0x5C000000)</code>); the board's physical NOR is only 16 MiB.</p>
<h3>SD: storage, not another CPU RAM range</h3>

<div class="map-pair">
<article class="map-panel" data-era="current" aria-label="Current · implemented">
<h3>Current · implemented</h3>
<pre><code>NOR -&amp;gt; D0 loader
       | decompress U-Boot
       | copy DTB / OpenSBI
       v
PSRAM -&amp;gt; OpenSBI -&amp;gt; S-mode U-Boot

SD controller / file reads:
not yet verified on this path.</code></pre>
<p>The generic OpenSBI → S-mode U-Boot prompt was verified with 63 MiB RAM and a 2 Mbps UART. The later Rust D0 experiment separately verified its marker output.</p>
</article>
<article class="map-panel" data-era="future" aria-label="Future · proposed, not applied">
<h3>Future · proposed, not applied</h3>
<pre><code>NOR: Zephyr + loader + firmware
              |
              v
Internal SRAM: OpenSBI (M-mode)
PSRAM: U-Boot (temporary)
              ^
              | read files / blocks
SD: Linux Image + DTB + rootfs
              |
              v
PSRAM: Linux / userspace
SRAM: optional Linux pool + IPC</code></pre>
<p>SD uses block/file offsets, not a CPU memory address interval. SD/MMC initialization, the interrupt or polling path, Linux entry and early console remain to be verified.</p>
</article>
</div>

</section>
</div>

## Source of truth

Current diagrams describe the checked-in loader configuration and local build
inputs, not a live register dump. Capacities are linker limits, not measured
occupancy. Future diagrams describe intended ownership only.

| Source | What it establishes |
|---|---|
| SDK `drivers/bl808_driver/regs/bl808.h` | SRAM capacities, aliases, XIP aperture and IPC flag addresses |
| SDK `startup/m0/bl808_flash.ld` | Current M0 linker regions |
| SDK `examples/low_load/bl808_flash_d0.ld` | Current D0 linker regions |
| SDK `startup/{m0,d0}/source/system_bl808.c` | Startup access control, cache, SRAM and synchronization |
| SDK `bsp/board/bl808/board.c` | M0 UHS PSRAM initialization |
| SDK `examples/low_load/main.c` | Loader copy addresses, cache operations and D0 PMP table |
| `utils/prepare_blflash_low_load.py` | Group entries and physical body offsets |
| `utils/merge_linux_image.py` | Current whole-image slots and size checks |
| `M1s_BL808_Linux_SDK/build.sh` | U-Boot payload packaging and generic OpenSBI build |
| `u-boot/arch/riscv/dts/bl808-d0-m1s-u-boot.dtsi` | 63 MiB exposed RAM and OpenSBI reservation |
| `M1s_BL808_Linux_SDK/bl808_dts/hw808c.dts` | SDK Linux DT RAM and reserved-memory definitions |
| `opensbi/lib/sbi/sbi_init.c` | Generic hart protection configuration before next-stage execution |
| `zephyr/soc/bflb/bl808/soc.c` | Existing Zephyr secondary-core halt sequence |

SDK paths in this table are relative to
`M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/`.
The former book chapters remain in the source tree but are temporarily omitted
from navigation. Their historical layouts are not the baseline for this page.
