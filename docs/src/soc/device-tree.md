# Device Tree

```dts
// SPDX-License-Identifier: (GPL-2.0-or-later OR MIT)
/*
 * Sipeed M1s Dock, BL808 D0 (C906): proposed future device tree.
 * Adapted from the BL808 Linux v4 patch series and Sipeed SDK.
 *
 * A standalone design draft targeting future U-Boot upstream integration,
 * not the current working DTB or an OpenSBI-owned platform DTS.
 * Bindings and driver support still require upstream review.
 *
 * PSRAM: 64 MiB for the next-stage OS, subject to boot/IPC reservations.
 * Internal MM DRAM: tentative 256 KiB Linux SRAM pool + 256 KiB OpenSBI.
 * The loader and OpenSBI have NOT been relocated to this SRAM layout.
 * Runtime sizing, loader overlap and cache/PMP policy remain unverified.
 * No invented SD, DMA, clock-controller or pinctrl nodes are included.
 */
/dts-v1/;

/ {
	model = "Sipeed M1s Dock (BL808 D0)";
	compatible = "sipeed,m1s-dock", "sipeed,m1s", "bouffalolab,bl808";
	#address-cells = <1>;
	#size-cells = <1>;

	aliases {
		serial3 = &uart3;
	};

	chosen {
		stdout-path = "serial3:2000000n8";
	};

	memory@50000000 {
		device_type = "memory";
		reg = <0x50000000 0x04000000>;
	};

	/*
	 * Future OpenSBI runtime: [0x3EFC0000, 0x3F000000), 256 KiB.
	 * Replaces the current PSRAM reservation at 0x53F00000 (1 MiB).
	 * This node declares intent; it does not relocate the firmware or
	 * configure PMP. no-map is distinct from hardware access protection.
	 */
	reserved-memory {
		#address-cells = <1>;
		#size-cells = <1>;
		ranges;

		opensbi@3efc0000 {
			reg = <0x3efc0000 0x00040000>;
			no-map;
		};
	};

	/*
	 * Future Linux SRAM pool: [0x3EF80000, 0x3EFC0000), 256 KiB.
	 * Not normal PSRAM and not added to /memory. Pool/consumer nodes
	 * and reservations will follow once ownership and loader reuse are
	 * settled. 0x7EF80000 is a cacheable alias, not another 512 KiB.
	 */

	cpus {
		#address-cells = <1>;
		#size-cells = <0>;
		timebase-frequency = <1000000>;

		cpu0: cpu@0 {
			device_type = "cpu";
			compatible = "thead,c906", "riscv";
			reg = <0>;
			riscv,isa = "rv64imafdc";
			mmu-type = "riscv,sv39";

			cpu0_intc: interrupt-controller {
				compatible = "riscv,cpu-intc";
				interrupt-controller;
				#address-cells = <0>;
				#interrupt-cells = <1>;
			};
		};
	};

	xtal: xtal-clk {
		compatible = "fixed-clock";
		#clock-cells = <0>;
		clock-frequency = <40000000>;
	};

	soc {
		compatible = "simple-bus";
		#address-cells = <1>;
		#size-cells = <1>;
		ranges;
		interrupt-parent = <&plic>;
		dma-noncoherent;

		uart3: serial@30002000 {
			/*
			 * Linux-oriented candidate binding. The current local
			 * U-Boot serial driver matches "bflb,bl808-uart";
			 * this spelling is not a working-driver guarantee.
			 */
			compatible = "bouffalolab,bl808-uart";
			reg = <0x30002000 0x1000>;
			interrupts = <20 4>; /* Linux IRQ_TYPE_LEVEL_HIGH */
			clocks = <&xtal>;
			current-speed = <2000000>;
			status = "okay";
		};

		plic: interrupt-controller@e0000000 {
			compatible = "bouffalolab,bl808-plic", "thead,c900-plic";
			reg = <0xe0000000 0x04000000>;
			interrupts-extended = <&cpu0_intc 11>, <&cpu0_intc 9>;
			interrupt-controller;
			#address-cells = <0>;
			#interrupt-cells = <2>;
			riscv,ndev = <82>;
		};

		/*
		 * Candidate from the vendor C906 OpenSBI CLINT-base calculation:
		 * PLIC base + 0x04000000. Keep disabled until MTIP works on D0.
		 * This draft therefore does not establish an SBI timer service.
		 */
		clint: timer@e4000000 {
			compatible = "thead,c900-clint";
			reg = <0xe4000000 0x10000>;
			interrupts-extended = <&cpu0_intc 7>;
			status = "disabled";
		};
	};
};
```
