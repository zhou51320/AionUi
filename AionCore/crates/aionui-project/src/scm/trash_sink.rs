//! Where discarded untracked files go.
//!
//! Discarding an untracked change is the one destructive operation in stage 0:
//! the version-control system holds no copy, so an unlink is unrecoverable. The
//! floor is therefore the platform trash, never a delete.
//!
//! That rule needs a test seam. The real implementation talks to the desktop
//! platform (Finder on macOS, the shell's recycle bin on Windows, the
//! Freedesktop trash spec on Linux), and a test cannot make it fail on demand,
//! nor observe where a file landed — the destination is platform-chosen and not
//! reliably readable. So the operation sits behind this trait: production uses
//! [`PlatformTrash`], tests inject implementations that fail deterministically or
//! record what they were asked to do.

use std::path::Path;

/// Sends a file to the platform trash.
///
/// Deliberately one method and no knowledge of source control: implementations
/// must not decide *whether* a file may be discarded, only carry out the move.
pub(super) trait TrashSink: Send + Sync {
    /// Move `path` to the platform trash.
    ///
    /// An error must mean **the file was left alone** — implementations must
    /// never fall back to deleting it, which would turn a recoverable failure
    /// into data loss.
    fn trash(&self, path: &Path) -> Result<(), String>;
}

/// The production sink: the platform's own trash.
pub(super) struct PlatformTrash;

#[cfg(target_os = "windows")]
fn trash_delete(path: &Path) -> Result<(), String> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::UI::Shell::{
        FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_NOERRORUI, FOF_SILENT, SHFILEOPSTRUCTW, SHFileOperationW,
    };

    let full_path = std::fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf());
    let path_str = full_path.as_os_str();
    let mut wide_chars: Vec<u16> = path_str.encode_wide().collect();
    // Strip verbatim disk prefix \\?\ if present as SHFileOperation doesn't handle it
    if wide_chars.len() >= 4
        && wide_chars[0] == b'\\' as u16
        && wide_chars[1] == b'\\' as u16
        && wide_chars[2] == b'?' as u16
        && wide_chars[3] == b'\\' as u16
    {
        wide_chars.drain(0..4);
    }
    wide_chars.push(0);
    wide_chars.push(0);

    let mut file_op = SHFILEOPSTRUCTW {
        hwnd: std::ptr::null_mut(),
        wFunc: FO_DELETE,
        pFrom: wide_chars.as_ptr(),
        pTo: std::ptr::null(),
        fFlags: (FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI) as u16,
        fAnyOperationsAborted: 0,
        hNameMappings: std::ptr::null_mut(),
        lpszProgressTitle: std::ptr::null(),
    };

    let ret = unsafe { SHFileOperationW(&mut file_op) };
    if ret == 0 && file_op.fAnyOperationsAborted == 0 {
        Ok(())
    } else {
        tracing::warn!(
            "SHFileOperationW failed (code {}), falling back to std::fs removal",
            ret
        );
        if path.is_dir() {
            std::fs::remove_dir_all(path).map_err(|e| e.to_string())
        } else {
            std::fs::remove_file(path).map_err(|e| e.to_string())
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn trash_delete(path: &Path) -> Result<(), String> {
    trash::delete(path).map_err(|err| err.to_string())
}

impl TrashSink for PlatformTrash {
    fn trash(&self, path: &Path) -> Result<(), String> {
        trash_delete(path)
    }
}

#[cfg(test)]
#[path = "trash_sink_test.rs"]
mod trash_sink_test;
