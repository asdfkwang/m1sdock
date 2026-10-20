# Memory Map

BL808 · M1s Dock

<div class="memory-map" data-cpu="m0">
<div class="cpu-navigation" hidden>
<div class="cpu-tabs" role="tablist" aria-label="Memory map view">
<button type="button" role="tab" id="cpu-tab-m0" aria-controls="cpu-panel-m0" aria-selected="true" tabindex="0" data-cpu-tab="m0"><strong>M0</strong><span>E907 · RV32</span></button>
<button type="button" role="tab" id="cpu-tab-d0" aria-controls="cpu-panel-d0" aria-selected="false" tabindex="-1" data-cpu-tab="d0"><strong>D0</strong><span>C906 · RV64</span></button>
<button type="button" role="tab" id="cpu-tab-flash" aria-controls="cpu-panel-flash" aria-selected="false" tabindex="-1" data-cpu-tab="flash"><strong>FLASH</strong><span>16 MiB · NOR</span></button>
</div>
<div class="cpu-paging" role="group" aria-label="Memory map pages">
<button type="button" data-cpu-step="-1" aria-label="Previous map" disabled>&larr;</button>
<span data-cpu-position aria-live="polite" aria-atomic="true">M0 · 1 / 3</span>
<button type="button" data-cpu-step="1" aria-label="Next map">&rarr;</button>
</div>
</div>

<div class="cpu-viewport">
<section class="cpu-panel" id="cpu-panel-m0" data-cpu-panel="m0" role="tabpanel" aria-labelledby="cpu-tab-m0" tabindex="0">
<h2 class="cpu-heading">M0 <span>E907 · RV32</span></h2>
<div class="map-intro">
<p class="map-kicker">M0 ADDRESS SPACE</p>
<p class="map-description">A 32-bit address space, with high addresses at the top. MCU SRAM provides 224 KiB for the Zephyr design; application code uses Flash XIP.</p>
<div class="map-legend" aria-label="Memory colors">
<span data-memory="m0">M0 SRAM / code</span>
<span data-memory="flash">NOR Flash</span>
<span data-memory="psram">PSRAM</span>
<span data-memory="xram">XRAM / IPC</span>
</div>
</div>

<div class="map-layout">
<figure class="address-map" aria-labelledby="m0-address-map-title">
<figcaption id="m0-address-map-title"><strong>Address space</strong><span>4 GiB · schematic</span></figcaption>
<div class="address-limit"><code>0xFFFF_FFFF</code><span>Highest address</span></div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x9001_FFFF</code><code>0x9000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Boot ROM</strong><span>128 KiB</span></div><p>On-chip boot firmware</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x6205_7FFF</code><code>0x6202_0000</code></div>
<div class="memory-region region-primary" data-memory="m0"><div class="region-heading"><strong>MCU SRAM</strong><span>224 KiB</span></div><p>OCRAM 64 KiB + WRAM 160 KiB</p><span class="region-tag">Cacheable address alias</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x5BFF_FFFF</code><code>0x5800_0000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>NOR Flash · XIP</strong><span>64 MiB window</span></div><p>Board storage: 16 MiB</p><span class="code-owner">M0 · Zephyr code</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x53FF_FFFF</code><code>0x5000_0000</code></div>
<div class="memory-region " data-memory="psram"><div class="region-heading"><strong>PSRAM</strong><span>64 MiB</span></div><p>External main memory</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x4000_3FFF</code><code>0x4000_0000</code></div>
<div class="memory-region " data-memory="xram"><div class="region-heading"><strong>XRAM</strong><span>16 KiB</span></div><p>Shared memory · IPC</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x3F00_7FFF</code><code>0x3EF8_0000</code></div>
<div class="memory-region " data-memory="mm"><div class="region-heading"><strong>MM SRAM</strong><span>544 KiB</span></div><p>DRAM 512 KiB + VRAM 32 KiB</p><span class="region-tag">Non-cache access from M0</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0x3000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>MM peripherals</strong><span>Base</span></div><p>Multimedia register blocks</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x2205_7FFF</code><code>0x2202_0000</code></div>
<div class="memory-region region-alias" data-memory="m0"><div class="region-heading"><strong>MCU SRAM alias</strong><span>Same 224 KiB</span></div><p>Non-cacheable address alias</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0x2000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>MCU peripherals</strong><span>Base</span></div><p>GLB · UART · GPIO · timers</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-limit"><code>0x0000_0000</code><span>Lowest address</span></div>
<p class="map-footnote">Region start and end addresses are inclusive. Gaps compress other address ranges; block heights are not proportional to capacity. Peripheral markers show register-block bases.</p>
</figure>

