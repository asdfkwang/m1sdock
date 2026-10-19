// ops.rs — command implementations: devices, doctor, flash engine, readback,
// verify, recover. The flash engine is transactional: journal first, program
// second, on-chip readback verification third. Every verdict is backed by
// evidence lines, and every failure ends with precise NEED-USER / NEXT lines.
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::core::{need, parse_num, Ctx, ECode};
use crate::journal::{archive, finalize, open_active, save_active, Region, Txn};
use crate::logger;
use crate::procs;
use crate::pyt;

const ALL_OK: &str = "[All Successful]";

fn hx(v: u64) -> String {
    format!("0x{v:x}")
}

// ---------------------------------------------------------------------------
// devices
// ---------------------------------------------------------------------------

pub fn devices(ctx: &Ctx) -> ECode {
    let ls = logger::status(ctx);
    for p in [&ctx.port_c0, &ctx.port_c1] {
        let present = Path::new(p).exists();
        let holders = procs::holders_of(p);
        el!("[bdb] port={p} present={present} holders={}", holders.len());
        for h in &holders {
            el!("[bdb]   {}", h.summary());
        }
    }
    el!(
        "[bdb] logger=c0:{}/c1:{} tmux={}",
        if ls.c0_running { "up" } else { "down" },
        if ls.c1_running { "up" } else { "down" },
        if ls.tmux_ok { "ok" } else { "missing" }
    );
    if let Some(m) = crate::lock::read_meta(&ctx.lock_file()) {
        for line in m.lines() {
            el!("[bdb] bdb-lock: {line}");
        }
    }
    ECode::Ok
}

// ---------------------------------------------------------------------------
// doctor
// ---------------------------------------------------------------------------

pub fn doctor(ctx: &Ctx) -> ECode {
    let mut failures = 0;
    let bin_ok = |bin: &str| {
        Command::new("sh")
            .args(["-lc", &format!("command -v {bin} >/dev/null 2>&1")])
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    };
    let check = |label: &str, ok: bool, pkg: Option<&str>, tip: Option<&str>| -> bool {
        if ok {
            el!("[bdb] check={label} result=ok");
            true
        } else {
            el!("[bdb] check={label} result=missing");
            if let Some(p) = pkg {
                el!("{}", need("exec", &format!("run: sudo apt install {p}")));
            }
            if let Some(t) = tip {
                el!("{}", need("fix-repo", t));
            }
            false
        }
    };
    failures += !check("bin:tmux", bin_ok("tmux"), Some("tmux"), None) as u32;
    failures += !check("bin:tio", bin_ok("tio"), Some("tio"), None) as u32;
    failures += !check("bin:flock", Path::new("/usr/bin/flock").exists(), Some("util-linux"), None) as u32;
    failures += !check("bin:sha256sum", bin_ok("sha256sum"), Some("coreutils"), None) as u32;

    let venv = ctx.venv_python();
    check(
        "python-venv",
        venv.exists(),
        None,
        Some("restore tools/venv so tools/venv/bin/python3 exists and can import the bflb tool packages"),
    );
    check(
        "mcu-tool-tree",
        ctx.mcu_tool().join("core/bflb_mcu_tool.py").exists(),
        None,
        Some("restore the vendored tools tree (git checkout -- tools/bflb_mcu_tool)"),
    );
    check(
        "iot-tool-tree",
        ctx.iot_tool().join("core/bflb_iot_tool.py").exists(),
        None,
        Some("restore the vendored tools tree (git checkout -- tools/bflb_iot_tool)"),
    );
    check(
        "vendor-low-load-images",
        ctx.vendor_m0().exists() && ctx.vendor_d0().exists(),
        None,
        Some("rebuild the vendor outputs per docs/build.md (M1s_BL808_Linux_SDK/out/low_load_bl808_*.bin)"),
    );
    check(
        "whole-img-reference",
        ctx.fw_whole_img().exists(),
        None,
        Some("restore M1s_BL808_Linux_SDK/out/whole_img_linux.bin (needed as a placeholder path by the readback driver)"),
    );
    check(
        "factory-bootinfo-asset",
        ctx.asset_bootinfo().exists(),
        None,
        Some("restore bdb/assets/factory_bootinfo.bin (8 KiB factory bootinfo dump used by 'bdb flash factory-bootinfo')"),
    );

    let has0 = Path::new(&ctx.port_c0).exists();
    let has1 = Path::new(&ctx.port_c1).exists();
    el!("[bdb] info: ports c0={has0} c1={has1} (not an error; only reported)");
    if failures > 0 {
        el!("[bdb] result=doctor-failed missing={failures}");
        ECode::NeedUser
    } else {
        el!("[bdb] result=doctor-ok");
        ECode::Ok
    }
}

