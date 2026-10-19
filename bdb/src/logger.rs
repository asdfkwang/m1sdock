// logger.rs — tmux-based UART logger control + log-based wait-for.
//
// The logger captures /dev/ttyUSB0 -> logs/c0.log (c0 console) and
// /dev/ttyUSB1 -> logs/c1.log via tio inside tmux sessions (scripts
// utils/uart_logger_*.sh). Ports may only reach the flasher once these
// sessions are stopped; ownership is our own tmux, so stopping is safe.
use std::path::Path;
use std::process::Command;
use std::time::{Duration, Instant, SystemTime};

use crate::core::{need, Ctx, ECode};
use crate::procs;

pub const SESS_C0: &str = "uart-c0";
pub const SESS_C1: &str = "uart-c1";

pub struct LogStatus {
    pub c0_running: bool,
    pub c1_running: bool,
    pub c0: Option<(u64, u64)>, // (mtime, size)
    pub c1: Option<(u64, u64)>,
    pub tmux_ok: bool,
}

pub fn status(ctx: &Ctx) -> LogStatus {
    let has = |s: &str| {
        Command::new("tmux")
            .args(["has-session", "-t", s])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|x| x.success())
            .unwrap_or(false)
    };
    let probe = |p: &Path| {
        std::fs::metadata(p)
            .ok()
            .map(|m| {
                (
                    m.modified()
                        .ok()
                        .and_then(|t| t.duration_since(SystemTime::UNIX_EPOCH).ok())
                        .map(|d| d.as_secs())
                        .unwrap_or(0),
                    m.len(),
                )
            })
    };
    LogStatus {
        c0_running: has(SESS_C0),
        c1_running: has(SESS_C1),
        c0: probe(&ctx.log_c0()),
        c1: probe(&ctx.log_c1()),
        tmux_ok: Command::new("tmux")
            .arg("-V")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false),
    }
}

fn script(ctx: &Ctx, which: &str) -> ECode {
    let p = ctx.repo.join(format!("utils/uart_logger_{which}.sh"));
    if !p.exists() {
        el!("[bdb] error: logger script missing: {}", p.display());
        return ECode::Usage;
    }
    let st = Command::new("bash").arg(&p).status();
    if st.map(|x| x.success()).unwrap_or(false) {
        ECode::Ok
    } else {
        ECode::Fail
    }
}

pub fn start(ctx: &Ctx) -> ECode {
    let code = script(ctx, "start");
    if code != ECode::Ok {
        return code;
    }
    // Verify the sessions really came up (a foreign port holder silently
    // kills the tio sessions inside tmux, which must surface as an error).
    std::thread::sleep(std::time::Duration::from_millis(1200));
    let s = status(ctx);
    if !s.c0_running || !s.c1_running {
        el!("[bdb] error: logger sessions did not come up (c0={} c1={}) — a port holder may have blocked tio", s.c0_running, s.c1_running);
        for p in [&ctx.port_c0, &ctx.port_c1] {
            for h in procs::holders_of(p) {
                el!("[bdb]   {} {}", p, h.summary());
            }
        }
        el!(
            "{}",
            need("exec", "close the holder(s) above (e.g. kill <pid> or bdb log stop) and rerun: bdb log start")
        );
        return ECode::Busy;
    }
    ECode::Ok
}

pub fn stop(ctx: &Ctx) -> ECode {
    script(ctx, "stop")
}

pub fn print_status(ctx: &Ctx) -> ECode {
    let s = status(ctx);
    el!(
        "[bdb] logger=c0 running={} logger=c1 running={} tmux_available={}",
        s.c0_running, s.c1_running, s.tmux_ok
    );
    for (name, f, st) in [
        ("c0.log", ctx.log_c0(), s.c0),
        ("c1.log", ctx.log_c1(), s.c1),
    ] {
        match st {
            Some((mtime, size)) => {
                let age = crate::core::now_secs().saturating_sub(mtime);
                el!("[bdb] log={name} size={size} last_modified_age={age}s path={}", f.display());
            }
            None => el!("[bdb] log={name} missing path={}", f.display()),
        }
    }
    if !s.tmux_ok {
        el!("{}", need("exec", "run: sudo apt install tmux"));
        return ECode::NeedUser;
    }
    ECode::Ok
}

