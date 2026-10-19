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

const SESSION_OK: &str = "[bdb-driver] session-ok";

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

    failures += !check("python-venv", ctx.venv_python().exists(), None,
        Some("restore blflashcommand/venv and install blflashcommand/requirements.txt plus setuptools<81")) as u32;
    failures += !check("blflashcommand", ctx.flash_tool().join("BLFlashCommand.py").exists(), None,
        Some("restore the corrected blflashcommand checkout")) as u32;
    failures += !check("image-preparer", ctx.repo.join("utils/prepare_blflash_low_load.py").exists(), None,
        Some("restore utils/prepare_blflash_low_load.py")) as u32;
    failures += !check("sdk-low-load-images", ctx.vendor_m0().exists() && ctx.vendor_d0().exists(), None,
        Some("build M1s_BL808_Linux_SDK/out/low_load_bl808_{m0,d0}.bin")) as u32;
    if ctx.venv_python().exists() && ctx.flash_tool().exists() {
        let result = Command::new(ctx.venv_python()).args(["-B", "BLFlashCommand.py", "--help"])
            .current_dir(ctx.flash_tool()).output();
        let ok = result.as_ref().map(|r| r.status.success()).unwrap_or(false);
        failures += !check("blflashcommand-imports", ok, None,
            Some("inspect blflashcommand Python dependencies; CryptoPlus needs setuptools<81")) as u32;
        if !ok {
            if let Ok(result) = result { el!("{}", String::from_utf8_lossy(&result.stderr)); }
        }
    }

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
        if h.is_flash_child() && parent_gone {
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

    let st = logger::status(ctx);
    let stopped_logger = st.c0_running || st.c1_running;
    if stopped_logger {
        el!("[bdb] preflight: stopping tmux logger and releasing ports before flashing");
        if logger::stop(ctx) != ECode::Ok {
            el!("[bdb] error: cannot stop UART loggers; no flash-mode instruction issued");
            return Some(ECode::Fail);
        }
        let after = logger::status(ctx);
        if after.c0_running || after.c1_running {
            el!("[bdb] error: UART logger still active");
            return Some(ECode::Busy);
        }
    }

    // Any residual holder blocks the flasher (transparent to us).
    let mut holders = procs::holders_of(&ctx.port_c1);
    holders.extend(procs::holders_of(&ctx.port_c0));
    for h in &holders {
        if h.is_flash_child() {
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

    if !Path::new(&ctx.port_c1).exists() {
        el!("[bdb] error: control port {} absent", ctx.port_c1);
        el!("{}", need("exec", "connect the dock and check the serial port path"));
        return Some(ECode::NeedUser);
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

/// Prepare and journal source hashes BEFORE opening UART; write and read back
/// with blflashcommand using one connection.
pub fn engine(ctx: &Ctx, kind: &FlashKind, recover_of: Option<String>) -> ECode {
    if let Some(code) = preflight(ctx, kind, recover_of.is_some()) { return code; }
    if matches!(kind, FlashKind::LowLoad) {
        let prepared = pyt::prepare_low_load(ctx);
        if prepared.exit != Some(0) || prepared.timeout {
            el!("[bdb] error: low-load image generation/validation failed; UART not opened");
            return ECode::Fail;
        }
    }
    let mut txn = Txn::new(&kind.cmd_string());
    txn.recover_of = recover_of;
    txn.regions = match kind {
        FlashKind::LowLoad => match expected_low_load_regions(ctx) {
            Some(regions) => regions,
            None => { el!("[bdb] error: generated images missing"); return ECode::Fail; }
        },
        FlashKind::Single { name, addr_hex, src } => {
            let size = std::fs::metadata(src).map(|m| m.len()).unwrap_or(0);
            let Some(sha) = pyt::sha256_file(src) else { return ECode::Fail; };
            if size == 0 { el!("[bdb] error: source is empty"); return ECode::Usage; }
            vec![Region { name: name.clone(), addr: addr_hex.clone(), size,
                src: src.display().to_string(), src_sha256: sha, verified: false }]
        }
    };
    el!("[bdb] txn={} backend=blflashcommand cmd=\"{}\"", txn.id, txn.cmd);
    if save_active(&ctx.txn_file(), &txn).is_err() {
        el!("[bdb] error: cannot persist transaction; UART not opened");
        return ECode::Fail;
    }
    for r in &txn.regions {
        el!("[bdb] region={} addr={} size={} sha256={}", r.name, r.addr, r.size, r.src_sha256);
    }
    let result = pyt::run_session(ctx, &txn.regions, true);
    if result.timeout || result.exit.is_none() { return finish_interrupted(ctx, &txn); }
    if result.exit != Some(0) || !result.output.lines().any(|s| s == SESSION_OK) {
        txn.status = "failed".into();
        el!("[bdb] program/readback result=failed exit={:?}", result.exit);
        return finish_program_failure(ctx, &txn, kind);
    }
    let verified = compare_readback(ctx, &mut txn, &result);
    txn.status = if verified { "done" } else { "failed" }.into();
    if verified {
        if finalize(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn).is_err() { return ECode::Fail; }
        el!("[bdb] result=success txn={} verification=on-chip-readback-sha256", txn.id);
        post_session_instructions();
        ECode::Ok
    } else {
        let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
        el!("[bdb] result=verify-mismatch txn={}", txn.id);
        post_session_instructions();
        ECode::Fail
    }
}

fn post_session_instructions() {
    el!("NEXT: run: bdb log start");
    el!("NEXT: press RESET without BOOT and inspect: bdb log tail");
}

fn finish_program_failure(ctx: &Ctx, txn: &Txn, _kind: &FlashKind) -> ECode {
    let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), txn);
    el!("[bdb] hints: flash/readback failed; keep loggers OFF and check that no process holds either UART");
    el!("{}", need("buttons", "enter flash-mode: hold BOOT, press and release RESET, then release BOOT"));
    el!("NEXT: rerun the same command with the ports free");
    ECode::Fail
}

fn finish_interrupted(ctx: &Ctx, txn: &Txn) -> ECode {
    let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), txn);
    el!("[bdb] result=interrupted txn={} (owner died) — able to retry via: bdb recover", txn.id);
    post_session_instructions();
    // Do NOT restart logger: the port may still be held by the killed child.
    ECode::Fail
}