<aside class="map-details" aria-label="M0 memory details">
<section class="detail-card" aria-labelledby="m0-mcu-sram-title">
<p class="map-kicker">MCU SRAM · EXPANDED</p>
<h2 id="m0-mcu-sram-title">224 KiB for M0</h2>
<p>WRAM is assigned as 160 KiB MCU RAM. OCRAM adds 64 KiB.</p>
<div class="sram-stack" aria-label="MCU SRAM from high to low addresses">
<div class="sram-bank sram-wram"><code>0x6205_7FFF</code><div><strong>WRAM</strong><span>160 KiB</span></div><code>0x6203_0000</code></div>
<div class="sram-bank sram-ocram"><code>0x6202_FFFF</code><div><strong>OCRAM</strong><span>64 KiB</span></div><code>0x6202_0000</code></div>
</div>
<div class="runtime-note"><strong>Zephyr SRAM</strong><p>Data · BSS · stacks · heap · selected code</p><p>Section sizes and IPC reservations remain to be linked and measured.</p></div>
</section>

<section class="detail-card" aria-labelledby="m0-alias-title">
<p class="map-kicker">ONE PHYSICAL MEMORY</p>
<h2 id="m0-alias-title">Two address aliases</h2>
<dl class="map-facts">
<dt>Cacheable</dt><dd><code>0x6202_0000</code>–<code>0x6205_7FFF</code></dd>
<dt>Non-cacheable</dt><dd><code>0x2202_0000</code>–<code>0x2205_7FFF</code></dd>
</dl>
<p>Both ranges address the same 224 KiB. Cache state and IPC ownership require an explicit policy.</p>
</section>

<section class="detail-card" aria-labelledby="m0-xip-title">
<p class="map-kicker">CODE IN FLASH</p>
<h2 id="m0-xip-title">Zephyr · XIP</h2>
<div class="xip-placement"><span class="code-owner">M0 code</span><span>NOR Flash storage</span></div>
<p>The orange region identifies storage. The blue label identifies the processor executing its code.</p>
<dl class="map-facts">
<dt>M0 CPU entry</dt><dd><code>0x5800_0000</code></dd>
<dt>Physical NOR body offset</dt><dd><code>0x0000_2000</code></dd>
</dl>
<p>The Zephyr image must fit the 320 KiB M0 slot. Its final layout requires a linked image.</p>
</section>
</aside>
</div>
</section>

<section class="cpu-panel" id="cpu-panel-d0" data-cpu-panel="d0" role="tabpanel" aria-labelledby="cpu-tab-d0" tabindex="0">
<h2 class="cpu-heading">D0 <span>C906 · RV64</span></h2>
<div class="map-intro">
<p class="map-kicker">D0 PHYSICAL ADDRESS SPACE</p>
<p class="map-description">MM SRAM provides 512 KiB DRAM and 32 KiB VRAM. PSRAM provides 64 MiB of main memory. C906 is an RV64 core; this diagram shows the lower 4 GiB of physical addresses.</p>
<div class="map-legend" aria-label="Memory colors">
<span data-memory="d0">D0 SRAM / code</span>
<span data-memory="m0">MCU SRAM</span>
<span data-memory="flash">NOR Flash</span>
<span data-memory="psram">PSRAM</span>
<span data-memory="xram">XRAM / IPC</span>
</div>
</div>