pub fn tail(ctx: &Ctx, which: &str, lines: usize) -> ECode {
    let show = |name: &str, p: &Path| {
        el!("[bdb] ---- tail {name} ----");
        match std::fs::read(p) {
            Ok(b) => {
                let text = String::from_utf8_lossy(&b);
                let all: Vec<&str> = text.lines().collect();
                let start = all.len().saturating_sub(lines);
                for l in &all[start..] {
                    el!("{l}");
                }
            }
            Err(_) => el!("[bdb] log={name} missing"),
        }
    };
    match which {
        "c0" => show("c0.log", &ctx.log_c0()),
        "c1" => show("c1.log", &ctx.log_c1()),
        _ => {
            show("c0.log", &ctx.log_c0());
            show("c1.log", &ctx.log_c1());
        }
    }
    ECode::Ok
}

// ---------------------------------------------------------------------------
// wait-for
// ---------------------------------------------------------------------------

pub struct WaitForStep {
    pub name: &'static str,
    pub log: &'static str, // "c0" | "c1"
    pub pattern: &'static str,
}

pub const STEPS: &[WaitForStep] = &[
    WaitForStep { name: "linux", log: "c0", pattern: "Linux login:" },
    WaitForStep { name: "opensbi", log: "c0", pattern: "OpenSBI" },
    WaitForStep { name: "d0", log: "c0", pattern: "C906 start" },
    WaitForStep { name: "m0", log: "c1", pattern: "E907 start" },
];

/// Grow-and-match polling on the append-only log file.
/// exit 0 = seen, 1 = timeout, 3 = logger missing.
pub fn wait_for(ctx: &Ctx, step_name: &str) -> ECode {
    let Some(step) = STEPS.iter().find(|s| s.name == step_name) else {
        el!("[bdb] error: known wait targets: {}", STEPS.iter().map(|s| s.name).collect::<Vec<_>>().join(", "));
        return ECode::Usage;
    };
    let st = status(ctx);
    let logger_ok = if step.log == "c0" { st.c0_running } else { st.c1_running };
    if !logger_ok {
        el!("[bdb] logger session for {step} not running", step = step.name);
        el!("{}", need("exec", "run: bdb log start"));
        return ECode::NeedUser;
    }
    let path = if step.log == "c0" { ctx.log_c0() } else { ctx.log_c1() };
    let path = Path::new(&path);
    let mut offset = std::fs::metadata(path).map(|m| m.len()).unwrap_or(0);
    let keep = (step.pattern.len().saturating_sub(1)) as u64; // overlap guard
    let start = Instant::now();
    el!("[bdb] wait-for {} pattern=\"{}\" timeout={}s", step.name, step.pattern, ctx.timeout);
    loop {
        if let Ok(md) = std::fs::metadata(path) {
            let len = md.len();
            if len < offset {
                offset = 0; // file was recreated (logger restart)
            }
            if len > offset {
                if let Ok(mut f) = std::fs::File::open(path) {
                    use std::io::{Seek, SeekFrom, Read};
                    if f.seek(SeekFrom::Start(offset)).is_ok() {
                        let room = (len - offset) as usize;
                        let mut buf = vec![0u8; room];
                        let _ = f.read(&mut buf);
                        let text = String::from_utf8_lossy(&buf).into_owned();
                        for line in text.lines() {
                            if line.contains(step.pattern) {
                                el!("[bdb] matched line: {line}");
                                el!("[bdb] result=seen target={}", step.name);
                                return ECode::Ok;
                            }
                        }
                        offset = len.saturating_sub(keep); // keep a small overlap
                    }
                }
            }
        }
        if start.elapsed() >= Duration::from_secs(ctx.timeout) {
            el!("[bdb] result=timeout target={}", step.name);
            el!("[bdb] timeout-reached without signature; run: bdb state for diagnosis");
            el!(
                "{}",
                need("buttons", "press and release RESET (normal boot), then rerun this wait-for")
            );
            el!(
                "{}",
                need("replug", "if RESET does nothing: unplug the USB cable, wait 3s, plug back, then: bdb state")
            );
            return ECode::Fail;
        }
        std::thread::sleep(Duration::from_millis(400));
    }
}
