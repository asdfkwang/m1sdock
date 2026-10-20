/* RAM-only diagnostic; no block reads/writes and no OpenSBI changes. */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define R32(a) (*(volatile u32 *)(u64)(a))
#define R16(a) (*(volatile u16 *)(u64)(a))
#define R8(a) (*(volatile u8 *)(u64)(a))
#define SDH 0x20060000UL
#define MASK0 0x20000058UL
#define MASK1 0x2000005cUL
#define CLEAR0 0x20000060UL
#define CLEAR1 0x20000064UL
#define PRIORITY 0xe0000144UL
#define CLAIM 0xe0201004UL
#define SOURCE17 (1U << 17)
#define CMD_EVENTS 0x000f0001U
#define CSR_READ(csr) ({ u64 v; __asm__ volatile("csrr %0, " #csr : "=r"(v)); v; })
#define CSR_WRITE(csr, v) __asm__ volatile("csrw " #csr ", %0" :: "r"((u64)(v)) : "memory")
#define IRQ_OFF() __asm__ volatile("csrci sstatus, 2" ::: "memory")
#define IRQ_ON() __asm__ volatile("csrsi sstatus, 2" ::: "memory")

extern void trap_entry(void);
static volatile u32 irq_count, last_claim, last_status, last_m0ic;
static volatile u64 last_cause;
static u32 stages_passed;

void *memcpy(void *dst, const void *src, u64 len)
{
    u8 *d = dst;
    const u8 *s = src;
    while (len--) *d++ = *s++;
    return dst;
}

static void putc_uart(char c)
{
    while (!(R32(0x30002084) & 0x3f)) {}
    R32(0x30002088) = (u8)c;
}

static void puts_uart(const char *s)
{
    while (*s) {
        if (*s == '\n') putc_uart('\r');
        putc_uart(*s++);
    }
}

static void hex(u64 n)
{
    puts_uart("0x");
    for (int i = 60; i >= 0; i -= 4)
        putc_uart("0123456789abcdef"[(n >> i) & 15]);
}

static void field(const char *name, u64 value)
{
    puts_uart(name); hex(value); puts_uart(" ");
}

static void delay_us(u64 n)
{
    u64 start = CSR_READ(time);
    while (CSR_READ(time) - start < n) {}
}

void trap_handler(void)
{
    /* Quiesce CPU delivery until main explicitly arms the next observation. */
    CSR_WRITE(sie, 0);
    last_cause = CSR_READ(scause);
    if (last_cause != (1UL << 63 | 9)) {
        puts_uart("\nUNEXPECTED TRAP ");
        field("scause=", last_cause);
        field("sepc=", CSR_READ(sepc));
        field("stval=", CSR_READ(stval));
        puts_uart("\nSTOP: board RESET required\n");
        for (;;) {}
    }
    last_claim = R32(CLAIM);
    last_status = R32(SDH + 0x30);
    last_m0ic = R32(0x20000050);
    R32(SDH + 0x38) = 0;
    R32(MASK0) = 0xffffffff;
    if (last_claim == 81) {
        R32(SDH + 0x30) = last_status;
        R32(CLEAR0) = SOURCE17;
    }
    __asm__ volatile("fence iorw, iorw" ::: "memory");
    (void)R32(0x20000050);
    if (last_claim) R32(CLAIM) = last_claim;
    irq_count++;
}

static void arm(u32 events)
{
    IRQ_OFF();
    R32(SDH + 0x38) = 0;
    R32(MASK0) = 0xffffffff;
    R32(SDH + 0x30) = 0xffffffff;
    R32(CLEAR0) = SOURCE17;
    u32 old = R32(CLAIM);
    if (old) R32(CLAIM) = old;
    last_claim = last_status = last_m0ic = 0;
    last_cause = 0;
    R32(SDH + 0x34) = events;
    R32(SDH + 0x38) = events;
    R32(MASK0) = ~SOURCE17;
    __asm__ volatile("fence iorw, iorw" ::: "memory");
}

static int wait_irq(u32 before)
{
    CSR_WRITE(sie, 1 << 9);
    IRQ_ON();
    u64 start = CSR_READ(time);
    while (irq_count == before && CSR_READ(time) - start < 500000) {}
    IRQ_OFF();
    field("irq_count=", irq_count);
    field("scause=", last_cause);
    field("claim=", last_claim);
    field("sdh=", last_status);
    field("m0ic=", last_m0ic);
    puts_uart("\n");
    if (irq_count == before) {
        field("live_sdh=", R32(SDH + 0x30));
        field("live_m0ic=", R32(0x20000050));
        field("live_plic=", R32(0xe0001008));
        field("sip=", CSR_READ(sip)); puts_uart("\n");
    }
    return irq_count == before + 1 && last_claim == 81 &&
           last_cause == (1UL << 63 | 9) && (last_m0ic & SOURCE17);
}

