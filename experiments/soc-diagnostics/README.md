# M1s Dock clock and S-mode memory-protection study

The scope is the currently flashed generic OpenSBI -> S-mode U-Boot chain.
Clock selectors, dividers and gate states are observed, not reprogrammed.
The only RAM writes outside the diagnostic image/stack are bounded to
unreserved PSRAM `[0x51200000, 0x51280000)`. Firmware memory is only read.

## Clock snapshot

See the complete U-Boot `clk dump` and raw register reads in
[the characterization transcript](../sdh-irq/2026-10-20/characterize-032621/transcript.txt)
and [register JSON](../sdh-irq/2026-10-20/characterize-032621/registers.json).

| Domain | Driver/register interpretation | Evidence limit |
|---|---|---|
| MCU/M0 CPU | HBN_ROOT -> PDS_PLL -> WIFIPLL 320 MHz branch; CPU divider 0 | Driver calculation, not an M0 counter measurement |
| MCU bus | 320 MHz / 4 = 80 MHz | Register interpretation |
| D0 CPU | MM_MUXPLL CPUPLL 400 MHz branch, divider 0 | Driver calculation; cycle/time sampling is a separate test |
| MM bus | BCLK1X 160 MHz, BCLK2X 200 MHz | Register interpretation |
| SDH module | WIFIPLL 480 MHz / 5, divider 0, enabled = 96 MHz | PLL rate is a driver assumption; no scope measurement |
| SD bus | SDHCI register `0x0107`: source / 2 = 48 MHz | U-Boot reports requested mode 50 MHz; actual inferred divisor differs |
| UART3 | MM_UART selects MM_XCLK 40 MHz; period register `0x00130013` | TX/RX divider 20 implies 2 Mbps; console works at 2 Mbps |

The clock dump includes `-19`/`<NULL>` entries for missing parent/clock
definitions. These are driver/model gaps, not proof that the physical clock
is absent. Fixed-rate clock table entries do not measure PLL output.

## Initial protection observations

[First raw run](2026-10-20/probe-033104/transcript.txt) used a temporary
S-mode trap vector and recovered from deliberately attempted illegal CSR
reads and load access faults:

- `satp = 0`: bare address translation in this test.
- `cycle` was readable; `pmpcfg0`, `pmpaddr0`, `mstatus` and `mideleg` reads
  raised illegal-instruction exception 2 and recovered. No PMP register was
  modified, and no PMP CSR contents were obtained.
- Reads at `0x53F00000`, `0x53F01000`, `0x53F5FFFC` raised load-access fault
  5, consistent with OpenSBI runtime protection.
- Reads at `0x53F60000` and `0x53FFFFFC` succeeded. Thus the DT's complete
  1 MiB reservation must not be described as fully read-protected by PMP.
  These are sampled points, not an exhaustive permission map.
- `0x3EF80000` was readable. The subsequent `0x7EF80000` alias read produced
  a load-access fault with reported PC after the isolated load probe. The
  handler refused to guess a recovery point and stopped; RESET was required.

The failed alias probe is not evidence of a defective RAM, a nonexistent
alias or a particular PMP entry. Bus/cache configuration and fault timing
require separate study before using this alias in a new layout. The initial
run did not reach cycle/time sampling or the scratch-RAM test.

## Completed bounded probes after RESET

[Successful raw run](2026-10-20/probe-033603/transcript.txt),
[decoded observations](2026-10-20/probe-033603/results.json) and the exact
sources/image retained alongside them establish:

- The generic OpenSBI advertises SBI specification 3.0 and the TIME extension.
  Three `set_timer` requests, each 10,000 time ticks ahead, produced three
  supervisor timer interrupts (`scause = 0x8000000000000005`). Observed
  intervals were 10,423, 10,421 and 10,421 ticks, including handler/software
  overhead. No OpenSBI patch was used.
- All four attempted machine/PMP CSR reads trapped with exception 2 and
  recovered. This proves privilege enforcement for these accesses, not the
  values of the PMP registers.
- The three protected OpenSBI sample reads again faulted; the two samples
  above `0x53F60000` again succeeded. Keep the complete 1 MiB reserved in the
  memory map: OS reservation and observed hardware access denial differ.
- Three cycle/time samples measured approximately 380 cycles per time tick
  (379.99843, 379.99918, 379.99638). If `time` really runs at 1 MHz, these imply
  approximately 380 MHz, whereas the clock driver's table says 400 MHz.
  The discrepancy is unresolved; neither the assumed time reference nor
  the PLL output was calibrated against an external clock. Do not present
  the driver table as a measured CPU frequency.
- A 512 KiB pattern write/read at `[0x51200000, 0x51280000)` found zero errors.
  Cache may serve these accesses; this is a bounded CPU-visible RAM check,
  not a physical full-capacity PSRAM or DMA-coherency test.
- The diagnostic restored the supervisor context, returned zero and the
  original U-Boot `version` command responded afterward. The unvalidated
  SRAM alias was excluded. No flash, clock or PMP configuration was written.

## Reproduce bounded probes

```sh
make -C experiments/soc-diagnostics
# Close picocom and both UART loggers; board must be at the U-Boot prompt.
blflashcommand/venv/bin/python -B experiments/soc-diagnostics/run.py
```

The uploader uses the existing U-Boot `loads`, `crc32`, `go` commands and
checks current reservations. S-record CRC is checked before execution.
The target's trap handler recovers only at explicitly identified 4-byte test
instructions. Unexpected traps print cause/PC/address and stop for RESET.
Unvalidated cacheable SRAM aliases are excluded from subsequent probes.
Normal completion restores the supervisor trap/interrupt context and returns
to U-Boot. It does not test write/execute denial against live firmware.

Every run retains raw UART text, the exact target sources, the S-record image
and SHA-256. These are diagnostic sources and evidence, not an upstream DTS
or production memory test. No live CPU/PSRAM/UART clock switching is attempted.
