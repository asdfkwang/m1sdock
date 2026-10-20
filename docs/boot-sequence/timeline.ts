export type HardwareId = 'rom' | 'flash' | 'm0' | 'mcu' | 'd0' | 'mm' | 'xram' | 'psram';
export type TransferKind = 'read' | 'copy' | 'pointer' | 'zero' | 'signal' | 'configure';
export type Transfer = {
  source: HardwareId;
  target: HardwareId;
  label: string;
  kind: TransferKind;
  owner: 'm0' | 'd0' | 'system';
};
export type Beat = {
  id: string;
  title: string;
  description: string;
  duration: number;
  focus: HardwareId[];
  transfer?: Transfer;
  detail: string;
};
export type Scene = { id: string; title: string; subtitle: string; owner: 'm0' | 'd0'; beats: Beat[] };

export const ADDRESSES = {
  m0Flash: 0x2000,
  d0Flash: 0x52000,
  xipEntry: 0x58000000,
  m0StackTop: 0x62030000,
  m0StackLimit: 0x6202fc00,
  m0HeapLimit: 0x62058000,
  d0StackTop: 0x3f008000,
  d0StackLimit: 0x3f007c00,
  d0HeapLimit: 0x3ef88000,
  flag1: 0x40000000,
  flag2: 0x40000004,
  ready: 0x12345678,
} as const;

export const hex = (value: number) => {
  const digits = value.toString(16).toUpperCase().padStart(8, '0');
  return `0x${digits.slice(0, 4)}_${digits.slice(4)}`;
};