static int send_command(u32 idx, u32 arg, u32 flags)
{
    u64 start = CSR_READ(time);
    while (R32(SDH + 0x24) & 3) {
        if (CSR_READ(time) - start > 200000) {
            puts_uart("FAIL: command/data inhibit stuck\n");
            return 0;
        }
    }
    field("CMD=", idx); field("arg=", arg); puts_uart("\n");
    arm(CMD_EVENTS);
    u32 before = irq_count;
    R32(SDH + 0x08) = arg;
    R16(SDH + 0x0e) = (idx << 8) | flags;
    int delivered = wait_irq(before);
    field("response0=", R32(SDH + 0x10));
    field("present=", R32(SDH + 0x24)); puts_uart("\n");
    return delivered && (last_status & 1) && !(last_status & 0x8000);
}

static int reset_command_data(void)
{
    R32(SDH + 0x38) = 0;
    R8(SDH + 0x2f) = 6;
    u64 start = CSR_READ(time);
    while (R8(SDH + 0x2f) & 6) {
        if (CSR_READ(time) - start > 100000) {
            puts_uart("FAIL: command/data reset stuck\n");
            return 0;
        }
    }
    return 1;
}

u64 app_main(void)
{
    u64 saved_status = CSR_READ(sstatus);
    IRQ_OFF();
    u64 saved_sie = CSR_READ(sie), saved_stvec = CSR_READ(stvec);
    u64 saved_sepc = CSR_READ(sepc), saved_scause = CSR_READ(scause);
    u64 saved_stval = CSR_READ(stval);
    u32 orig_en[6];
    const u64 en[6] = {0xe0002000, 0xe0002004, 0xe0002008,
                       0xe0002080, 0xe0002084, 0xe0002088};
    u32 orig_mask0 = R32(MASK0), orig_mask1 = R32(MASK1);
    u32 orig_prio = R32(PRIORITY), orig_mt = R32(0xe0200000), orig_st = R32(0xe0201000);
    u32 orig_ie = R32(SDH + 0x34), orig_sig = R32(SDH + 0x38);
    u16 orig_clk = R16(SDH + 0x2c), orig_mode = R16(SDH + 0x0c);
    u8 orig_power = R8(SDH + 0x29), orig_timeout = R8(SDH + 0x2e);
    u8 orig_host = R8(SDH + 0x28);
    u32 orig_arg = R32(SDH + 0x08);
    u32 orig_gpio[6];
    for (u32 i = 0; i < 6; i++) orig_en[i] = R32(en[i]);
    for (u32 i = 0; i < 6; i++) orig_gpio[i] = R32(0x200008c4 + 4 * i);

    puts_uart("\nBL808 S-MODE IRQ RAM PROBE v1\n");
    field("original_stvec=", saved_stvec);
    field("original_sstatus=", saved_status);
    field("original_sie=", saved_sie); puts_uart("\n");
    for (u32 i = 0; i < 6; i++) R32(en[i]) = 0;
    CSR_WRITE(sie, 0);
    CSR_WRITE(stvec, (u64)trap_entry);
    R32(0xe0200000) = 7;
    R32(0xe0201000) = 7;
    R32(PRIORITY) = 1;
    R32(en[5]) = SOURCE17;
    R32(SDH + 0x38) = 0;
    R32(MASK0) = R32(MASK1) = 0xffffffff;
    R32(CLEAR0) = R32(CLEAR1) = 0xffffffff;
    u32 stale = R32(CLAIM);
    if (stale) R32(CLAIM) = stale;
    R16(SDH + 0x2c) = 1;
    u64 start = CSR_READ(time);
    while (!(R16(SDH + 0x2c) & 2)) {
        if (CSR_READ(time) - start > 100000) {
            puts_uart("FAIL: internal clock not stable\n"); goto restore;
        }
    }
    CSR_WRITE(sie, 1 << 9);
    R32(0xe0201000) = 0;

    for (u32 cycle = 0; cycle < 2; cycle++) {
        puts_uart("FORCED EVENT "); field("cycle=", cycle + 1); puts_uart("\n");
        arm(1 << 16);
        u32 before = irq_count;
        R16(SDH + 0x52) = 1;
        if (!wait_irq(before) || !(last_status & (1 << 16))) {
            puts_uart("FAIL: forced IRQ handler\n"); goto restore;
        }
    }
    stages_passed = 1;
    puts_uart("PASS: actual S-mode external trap + claim81, repeated twice\n");

    R8(SDH + 0x29) = 0x0f;
    R8(SDH + 0x28) = orig_host & ~(2 | 4 | 0x20);
    R8(SDH + 0x2e) = 0x0e;
    R16(SDH + 0x0c) = 0;
    /* Encoded divisors 120, 480, 1023: nominal 400, 100, 47 kHz
     * assuming the configured 96 MHz source. No physical-clock measurement. */
    const u16 clocks[3] = {0x7800, 0xe040, 0xffc0};
    for (u32 profile = 0; profile < 3; profile++) {
        if (!reset_command_data()) goto restore;
        field("CARD_PROFILE=", profile); puts_uart("\n");
        if (profile) {
            /* Match vendor AF config: SDH func0, IE, SMT, drive1, pull-up,
             * no GPIO OE, normal mode. GPIO0..5 only; restore afterwards. */
            for (u32 i = 0; i < 6; i++)
                R32(0x200008c4 + 4 * i) = (orig_gpio[i] & ~0xc0001fffU) | 0x17;
        }
        R16(SDH + 0x2c) = clocks[profile] | 1;
        start = CSR_READ(time);
        while (!(R16(SDH + 0x2c) & 2)) {
            if (CSR_READ(time) - start > 100000) {
                puts_uart("FAIL: divided internal clock not stable\n"); goto restore;
            }
        }
        R16(SDH + 0x2c) = clocks[profile] | 5;
        delay_us(10000);
        field("clock=", R16(SDH + 0x2c));
        field("power=", R8(SDH + 0x29));
        field("present=", R32(SDH + 0x24)); puts_uart("\n");
        if (!send_command(0, 0, 0)) {
            puts_uart("FAIL: CMD0\n"); continue;
        }
        delay_us(1000);
        if (send_command(8, 0x1aa, 0x1a)) {
            if ((R32(SDH + 0x10) & 0xfff) == 0x1aa) {
                stages_passed = 2;
                puts_uart("PASS: real CMD8 R7=0x1aa delivered through S-mode IRQ handler\n");
                goto restore;
            }
            puts_uart("FAIL: CMD8 echo mismatch\n");
        } else {
            puts_uart("CMD8 failed; check CMD55 for legacy-card response\n");
        }
        if (!reset_command_data()) goto restore;
        if (send_command(55, 0, 0x1a)) {
            puts_uart("CARD RESPONDED to CMD55 (SD v1 fallback candidate)\n");
            if (send_command(41, 0x00ff8000, 2))
                puts_uart("CARD RESPONDED to ACMD41; full identification still required\n");
        }
    }
    puts_uart("FAIL: no successful CMD8 echo in tested profiles\n");

restore:
    IRQ_OFF();
    CSR_WRITE(sie, 0);
    R32(SDH + 0x38) = 0;
    R32(MASK0) = R32(MASK1) = 0xffffffff;
    R32(SDH + 0x30) = 0xffffffff;
    R32(CLEAR0) = SOURCE17;
    u32 pending = R32(CLAIM);
    if (pending) R32(CLAIM) = pending;
    for (u32 i = 0; i < 6; i++) R32(en[i]) = orig_en[i];
    R32(PRIORITY) = orig_prio;
    R32(0xe0200000) = orig_mt;
    R32(0xe0201000) = orig_st;
    R16(SDH + 0x2c) = orig_clk;
    R16(SDH + 0x0c) = orig_mode;
    R8(SDH + 0x29) = orig_power;
    R8(SDH + 0x2e) = orig_timeout;
    R8(SDH + 0x28) = orig_host;
    R32(SDH + 0x08) = orig_arg;
    R32(SDH + 0x34) = orig_ie;
    for (u32 i = 0; i < 6; i++) R32(0x200008c4 + 4 * i) = orig_gpio[i];
    R32(MASK0) = orig_mask0;
    R32(MASK1) = orig_mask1;
    R32(SDH + 0x38) = orig_sig;
    CSR_WRITE(stvec, saved_stvec);
    CSR_WRITE(sepc, saved_sepc);
    CSR_WRITE(scause, saved_scause);
    CSR_WRITE(stval, saved_stval);
    CSR_WRITE(sie, saved_sie);
    CSR_WRITE(sstatus, saved_status);
    puts_uart("RESTORED configuration and supervisor trap context; returning to U-Boot\n");
    field("stages_passed=", stages_passed); puts_uart("\n");
    return stages_passed == 2 ? 0 : 1;
}
