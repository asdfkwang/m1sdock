// state.rs — device state classification built only on direct evidence:
// port presence, port holders, tmux logger sessions, log-file signatures,
// bdb lock state and the transaction journal. Opening the serial ports is
// avoided so `state` stays side-effect free and concurrent with flashes.
use std::path::Path;

use crate::core::Ctx;
use crate::journal;
use crate::procs;
use crate::logger;

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
#[allow(dead_code)]
pub enum State {
    Absent,
    Linux,
    M0Only,
    FlashMode,
    Busy,
    FlashInterrupted,
    Unknown,
}

pub struct Snapshot {
    pub state: State,
    pub hints: Vec<String>,
    pub evidence: Vec<String>,
}

fn tail_text(ctx: &Ctx, which: &str, max: usize) -> (Option<String>, Option<u64>) {
    let path = if which == "c0" { ctx.log_c0() } else { ctx.log_c1() };
    let (text, mtime) = match std::fs::read(&path) {
        Ok(b) => {
            let md = std::fs::metadata(&path).ok();
            let mt = md
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs());
            (String::from_utf8_lossy(&b).into_owned(), mt)
        }
        Err(_) => (String::new(), None),
    };
    let seg_start = {
        let last = text
            .rmatch_indices("UART LOGGER START")
            .next()
            .map(|(i, _)| i);
        match last {
            Some(pos) => {
                // Line start of that marker.
                let (line_start, _) = text[..pos].rfind('\n').map(|i| (i + 1, i)).unwrap_or((0, pos));
                line_start
            }
            None => text.len().saturating_sub(4 * 1024), // fall back to a recent window
        }
    };
    let seg = &text[seg_start..];
    // Restrict to the last `max` characters but stay on a line boundary.
    let start_byte = if seg.chars().count() > max {
        let cut = seg
            .char_indices()
            .nth(seg.chars().count() - max)
            .map(|(i, _)| i)
            .unwrap_or(0);
        match seg[cut.min(seg.len())..].find('\n') {
            Some(nl) => (cut + nl + 1).min(seg.len()),
            None => cut,
        }
    } else {
        0
    };
    (Some(seg[start_byte.min(seg.len())..].to_string()), mtime)
}