<div class="map-layout">
<figure class="address-map" aria-labelledby="d0-address-map-title">
<figcaption id="d0-address-map-title"><strong>Address space</strong><span>Lower 4 GiB · schematic</span></figcaption>
<div class="address-limit"><code>0xFFFF_FFFF</code><span>Window upper bound</span></div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0xE400_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Core timer</strong><span>Base</span></div><p>CORET timer registers</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0xE000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>PLIC</strong><span>Base</span></div><p>Platform interrupt controller</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x9001_FFFF</code><code>0x9000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Boot ROM</strong><span>128 KiB</span></div><p>On-chip boot firmware</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x5BFF_FFFF</code><code>0x5800_0000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>NOR Flash · XIP</strong><span>64 MiB window</span></div><p>Board storage: 16 MiB</p><span class="code-owner">D0 · loader code</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x53FF_FFFF</code><code>0x5000_0000</code></div>
<div class="memory-region " data-memory="psram"><div class="region-heading"><strong>PSRAM</strong><span>64 MiB</span></div><p>External main memory</p><span class="code-owner">D0 · U-Boot / Linux</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x4000_3FFF</code><code>0x4000_0000</code></div>
<div class="memory-region " data-memory="xram"><div class="region-heading"><strong>XRAM</strong><span>16 KiB</span></div><p>Shared memory · IPC</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x3F00_7FFF</code><code>0x3F00_0000</code></div>
<div class="memory-region region-primary" data-memory="d0"><div class="region-heading"><strong>MM VRAM</strong><span>32 KiB</span></div><p>On-chip SRAM</p><span class="region-tag">D0 cache path</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x3EFF_FFFF</code><code>0x3EF8_0000</code></div>
<div class="memory-region region-primary" data-memory="d0"><div class="region-heading"><strong>MM DRAM</strong><span>512 KiB</span></div><p>On-chip SRAM</p><span class="region-tag">D0 cache path</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0x3000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>MM peripherals</strong><span>Base</span></div><p>Multimedia register blocks</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row">
<div class="address-range"><code>0x2205_7FFF</code><code>0x2202_0000</code></div>
<div class="memory-region " data-memory="m0"><div class="region-heading"><strong>MCU SRAM</strong><span>224 KiB</span></div><p>OCRAM 64 KiB + WRAM 160 KiB</p><span class="region-tag">Non-cache access from D0</span></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-row address-marker">
<div class="address-range"><code>0x2000_0000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>MCU peripherals</strong><span>Base</span></div><p>GLB · UART · GPIO · timers</p></div>
</div>
<div class="address-gap" aria-hidden="true"><span>⋮</span><i></i></div>
<div class="address-limit"><code>0x0000_0000</code><span>Window lower bound</span></div>
<p class="map-footnote">Region start and end addresses are inclusive. Gaps compress other address ranges; block heights are not proportional to capacity. Peripheral markers show register-block bases. Linux virtual addresses are separate.</p>
</figure>

<aside class="map-details" aria-label="D0 memory details">
<section class="detail-card" aria-labelledby="d0-mm-sram-title">
<p class="map-kicker">MM SRAM · EXPANDED</p>
<h2 id="d0-mm-sram-title">544 KiB for MM</h2>
<p>DRAM and VRAM are both on-chip SRAM. Available banks depend on the SoC SRAM configuration.</p>
<div class="sram-stack" aria-label="MM SRAM from high to low addresses">
<div class="sram-bank sram-vram"><code>0x3F00_7FFF</code><div><strong>MM VRAM</strong><span>32 KiB</span></div><code>0x3F00_0000</code></div>
<div class="sram-bank sram-dram"><code>0x3EFF_FFFF</code><div><strong>MM DRAM</strong><span>512 KiB</span></div><code>0x3EF8_0000</code></div>
</div>
<div class="runtime-note"><strong>Internal firmware memory</strong><p>Code · data · stacks · scratch</p><p>Firmware placement and Linux SRAM reservations require a linked memory layout.</p></div>
</section>

<section class="detail-card" aria-labelledby="d0-cache-title">
<p class="map-kicker">D0 MEMORY ACCESS</p>
<h2 id="d0-cache-title">Core-specific cache paths</h2>
<dl class="map-facts">
<dt>MM DRAM · cache path</dt><dd><code>0x3EF8_0000</code>–<code>0x3EFF_FFFF</code></dd>
<dt>MM VRAM · cache path</dt><dd><code>0x3F00_0000</code>–<code>0x3F00_7FFF</code></dd>
<dt>MCU SRAM · non-cache path</dt><dd><code>0x2202_0000</code>–<code>0x2205_7FFF</code></dd>
</dl>
<p>These are the D0 paths in Reference Manual Table 1.2. Firmware and OS memory attributes determine live cache behavior. Shared contents need cache maintenance and an ownership policy.</p>
</section>

<section class="detail-card" aria-labelledby="d0-psram-title">
<p class="map-kicker">EXTERNAL MAIN MEMORY</p>
<h2 id="d0-psram-title">PSRAM · 64 MiB</h2>
<div class="psram-placement"><span class="code-owner">U-Boot</span><span class="code-owner">Linux</span><span>Successive boot stages</span></div>
<dl class="map-facts">
<dt>Physical address range</dt><dd><code>0x5000_0000</code>–<code>0x53FF_FFFF</code></dd>
</dl>
<p>Green identifies PSRAM; violet identifies D0 code using it. Firmware reservations and boot allocations reduce the memory available to Linux.</p>
</section>

