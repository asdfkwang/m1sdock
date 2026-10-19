// bdb/src/core.rs — shared context: paths, run dir, small helpers (time, json, files).
// All output is English. bdb is a trusted AI-facing tool for the Sipeed M1s (BL808) dock.
#![allow(dead_code)]
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Canonical process exit codes for every bdb command.
/// 0 ok; 1 judging failure (verify/program/timeout); 2 contention;
/// 3 NEED-USER (manual step required: buttons/replug/install); 4 usage error.
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum ECode {
    Ok,
    Fail,
    Busy,
    NeedUser,
    Usage,
}

impl ECode {
    pub const fn num(self) -> u8 {
        match self {
            ECode::Ok => 0,
            ECode::Fail => 1,
            ECode::Busy => 2,
            ECode::NeedUser => 3,
            ECode::Usage => 4,
        }
    }
}

pub const NEED: &str = "NEED-USER: ";

pub fn need(tag: &str, msg: &str) -> String {
    format!("{NEED}[{tag}] {msg}")
}

// Documented flash layout (see docs/): tool-generated bootinfo g0/g1 live at
// 0x0 / 0x1000 and the m0/d0 image bodies at 0x2000 / 0x52000.
pub const ADDR_G0: &str = "0x0";
pub const ADDR_G1: &str = "0x1000";
pub const ADDR_IMG_G0: &str = "0x2000";
pub const ADDR_IMG_G1: &str = "0x52000";

pub struct Ctx {
    pub repo: PathBuf,
    pub run_dir: PathBuf,
    pub port_c0: String,
    pub port_c1: String,
    pub baud: String,
    pub timeout: u64,
    pub json: bool,
}

#[derive(Debug, Clone)]
pub struct Opts {
    pub json: bool,
    pub timeout: u64,
    pub port_c0: Option<String>,
    pub port_c1: Option<String>,
    pub baud: Option<String>,
    pub repo: Option<PathBuf>,
}

impl Default for Opts {
    fn default() -> Self {
        Opts { json: false, timeout: 600, port_c0: None, port_c1: None, baud: None, repo: None }
    }
}

pub fn ctx_from(o: &Opts) -> Ctx {    // Build-time baked repo root: <repo>/bdb -> parent. BDB_REPO_ROOT env and
    // the --repo-root flag take priority, in that order.
    let default_repo = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    let uid = current_uid();
    let base = std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| format!("/tmp/bdb-{uid}"));
    let repo = {
        if let Some(r) = &o.repo {
            r.clone()
        } else {
            let envbase = std::env::var("BDB_REPO_ROOT").unwrap_or_default();
            if envbase.trim().is_empty() {
                default_repo
            } else {
                match Path::new(&envbase).canonicalize() {
                    Ok(p) => p,
                    Err(_) => PathBuf::from(envbase),
                }
            }
        }
    };
    Ctx {
        repo,
        run_dir: PathBuf::from(&base).join("bdb"),
        port_c0: o
            .port_c0
            .clone()
            .unwrap_or_else(|| std::env::var("BDB_PORT_C0").unwrap_or_else(|_| "/dev/ttyUSB0".into())),
        port_c1: o
            .port_c1
            .clone()
            .unwrap_or_else(|| std::env::var("BDB_PORT_C1").unwrap_or_else(|_| "/dev/ttyUSB1".into())),
        baud: o
            .baud
            .clone()
            .unwrap_or_else(|| std::env::var("BDB_BAUD").unwrap_or_else(|_| "2000000".into())),
        timeout: o.timeout,
        json: o.json,
    }
}