export const scenes: Scene[] = [
  {
    id: 'm0-runtime', title: 'M0 builds its runtime', subtitle: 'Power-on → a working C runtime', owner: 'm0',
    beats: [
      { id: 'headers', title: 'Power on · boot metadata', duration: 1400, focus: ['rom', 'flash'],
        transfer: { source: 'rom', target: 'flash', label: 'Read boot headers', kind: 'read', owner: 'system' },
        description: 'BootROM uses the Group0 / Group1 metadata to establish the image entry and Flash mappings.',
        detail: 'Physical NOR: Group0 @ 0x0000_0000 · Group1 @ 0x0000_1000. The reset-ROM PC is not inferred from these offsets.' },
      { id: 'm0-fetch', title: 'M0 starts executing from Flash', duration: 1300, focus: ['m0', 'flash'],
        transfer: { source: 'flash', target: 'm0', label: 'XIP instruction fetch', kind: 'read', owner: 'm0' },
        description: 'Group0 maps the M0 low_load body into the CPU XIP address space. Instructions execute through this mapping.',
        detail: 'Physical NOR 0x0000_2000 → M0 CPU entry 0x5800_0000. These are two coordinates for the same image.' },
      { id: 'm0-stack', title: 'Set the M0 stack pointer', duration: 1400, focus: ['m0', 'mcu'],
        transfer: { source: 'm0', target: 'mcu', label: 'sp ← __StackTop', kind: 'pointer', owner: 'm0' },
        description: 'Reset_Handler sets sp from a linker symbol and aligns it to 16 bytes. The stack grows down into the reserved RAM.',
        detail: 'Initial sp = 0x6203_0000. The 1 KiB stack is [0x6202_FC00, 0x6203_0000); DTCM is a larger 4 KiB region.' },
      { id: 'm0-system', title: 'Configure MCU memory access', duration: 1100, focus: ['m0', 'mcu'],
        transfer: { source: 'm0', target: 'mcu', label: 'System_Init()', kind: 'configure', owner: 'm0' },
        description: 'System_Init configures protection and cache settings, then assigns WRAM as 160 KiB of MCU RAM.',
        detail: 'OCRAM 64 KiB + WRAM 160 KiB = 224 KiB. This stage models the vendor low_load startup, rather than a linked Zephyr image.' },
      { id: 'm0-copy', title: 'Copy initialized sections into SRAM', duration: 1600, focus: ['m0', 'flash', 'mcu'],
        transfer: { source: 'flash', target: 'mcu', label: 'start_load() · copy', kind: 'copy', owner: 'm0' },
        description: 'M0 copies selected ITCM, DTCM and initialized data sections from their Flash load addresses to their RAM run addresses.',
        detail: 'ITCM region: 0x6202_8000 · DTCM region: 0x6202_F000 · WRAM: 0x6203_0000. Copy lengths and Flash LMAs are linker symbols.' },
      { id: 'm0-bss', title: 'Clear BSS in MCU SRAM', duration: 1200, focus: ['m0', 'mcu'],
        transfer: { source: 'm0', target: 'mcu', label: '.bss ← 0', kind: 'zero', owner: 'm0' },
        description: 'start_load clears [__bss_start__, __bss_end__) so uninitialized C globals start at zero.',
        detail: 'BSS is zeroed by M0. The heap and stack are not firmware payloads copied wholesale out of Flash.' },
      { id: 'm0-platform', title: 'Prepare the multimedia domain and PSRAM', duration: 1700, focus: ['m0', 'mm', 'psram'],
        transfer: { source: 'm0', target: 'psram', label: 'Prepare platform memory', kind: 'configure', owner: 'm0' },
        description: 'System_Post_Init powers the MM domain and configures its SRAM. Later, board_init initializes clocks, pins and UHS PSRAM.',
        detail: 'board_init runs inside bflb_platform_init. PSRAM access is released before D0 starts loading payloads into it.' },
      { id: 'm0-heap', title: 'Initialize the M0 heap allocator', duration: 1600, focus: ['m0', 'mcu'],
        transfer: { source: 'm0', target: 'mcu', label: 'mmheap_init()', kind: 'pointer', owner: 'm0' },
        description: 'The allocator receives the RAM left after linked data, BSS and no-init sections. It prepares allocator metadata in that range.',
        detail: 'Heap = [__HeapBase, 0x6205_8000). __HeapBase and the usable byte count depend on the linked image; no measured heap size is invented here.' },
      { id: 'm0-ready', title: 'M0 runtime is ready', duration: 900, focus: ['m0', 'mcu', 'psram'],
        description: 'The M0 stack, initialized data, BSS and heap are ready. The next scene explains the two-core synchronization handshake.',
        detail: 'D0 startup can overlap M0 initialization. Scene ordering is explanatory and does not claim cycle-accurate reset sequencing.' },
    ],
  },
  {
    id: 'd0-sync', title: 'D0 joins the boot chain', subtitle: 'XIP startup → M0 handshake → loader ready', owner: 'd0',
    beats: [
      { id: 'd0-fetch', title: 'D0 enters its low_load image', duration: 1300, focus: ['d0', 'flash'],
        transfer: { source: 'flash', target: 'd0', label: 'Group1 · XIP fetch', kind: 'read', owner: 'd0' },
        description: 'The Group1 mapping supplies D0 instructions. This is the D0 entry path; M0 is not shown issuing an unsupported direct reset-release command.',
        detail: 'Physical NOR 0x0005_2000 → D0 CPU entry 0x5800_0000. M0 uses the same entry value with a different Flash body offset.' },
      { id: 'd0-stack', title: 'Set the D0 stack pointer', duration: 1400, focus: ['d0', 'mm'],
        transfer: { source: 'd0', target: 'mm', label: 'sp ← __StackTop', kind: 'pointer', owner: 'd0' },
        description: 'D0 Reset_Handler sets sp before it calls System_Init. Its bootstrap stack is inside MM SRAM.',
        detail: 'Initial sp = 0x3F00_8000. The 1 KiB stack is [0x3F00_7C00, 0x3F00_8000), within the loader DTCM region.' },
      { id: 'd0-wait', title: 'D0 waits for both readiness flags', duration: 1500, focus: ['d0', 'xram'],
        transfer: { source: 'xram', target: 'd0', label: 'Poll readiness', kind: 'read', owner: 'd0' },
        description: 'With SUPPORT_DUALCORE enabled, D0 stays in System_Init until both shared words equal the readiness value.',
        detail: 'XRAM words: 0x4000_0000 and 0x4000_0004. Expected value: 0x1234_5678. Initial RAM contents are not assumed to be zero.' },
      { id: 'flag-one', title: 'M0 publishes the first ready word', duration: 1100, focus: ['m0', 'xram', 'd0'],
        transfer: { source: 'm0', target: 'xram', label: 'Write ready · word 1', kind: 'signal', owner: 'm0' },
        description: 'After platform initialization, M0 disables its D-cache and writes the first synchronization word. D0 still needs the second word.',
        detail: '*(uint32_t *)0x4000_0000 = 0x1234_5678. This is an IPC readiness flag, not a hardware reset signal.' },
      { id: 'flag-two', title: 'M0 publishes the second ready word', duration: 1100, focus: ['m0', 'xram', 'd0'],
        transfer: { source: 'm0', target: 'xram', label: 'Write ready · word 2', kind: 'signal', owner: 'm0' },
        description: 'M0 writes the second word and performs the existing cache-clean operation. Both readiness conditions are now satisfied.',
        detail: '*(uint32_t *)0x4000_0004 = 0x1234_5678. M0 then remains in its low_load wait loop.' },
      { id: 'd0-consume', title: 'D0 consumes the handshake', duration: 1500, focus: ['d0', 'xram'],
        transfer: { source: 'xram', target: 'd0', label: 'Accept · clear both words', kind: 'signal', owner: 'd0' },
        description: 'D0 leaves the polling loop, clears both words, then enables its instruction and data caches and configures prefetch.',
        detail: 'Both shared words return to 0x0000_0000. The readiness check happens before D0 enables these caches.' },
      { id: 'd0-copy', title: 'Build the D0 C runtime in MM SRAM', duration: 1900, focus: ['d0', 'flash', 'mm'],
        transfer: { source: 'flash', target: 'mm', label: 'start_load() · copy / clear', kind: 'copy', owner: 'd0' },
        description: 'D0 copies initialized sections, clears BSS, completes platform interrupt setup and initializes its heap through bflb_platform_init.',
        detail: 'Data / heap region: [0x3EF8_0000, 0x3EF8_8000). ITCM begins at 0x3EFF_C000 and crosses into MM VRAM. Heap base and section sizes are linker-defined.' },
      { id: 'd0-ready', title: 'D0 loader is ready', duration: 1100, focus: ['d0', 'mm', 'psram'],
        description: 'The D0 runtime is initialized and PSRAM is available. Loading U-Boot, DTB, OpenSBI and the kernel belongs to the later storyboard scenes.',
        detail: 'This preview ends before linux_load(). It does not simulate later payload copies or imply a verified Linux boot.' },
    ],
  },
];

