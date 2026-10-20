import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Background, BaseEdge, Controls, EdgeText, Handle, MarkerType, Position, ReactFlow,
  type Edge, type EdgeProps, type Node, type NodeProps, type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './style.css';
import {
  ADDRESSES, durationOf, hex, initialPlayback, locateBeat, playbackReducer, scenes, snapshotAt,
  type HardwareId, type Snapshot, type Transfer,
} from './timeline.ts';

type HardwareData = { hardware: HardwareId; snapshot: Snapshot; active: boolean; beatId: string };
type HardwareNode = Node<HardwareData, 'hardware'>;
type TransferData = { transfer: Transfer; progress: number };
type TransferEdge = Edge<TransferData, 'transfer'>;

const colors = { m0: '#2563EB', d0: '#7C3AED', system: '#64748B' };
const board: { id: HardwareId; x: number; y: number; width: number }[] = [
  { id: 'rom', x: 0, y: 0, width: 220 },
  { id: 'flash', x: 285, y: 0, width: 375 },
  { id: 'm0', x: 0, y: 180, width: 220 },
  { id: 'mcu', x: 285, y: 180, width: 375 },
  { id: 'xram', x: 0, y: 365, width: 220 },
  { id: 'psram', x: 285, y: 415, width: 375 },
  { id: 'd0', x: 0, y: 535, width: 220 },
  { id: 'mm', x: 285, y: 535, width: 375 },
];

function Ports() {
  return <>{[Position.Left, Position.Right, Position.Top, Position.Bottom].map(position =>
    <span key={position}>
      <Handle type="source" position={position} id={`s-${position}`} isConnectable={false} />
      <Handle type="target" position={position} id={`t-${position}`} isConnectable={false} />
    </span>)}</>;
}

function MemoryRow({ title, address, size, ready, active }: {
  title: string; address: string; size: string; ready: boolean; active?: boolean;
}) {
  return <div className={`boot-memory-row ${ready ? 'is-ready' : ''} ${active ? 'is-target' : ''}`}>
    <div><strong>{title}</strong><span>{size}</span></div><code>{address}</code>
  </div>;
}

