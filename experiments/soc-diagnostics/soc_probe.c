/* Read-only MMIO/PMP probes plus a bounded scratch-PSRAM test. No clock writes. */
typedef unsigned long u64;
typedef unsigned int u32;
#define R32(a) (*(volatile u32 *)(u64)(a))
#define CSR_READ(csr) ({ u64 v; __asm__ volatile("csrr %0, " #csr : "=r"(v)); v; })
#define CSR_WRITE(csr, v) __asm__ volatile("csrw " #csr ", %0" :: "r"((u64)(v)) : "memory")

extern void trap_entry(void);
extern u64 read32_probe(u64), read_cycle_probe(void), read_satp_probe(void);
extern u64 read_pmpcfg0_probe(void), read_pmpaddr0_probe(void);
extern u64 read_mstatus_probe(void), read_mideleg_probe(void);
extern char read32_probe_insn[], read_cycle_probe_insn[], read_satp_probe_insn[];
extern char read_pmpcfg0_probe_insn[], read_pmpaddr0_probe_insn[];
extern char read_mstatus_probe_insn[], read_mideleg_probe_insn[];
static volatile u64 fault_cause, fault_value;
static volatile u64 timer_count, timer_last_cause;

struct sbiret { long error; u64 value; };
static struct sbiret sbi_call(u64 ext, u64 fid, u64 arg)
{
    register u64 a0 __asm__("a0") = arg;
    register u64 a1 __asm__("a1") = 0;
    register u64 a6 __asm__("a6") = fid;
    register u64 a7 __asm__("a7") = ext;
    __asm__ volatile("ecall" : "+r"(a0), "+r"(a1) : "r"(a6), "r"(a7) : "memory");
    return (struct sbiret){(long)a0, a1};
}

void *memcpy(void *dst, const void *src, u64 len)
{
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (len--) *d++ = *s++;
    return dst;
}

static void putc_uart(char c)
{
    while (!(R32(0x30002084) & 0x3f)) {}
    R32(0x30002088) = (unsigned char)c;
}
static void puts_uart(const char *s)
{
    while (*s) { if (*s == '\n') putc_uart('\r'); putc_uart(*s++); }
}
static void hex(u64 n)
{
    puts_uart("0x");
    for (int i = 60; i >= 0; i -= 4) putc_uart("0123456789abcdef"[(n >> i) & 15]);
}
static void field(const char *s, u64 v) { puts_uart(s); hex(v); puts_uart(" "); }

void trap_handler(void)
{
    u64 pc = CSR_READ(sepc), cause = CSR_READ(scause);
    if (cause == ((1UL << 63) | 5)) {
        /* Clear STIP through the standard SBI TIME service, not MMIO. */
        (void)sbi_call(0x54494d45, 0, ~0UL);
        timer_last_cause = cause;
        timer_count++;
        CSR_WRITE(sie, 0);
        return;
    }
    int load_fault = pc == (u64)read32_probe_insn && (cause == 5 || cause == 13);
    int csr_fault = cause == 2 && (pc == (u64)read_cycle_probe_insn ||
        pc == (u64)read_satp_probe_insn || pc == (u64)read_pmpcfg0_probe_insn ||
        pc == (u64)read_pmpaddr0_probe_insn || pc == (u64)read_mstatus_probe_insn ||
        pc == (u64)read_mideleg_probe_insn);
    if (!load_fault && !csr_fault) {
        puts_uart("UNEXPECTED TRAP "); field("cause=", cause); field("pc=", pc);
        field("stval=", CSR_READ(stval)); puts_uart("\nRESET required\n");
        for (;;) {}
    }
    fault_cause = cause;
    fault_value = CSR_READ(stval);
    CSR_WRITE(sepc, pc + 4);
}

static void csr_probe(const char *name, u64 (*fn)(void))
{
    fault_cause = fault_value = 0;
    u64 value = fn();
    puts_uart("CSR "); puts_uart(name); puts_uart(" ");
    field("value=", value); field("fault=", fault_cause);
    field("stval=", fault_value); puts_uart("\n");
}

static void memory_probe(u64 address)
{
    fault_cause = fault_value = 0;
    u64 value = read32_probe(address);
    puts_uart("READ32 "); field("address=", address); field("value=", value);
    field("fault=", fault_cause); field("stval=", fault_value); puts_uart("\n");
}

