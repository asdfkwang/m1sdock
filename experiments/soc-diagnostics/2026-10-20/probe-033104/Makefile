CROSS_COMPILE ?= riscv64-linux-gnu-
CFLAGS = -march=rv64imac_zicsr_zifencei -mabi=lp64 -mcmodel=medany \
         -msmall-data-limit=0 -ffreestanding -fno-builtin -fno-pic \
         -fno-stack-protector -fno-asynchronous-unwind-tables -Wall -Wextra -Werror -Os
.PHONY: all
all: build/soc_probe.srec
build/soc_probe.elf: soc_probe.c probes.S ram.ld ../sdh-irq/irq_entry.S
	mkdir -p build
	$(CROSS_COMPILE)gcc $(CFLAGS) -nostdlib -static -no-pie \
	  -Wl,--build-id=none,-T,ram.ld -o $@ ../sdh-irq/irq_entry.S probes.S soc_probe.c
build/soc_probe.srec: build/soc_probe.elf
	$(CROSS_COMPILE)objcopy -O srec --srec-forceS3 $< $@