// ---------------------------------------------------------------------------
// flash engine
// ---------------------------------------------------------------------------

pub enum FlashKind {
    /// Vendor low_load recipe: program m0+d0 with tool-generated bootinfos
    /// (bootinfo g0 @0x0 / g1 @0x1000 / img_g0 @0x2000 / img_g1 @0x52000).
    LowLoad,
    /// Single raw file programmed at a fixed offset (also used to restore the
    /// factory bootinfo dump).
    Single { name: String, addr_hex: String, src: PathBuf },
}

impl FlashKind {
    pub fn cmd_string(&self) -> String {
        match self {
            FlashKind::LowLoad => "flash low-load".into(),
            FlashKind::Single { name, addr_hex, src } => {
                format!("flash {} {} --addr {}", name, src.display(), addr_hex)
            }
        }
    }
}

/// Preflight while already holding the port lock. None = continue.
/// `recovering` marks a recovery run: an interrupted txn is then deliberately
/// superseded instead of blocking the flow.
fn preflight(ctx: &Ctx, kind: &FlashKind, recovering: bool) -> Option<ECode> {
    if !Path::new(&ctx.port_c1).exists() {
        el!("[bdb] error: control port {} absent", ctx.port_c1);
        el!("{}", need("replug", "check the dock USB cable: unplug, wait 3s, plug back, then rerun this command"));
        return Some(ECode::NeedUser);
    }
    if let Some(a) = open_active(&ctx.txn_file()) {
        if a.txn.status == "running" && a.owner_dead {
            if recovering {
                el!("[bdb] notice: superseding interrupted transaction id={}", a.txn.id);
            } else {
                el!(
                    "[bdb] error: unfinished transaction id={} owner died mid-run",
                    a.txn.id
                );
                el!("[bdb] hint: run: bdb recover");
                return Some(ECode::Busy);
            }
        } else if a.txn.status == "running" {
            el!("[bdb] error: transaction id={} still running elsewhere", a.txn.id);
            return Some(ECode::Busy);
        } else if a.txn.status == "failed" {
            // failed txn: allowed; the new run supersedes it.
            el!("[bdb] notice: superseding failed transaction id={}", a.txn.id);
        }
    }

    // Reap orphaned flash children (our own python tool with a dead parent).
    for h in procs::holders_of(&ctx.port_c1) {
        let parent_gone = h.ppid > 0 && !Path::new(&format!("/proc/{}", h.ppid)).exists();
        if h.is_bflb_child() && parent_gone {
            el!("[bdb] reaping orphaned flash child pid={} name={}", h.pid, h.comm);
            procs::kill_pid(h.pid, "-TERM");
            std::thread::sleep(std::time::Duration::from_millis(1200));
            if Path::new(&format!("/proc/{}", h.pid)).exists() {
                procs::kill_pid(h.pid, "-KILL");
                std::thread::sleep(std::time::Duration::from_millis(500));
            }
            el!("[bdb] reaped pid={}", h.pid);
        }
    }

    // Stop our own tmux logger so the ports are free for the flasher.
    let st = logger::status(ctx);
    if st.c0_running || st.c1_running {
        el!("[bdb] preflight: stopping tmux logger to free ports");
        let _ = logger::stop(ctx);
    }

    // Any residual holder blocks the flasher (transparent to us).
    let holders = procs::holders_of(&ctx.port_c1);
    for h in &holders {
        if h.is_bflb_child() {
            el!("[bdb] error: flash child still alive on {}: {}", ctx.port_c1, h.summary());
        } else {
            el!("[bdb] error: port held by external process: {}", h.summary());
            el!(
                "{}",
                need(
                    "exec",
                    &format!("close it first, e.g.: kill {} (same user, no sudo required)", h.pid)
                )
            );
        }
    }
    if !holders.is_empty() {
        return Some(ECode::Busy);
    }

    if let FlashKind::Single { src, .. } = kind {
        if !src.exists() {
            el!("[bdb] error: source file missing: {}", src.display());
            return Some(ECode::Usage);
        }
    }
    let _ = ctx.ensure_dirs();
    None
}