export const durationOf = (scene: Scene) => scene.beats.reduce((sum, beat) => sum + beat.duration, 0);

export function locateBeat(scene: Scene, elapsed: number) {
  let start = 0;
  for (let index = 0; index < scene.beats.length; index++) {
    const beat = scene.beats[index];
    if (elapsed < start + beat.duration || index === scene.beats.length - 1) {
      return { beat, index, progress: Math.max(0, Math.min(1, (elapsed - start) / beat.duration)) };
    }
    start += beat.duration;
  }
  throw new Error('A boot scene must have at least one beat');
}

export type Snapshot = {
  m0Started: boolean; m0Stack: boolean; m0Sections: boolean; m0Bss: boolean; m0Heap: boolean;
  psramReady: boolean; mmPowered: boolean; m0Status: string;
  d0Started: boolean; d0Stack: boolean; d0Sections: boolean; d0Heap: boolean; d0Status: string;
  flags: [number | null, number | null];
};

export function snapshotAt(sceneIndex: number, beatIndex: number): Snapshot {
  const d0 = sceneIndex === 1;
  const reached = (index: number) => d0 || beatIndex >= index;
  return {
    m0Started: reached(1), m0Stack: reached(2), m0Sections: reached(4), m0Bss: reached(5), m0Heap: reached(7),
    psramReady: reached(6), mmPowered: reached(6),
    m0Status: d0 ? beatIndex >= 4 ? 'Wait loop' : beatIndex >= 3 ? 'Publish readiness' : 'Runtime ready' : beatIndex >= 8 ? 'Runtime ready' : beatIndex >= 1 ? 'Initializing' : 'Boot metadata',
    d0Started: d0, d0Stack: d0 && beatIndex >= 1, d0Sections: d0 && beatIndex >= 6, d0Heap: d0 && beatIndex >= 6,
    d0Status: d0 ? beatIndex >= 7 ? 'Loader ready' : beatIndex >= 6 ? 'Build C runtime' : beatIndex >= 5 ? 'Handshake accepted' : beatIndex >= 2 ? 'Waiting for M0' : 'Starting' : 'Startup may overlap',
    flags: d0 ? beatIndex >= 5 ? [0, 0] : beatIndex >= 4 ? [ADDRESSES.ready, ADDRESSES.ready] : beatIndex >= 3 ? [ADDRESSES.ready, null] : [null, null] : [null, null],
  };
}

export type Playback = { scene: number; elapsed: number; playing: boolean; run: number };
export type PlaybackAction =
  | { type: 'select'; scene: number; animate: boolean }
  | { type: 'replay'; animate: boolean }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'tick'; elapsed: number; run: number };

export const initialPlayback: Playback = { scene: 0, elapsed: 0, playing: false, run: 0 };

export function playbackReducer(state: Playback, action: PlaybackAction): Playback {
  switch (action.type) {
    case 'select':
      if (action.scene < 0 || action.scene >= scenes.length) return state;
      return { scene: action.scene, elapsed: action.animate ? 0 : durationOf(scenes[action.scene]), playing: action.animate, run: state.run + 1 };
    case 'replay':
      return { ...state, elapsed: action.animate ? 0 : durationOf(scenes[state.scene]), playing: action.animate, run: state.run + 1 };
    case 'pause': return { ...state, playing: false, run: state.run + 1 };
    case 'resume':
      return state.elapsed >= durationOf(scenes[state.scene]) ? state : { ...state, playing: true, run: state.run + 1 };
    case 'tick': {
      if (!state.playing || action.run !== state.run) return state;
      const elapsed = Math.max(state.elapsed, Math.min(action.elapsed, durationOf(scenes[state.scene])));
      return { ...state, elapsed, playing: elapsed < durationOf(scenes[state.scene]) };
    }
  }
}
