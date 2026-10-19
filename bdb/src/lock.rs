// lock.rs — cross-instance port locking built on util-linux `flock(1)`.
//
// Model: the outer bdb process re-executes itself through
//   /usr/bin/flock -w <secs> -E 2 <lockfile> <bdb> <subcmd...>
// with env BDB_HELD=1 set. The inner process holds the kernel flock for its
// whole lifetime; a crash (SIGKILL/OOM/timeout) releases it automatically.
// No sudo, no daemon. The lock file's *content* records owner metadata for
// reporting; the kernel lock remains the single source of truth.
use std::path::Path;
use std::process::{Command, ExitCode, ExitStatus};

use crate::core::Ctx;
use crate::procs;

const FLOCK: &str = "/usr/bin/flock";
/// Sentinel exit code used by flock(1) (-E) when the lock was NOT acquired.
/// Inner bdb only ever returns 0..4, so 200 means "contention" unambiguous.
pub const BUSY_SENTINEL: i32 = 200;

pub fn is_held() -> bool {
    std::env::var_os("BDB_HELD").is_some()
}

/// Owner metadata written by the inner (holding) process.
pub fn read_meta(path: &Path) -> Option<String> {
    std::fs::read_to_string(path).ok().filter(|s| !s.trim().is_empty())
}

pub fn write_held_meta(ctx: &Ctx, subcmd: &str) {
    let (pid, start) = procs::self_meta();
    let ts = crate::core::now_secs();
    let meta = format!("pid={pid}\npid_start={start}\nts={ts}\ncmd={subcmd}\n");
    let _ = std::fs::write(ctx.lock_file(), meta);
}

/// Run `subcmd_args` while holding the port lock (outer process side):
/// re-exec self via flock(1) with BDB_HELD=1.
pub fn exec_held(ctx: &Ctx, subcmd_args: &[String]) -> ExitCode {
    let exe = match std::env::current_exe() {
        Ok(e) => e,
        Err(e) => {
            eel!("[bdb] error: cannot resolve own binary path: {e}");
            return ExitCode::from(4);
        }
    };
    let status = Command::new(FLOCK)
        .arg("-o") // --close: child closes the lock fd; prevents descendants
        // (tmux server, tio) from inheriting and pinning the lock forever.
        .arg("-w")
        .arg(ctx.timeout.to_string())
        .arg("-E")
        .arg(BUSY_SENTINEL.to_string())
        .arg(ctx.lock_file())
        .arg(&exe)
        .args(subcmd_args)
        .env("BDB_HELD", "1")
        .status();
    match status {
        Ok(s) => exit_of(s),
        Err(e) => {
            eel!("[bdb] error: failed to spawn {FLOCK}: {e}");
            ExitCode::from(4)
        }
    }
}

fn exit_of(s: ExitStatus) -> ExitCode {
    // flock(1) exits with BUSY_EXIT (via -E) when the lock was not acquired;
    // inner-process codes pass straight through, so no remapping is needed.
    ExitCode::from((s.code().unwrap_or(1) & 0xff) as u8)
}

/// Contention report (outer side, after flock(1) returned the busy sentinel).
/// Returns the final exit code 2.
pub fn report_contention(ctx: &Ctx) -> ExitCode {
    el!(
        "[bdb] result=busy lock={} reason=lock-not-acquired-within-timeout",
        ctx.lock_file().display()
    );
    if let Some(meta) = read_meta(&ctx.lock_file()) {
        el!("[bdb] last-known holder record:");
        for line in meta.lines() {
            el!("[bdb]   {line}");
        }
    }
    for h in procs::holders_of(&ctx.port_c1) {
        el!("[bdb] port={} {}", ctx.port_c1, h.summary());
        let parent_dead = !Path::new(&format!("/proc/{}", h.ppid)).exists();
        if h.is_bflb_child() && parent_dead {
            el!(
                "[bdb] ghost-flash-child: orphaned bflb python (parent gone) — the next flash run reaps pid {} automatically",
                h.pid
            );
        } else if h.is_bflb_child() {
            el!("[bdb] flash run in progress — wait for it, or kill pid {} if it is truly stale", h.pid);
        } else {
            el!(
                "[bdb] hint: release the port via 'bdb log stop' first; to kill a foreign same-user pid: kill {} (no sudo required)",
                h.pid
            );
        }
    }
    ExitCode::from(2)
}