struct ProgramResult {
    timed_out: bool,
    exit: Option<i32>,
    output: String,
}

/// Build the regions list the program step is expected to produce.
/// For LowLoad this requires the tool's generated files; returns None when
/// they are absent (indicating a failed program run).
fn expected_low_load_regions(ctx: &Ctx) -> Option<Vec<Region>> {
    let gen_root = ctx.gen_dir();
    let entries = [
        ("bootinfo_g0", crate::core::ADDR_G0, "bootinfo_group0.bin"),
        ("bootinfo_g1", crate::core::ADDR_G1, "bootinfo_group1.bin"),
        ("img_group0", crate::core::ADDR_IMG_G0, "img_group0.bin"),
        ("img_group1", crate::core::ADDR_IMG_G1, "img_group1.bin"),
    ];
    let mut out = Vec::new();
    for (name, addr, file) in entries {
        let p = gen_root.join(file);
        if !p.exists() {
            return None;
        }
        let size = std::fs::metadata(&p).ok()?.len();
        let sha = pyt::sha256_file(&p)?;
        out.push(Region {
            name: name.into(),
            addr: addr.into(),
            size,
            src: p.display().to_string(),
            src_sha256: sha,
            verified: false,
        });
    }
    Some(out)
}

fn run_program(ctx: &Ctx, kind: &FlashKind) -> ProgramResult {
    match kind {
        FlashKind::LowLoad => {
            let r = pyt::run_flash_low_load(ctx);
            ProgramResult { timed_out: r.timeout, exit: r.exit, output: r.output }
        }
        FlashKind::Single { src, addr_hex, .. } => {
            let mut cmd = Command::new(ctx.venv_python());
            cmd.arg("core/bflb_iot_tool.py")
                .args([
                    "--chipname", "bl808",
                    "--port", &ctx.port_c1,
                    "--baudrate", &ctx.baud,
                    "--firmware", &src.display().to_string(),
                    "--addr", addr_hex,
                    "--single",
                ])
                .current_dir(ctx.iot_tool())
                .env("PYTHONPATH", ctx.iot_tool());
            let r = pyt::run_streaming(&mut cmd, ctx.timeout);
            ProgramResult { timed_out: r.timeout, exit: r.exit, output: r.output }
        }
    }
}

