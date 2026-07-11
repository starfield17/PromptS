//! Linux process-group helpers.

use nix::sys::signal::{killpg, Signal};
use nix::unistd::Pid;

use crate::error::SpawnError;

pub fn platform_supported() -> bool {
    cfg!(any(target_arch = "x86_64", target_arch = "aarch64"))
}

pub fn configure_command(cmd: &mut tokio::process::Command) -> Result<(), SpawnError> {
    cmd.process_group(0);
    cmd.kill_on_drop(true);
    Ok(())
}

pub fn kill_process_group(pgid: i32, sig: Signal) -> Result<(), String> {
    if pgid <= 1 {
        return Err("refusing to signal process group <= 1".into());
    }
    match killpg(Pid::from_raw(pgid), sig) {
        Ok(()) => Ok(()),
        Err(nix::errno::Errno::ESRCH) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

/// Signal 0 liveness check for a process group.
pub fn process_group_exists(pgid: i32) -> bool {
    pgid_alive(pgid)
}

pub fn pid_exists(pid: u32) -> bool {
    std::path::Path::new(&format!("/proc/{pid}")).exists()
}

pub fn pgid_alive(pgid: i32) -> bool {
    if pgid <= 1 {
        return false;
    }
    // None => signal 0 (existence check)
    match killpg(Pid::from_raw(pgid), None) {
        Ok(()) => true,
        Err(nix::errno::Errno::EPERM) => true,
        Err(_) => false,
    }
}