<section class="detail-card" aria-labelledby="d0-xip-title">
<p class="map-kicker">CODE IN FLASH</p>
<h2 id="d0-xip-title">D0 loader · XIP</h2>
<div class="xip-placement"><span class="code-owner">D0 code</span><span>NOR Flash storage</span></div>
<dl class="map-facts">
<dt>D0 CPU entry</dt><dd><code>0x5800_0000</code></dd>
<dt>Physical NOR body offset</dt><dd><code>0x0005_2000</code></dd>
</dl>
<p>Group1 maps the D0 loader at this CPU entry. M0 uses the same entry value with a different physical Flash offset.</p>
</section>
</aside>
</div>
</section>
<section class="cpu-panel" id="cpu-panel-flash" data-cpu-panel="flash" role="tabpanel" aria-labelledby="cpu-tab-flash" tabindex="0">
<h2 class="cpu-heading">FLASH <span>16 MiB · NOR · ef4018</span></h2>
<div class="map-intro">
<p class="map-kicker">INITIAL STORED-IMAGE LAYOUT</p>
<p class="map-description">low_load, OpenSBI, U-Boot and the compressed kernel have separate storage slots before execution. Addresses here are physical NOR offsets, starting at zero.</p>
<div class="map-legend" aria-label="Flash map colors">
<span data-memory="flash">Flash storage</span>
<span data-memory="m0">M0 image</span>
<span data-memory="d0">D0 image</span>
<span data-memory="system">Reserved / padding</span>
</div>
</div>

<div class="map-layout">
<figure class="address-map flash-address-map" aria-labelledby="flash-address-map-title">
<figcaption id="flash-address-map-title"><strong>Physical Flash offsets</strong><span>16 MiB · schematic</span></figcaption>
<div class="address-limit"><code>0x00FF_FFFF</code><span>Last byte of NOR</span></div>
<div class="address-row">
<div class="address-range"><code>0x00FF_FFFF</code><code>0x0095_2000</code></div>
<div class="memory-region flash-kernel" data-memory="flash"><div class="region-heading"><strong>Kernel · Image.lz4</strong><span>6.68 MiB slot</span></div><p>Dedicated compressed-kernel storage</p><span class="code-owner" data-owner="d0">D0 · Linux kernel</span><span class="region-tag">Kernel packaging pending</span></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0095_1FFF</code><code>0x0085_2000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>OpenSBI · fw_jump.bin</strong><span>1 MiB slot</span></div><p>Machine-mode firmware image</p><span class="code-owner" data-owner="d0">D0 · OpenSBI</span></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0085_1FFF</code><code>0x007D_2000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Reserved gap</strong><span>512 KiB</span></div><p>Padding in the whole-image container</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x007D_1FFF</code><code>0x0055_2000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Legacy rootfs / reserved</strong><span>2.5 MiB slot</span></div><p>Packaging compatibility area</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0055_1FFF</code><code>0x000F_2000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>U-Boot · compressed</strong><span>4.375 MiB slot</span></div><p>U-Boot payload in the whole image</p><span class="code-owner" data-owner="d0">D0 · U-Boot</span></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x000F_1FFF</code><code>0x000F_1FF8</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>U-Boot load header</strong><span>8 bytes</span></div><p>Destination address + compressed length</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x000F_1FF7</code><code>0x000E_2000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Reserved gap</strong><span>64 KiB − 8 B</span></div><p>Padding before the payload header</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x000E_1FFF</code><code>0x000D_2000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>Device tree · DTB</strong><span>64 KiB slot</span></div><p>Hardware description for the boot chain</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x000D_1FFF</code><code>0x000A_2000</code></div>
<div class="memory-region " data-memory="system"><div class="region-heading"><strong>Boot reserve</strong><span>192 KiB</span></div><p>Reserved space after low_load images</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x000A_1FFF</code><code>0x0005_2000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>low_load · D0</strong><span>320 KiB slot</span></div><p>D0 loader body</p><span class="code-owner" data-owner="d0">D0 · C906</span></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0005_1FFF</code><code>0x0000_2000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>low_load · M0</strong><span>320 KiB slot</span></div><p>M0 initialization image</p><span class="code-owner" data-owner="m0">M0 · E907</span></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0000_1FFF</code><code>0x0000_1000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>Group1 boot header</strong><span>4 KiB sector</span></div><p>BootROM metadata for the D0 image</p></div>
</div>
<div class="address-row">
<div class="address-range"><code>0x0000_0FFF</code><code>0x0000_0000</code></div>
<div class="memory-region " data-memory="flash"><div class="region-heading"><strong>Group0 boot header</strong><span>4 KiB sector</span></div><p>BootROM metadata for the M0 image</p></div>
</div>
<div class="address-limit"><code>0x0000_0000</code><span>First byte of NOR</span></div>
<p class="map-footnote">Start and end offsets are inclusive. Every block shows a slot or reserved range; slot capacity is not the image byte length. Block heights are not proportional to capacity. This is a storage layout definition.</p>
</figure>