function Hardware({ data }: NodeProps<HardwareNode>) {
  const { hardware: id, snapshot: s, active, beatId } = data;
  const owner = ['m0', 'mcu'].includes(id) ? 'm0' : ['d0', 'mm'].includes(id) ? 'd0' : id;
  const title = { rom: 'BootROM', flash: 'NOR Flash', m0: 'M0', mcu: 'MCU SRAM', d0: 'D0', mm: 'MM SRAM', xram: 'XRAM · IPC', psram: 'PSRAM' }[id];
  const size = { rom: 'BOOT METADATA', flash: '16 MiB · PHYSICAL OFFSETS', m0: 'E907 · RV32', mcu: '224 KiB', d0: 'C906 · RV64', mm: '512 + 32 KiB', xram: '16 KiB', psram: '64 MiB' }[id];
  return <div className={`boot-node boot-node--${id} ${active ? 'is-active' : ''}`} data-owner={owner}>
    <Ports />
    <div className="boot-node__head"><strong>{title}</strong><span>{size}</span></div>
    {id === 'rom' && <div className="boot-node__body boot-node__rom"><span>Group0 / Group1 metadata</span><code>0x0000_0000 · 0x0000_1000</code><small>Offsets in NOR Flash</small></div>}
    {id === 'flash' && <div className="boot-node__body">
      <div className={`boot-image boot-image--m0 ${active && beatId.startsWith('m0') ? 'is-read' : ''}`}><b>M0 low_load</b><code>{hex(ADDRESSES.m0Flash)}</code></div>
      <div className={`boot-image boot-image--d0 ${active && beatId.startsWith('d0') ? 'is-read' : ''}`}><b>D0 low_load</b><code>{hex(ADDRESSES.d0Flash)}</code></div>
      <div className="boot-node__foot">XIP entry per group <code>{hex(ADDRESSES.xipEntry)}</code></div>
    </div>}
    {(id === 'm0' || id === 'd0') && <div className="boot-node__body">
      <div className="boot-cpu-status"><i />{id === 'm0' ? s.m0Status : s.d0Status}</div>
      <dl className="boot-registers"><dt>Entry</dt><dd>{(id === 'm0' ? s.m0Started : s.d0Started) ? hex(ADDRESSES.xipEntry) : '—'}</dd>
        <dt>Initial sp</dt><dd>{(id === 'm0' ? s.m0Stack : s.d0Stack) ? hex(id === 'm0' ? ADDRESSES.m0StackTop : ADDRESSES.d0StackTop) : '—'}</dd></dl>
    </div>}
    {id === 'mcu' && <div className="boot-node__body">
      <MemoryRow title="ITCM" address="0x6202_8000" size="28 KiB region" ready={s.m0Sections} active={active && beatId === 'm0-copy'} />
      <MemoryRow title="DTCM / stack" address="0x6202_F000" size="4 KiB region" ready={s.m0Stack} active={active && beatId === 'm0-stack'} />
      <MemoryRow title="WRAM · data / BSS / heap" address="0x6203_0000" size="160 KiB" ready={s.m0Heap} active={active && ['m0-bss', 'm0-heap'].includes(beatId)} />
      <div className="boot-node__foot">{s.m0Heap ? 'Heap ready · __HeapBase → 0x6205_8000' : s.m0Bss ? 'BSS cleared · heap not initialized' : s.m0Sections ? 'Initialized sections copied' : s.m0Stack ? '1 KiB bootstrap stack reserved' : 'Linker regions · contents not initialized'}</div>
    </div>}
    {id === 'mm' && <div className="boot-node__body">
      <MemoryRow title="DRAM · data / heap" address="0x3EF8_0000" size="32 KiB region" ready={s.d0Heap} active={active && beatId === 'd0-copy'} />
      <MemoryRow title="ITCM · DRAM → VRAM" address="0x3EFF_C000" size="17 KiB region" ready={s.d0Sections} active={active && beatId === 'd0-copy'} />
      <MemoryRow title="DTCM / stack" address="0x3F00_0400" size="31 KiB region" ready={s.d0Stack} active={active && beatId === 'd0-stack'} />
      <div className="boot-node__foot">{s.d0Heap ? 'Heap ready · __HeapBase → 0x3EF8_8000' : s.d0Stack ? 'Initial sp · 0x3F00_8000' : s.mmPowered ? 'MM domain prepared by M0' : 'Waiting for MM domain setup'}</div>
    </div>}
    {id === 'xram' && <div className="boot-node__body boot-flags">
      {s.flags.map((value, index) => <div className={value === ADDRESSES.ready ? 'is-signaled' : ''} key={index}>
        <code>{hex(index === 0 ? ADDRESSES.flag1 : ADDRESSES.flag2)}</code><b>{value === null ? '—' : hex(value)}</b>
      </div>)}
      <small>{s.flags.every(value => value === 0) ? 'Consumed and cleared by D0' : 'Ready value · 0x1234_5678'}</small>
    </div>}
    {id === 'psram' && <div className="boot-node__body boot-psram-state"><span className={s.psramReady ? 'is-ready' : ''}>{s.psramReady ? '● Ready for D0 payloads' : '○ Awaiting M0 initialization'}</span><code>0x5000_0000 – 0x53FF_FFFF</code></div>}
  </div>;
}

function transferHandles(transfer: Transfer) {
  if (transfer.target === 'xram') return { sourceHandle: 's-bottom', targetHandle: 't-top' };
  if (transfer.source === 'xram') return { sourceHandle: 's-bottom', targetHandle: 't-top' };
  if (transfer.source === 'flash') return { sourceHandle: 's-left', targetHandle: ['m0', 'd0'].includes(transfer.target) ? 't-right' : 't-left' };
  return { sourceHandle: 's-right', targetHandle: 't-left' };
}

function TransferLine(props: EdgeProps<TransferEdge>) {
  const { sourceX: x0, sourceY: y0, targetX: x3, targetY: y3, sourcePosition, targetPosition, data, markerEnd } = props;
  if (!data) return null;
  const horizontal = [Position.Left, Position.Right].includes(sourcePosition);
  const equalSides = sourcePosition === targetPosition;
  const bend = equalSides ? 45 : Math.max(12, Math.min(100, (horizontal ? Math.abs(x3 - x0) : Math.abs(y3 - y0)) / 2));
  const direction = (position: Position): [number, number] => position === Position.Left ? [-1, 0] : position === Position.Right ? [1, 0] : position === Position.Top ? [0, -1] : [0, 1];
  const [dx1, dy1] = direction(sourcePosition), [dx2, dy2] = direction(targetPosition);
  const x1 = x0 + dx1 * bend, y1 = y0 + dy1 * bend, x2 = x3 + dx2 * bend, y2 = y3 + dy2 * bend;
  const path = `M${x0},${y0} C${x1},${y1} ${x2},${y2} ${x3},${y3}`;
  const at = (t: number) => {
    const u = 1 - t;
    return { x: u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
      y: u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3 };
  };
  const point = at(data.progress), middle = at(0.5), color = colors[data.transfer.owner];
  const label = { read: 'READ', copy: 'COPY', pointer: 'PTR', zero: 'ZERO', signal: 'SYNC', configure: 'SETUP' }[data.transfer.kind];
  return <>
    <BaseEdge path={path} markerEnd={markerEnd} style={{ stroke: color, strokeWidth: 2.3, strokeDasharray: ['read', 'pointer'].includes(data.transfer.kind) ? '5 4' : undefined }} />
    <circle cx={point.x} cy={point.y} r={4.5} fill={color} stroke="var(--boot-bg)" strokeWidth={2} />
    <EdgeText x={middle.x} y={middle.y} label={label} labelStyle={{ fill: color, fontSize: 8, fontWeight: 800 }} labelBgStyle={{ fill: 'var(--boot-bg)' }} labelBgPadding={[4, 3]} labelBgBorderRadius={3} />
  </>;
}

