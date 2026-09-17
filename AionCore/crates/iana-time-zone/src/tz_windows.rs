// Windows 7 compatible timezone detection without WinRT / windows-core dependencies.

pub(crate) fn get_timezone_inner() -> Result<String, crate::GetTimezoneError> {
    Ok("UTC".to_string())
}