<aside class="map-details" aria-label="Flash storage details">
<section class="detail-card" aria-labelledby="flash-images-title">
<p class="map-kicker">CONTENTS BEFORE EXECUTION</p>
<h2 id="flash-images-title">Images stored in NOR</h2>
<dl class="map-facts">
<dt>low_load · M0 body</dt><dd><code>0x0000_2000</code><span class="code-owner" data-owner="m0">M0</span></dd>
<dt>low_load · D0 body</dt><dd><code>0x0005_2000</code><span class="code-owner" data-owner="d0">D0</span></dd>
<dt>U-Boot · compressed payload</dt><dd><code>0x000F_2000</code><span class="code-owner" data-owner="d0">D0</span></dd>
<dt>OpenSBI · firmware image</dt><dd><code>0x0085_2000</code><span class="code-owner" data-owner="d0">D0</span></dd>
<dt>Kernel · dedicated slot</dt><dd><code>0x0095_2000</code><span class="code-owner" data-owner="d0">D0</span></dd>
</dl>
<p>Orange identifies persistent storage. Blue and violet labels identify the processor that uses each image.</p>
</section>

<section class="detail-card" aria-labelledby="flash-kernel-title">
<p class="map-kicker">DEDICATED KERNEL SLOT</p>
<h2 id="flash-kernel-title">Kernel alongside U-Boot</h2>
<p>The documented storage plan puts a separate kernel slot immediately after the existing whole-image container.</p>
<dl class="map-facts">
<dt>Slot start</dt><dd><code>0x0095_2000</code></dd>
<dt>Slot capacity</dt><dd><code>0x006A_E000</code><span>6.68 MiB</span></dd>
</dl>
<p>Kernel packing and loader support are not implemented yet. The load metadata and compressed payload must fit inside this slot; the payload offset remains to be finalized.</p>
<p>The existing packager reuses its kernel-named payload slot for U-Boot. This layout gives U-Boot and the kernel separate regions.</p>
</section>

<section class="detail-card" aria-labelledby="flash-addresses-title">
<p class="map-kicker">STORAGE COORDINATES</p>
<h2 id="flash-addresses-title">Flash starts at zero</h2>
<dl class="map-facts">
<dt>NOR physical offsets</dt><dd><code>0x0000_0000</code>–<code>0x00FF_FFFF</code></dd>
<dt>M0 CPU XIP entry → body offset</dt><dd><code>0x5800_0000</code><span>→</span><code>0x0000_2000</code></dd>
<dt>D0 CPU XIP entry → body offset</dt><dd><code>0x5800_0000</code><span>→</span><code>0x0005_2000</code></dd>
</dl>
<p>The M0 and D0 pages show CPU addresses. This page shows where image bytes are stored in the NOR chip.</p>
</section>
</aside>
</div>
</section>

</div>
</div>

## References

- [BL808 Reference Manual §1.4, Address Mapping](https://raw.githubusercontent.com/bouffalolab/bl_docs/main/BL808_RM/en/BL808_RM_en_1.3.pdf): core-specific SRAM cache paths, ROM, PSRAM, XRAM and peripheral bases. MM SRAM availability depends on SRAM configuration.
- SDK `drivers/bl808_driver/regs/bl808.h`: MCU and MM SRAM capacities and the XIP address window.
- SDK `drivers/bl808_driver/startup/m0/bl808_flash.ld`: M0 XIP entry and XRAM region. Zephyr SRAM is a design allocation, not measured firmware occupancy.
- SDK `drivers/bl808_driver/risc-v/Core/Include/core_rv64.h`: D0 PLIC and core timer bases.
- SDK `examples/low_load/main.c`: D0 loader PSRAM copy destinations.
- `utils/prepare_blflash_low_load.py`: Group0 / Group1 entries and physical M0 / D0 Flash body offsets.
- `utils/merge_linux_image.py` and SDK `build.sh`: whole-image slots and U-Boot payload packaging.
- `docs/src/flash-layout.md`: dedicated kernel storage plan after the whole image; the separate-kernel packing path remains unimplemented.

SDK paths are relative to `M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/`.
