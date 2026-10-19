// procs.rs — process inspection: which processes hold the serial ports.
// Pure /proc scanning; no external libraries.
use std::collections::HashSet;
use std::fs;

#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct Holder {
    pub pid: i32,
    pub ppid: i32,
    pub start_ticks: u64,
    pub comm: String,
    pub cmd: String,
}

impl Holder {
    /// ghost = our own flash child (bflb python) whose bdb parent is gone.
    pub fn is_bflb_child(&self) -> bool {
        self.cmd.contains("bflb")
    }
    pub fn summary(&self) -> String {
        format!(
            "holder_pid={} holder_pname={} holder_cmd=\"{}\"",
            self.pid, self.comm, self.cmd
        )
    }
}

fn proc_stat(pid: i32) -> Option<(i32, u64)> {
    let s = fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    // comm lives in parentheses; fields start after the last ')'.
    let rest_start = s.rfind(')')? + 1;
    let rest: Vec<&str> = s[rest_start..].split_whitespace().collect();
    // rest[0]=state(3) rest[1]=ppid(4) ... rest[k] = field k+3.
    let ppid = rest.get(1)?.parse().ok()?;
    // starttime is field 22 -> rest[19].
    let start: u64 = rest.get(19)?.parse().ok()?;
    Some((ppid, start))
}

fn proc_comm(pid: i32) -> Option<String> {
    fs::read_to_string(format!("/proc/{pid}/comm")).ok().map(|s| {
        s.lines().next().unwrap_or("").to_string()
    })
}

fn proc_cmdline(pid: i32) -> Option<String> {
    let raw = fs::read(format!("/proc/{pid}/cmdline")).ok()?;
    let parts: Vec<String> = raw
        .split(|b| *b == 0)
        .filter(|s| !s.is_empty())
        .map(|s| String::from_utf8_lossy(s).into_owned())
        .collect();
    if parts.is_empty() {
        return None;
    }
    Some(parts.join(" "))
}

fn self_pid() -> i32 {
    std::process::id() as i32
}

/// All processes whose /proc/<pid>/fd/* links point to `dev`.
pub fn holders_of(dev: &str) -> Vec<Holder> {
    let me = self_pid();
    let mut out = Vec::new();
    let mut seen: HashSet<i32> = HashSet::new();
    let dirs = match fs::read_dir("/proc") {
        Ok(d) => d,
        Err(_) => return out,
    };
    for dir in dirs.flatten() {
        let name = dir.file_name();
        let pid = match name.to_string_lossy().parse::<i32>() {
            Ok(p) if p > 0 => p,
            _ => continue,
        };
        let fds = match fs::read_dir(format!("/proc/{pid}/fd")) {
            Ok(d) => d,
            Err(_) => continue,
        };
        for fd in fds.flatten() {
            let Ok(target) = fs::read_link(fd.path()) else { continue };
            if target.to_string_lossy() != dev {
                continue;
            }
            if !seen.insert(pid) {
                break;
            }
            let (ppid, start_ticks) = proc_stat(pid).unwrap_or((0, 0));
            out.push(Holder {
                pid,
                ppid,
                start_ticks,
                comm: proc_comm(pid).unwrap_or_else(|| "?".into()),
                cmd: proc_cmdline(pid).unwrap_or_else(|| format!("[pid {pid}]")),
            });
            break;
        }
    }
    out.retain(|h| h.pid != me);
    out.sort_by_key(|h| h.pid);
    out
}

/// True when pid is alive and its /proc start ticks match `start_ticks`
/// (protects against pid reuse).
pub fn pid_alive(pid: i32, start_ticks: u64) -> bool {
    match proc_stat(pid) {
        Some((_, st)) if st == start_ticks => true,
        _ => false,
    }
}

pub fn self_meta() -> (i32, u64) {
    let pid = std::process::id() as i32;
    (pid, proc_stat(pid).map(|(_, s)| s).unwrap_or(0))
}

pub fn kill_pid(pid: i32, sig: &str) {
    let _ = std::process::Command::new("kill")
        .args([sig, pid.to_string().as_str()])
        .status();
}
