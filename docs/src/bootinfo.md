# Bootinfo Format (BFNP / BFAP)

Two bootinfos live in the first flash pages, one per CPU group.
Read directly from flash by the ROM, no intermediate download.

| Element | magic | Size | Covers |
|---|---|---|---|
| group0 (**BFNP**) | `0x504E4642` | 1636 B | m0 image |
| group1 (**BFAP**) | `0x50414642` | 352 B | d0 image |

## Common 352-byte header structure

```c
struct bootinfo_hdr {
    /*  0x00 */ char     magic[4];        // "BFNP"/"BFAP"
    /*  0x04 */ uint32_t revision;        // 1
    /*  0x08 */ uint32_t fcfg_magic;      // group0: "FCFG"; group1: 0
    /*  0x0C..0x7F */                      // flash cfg / crc_fixup / ota table (group0 only)
    /*  0x80..0xAF */ uint8_t bootcfg[48];   // see below
    /*  0xB0..0xFF */ cpu_cfg_t slot[3];     // m0, d0, lp
    /*  0xF8 */ uint16_t boot2_start;
    /*  0x100..0x107 */ flashcfg_t flash_cfg;   // group0 only
    /*  0x108..0x12F */ patch_on_read[32];
    /*  0x130..0x14F */ patch_on_jump[32];
    /*  0x15C */ uint32_t crc32;
};
struct cpu_cfg {                 // 24 bytes each
    uint32_t flags;              // bit 0 = slot valid
    uint32_t rsvd[2];
    uint32_t flash_addr;         // source offset in NOR
    uint32_t copy_dest;          // RAM/XIP destination
    uint32_t len;
};
struct bootcfg {                 // 48 bytes at 0x80
    /* 0x00 */ uint8_t  boot_mode;       // sign/encrypt/crc flags
    /* 0x01 */ uint8_t  boot_mode2;
    /* 0x02..0x03 */ uint16_t rsvd;
    /* 0x04 */ uint32_t img_offset;      // deviation from 'img_start_addr'
    /* 0x08 */ uint32_t hash_ignore : 1,  crc_ignore : 1, ...
    /* 0x0C */ uint32_t img_len_cnt;     // <= 0x9450 / 0x7240 (see flash-layout)
};
```

## Verified field samples

### group0 (BFNP, in-factory layout)

| Offset | Field | Value | Note |
|---|---|---|---|
| 0x000 | magic | `BFN..` | `424F 4E42` LE = `0x504E4642` |
| 0x004 | rev | 1 | |
| 0x008 | fcfg | `4643 4647` = "FCFG" | |
| 0x08C | `img_len_cnt` | `0x9450` | m0.XIP body (37 968 B, 16-aligned) |
| 0x0B0 | slot0 (m0) | `{1, 0, 0, 0x00000, 0x5800_0000, 0}` | flag=1, XIP at base |
| 0x0C8 | slot1 (d0) | `{0, 0, 0, 0x22000, 0x5802_0000, 0}` | unused; ROM uses BFAP for d0 |
| 0x0E0 | slot2 (lp) | `{0, 0x5805_0000, 0x5804_0000, 0x42000, 0x5804_0000, 0}` | unused |
| 0x100 | flashcfg | PLL/4B/… (FCFG-32B) | Not present in BFAP |

### group1 (BFAP, in-factory layout)

| Offset | Field | Value | Note |
|---|---|---|---|
| 0x000 | magic | `BFAP` | `4246 4150` LE = `0x50414642` |
| 0x004 | rev | 1 | |
| 0x008 | `fcfg` | `0` (no FCFG) | — |
| 0x08C | `img_len_cnt` | `0x7240` → d0 | See alignment rule |
| 0x0B0 | slot0 (m0 slot in group1) | `{1, 0, 0, 0, 0x5800_0000, 0}` | Set but d0 image never loaded here |
| 0x0C8 | slot1 (d0) | `{0, 0, 0, 0x52000, 0xD800_0000, 0}` | flash@`0x52000` → XIP base alias |
| 0x0E0 | slot2 (lp) | `{0, 0, 0, 0x82000, 0x5804_0000, 0}` | unused |

## Fact: `img_len_cnt` is a 16-alignment, not a "file size"

The bootrom reads `len = (len + 15) & ~15` from flash starting at the slot's `flash_addr`.
It does NOT depend on the file's own size. Keep them in sync by regenerating `bootinfo_group0/1`
whenever the m0/d0 body length changes.
