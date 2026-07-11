//! Platform abstraction — Linux first.

#[cfg(target_os = "linux")]
mod linux;

#[cfg(target_os = "linux")]
pub use linux::*;

#[cfg(not(target_os = "linux"))]
pub fn platform_supported() -> bool {
    false
}

#[cfg(not(target_os = "linux"))]
pub fn configure_command(
    _cmd: &mut tokio::process::Command,
) -> Result<(), crate::error::SpawnError> {
    Err(crate::error::SpawnError::ProcessGroup)
}

#[cfg(not(target_os = "linux"))]
pub fn kill_process_group(_pgid: i32, _sig: nix::sys::signal::Signal) -> Result<(), String> {
    Err("unsupported platform".into())
}

#[cfg(not(target_os = "linux"))]
pub fn process_group_exists(_pgid: i32) -> bool {
    false
}

#[cfg(not(target_os = "linux"))]
pub fn pid_exists(_pid: u32) -> bool {
    false
}