const nodeTypes = { hardware: Hardware };
const edgeTypes = { transfer: TransferLine };

function App() {
  const [state, dispatch] = useReducer(playbackReducer, initialPlayback, initial => {
    const scene = scenes.findIndex(item => `#${item.id}` === location.hash);
    return { ...initial, scene: Math.max(0, scene) };
  });
  const [reducedMotion, setReducedMotion] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [viewHint, setViewHint] = useState(false);
  const container = useRef<HTMLDivElement>(null), canvas = useRef<HTMLDivElement>(null);
  const instance = useRef<ReactFlowInstance<HardwareNode, TransferEdge> | null>(null);
  const autoStarted = useRef(false);
  const scene = scenes[state.scene];
  const duration = durationOf(scene);
  const { beat, index: beatIndex, progress } = locateBeat(scene, state.elapsed);
  const appliedIndex = progress >= 0.72 ? beatIndex : beatIndex - 1;
  const snapshot = useMemo(() => snapshotAt(state.scene, appliedIndex), [state.scene, appliedIndex]);
  const complete = state.elapsed >= duration;

  useEffect(() => {
    if (!state.playing) return;
    const start = performance.now(), offset = state.elapsed, run = state.run;
    let frame = 0;
    const tick = (now: number) => {
      const elapsed = offset + now - start;
      dispatch({ type: 'tick', elapsed, run });
      if (elapsed < duration) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // Each run owns one clock; elapsed updates must not restart it.
  }, [state.playing, state.run, duration]);

  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReducedMotion(media.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);

  useEffect(() => {
    if (reducedMotion) dispatch({ type: 'replay', animate: false });
  }, [reducedMotion]);

  useEffect(() => {
    if (!canvas.current) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting) && !autoStarted.current) {
        autoStarted.current = true;
        dispatch({ type: 'replay', animate: !reducedMotion });
      }
    }, { threshold: 0.15 });
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [reducedMotion]);

  useEffect(() => {
    const pauseWhenHidden = () => { if (document.hidden) dispatch({ type: 'pause' }); };
    document.addEventListener('visibilitychange', pauseWhenHidden);
    return () => document.removeEventListener('visibilitychange', pauseWhenHidden);
  }, []);

  useEffect(() => {
    const hashChanged = () => {
      const selected = scenes.findIndex(item => `#${item.id}` === location.hash);
      if (selected >= 0) dispatch({ type: 'select', scene: selected, animate: !reducedMotion });
    };
    window.addEventListener('hashchange', hashChanged);
    return () => window.removeEventListener('hashchange', hashChanged);
  }, [reducedMotion]);

  useEffect(() => {
    if (!canvas.current) return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        instance.current?.fitView({ padding: 0.07, duration: reducedMotion ? 0 : 180 });
      });
    });
    observer.observe(canvas.current);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [reducedMotion]);

  const selectScene = (selected: number) => {
    if (selected < 0 || selected >= scenes.length) return;
    autoStarted.current = true;
    dispatch({ type: 'select', scene: selected, animate: !reducedMotion });
    history.replaceState(null, '', `#${scenes[selected].id}`);
  };
  const togglePlay = () => {
    autoStarted.current = true;
    if (state.playing) dispatch({ type: 'pause' });
    else if (complete || state.elapsed === 0) dispatch({ type: 'replay', animate: !reducedMotion });
    else dispatch({ type: 'resume' });
  };
  const nodes = useMemo<HardwareNode[]>(() => board.map(item => ({
    id: item.id, type: 'hardware', position: { x: item.x, y: item.y }, style: { width: item.width },
    data: { hardware: item.id, snapshot, active: beat.focus.includes(item.id), beatId: beat.id },
    draggable: false, selectable: false, connectable: false,
  })), [snapshot, beat]);
  const edges: TransferEdge[] = beat.transfer ? [{
    id: 'current-operation', type: 'transfer', source: beat.transfer.source, target: beat.transfer.target,
    ...transferHandles(beat.transfer), data: { transfer: beat.transfer, progress },
    markerEnd: { type: MarkerType.ArrowClosed, color: colors[beat.transfer.owner], width: 16, height: 16 },
    selectable: false,
  }] : [];

  return <div className="boot-player" data-scene={scene.id} data-playing={state.playing} ref={container} role="region" aria-label="Boot sequence animation" tabIndex={0}
    onKeyDownCapture={event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
      event.preventDefault(); event.stopPropagation();
      selectScene(state.scene + (event.key === 'ArrowRight' ? 1 : -1));
    }}>
    <header className="boot-player__header">
      <div className="boot-player__eyebrow"><span>BOOT SEQUENCE</span><span>SCENE {String(state.scene + 1).padStart(2, '0')} / {String(scenes.length).padStart(2, '0')}</span></div>
      <h2>{scene.title}</h2><p>{scene.subtitle}</p>
      <div className="boot-controls" role="group" aria-label="Animation playback">
        <button type="button" onClick={() => selectScene(state.scene - 1)} disabled={state.scene === 0} aria-label="Previous scene">← <span>Previous</span></button>
        <button type="button" className="boot-play" onClick={togglePlay} disabled={reducedMotion} aria-label={state.playing ? 'Pause animation' : complete ? 'Play scene again' : 'Play animation'}>{state.playing ? 'Ⅱ' : '▶'} <span>{state.playing ? 'Pause' : 'Play'}</span></button>
        <button type="button" onClick={() => { autoStarted.current = true; dispatch({ type: 'replay', animate: !reducedMotion }); }} aria-label="Replay scene">↺ <span>Replay</span></button>
        <button type="button" onClick={() => selectScene(state.scene + 1)} disabled={state.scene === scenes.length - 1} aria-label="Next scene"><span>Next</span> →</button>
      </div>
      <div className="boot-scene-rail" aria-label="Playable scenes">{scenes.map((item, index) => <button type="button" key={item.id} aria-pressed={state.scene === index} onClick={() => selectScene(index)} data-owner={item.owner}><span>{String(index + 1).padStart(2, '0')}</span>{index === 0 ? 'M0 runtime' : 'D0 synchronization'}</button>)}</div>
    </header>

    <div className="boot-narration" aria-live="polite" aria-atomic="true">
      <div className="boot-narration__top"><span className="boot-beat-number">{state.scene + 1}.{beatIndex + 1}</span><h3>{beat.title}</h3><span className="boot-beat-count">{beatIndex + 1} / {scene.beats.length}</span></div>
      <p>{beat.description}</p>
    </div>

    <div className="boot-canvas" ref={canvas}>
      <ReactFlow<HardwareNode, TransferEdge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onInit={flow => { instance.current = flow; }} fitView fitViewOptions={{ padding: 0.07 }}
        minZoom={0.35} maxZoom={1.6} nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false}
        elementsSelectable={false} deleteKeyCode={null} panOnDrag zoomOnScroll={false} zoomOnDoubleClick={false}
        onMoveStart={event => { if (event) setViewHint(true); }}
        proOptions={{ hideAttribution: false }}>
        <Background gap={18} size={0.7} color="var(--boot-dot)" />
        <Controls showInteractive={false} position="bottom-right" fitViewOptions={{ padding: 0.07 }} />
      </ReactFlow>
      <div className="boot-canvas-label">ONE BOARD · FIXED MEMORY POSITIONS</div>
    </div>

    <div className="boot-timeline" role="progressbar" aria-label="Scene progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(state.elapsed / duration * 100)}><span style={{ width: `${state.elapsed / duration * 100}%` }} /></div>
    <div className="boot-detail"><span className="boot-detail-label">ADDRESS / OPERATION</span><p>{beat.detail}</p></div>
    <footer className="boot-player__footer"><span>{reducedMotion ? 'Reduced motion · final scene state' : complete ? 'Scene complete · choose the next scene or replay' : state.playing ? 'Playing once · illustrative timing' : 'Paused · inspect the addresses'}</span><span>{viewHint ? 'Use Fit view to restore the board' : 'Drag to pan · + / − to zoom'}</span></footer>
    <div className="boot-legend"><span data-color="m0">M0</span><span data-color="d0">D0</span><span data-color="flash">Flash</span><span data-color="psram">PSRAM</span><span data-color="xram">Shared IPC</span><span data-color="active">Active operation</span></div>
  </div>;
}

const root = document.getElementById('boot-sequence-root');
if (root) createRoot(root).render(<App />);