/// Collect the classified state plus greppable evidence lines.
pub fn snapshot(ctx: &Ctx) -> Snapshot {
    let mut hints = Vec::new();
    let mut evidence = Vec::new();

    let has_c0 = Path::new(&ctx.port_c0).exists();
    let has_c1 = Path::new(&ctx.port_c1).exists();
    evidence.push(format!("port={} present={}", ctx.port_c0, has_c0));
    evidence.push(format!("port={} present={}", ctx.port_c1, has_c1));
    if !has_c0 && !has_c1 {
        hints.push(format!("no serial ports found — plug the dock and recheck"));
        return Snapshot { state: State::Absent, hints, evidence };
    }

    // Port occupation (a held ttyUSB1 blocks flashing).
    let our_log_marker = format!("{}/logs/c", ctx.repo.display());
    let holders = procs::holders_of(&ctx.port_c1);
    for h in &holders {
        let tag = if h.is_bflb_child() {
            "flash-child"
        } else if h.comm == "tio" && h.cmd.contains(&our_log_marker) {
            "own-logger"
        } else {
            "external"
        };
        evidence.push(format!("{tag} {}", h.summary()));
    }

    // Logger sessions.
    let ls = logger::status(ctx);
    evidence.push(format!("logger-c0-running={} logger-c1-running={}", ls.c0_running, ls.c1_running));
    if !ls.c0_running {
        hints.push("run: bdb log start".to_string());
    }

    // Lock + journal.
    let lock_meta = crate::lock::read_meta(&ctx.lock_file());
    if let Some(m) = &lock_meta {
        evidence.push(format!("bdb-lock held-by=({})", m.trim().replace('\n', "; ")));
    }
    let active = journal::open_active(&ctx.txn_file());
    let active_ref = active.as_ref();
    if let Some(a) = active_ref {
        evidence.push(format!(
            "txn id={} cmd=\"{}\" status={} owner_dead={}",
            a.txn.id, a.txn.cmd, a.txn.status, a.owner_dead
        ));
        if a.txn.status == "failed" {
            hints.push("run: bdb recover (or rerun the flash) to converge the board".to_string());
        }
    }

    // Log signatures since the newest logger-start marker.
    let (c0_txt, c0_mt) = tail_text(ctx, "c0", 1200);
    let (c1_txt, c1_mt) = tail_text(ctx, "c1", 800);
    for (tag, (txt, mt)) in [("c0", (&c0_txt, &c0_mt)), ("c1", (&c1_txt, &c1_mt))] {
        let t = txt.as_deref().unwrap_or("");
        match (t.is_empty(), mt) {
            (true, _) => evidence.push(format!("signature={tag} none (log missing or empty)")),
            (false, Some(m)) => evidence.push(format!(
                "signature={tag} window=\"{}…\" mtime={}",
                t.lines().next().unwrap_or("").chars().take(60).collect::<String>(),
                m
            )),
            (false, None) => {}
        }
    }
    let sig = |t: &str, p: &str| t.lines().any(|l| l.contains(p));
    let c0 = c0_txt.unwrap_or_default();
    let c1 = c1_txt.unwrap_or_default();
    let linux = sig(&c0, "Linux login:");
    let c906 = sig(&c0, "C906 start");
    let sbi = sig(&c0, "OpenSBI");
    let e907 = sig(&c1, "E907 start");

    // Outer classification (precedence order matters).
    let state = if let Some(a) = active_ref {
        if a.txn.status == "running" && a.owner_dead {
            hints.push("run: bdb recover".to_string());
            State::FlashInterrupted
        } else if a.txn.status == "running" && holders.iter().any(|h| h.is_bflb_child()) {
            hints.push("a flash run is in progress — do not touch the ports".to_string());
            State::Busy
        } else if a.txn.status == "running" && lock_meta.is_some() {
            hints.push("run: bdb recover".to_string());
            State::Busy
        } else {
            classify_log(linux, c906, sbi, e907, &c0_mt, &c1_mt, &mut hints, &mut evidence)
        }
    } else if !holders.is_empty() {
        let all_ours = holders.iter().all(|h| {
            h.comm == "tio" && h.cmd.contains(&format!("{}/logs/c", ctx.repo.display()))
        });
        if all_ours && ls.c0_running && ls.c1_running && ls.tmux_ok {
            evidence.push("holders=own-logger (normal resting state after log start)".to_string());
            classify_log(linux, c906, sbi, e907, &c0_mt, &c1_mt, &mut hints, &mut evidence)
        } else {
            if holders.iter().any(|h| h.is_bflb_child()) {
                hints.push("orphaned flash child on the port; run: bdb recover or retry the flash".to_string());
            }
            State::Busy
        }
    } else {
        classify_log(linux, c906, sbi, e907, &c0_mt, &c1_mt, &mut hints, &mut evidence)
    };

    if matches!(state, State::M0Only) {
        hints.push("m0 banner seen but no Linux login — d0 may be mute; recovery recipe: bdb flash low-load, or: bdb flash factory-bootinfo".to_string());
        hints.push(crate::core::need(
            "buttons",
            "enter flash-mode: hold BOOT, tap RESET while holding, release BOOT after ~1s",
        ));
    }
    Snapshot { state, hints, evidence }
}

#[allow(clippy::too_many_arguments)]
fn classify_log(
    linux: bool,
    c906: bool,
    sbi: bool,
    e907: bool,
    c0_mt: &Option<u64>,
    c1_mt: &Option<u64>,
    hints: &mut Vec<String>,
    evidence: &mut Vec<String>,
) -> State {
    if linux {
        State::Linux
    } else if e907 {
        if c906 || sbi {
            evidence.push("d0-lines-present-but-no-login".to_string());
        }
        hints.push("m0 seen, Linux not up yet — run: bdb wait-for linux".to_string());
        State::M0Only
    } else {
        let fresh = c0_mt.map(|m| crate::core::now_secs().saturating_sub(m) < 90).unwrap_or(false)
            || c1_mt.map(|m| crate::core::now_secs().saturating_sub(m) < 90).unwrap_or(false);
        if fresh {
            evidence.push("logs recently written but with no boot signature".to_string());
        }
        hints.push("state unverifiable from logs; flash commands validate flash-mode by handshake".to_string());
        State::Unknown
    }
}

/// Human + JSON rendering.
pub fn print(_ctx: &Ctx, snap: &Snapshot, as_json: bool) -> crate::core::ECode {
    let st = match snap.state {
        State::Absent => "absent",
        State::Linux => "linux",
        State::M0Only => "m0-only",
        State::FlashMode => "flash-mode",
        State::Busy => "busy",
        State::FlashInterrupted => "flash-interrupted",
        State::Unknown => "unknown",
    };
    if as_json {
        el!(
            "[bdb] {{\"state\":\"{st}\",\"evidence\":[{}],\"hints\":[{}]}}",
            crate::core::jarr(&snap.evidence),
            crate::core::jarr(&snap.hints)
        );
        return crate::core::ECode::Ok;
    }
    el!("[bdb] state={st}");
    for e in &snap.evidence {
        el!("[bdb] {e}");
    }
    for h in &snap.hints {
        el!("[bdb] hint: {h}");
    }
    crate::core::ECode::Ok
}