/// One full flash transaction: journal -> program -> readback verify -> verdict.
pub fn engine(ctx: &Ctx, kind: &FlashKind, recover_of: Option<String>) -> ECode {
    if let Some(c) = preflight(ctx, kind, recover_of.is_some()) {
        return c;
    }
    let mut txn = Txn::new(&kind.cmd_string());
    txn.recover_of = recover_of;
    el!("[bdb] txn={} cmd=\"{}\"", txn.id, txn.cmd);
    let _ = save_active(&ctx.txn_file(), &txn);

    // ---- program phase ----
    el!("[bdb] phase=program");
    let prog = run_program(ctx, kind);
    let prog_ok = prog.exit == Some(0) && prog.output.contains(ALL_OK);
    if prog.timed_out || prog.exit.is_none() {
        // Timed out/aborted: leave the journal as running so that a later
        // invocation reports the interruption and recover can replay it.
        txn.status = "running".into();
        el!("[bdb] program result=timeout-or-aborted exit={:?}", prog.exit);
        return finish_interrupted(ctx, &txn);
    }
    if !prog_ok {
        txn.status = "failed".into();
        el!("[bdb] program result=failed exit={:?}", prog.exit);
        return finish_program_failure(ctx, &txn, kind);
    }
    el!("[bdb] program result=ok");

    // ---- build region records for the verify phase ----
    txn.regions = match kind {
        FlashKind::LowLoad => match expected_low_load_regions(ctx) {
            Some(r) => r,
            None => {
                txn.status = "failed".into();
                el!(
                    "[bdb] error: generated artifacts not found at {}; tool layout may have changed",
                    ctx.gen_dir().display()
                );
                el!("{}", need("fix-repo", "inspect the flash tool output above; keep the vendored tools tree intact"));
                let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
                return ECode::Fail;
            }
        },
        FlashKind::Single { name, addr_hex, src, .. } => {
            let (_base, _) = parse_num(addr_hex).unwrap_or((0, false));
            let size = std::fs::metadata(src).map(|m| m.len()).unwrap_or(0);
            let sha = pyt::sha256_file(src).unwrap_or_default();
            vec![Region {
                name: name.clone(),
                addr: addr_hex.clone(),
                size,
                src: src.display().to_string(),
                src_sha256: sha,
                verified: false,
            }]
        }
    };
    for r in &txn.regions {
        el!(
            "[bdb] region={} addr={} size={} src=\"{}\" sha256={}",
            r.name, r.addr, r.size, r.src, r.src_sha256
        );
    }
    let _ = save_active(&ctx.txn_file(), &txn);

    // ---- verify phase: on-chip readback + sha comparison ----
    let verified = onchip_verify(ctx, &mut txn);
    txn.status = if verified { "done" } else { "failed" }.into();
    let _ = save_active(&ctx.txn_file(), &txn);
    if verified {
        el!("[bdb] result=success txn={} regions=\"{}\"", txn.id,
            txn.regions.iter().map(|r| r.name.as_str()).collect::<Vec<_>>().join(","));
        let _ = finalize(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
        restore_logger(ctx);
        el!("[bdb] next: cold boot sequence — unplug USB, wait 3s, plug back");
        el!("[bdb] next: press RESET (no BOOT) once board re-enumerates");
        el!("[bdb] next: run: bdb wait-for linux");
        ECode::Ok
    } else {
        el!("[bdb] result=verify-mismatch txn={}", txn.id);
        el!("{}", need(
            "replug",
            "the flash was NOT fully applied (known ghost-write failure mode): unplug the USB cable, wait 3s, plug back",
        ));
        el!("[bdb] next: enter flash-mode, then rerun the same flash command (idempotent)");
        let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
        ECode::Fail
    }
}

fn finish_program_failure(ctx: &Ctx, txn: &Txn, _kind: &FlashKind) -> ECode {
    let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), txn);
    el!("[bdb] hints: no handshake response or incomplete program — the common causes are flash-mode not entered, or a polluted USB port");
    el!("{}", need(
        "buttons",
        "enter flash-mode: hold BOOT, tap RESET while holding, keep holding ~1s, release BOOT",
    ));
    el!("{}", need(
        "replug",
        "if a retry after flash-mode entry still fails: unplug the USB cable, wait 3s, plug back",
    ));
    el!("[bdb] next: rerun the same flash command (it is idempotent; history kept)");
    ECode::Fail
}

fn finish_interrupted(ctx: &Ctx, txn: &Txn) -> ECode {
    let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), txn);
    el!("[bdb] result=interrupted txn={} (owner died) — able to retry via: bdb recover", txn.id);
    // Do NOT restart logger: the port may still be held by the killed child.
    ECode::Fail
}

fn restore_logger(ctx: &Ctx) {
    el!("[bdb] restoring tmux logger");
    if logger::start(ctx) != ECode::Ok {
        el!("[bdb] hint: logger start failed; run: bdb log start and check tmux availability");
    }
}

// ---------------------------------------------------------------------------
// on-chip verification helpers
// ---------------------------------------------------------------------------

