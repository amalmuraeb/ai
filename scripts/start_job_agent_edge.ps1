<#
.SYNOPSIS
Starts Microsoft Edge for Job-Agent with Chrome DevTools Protocol enabled.

.DESCRIPTION
Copy this script to a convenient location on the Windows filesystem, save
it as start_job_agent_edge.ps1, and run it from a Windows PowerShell terminal:

    .\start_job_agent_edge.ps1 `
        -LandingUrl "https://www.higheredjobs.com/myHigherEdJobs/Agent/viewagent.cfm?AgentID=123456"

If the PowerShell execution policy blocks local scripts, run:

    powershell -ExecutionPolicy Bypass `
        -File .\start_job_agent_edge.ps1 `
        -LandingUrl "https://www.higheredjobs.com/myHigherEdJobs/Agent/viewagent.cfm?AgentID=123456"

WARNING: The script closes all currently running Microsoft Edge processes
before starting the dedicated Job-Agent browser profile. Save any work open
in Edge before running it.
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://(www\.)?higheredjobs\.com/myHigherEdJobs/Agent/viewagent\.cfm\?.*AgentID=\d+')]
    [string]$LandingUrl
)

$ErrorActionPreference = "Stop"

$EdgeCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
)

$EdgeExecutable = $EdgeCandidates |
    Where-Object { Test-Path $_ } |
    Select-Object -First 1

if (-not $EdgeExecutable) {
    throw "Microsoft Edge was not found in either standard installation directory."
}

$ProfileDirectory = "C:\JobAgent\HigherEdJobsProfile"
$CdpEndpoint = "http://127.0.0.1:9222/json/version"

Write-Host "Closing existing Microsoft Edge processes..."
Get-Process msedge -ErrorAction SilentlyContinue |
    Stop-Process -Force

New-Item -ItemType Directory -Path $ProfileDirectory -Force |
    Out-Null

$EdgeArguments = @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$ProfileDirectory",
    "--new-window",
    $LandingUrl
)

Write-Host "Starting Microsoft Edge for Job-Agent..."
Start-Process `
    -FilePath $EdgeExecutable `
    -ArgumentList $EdgeArguments

Write-Host "Waiting for the CDP endpoint..."
$CdpReady = $false

for ($Attempt = 1; $Attempt -le 15; $Attempt++) {
    try {
        $Version = Invoke-RestMethod `
            -Uri $CdpEndpoint `
            -TimeoutSec 2

        $CdpReady = $true
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $CdpReady) {
    throw "Microsoft Edge started, but the CDP endpoint did not become available at $CdpEndpoint."
}

Write-Host "Job-Agent Edge browser is ready."
Write-Host "Browser: $($Version.Browser)"
Write-Host "CDP endpoint: $CdpEndpoint"
Write-Host "Landing page: $LandingUrl"
