// main.rs — bdb: trusted, sudo-free dock companion for the Sipeed M1s BL808.
// AI-facing CLI: every command prints greppable evidence lines, exits with a
// canonical code and, when a human action is required, prints NEED-USER lines
// with copy-pasteable remediation.
//
// Macros el!/eln! are panic-free stdout writes: a closed pipe (e.g. an
// upstream agent truncating us with `head`) must NEVER tear down an ongoing
// flash transaction. They are declared before the modules so the unqualified
// names are textually visible inside them.
macro_rules! el {
    ($($arg:tt)*) => {{
        use std::io::Write;
        let mut o = std::io::stdout().lock();
        let _ = writeln!(o, $($arg)*);
        let _ = o.flush();
    }};
}

macro_rules! eln {
    ($($arg:tt)*) => {{
        use std::io::Write;
        let mut o = std::io::stdout().lock();
        let _ = write!(o, $($arg)*);
        let _ = o.flush();
    }};
}

macro_rules! eel {
    ($($arg:tt)*) => {{
        use std::io::Write;
        let _ = writeln!(std::io::stderr().lock(), $($arg)*);
    }};
}

mod core;
mod journal;
mod lock;
mod logger;
mod ops;
mod procs;
mod pyt;
mod state;

use std::path::PathBuf;
use std::process::ExitCode;

use crate::core::{ECode, Opts};

fn flag_val(tail: &[String], names: &[&str]) -> Option<String> {
    for (i, t) in tail.iter().enumerate() {
        if names.contains(&t.as_str()) {
            if let Some(v) = tail.get(i + 1) {
                if !v.starts_with("--") {
                    return Some(v.clone());
                }
            }
            return Some(String::new()); // flag present without value
        }
    }
    None
}

fn parse(argv: &[String]) -> (Opts, Vec<String>) {
    let mut o = Opts::default();
    let mut rest = Vec::new();
    let mut it = argv.iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--json" => o.json = true,
            "--timeout" => {
                if let Some(v) = it.next() {
                    o.timeout = v.parse().unwrap_or(o.timeout);
                }
            }
            "--port-c0" => o.port_c0 = it.next().cloned(),
            "--port-c1" => o.port_c1 = it.next().cloned(),
            "--baud" => o.baud = it.next().cloned(),
            "--repo-root" => o.repo = it.next().map(PathBuf::from),
            other => rest.push(other.to_string()),
        }
    }
    (o, rest)
}

const HELP: &str = "\
bdb — trusted, sudo-free companion for the Sipeed M1s BL808 dock (AI-facing)

Global options (usable before any subcommand):
  --json                 machine-readable state/devices output
  --timeout SECONDS      lock wait + flash-tool child soft cap (default 600)
  --port-c0 /dev/ttyUSB0   --port-c1 /dev/ttyUSB1   --baud 2000000

Commands:
  devices                     port inventory + holders (read-only)
  state [--json]              classified device state + evidence + hints (read-only)
  doctor                      dependency self-check; NEED-USER hints on misses
  log start|stop|status       tmux logger control (start/stop take the port lock)
  log tail [--lines N] [--which c0|c1|all]
  wait-for linux|opensbi|d0|m0  poll a log signature; long waits are fine
  flash low-load | factory-bootinfo | file PATH --addr 0xX [--no-verify]
  readback --addr 0xX --len 0xN [--out PATH]
  verify                      re-read and compare the last completed transaction
  recover                     replay an unfinished/failed transaction
  help

Trust model:
  - exclusive commands hold a kernel flock over the port; crash releases it
  - every flash is journaled BEFORE any write; a dead owner is detected via
    /proc and `bdb recover` replays the transaction to converge the board
  - success is judged only by on-chip readback SHA equality; tool output
    claiming success is never trusted
  - flash-mode entry (hold BOOT, tap RESET) and USB replug are human steps:
    bdb prints NEED-USER lines instead of pretending they happened

Exit codes: 0 ok | 1 judged failure | 2 contention | 3 NEED-USER | 4 usage
";

fn print_help() {
    eln!("{HELP}");
}

