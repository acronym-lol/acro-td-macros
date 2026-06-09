$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
[System.Environment]::SetEnvironmentVariable('ACRO_TD_MACROS', $ScriptDir, 'User')
$env:ACRO_TD_MACROS = $ScriptDir
Write-Host "ACRO_TD_MACROS set to $ScriptDir"