impl Ctx {
    pub fn venv_python(&self) -> PathBuf {
        self.repo.join("tools/venv/bin/python3")
    }
    pub fn mcu_tool(&self) -> PathBuf {
        self.repo.join("tools/bflb_mcu_tool")
    }
    pub fn iot_tool(&self) -> PathBuf {
        self.repo.join("tools/bflb_iot_tool")
    }
    pub fn gen_dir(&self) -> PathBuf {
        self.mcu_tool().join("chips/bl808/img_create_mcu")
    }
    pub fn log_dir(&self) -> PathBuf {
        self.repo.join("logs")
    }
    pub fn log_c0(&self) -> PathBuf {
        self.log_dir().join("c0.log")
    }
    pub fn log_c1(&self) -> PathBuf {
        self.log_dir().join("c1.log")
    }
    pub fn asset_bootinfo(&self) -> PathBuf {
        self.repo.join("bdb/assets/factory_bootinfo.bin")
    }
    pub fn fw_whole_img(&self) -> PathBuf {
        self.repo.join("M1s_BL808_Linux_SDK/out/whole_img_linux.bin")
    }
    pub fn vendor_m0(&self) -> PathBuf {
        self.repo.join("M1s_BL808_Linux_SDK/out/low_load_bl808_m0.bin")
    }
    pub fn vendor_d0(&self) -> PathBuf {
        self.repo.join("M1s_BL808_Linux_SDK/out/low_load_bl808_d0.bin")
    }
    pub fn lock_file(&self) -> PathBuf {
        self.run_dir.join("ttyUSB1.lock")
    }
    pub fn txn_file(&self) -> PathBuf {
        self.run_dir.join("txn.json")
    }
    pub fn txn_hist_dir(&self) -> PathBuf {
        self.run_dir.join("txn-hist")
    }
    pub fn work_dir(&self) -> PathBuf {
        self.run_dir.join("work")
    }
    pub fn ensure_dirs(&self) -> std::io::Result<()> {
        std::fs::create_dir_all(&self.run_dir)?;
        std::fs::create_dir_all(self.work_dir())?;
        std::fs::create_dir_all(self.txn_hist_dir())?;
        Ok(())
    }
}

pub fn current_uid() -> u32 {
    // Parse "Uid:" line from /proc/self/status (no libc dependency).
    if let Ok(s) = std::fs::read_to_string("/proc/self/status") {
        for line in s.lines() {
            if let Some(rest) = line.strip_prefix("Uid:") {
                if let Some(tok) = rest.split_whitespace().next() {
                    return tok.parse().unwrap_or(0);
                }
            }
        }
    }
    0
}

pub fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub fn ts_hm(secs: u64) -> String {
    // Coarse HH:MM:SS in local time is not available without tz db; use
    // UTC-formatted compact stamp (evidence timestamps are relative anyway).
    let d = secs % 86400;
    format!("{:02}:{:02}:{:02}", d / 3600, (d % 3600) / 60, d % 60)
}

pub fn fmt_evidence(pat: &str, in_w: bool) -> String {
    format!("evidence: {pat} ({} present)", if in_w { "" } else { "not " })
}

/// Minimal JSON string escaper (control chars, quotes, backslashes).
pub fn jesc(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

/// Quote-mark each element for use inside a JSON array.
pub fn jarr(items: &[String]) -> String {
    items
        .iter()
        .map(|s| format!("\"{}\"", jesc(s)))
        .collect::<Vec<_>>()
        .join(",")
}

pub fn json_kv(k: &str, v: &str) -> String {
    format!("\"{}\":\"{}\"", jesc(k), jesc(v))
}

/// Parse "0x1A" / "0x1a" / "5270" ((value, was_hex)).
pub fn parse_num(s: &str) -> Option<(u64, bool)> {
    let t = s.trim();
    if let Some(h) = t.strip_prefix("0x").or_else(|| t.strip_prefix("0X")) {
        u64::from_str_radix(h, 16).ok().map(|v| (v, true))
    } else {
        t.parse().ok().map(|v| (v, false))
    }
}

pub fn read_bytes(p: &Path) -> Option<Vec<u8>> {
    std::fs::read(p).ok()
}

pub fn path_exists(p: &Path) -> bool {
    p.exists()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn hex_parse() {
        assert_eq!(parse_num("0x10"), Some((16, true)));
        assert_eq!(parse_num("8192"), Some((8192, false)));
        assert_eq!(parse_num("zz"), None);
    }
    #[test]
    fn esc() {
        assert_eq!(jesc("a\"b\\c\n"), "a\\\"b\\\\c\\n");
    }
}