/// On-chip truth: run the readback driver over the txn regions and compare
/// each rd_* file's sha256 to the expected src sha.
pub fn onchip_verify(ctx: &Ctx, txn: &mut Txn) -> bool {
    el!("[bdb] phase=verify kind=on-chip-readback regions={}", txn.regions.len());
    let list: Vec<(String, String, String)> = txn
        .regions
        .iter()
        .map(|r| {
            let (base, _) = parse_num(&r.addr).unwrap_or((0, false));
            // The tool's read command treats end_addr as INCLUSIVE: it returns
            // end-start+1 bytes. Probe it for exactly size bytes, i.e. last
            // address = base + size - 1.
            (r.name.clone(), r.addr.clone(), hx(base + r.size - 1))
        })
        .collect();
    let res = pyt::run_readback(ctx, &list);
    if res.exit != Some(0) {
        el!("[bdb] verify result=readback-failed exit={:?} (flash-mode absent or port polluted)", res.exit);
        el!("{}", need(
            "buttons",
            "enter flash-mode to allow on-chip readback: hold BOOT, tap RESET, release after ~1s",
        ));
        return false;
    }
    // find output dir in our own tail marker
    let out_dir = res
        .output
        .lines()
        .find_map(|l| l.strip_prefix("[bdb] readback-output-dir=").map(PathBuf::from))
        .unwrap_or_else(|| ctx.work_dir());
    let mut all_ok = true;
    for r in txn.regions.iter_mut() {
        let rd = out_dir.join(format!("rd_{}.bin", r.name));
        // Trust rule: compare the first `size` bytes even when the tool
        // overshoots (end_addr inclusivity); a SHORT read is a hard failure.
        let (got, size, tool_pad) = match std::fs::read(&rd) {
            Ok(b) => {
                let have = b.len() as u64;
                if have < r.size {
                    ("<short-read>".into(), have, false)
                } else {
                    let trunc = ctx.work_dir().join(format!("trunc_{}.bin", r.name));
                    let _ = std::fs::write(&trunc, &b[..r.size as usize]);
                    (pyt::sha256_file(&trunc).unwrap_or_else(|| "-".into()), r.size, have > r.size)
                }
            }
            Err(_) => ("<missing>".into(), 0, false),
        };
        let ok = got == r.src_sha256 && size == r.size;
        r.verified = ok;
        all_ok &= ok;
        el!(
            "[bdb] verify region={} expected-sha={} got-sha={} size={}/{} tool-extra-bytes={} verdict={}",
            r.name,
            r.src_sha256,
            got,
            size,
            r.size,
            tool_pad,
            if ok { "match" } else { "MISMATCH" }
        );
    }
    all_ok
}

// ---------------------------------------------------------------------------
// top-level wrappers
// ---------------------------------------------------------------------------

pub fn flash_low_load(ctx: &Ctx) -> ECode {
    engine(ctx, &FlashKind::LowLoad, None)
}

pub fn flash_bootinfo_asset(ctx: &Ctx) -> ECode {
    let src = ctx.asset_bootinfo();
    engine(
        ctx,
        &FlashKind::Single {
            name: "factory_bootinfo".into(),
            addr_hex: "0x0".into(),
            src,
            
        },
        None,
    )
}

pub fn flash_file(ctx: &Ctx, src: PathBuf, addr: String) -> ECode {
    if parse_num(&addr).is_none() {
        el!("[bdb] error: --addr expects hex e.g. 0x52000");
        return ECode::Usage;
    }
    let abs = src.canonicalize().unwrap_or(src);
    engine(
        ctx,
        &FlashKind::Single {
            name: "file".into(),
            addr_hex: addr,
            src: abs,
            
        },
        None,
    )
}

