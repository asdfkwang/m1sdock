// pyt.rs — embedded python drivers + subprocess plumbing.
//
// The driver uses the repo's corrected blflashcommand library. bdb streams child output line by
// line so a supervising AI agent can watch progress; a hard timeout reaps
// stuck children (SIGKILL) and reports `timeout=true`.
use std::path::Path;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::core::Ctx;

/// sha256 via coreutils (single line, first token).
pub fn sha256_file(path: &Path) -> Option<String> {
    let out = std::process::Command::new("sha256sum")
        .arg(path)
        .output()
        .ok()?;
    let s = String::from_utf8_lossy(&out.stdout);
    s.split_whitespace().next().map(String::from)
}

pub struct RunOutcome {
    pub exit: Option<i32>,
    pub timeout: bool,
    pub output: String, // full collected output (stdout+stderr merged)
}

/// Run a child, streaming (printing) its output as it arrives while keeping
/// the full text for parsing. `timeout_secs == 0` means unlimited.
pub fn run_streaming(cmd: &mut Command, timeout_secs: u64) -> RunOutcome {
    use std::io::Write;
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;

    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            eel!("[bdb] error: spawn failed: {e}");
            return RunOutcome {
                exit: Some(240),
                timeout: false,
                output: format!("[bdb] error: spawn failed: {e}\n"),
            }
        }
    };
    type Shared = Mutex<Shared_>;
    struct Shared_ {
        s: String,
        printed: usize,
    }
    let shared: Arc<Shared> = Arc::new(Mutex::new(Shared_ { s: String::new(), printed: 0 }));

    fn drain(sh: &Arc<Shared>, final_mode: bool) {
        let mut g = sh.lock().unwrap();
        // Emit up to the last '\n' (or everything in final_mode).
        let max = if final_mode { g.s.len() } else {
            g.s[g.printed..].rfind('\n').map(|i| g.printed + i + 1).unwrap_or(g.printed)
        };
        if g.printed < max {
            eln!("{}", &g.s[g.printed..max]);
            let _ = std::io::stdout().flush();
            g.printed = max;
        }
    }

    let mut pipes: Vec<Box<dyn std::io::Read + Send>> = Vec::new();
    if let Some(s) = child.stdout.take() {
        pipes.push(Box::new(s));
    }
    if let Some(s) = child.stderr.take() {
        pipes.push(Box::new(s));
    }
    let mut readers = Vec::new();
    for pipe in pipes {
        let sh = shared.clone();
        readers.push(std::thread::spawn(move || {
            let r = BufReader::new(pipe);
            for line in r.lines().flatten() {
                let mut g = sh.lock().unwrap();
                g.s.push_str(&line);
                g.s.push('\n');
            }
        }));
    }

    let start = Instant::now();
    let deadline = (timeout_secs > 0).then(|| start + Duration::from_secs(timeout_secs));
    let mut timeout_hit = false;
    let mut status = None;
    loop {
        match child.try_wait() {
            Ok(Some(st)) => {
                status = Some(st);
                break;
            }
            Ok(None) => {}
            Err(_) => break,
        }
        drain(&shared, false);
        if deadline.is_some_and(|d| Instant::now() >= d) {
            timeout_hit = true;
            let _ = child.kill();
            // Reap even if deadlocked in the child's writer side.
            for _ in 0..20 {
                if child.try_wait().map(|s| s.is_some()).unwrap_or(true) {
                    break;
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            status = child.wait().ok();
            break;
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    for t in readers {
        let _ = t.join();
    }
    drain(&shared, true);
    let output = shared.lock().unwrap().s.clone();
    RunOutcome {
        exit: status.as_ref().and_then(|s| s.code()),
        timeout: timeout_hit,
        output,
    }
}

// One connection per session: program and read back before closing the UART.
pub const PY_DRIVER: &str = include_str!("blflash_driver.py");

pub fn prepare_low_load(ctx: &Ctx) -> RunOutcome {
    let mut cmd = Command::new(ctx.venv_python());
    cmd.args(["-u", "-B"])
        .arg(ctx.repo.join("utils/prepare_blflash_low_load.py"))
        .current_dir(&ctx.repo);
    run_streaming(&mut cmd, ctx.timeout)
}

pub fn run_session(ctx: &Ctx, regions: &[crate::journal::Region], program: bool) -> RunOutcome {
    let tag = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
    let out_dir = ctx.work_dir().join(format!("session-{tag}"));
    let setup = || -> std::io::Result<_> {
        std::fs::create_dir_all(&out_dir)?;
        let script = ctx.work_dir().join("drv_blflash.py");
        std::fs::write(&script, PY_DRIVER)?;
        let mut manifest = crate::journal::Txn::new("blflashcommand-session");
        manifest.regions = regions.to_vec();
        let input = out_dir.join("regions.json");
        std::fs::write(&input, manifest.to_json())?;
        Ok((script, input))
    };
    let (script, input) = match setup() {
        Ok(v) => v,
        Err(e) => return RunOutcome {
            exit: Some(4), timeout: false,
            output: format!("[bdb] error: cannot prepare blflashcommand session: {e}\n"),
        },
    };
    let mut cmd = Command::new(ctx.venv_python());
    cmd.args(["-u", "-B"]).arg(script)
        .current_dir(ctx.flash_tool())
        .env("BDB_TOOL_ROOT", ctx.flash_tool())
        .env("BDB_REGIONS_JSON", input)
        .env("BDB_RB_OUT_DIR", &out_dir)
        .env("BDB_PROGRAM", if program { "1" } else { "0" })
        .env("BDB_PORT_C1", &ctx.port_c1)
        .env("BDB_BAUD", &ctx.baud);
    let mut result = run_streaming(&mut cmd, ctx.timeout);
    result.output.push_str(&format!("\n[bdb] readback-output-dir={}\n", out_dir.display()));
    result
}