fn main() -> ExitCode {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let (mut opts, rest) = parse(&argv);
    if rest.iter().any(|a| a == "help") {
        print_help();
        return ExitCode::from(0);
    }
    let held = lock::is_held();
    let ctx = core::ctx_from(&opts);
    if held {
        lock::write_held_meta(&ctx, &rest.join(" "));
        return code(dispatch(&ctx, &mut opts, &rest));
    }
    if rest.is_empty() {
        print_help();
        return ExitCode::from(4);
    }
    let exclusive = match rest[0].as_str() {
        "flash" | "readback" | "verify" | "recover" => true,
        "log" => rest.len() >= 2 && matches!(rest[1].as_str(), "start" | "stop"),
        _ => false,
    };
    if !exclusive {
        return code(dispatch(&ctx, &mut opts, &rest));
    }
    let ec = lock::exec_held(&ctx, &rest);
    if ec == ExitCode::from(lock::BUSY_SENTINEL as u8) {
        let _ = lock::report_contention(&ctx);
        return ExitCode::from(2);
    }
    ec
}

fn code(e: ECode) -> ExitCode {
    ExitCode::from(e.num())
}

fn dispatch(ctx: &core::Ctx, opts: &mut Opts, args: &[String]) -> ECode {
    let Some((sub, tail)) = args.split_first() else {
        print_help();
        return ECode::Usage;
    };
    opts.json = opts.json || tail.iter().any(|a| a == "--json");
    match sub.as_str() {
        "help" | "--help" | "-h" => {
            print_help();
            ECode::Ok
        }
        "devices" => ops::devices(ctx),
        "state" => {
            let snap = state::snapshot(ctx);
            state::print(ctx, &snap, opts.json)
        }
        "doctor" => ops::doctor(ctx),
        "log" => match tail.first().map(String::as_str) {
            Some("start") => logger::start(ctx),
            Some("stop") => logger::stop(ctx),
            Some("status") => logger::print_status(ctx),
            Some("tail") => {
                let lines = flag_val(tail, &["--lines"])
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(20usize);
                let which = flag_val(tail, &["--which"]).unwrap_or_else(|| "all".into());
                logger::tail(ctx, &which, lines)
            }
            _ => {
                el!("[bdb] error: log start|stop|status|tail");
                ECode::Usage
            }
        },
        "wait-for" => match tail.first().map(String::as_str) {
            Some(t) => logger::wait_for(ctx, t),
            None => {
                el!("[bdb] error: wait-for linux|opensbi|d0|m0");
                ECode::Usage
            }
        },
        "flash" => match tail.first().map(String::as_str) {
            Some("low-load") => {
                note_no_verify(tail);
                let _ = ctx.ensure_dirs();
                ops::flash_low_load(ctx)
            }
            Some("factory-bootinfo") => {
                note_no_verify(tail);
                ops::flash_bootinfo_asset(ctx)
            }
            Some("file") => {
                let Some(path) = tail.get(1).filter(|p| !p.starts_with("--")) else {
                    el!("[bdb] error: flash file PATH --addr 0xX");
                    return ECode::Usage;
                };
                let Some(addr) = flag_val(tail, &["--addr"]) else {
                    el!("[bdb] error: --addr is required for file mode");
                    return ECode::Usage;
                };
                let parsed = core::parse_num(&addr);
                if parsed.is_none() || addr.is_empty() {
                    el!("[bdb] error: --addr expects a hex value like 0x52000");
                    return ECode::Usage;
                }
                note_no_verify(tail);
                ops::flash_file(ctx, PathBuf::from(path), addr)
            }
            _ => {
                el!("[bdb] error: flash low-load | factory-bootinfo | file PATH --addr 0xX");
                ECode::Usage
            }
        },
        "readback" => {
            let Some(addr) = flag_val(tail, &["--addr"]) else {
                el!("[bdb] error: readback --addr 0xX --len 0xN");
                return ECode::Usage;
            };
            let Some(len) = flag_val(tail, &["--len"]) else {
                el!("[bdb] error: readback --addr 0xX --len 0xN");
                return ECode::Usage;
            };
            let out = flag_val(tail, &["--out"]).map(PathBuf::from);
            ops::readback(ctx, addr, len, out)
        }
        "verify" => ops::verify(ctx),
        "recover" => {
            let _ = ctx.ensure_dirs();
            ops::recover(ctx)
        }
        other => {
            el!("[bdb] error: unknown command: {other}");
            print_help();
            ECode::Usage
        }
    }
}

fn note_no_verify(tail: &[String]) {
    if tail.iter().any(|a| a == "--no-verify") {
        el!("[bdb] notice: --no-verify accepted but ignored: on-chip readback verification is always enforced");
    }
}
