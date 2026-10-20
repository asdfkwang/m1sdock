CROSS_COMPILE ?= riscv64-linux-gnu-
CFLAGS = -march=rv64imac_zicsr_zifencei -mabi=lp64 -mcmodel=medany \
         -msmall-data-limit=0 -ffreestanding -fno-builtin -fno-pic \
         -fno-stack-protector -fno-asynchronous-unwind-tables -Wall -Wextra -Werror -Os

.PHONY: all
all: build/irq_probe.srec

build/irq_probe.elf: irq_probe.c irq_entry.S ram.ld
	mkdir -p build
	$(CROSS_COMPILE)gcc $(CFLAGS) -nostdlib -static -no-pie \
	    -Wl,--build-id=none,-T,ram.ld -o $@ irq_entry.S irq_probe.c

build/irq_probe.srec: build/irq_probe.elf
	$(CROSS_COMPILE)objcopy -O srec --srec-forceS3 $< $@