// ---------------------------------------------------------------------------
// on-chip verification helpers
// ---------------------------------------------------------------------------

/// On-chip truth: run the readback driver over the txn regions and compare
/// each rd_* file's sha256 to the expected src sha.
pub fn onchip_verify(ctx: &Ctx, txn: &mut Txn) -> bool {
    let result = pyt::run_session(ctx, &txn.regions, false);
    if result.exit != Some(0) || result.timeout || !result.output.lines().any(|s| s == SESSION_OK) {
        el!("[bdb] verify result=readback-failed exit={:?}", result.exit);
        return false;
    }
    compare_readback(ctx, txn, &result)
}

fn compare_readback(ctx: &Ctx, txn: &mut Txn, res: &pyt::RunOutcome) -> bool {
    el!("[bdb] phase=verify kind=on-chip-readback regions={}", txn.regions.len());
    // find output dir in our own tail marker
    let out_dir = res
        .output
        .lines()
        .find_map(|l| l.strip_prefix("[bdb] readback-output-dir=").map(PathBuf::from))
        .unwrap_or_else(|| ctx.work_dir());
    let mut all_ok = true;
    for r in txn.regions.iter_mut() {
        let rd = out_dir.join(format!("rd_{}.bin", r.name));
        let size = std::fs::metadata(&rd).map(|m| m.len()).unwrap_or(0);
        let got = if size == r.size {
            pyt::sha256_file(&rd).unwrap_or_else(|| "<unreadable>".into())
        } else {
            "<wrong-size>".into()
        };
        let ok = got == r.src_sha256 && size == r.size;
        r.verified = ok;
        all_ok &= ok;
        el!(
            "[bdb] verify region={} expected-sha={} got-sha={} size={}/{} verdict={}",
            r.name,
            r.src_sha256,
            got,
            size,
            r.size,
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
    let Some((address, _)) = parse_num(&addr) else {
        el!("[bdb] error: --addr expects hex e.g. 0x52000");
        return ECode::Usage;
    };
    let abs = src.canonicalize().unwrap_or(src);
    engine(
        ctx,
        &FlashKind::Single {
            name: "file".into(),
            addr_hex: hx(address),
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
    if ln == 0 || ad.checked_add(ln).is_none() { return ECode::Usage; }
    if let Some(c) = preflight(ctx, &FlashKind::LowLoad, false) { return c; }
    let mut txn = Txn::new("readback");
    let name = format!("rb_{ad:08x}_len{ln:x}");
    txn.regions.push(Region {
        name,
        addr: hx(ad),
        size: ln,
        src: out.clone().map(|o| o.display().to_string()).unwrap_or_default(),
        src_sha256: String::new(),
        verified: false,
    });
    if save_active(&ctx.txn_file(), &txn).is_err() { return ECode::Fail; }
    let res = pyt::run_session(ctx, &txn.regions, false);
    let ok = res.exit == Some(0) && !res.timeout && res.output.lines().any(|s| s == SESSION_OK);
    txn.status = if ok { "done" } else { "failed" }.into();
    if ok {
        let _ = finalize(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
    } else {
        let _ = archive(&ctx.txn_file(), &ctx.txn_hist_dir(), &txn);
    }
    if !ok {
        el!("[bdb] result=readback-failed");
        post_session_instructions();
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
            Err(e) => {
                el!("[bdb] error: copy failed: {e}");
                post_session_instructions();
                return ECode::Fail;
            },
        }
    }
    post_session_instructions();
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
    if let Some(code) = preflight(ctx, &FlashKind::LowLoad, false) { return code; }
    let ok = onchip_verify(ctx, &mut info);
    post_session_instructions();
    if ok {
        el!("[bdb] result=verify-ok");
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
        let Some(record) = open_active(&p) else { continue };
        if record.txn.status != "done" || !record.txn.cmd.starts_with("flash ")
            || record.txn.regions.is_empty()
            || record.txn.regions.iter().any(|r| r.src_sha256.is_empty()) {
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
    if a.txn.cmd == "readback" && a.txn.regions.len() == 1 {
        let r = &a.txn.regions[0];
        // Supersede the dead read transaction before calling readback preflight.
        let mut previous = a.txn.clone();
        previous.status = "failed".into();
        if save_active(&ctx.txn_file(), &previous).is_err() { return ECode::Fail; }
        let out = (!r.src.is_empty()).then(|| PathBuf::from(&r.src));
        return readback(ctx, r.addr.clone(), hx(r.size), out);
    }
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
    } else {
        el!("[bdb] error: cannot rebuild command from txn {}", a.txn.id);
        return ECode::Usage;
    };
    engine(ctx, &kind, Some(a.txn.id.clone()))
}