/// Arbitrary region readback (flash-mode required).
pub fn readback(ctx: &Ctx, addr: String, len: String, out: Option<PathBuf>) -> ECode {
    let (Some((ad, _)), Some((ln, _))) = (parse_num(&addr), parse_num(&len)) else {
        el!("[bdb] error: --addr/--len expect hex values e.g. 0x0 0x2000");
        return ECode::Usage;
    };
    if let Some(c) = preflight(ctx, &FlashKind::LowLoad, false) {
        return c;
    }
    let mut txn = Txn::new("readback");
    let name = format!("rb_{ad:08x}_len{ln:x}");
    txn.regions.push(Region {
        name,
        addr: addr.clone(),
        size: ln,
        src: out.clone().map(|o| o.display().to_string()).unwrap_or_default(),
        src_sha256: String::new(),
        verified: false,
    });
    let _ = save_active(&ctx.txn_file(), &txn);
    let list = vec![(txn.regions[0].name.clone(), hx(ad), hx(ad + ln - 1))];
    let res = pyt::run_readback(ctx, &list);
    let ok = res.exit == Some(0);
    txn.status = if ok { "done" } else { "failed" }.into();
    let _ = finalize(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
    if !ok {
        el!("[bdb] result=readback-failed");
        el!("{}", need(
            "buttons",
            "enter flash-mode: hold BOOT, tap RESET while holding, release after ~1s",
        ));
        return ECode::Fail;
    }
    // locate emitted region file
    let out_dir = res
        .output
        .lines()
        .find_map(|l| l.strip_prefix("[bdb] readback-output-dir=").map(PathBuf::from))
        .unwrap_or_else(|| ctx.work_dir());
    let rd = out_dir.join(format!("rd_{}.bin", txn.regions[0].name));
    let sha = pyt::sha256_file(&rd).unwrap_or_else(|| "-".into());
    el!("[bdb] readback file={} sha256={}", rd.display(), sha);
    if let Some(o) = out {
        match std::fs::copy(&rd, &o) {
            Ok(_) => el!("[bdb] copied to {}", o.display()),
            Err(e) => el!("[bdb] error: copy failed: {e}"),
        }
    }
    restore_logger(ctx);
    ECode::Ok
}

/// Re-verify the newest finished transaction from the history dir.
pub fn verify(ctx: &Ctx) -> ECode {
    let Some(hist) = newest_hist(ctx) else {
        el!("[bdb] no finished transaction found in {}", ctx.txn_hist_dir().display());
        return ECode::Usage;
    };
    let mut info = match open_active(&hist) {
        Some(i) => i.txn,
        None => {
            el!("[bdb] error: cannot parse {hist:?}");
            return ECode::Usage;
        }
    };
    if info.regions.is_empty() || info.status != "done" {
        el!("[bdb] error: transaction {} status={} not verifiable", info.id, info.status);
        return ECode::Usage;
    }
    el!("[bdb] verify txn={} cmd=\"{}\"", info.id, info.cmd);
    let ok = onchip_verify(ctx, &mut info);
    if ok {
        el!("[bdb] result=verify-ok");
        restore_logger(ctx);
        ECode::Ok
    } else {
        el!("[bdb] result=verify-mismatch — rerun: bdb flash or bdb recover");
        ECode::Fail
    }
}

fn newest_hist(ctx: &Ctx) -> Option<PathBuf> {
    let mut best: Option<(String, PathBuf)> = None;
    let dir = std::fs::read_dir(ctx.txn_hist_dir()).ok()?;
    for e in dir.flatten() {
        let p = e.path();
        if p.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let name = p.file_stem()?.to_string_lossy().to_string();
        if best.as_ref().map(|(b, _)| name.as_str() > b.as_str()).unwrap_or(true) {
            best = Some((name, p));
        }
    }
    best.map(|(_, p)| p)
}

/// Replay an unfinished/failed transaction: converges the board to the same
/// target state as the original run (plain re-run of the recorded command).
pub fn recover(ctx: &Ctx) -> ECode {
    let Some(a) = open_active(&ctx.txn_file()) else {
        el!("[bdb] no active transaction — nothing to recover");
        return ECode::Ok;
    };
    let dead_or_failed =
        (a.txn.status == "running" && a.owner_dead) || a.txn.status == "failed";
    if a.txn.status == "running" && !a.owner_dead {
        el!("[bdb] transaction {} is running in another process", a.txn.id);
        return ECode::Busy;
    }
    if a.txn.status == "done" {
        el!("[bdb] transaction {} is done — nothing to recover", a.txn.id);
        return ECode::Ok;
    }
    if !dead_or_failed {
        el!("[bdb] transaction {} status={} — nothing to recover", a.txn.id, a.txn.status);
        return ECode::Ok;
    }
    el!("[bdb] recovering txn={} cmd=\"{}\"", a.txn.id, a.txn.cmd);
    let kind = if a.txn.cmd.contains("low-load") {
        FlashKind::LowLoad
    } else if a.txn.regions.len() == 1 {
        let r = a.txn.regions[0].clone();
        FlashKind::Single {
            name: r.name.clone(),
            addr_hex: r.addr.clone(),
            src: PathBuf::from(r.src.clone()),
            
        }
    } else if a.txn.cmd.contains("factory-bootinfo") {
        FlashKind::Single {
            name: "factory_bootinfo".into(),
            addr_hex: "0x0".into(),
            src: ctx.asset_bootinfo(),
            
        }
    } else if a.txn.cmd == "readback" && a.txn.regions.len() == 1 {
        let r = a.txn.regions[0].clone();
        return readback(ctx, r.addr.clone(), hx(r.size), None);
    } else {
        el!("[bdb] error: cannot rebuild command from txn {}", a.txn.id);
        return ECode::Usage;
    };
    engine(ctx, &kind, Some(a.txn.id.clone()))
}