u64 app_main(void)
{
    u64 status = CSR_READ(sstatus);
    __asm__ volatile("csrci sstatus, 2" ::: "memory");
    u64 sie = CSR_READ(sie), vector = CSR_READ(stvec);
    u64 epc = CSR_READ(sepc), cause = CSR_READ(scause), tval = CSR_READ(stval);
    CSR_WRITE(sie, 0);
    CSR_WRITE(stvec, (u64)trap_entry);
    puts_uart("\nBL808 SOC READ/PROTECTION RAM PROBE v1\n");
    field("sstatus=", status); field("sie=", sie); puts_uart("\n");
    csr_probe("satp", read_satp_probe);
    csr_probe("cycle", read_cycle_probe);
    csr_probe("pmpcfg0", read_pmpcfg0_probe);
    csr_probe("pmpaddr0", read_pmpaddr0_probe);
    csr_probe("mstatus", read_mstatus_probe);
    csr_probe("mideleg", read_mideleg_probe);

    struct sbiret spec = sbi_call(0x10, 0, 0);
    struct sbiret supported = sbi_call(0x10, 3, 0x54494d45);
    puts_uart("SBI "); field("spec_error=", spec.error); field("spec_version=", spec.value);
    field("TIME_probe_error=", supported.error); field("TIME_available=", supported.value);
    puts_uart("\n");
    if (!supported.error && supported.value && !(CSR_READ(sip) & 32) && !sie) {
        for (u32 i = 0; i < 3; i++) {
            u64 before = timer_count, t0 = CSR_READ(time);
            struct sbiret ret = sbi_call(0x54494d45, 0, t0 + 10000);
            CSR_WRITE(sie, 32);
            __asm__ volatile("csrsi sstatus, 2" ::: "memory");
            while (timer_count == before && CSR_READ(time) - t0 < 100000) {}
            __asm__ volatile("csrci sstatus, 2" ::: "memory");
            CSR_WRITE(sie, 0);
            (void)sbi_call(0x54494d45, 0, ~0UL);
            puts_uart("SBI_TIMER "); field("sample=", i); field("error=", ret.error);
            field("count=", timer_count); field("scause=", timer_last_cause);
            field("elapsed_ticks=", CSR_READ(time) - t0); puts_uart("\n");
        }
    } else {
        puts_uart("SBI_TIMER skipped: absent TIME or existing timer/interrupt state\n");
    }

    const u64 addresses[] = {
        0x50000000, 0x50100000, 0x51000000,
        0x53f00000, 0x53f01000, 0x53f5fffc, 0x53f60000, 0x53fffffc,
        /* 0x7ef80000 produced a late access fault on this boot state.
         * Exclude unvalidated SRAM aliases until bus/cache setup is studied. */
        0x3ef80000, 0x40000000, 0x58000000,
        0x20000090, 0x20060024, 0x30002008, 0xe0001008,
    };
    for (u32 i = 0; i < sizeof(addresses) / sizeof(addresses[0]); i++)
        memory_probe(addresses[i]);

    fault_cause = 0;
    (void)read_cycle_probe();
    if (!fault_cause) {
        for (u32 i = 0; i < 3; i++) {
            u64 t0 = CSR_READ(time), c0 = read_cycle_probe();
            while (CSR_READ(time) - t0 < 100000) {}
            u64 c1 = read_cycle_probe(), t1 = CSR_READ(time);
            puts_uart("CYCLE_TIME "); field("sample=", i);
            field("ticks=", t1 - t0); field("cycles=", c1 - c0);
            field("cycles_per_tick=", (c1 - c0) / (t1 - t0)); puts_uart("\n");
        }
    }
    /* Only [0x51200000,0x51280000), independently checked by the uploader. */
    volatile u32 *scratch = (volatile u32 *)0x51200000;
    u32 errors = 0;
    const u32 count = 0x80000 / 4;
    u64 begin = CSR_READ(time);
    for (u32 i = 0; i < count; i++) scratch[i] = 0xa55a0000U ^ (i * 0x9e3779b9U);
    __asm__ volatile("fence rw, rw" ::: "memory");
    u64 written = CSR_READ(time);
    for (u32 i = 0; i < count; i++)
        if (scratch[i] != (0xa55a0000U ^ (i * 0x9e3779b9U))) errors++;
    u64 read = CSR_READ(time);
    puts_uart("PSRAM_SCRATCH "); field("bytes=", 0x80000); field("errors=", errors);
    field("write_ticks=", written - begin); field("read_ticks=", read - written);
    puts_uart("\nCPU-visible test; cache may satisfy accesses, not a full physical DRAM test\n");
    CSR_WRITE(stvec, vector); CSR_WRITE(sepc, epc);
    CSR_WRITE(scause, cause); CSR_WRITE(stval, tval);
    CSR_WRITE(sie, sie); CSR_WRITE(sstatus, status);
    puts_uart("RESTORED supervisor context; no clock/PMP register writes performed\n");
    return errors ? 1 : 0;
}
