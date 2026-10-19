// journal.rs — crash-safe flash transaction journal.
//
// A transaction manifest is written BEFORE any flash step; each region record
// is updated after verification. Any later bdb invocation can therefore
// reconstruct "what happened so far" even when the writing process died
// (owner pid + /proc start ticks detect death and pid reuse).
use std::fs;
use std::path::Path;

use crate::core::{json_kv, now_secs};
use crate::procs;

#[derive(Clone, Debug)]
pub struct Region {
    pub name: String,
    pub addr: String,
    pub size: u64,
    pub src: String,
    pub src_sha256: String,
    pub verified: bool,
}

#[derive(Clone, Debug)]
pub struct Txn {
    pub id: String,
    pub ts: u64,
    pub pid: i32,
    pub pid_start: u64,
    pub cmd: String,
    pub status: String, // running | done | failed | superseded
    pub regions: Vec<Region>,
    pub recover_of: Option<String>,
}

pub struct OpenTxn {
    pub txn: Txn,
    pub owner_dead: bool,
}

impl Txn {
    pub fn new(cmd: &str) -> Txn {
        let (pid, pid_start) = procs::self_meta();
        Txn {
            id: new_id(),
            ts: now_secs(),
            pid,
            pid_start,
            cmd: cmd.to_string(),
            status: "running".into(),
            regions: Vec::new(),
            recover_of: None,
        }
    }

    pub fn to_json(&self) -> String {
        let mut s = String::new();
        s.push_str("{");
        s.push_str(&json_kv("id", &self.id));
        s.push_str(",");
        s.push_str(&format!("\"ts\":{}", self.ts));
        s.push_str(",");
        s.push_str(&json_kv("cmd", &self.cmd));
        s.push_str(",");
        s.push_str(&json_kv("status", &self.status));
        s.push_str(",");
        s.push_str(&format!("\"pid\":{}", self.pid));
        s.push_str(",");
        s.push_str(&format!("\"pid_start\":{}", self.pid_start));
        if let Some(r) = &self.recover_of {
            s.push_str(",");
            s.push_str(&json_kv("recover_of", r));
        }
        s.push_str(",\"regions\":[");
        for (i, r) in self.regions.iter().enumerate() {
            if i > 0 {
                s.push_str(",");
            }
            s.push_str(&format!(
                "{{{},{},{},{},{},{}}}",
                json_kv("name", &r.name),
                json_kv("addr", &r.addr),
                format!("\"size\":{}", r.size),
                json_kv("src", &r.src),
                json_kv("src_sha256", &r.src_sha256),
                format!("\"verified\":{}", r.verified),
            ));
        }
        s.push_str("]}");
        s
    }
}

fn field_scalar(json: &str, key: &str) -> Option<String> {
    // Robust-enough scalar grab for keys we emit ourselves.
    let pat = format!("\"{key}\":");
    let at = json.find(&pat)? + pat.len();
    let rest = &json[at..];
    if rest.starts_with('"') {
        let end = rest[1..].find('"')? + 1;
        Some(rest[1..end].to_string())
    } else {
        let t = rest
            .find(|c| c == ',' || c == '}')
            .map(|i| &rest[..i])
            .unwrap_or(rest);
        Some(t.trim().to_string())
    }
}

fn new_id() -> String {
    let secs = now_secs();
    let millis = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_millis())
        .unwrap_or(0);
    format!("txn-{secs:x}-{millis:04x}")
}

fn with_unescape(v: String) -> String {
    // Our jesc-escaped values only ever contain \\n escapes; undo those.
    v.replace("\\n", "\n")
}

/// Load the active transaction (if any) and detect owner death.
pub fn open_active(path: &Path) -> Option<OpenTxn> {
    let raw = fs::read_to_string(path).ok().filter(|s| !s.trim().is_empty())?;
    let id = field_scalar(&raw, "id")?;
    let cmd = with_unescape(field_scalar(&raw, "cmd").unwrap_or_default());
    let status = field_scalar(&raw, "status").unwrap_or_else(|| "running".into());
    let pid: i32 = field_scalar(&raw, "pid").and_then(|v| v.parse().ok())?;
    let pid_start: u64 = field_scalar(&raw, "pid_start").and_then(|v| v.parse().ok()).unwrap_or(0);
    let recover_of = field_scalar(&raw, "recover_of").filter(|v| !v.trim().is_empty());
    let mut txn = Txn {
        id,
        ts: 0,
        pid,
        pid_start,
        cmd,
        status,
        regions: Vec::new(),
        recover_of,
    };
    if let Some(at) = raw.find("\"regions\":[") {
        let seg = &raw[at + "\"regions\":[".len()..];
        for obj in split_objects(seg) {
            txn.regions.push(Region {
                name: field_scalar(obj, "name").unwrap_or_default(),
                addr: field_scalar(obj, "addr").unwrap_or_default(),
                size: field_scalar(obj, "size").and_then(|v| v.parse().ok()).unwrap_or(0),
                src: with_unescape(field_scalar(obj, "src").unwrap_or_default()),
                src_sha256: field_scalar(obj, "src_sha256").unwrap_or_default(),
                verified: field_scalar(obj, "verified").as_deref() == Some("true"),
            });
        }
    }
    let owner_dead = txn.status == "running" && !procs::pid_alive(pid, pid_start);
    Some(OpenTxn { txn, owner_dead })
}

/// Split a "[{...},{...}]" fragment into raw "{...}" strings.
fn split_objects(seg: &str) -> Vec<&str> {
    let seg = seg.split_once(']').map(|(a, _)| a).unwrap_or(seg);
    let mut out = Vec::new();
    let bytes = seg.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'{' {
            for j in i..bytes.len() {
                if bytes[j] == b'}' {
                    out.push(&seg[i..=j]);
                    i = j;
                    break;
                }
            }
        }
        i += 1;
    }
    out
}

pub fn save_active(path: &Path, txn: &Txn) -> std::io::Result<()> {
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, txn.to_json())?;
    fs::rename(&tmp, path)
}

/// Move the finished txn into the history dir; clears the active slot.
pub fn finalize(path: &Path, hist_dir: &Path, txn: &Txn) -> std::io::Result<()> {
    fs::write(hist_dir.join(format!("{}.json", txn.id)), txn.to_json())?;
    fs::write(path, "")
}

/// Archive a copy to the history dir but keep the active slot occupied
/// (failed/interrupted txns stay discoverable and recoverable).
pub fn archive(path: &Path, hist_dir: &Path, txn: &Txn) -> std::io::Result<()> {
    fs::write(hist_dir.join(format!("{}.json", txn.id)), txn.to_json())?;
    save_active(path, txn)
}
