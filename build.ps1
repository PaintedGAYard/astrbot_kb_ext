<#
.SYNOPSIS
    Builds the astrbot_kb_ext_access plugin into a deployable .zip archive.

.DESCRIPTION
    Packages the plugin source from ./src/astrbot_kb_ext_access/ into
    ./out/astrbot_kb_ext_access_<version>.zip, ready for AstrBot
    plugin installation (drag-and-drop or upload).

    The zip archive contains the plugin files at root level, matching
    AstrBot's expected layout for plugin zip files.

.EXAMPLE
    .\build.ps1
#>

$ErrorActionPreference = "Stop"

# ── Configuration ────────────────────────────────────────────────
$PluginName   = "astrbot_kb_ext_access"
$SourceDir    = Join-Path $PSScriptRoot "src" $PluginName
$OutDir       = Join-Path $PSScriptRoot "out"

# 自动从 metadata.yaml 读取版本号
$Version      = if (Test-Path (Join-Path $SourceDir "metadata.yaml")) {
    $yaml = Get-Content (Join-Path $SourceDir "metadata.yaml") -Raw
    if ($yaml -match 'version:\s*([\d.]+)') { $Matches[1] } else { "0.0.0" }
} else { "0.0.0" }

# ── Validate source directory ────────────────────────────────────
$OutputZip    = Join-Path $OutDir "${PluginName}_${Version}.zip"

# ── Validate source directory ────────────────────────────────────
if (-not (Test-Path $SourceDir)) {
    Write-Error "Source directory not found: $SourceDir"
    exit 1
}

Write-Host "Packing plugin v$Version from: $SourceDir" -ForegroundColor Cyan

# ── Ensure output directory ──────────────────────────────────────
if (-not (Test-Path $OutDir)) {
    $null = New-Item -ItemType Directory -Path $OutDir -Force
}

# ── Remove existing zip if present ───────────────────────────────
if (Test-Path $OutputZip) {
    Remove-Item $OutputZip -Force
}

# ── Collect all files and folders (maintains subdirectory structure) ──
$items = Get-ChildItem -Path $SourceDir

# Also include README.md from project root
$readmePath = Join-Path $PSScriptRoot "README.md"
if (Test-Path $readmePath) {
    $items += Get-Item $readmePath
}

# ── Create zip ───────────────────────────────────────────────────
$compressParams = @{
    Path             = $items.FullName
    DestinationPath  = $OutputZip
    CompressionLevel = "Optimal"
}
Compress-Archive @compressParams

Write-Host "✅ Plugin archive created: $OutputZip" -ForegroundColor Green
Write-Host "   Size: $((Get-Item $OutputZip).Length / 1KB -as [int]) KB" -ForegroundColor Green

# ── List archive contents ────────────────────────────────────────
Write-Host "`nArchive contents:" -ForegroundColor Cyan
try {
    Add-Type -AssemblyName System.IO.Compression 2>$null
    $archive = [System.IO.Compression.ZipFile]::OpenRead($OutputZip)
    foreach ($entry in $archive.Entries) {
        $sizeKB = [Math]::Max(1, [int]($entry.Length / 1KB))
        $marker = if ($entry.Name -eq "") { "  " } else { "  " }
        Write-Host "$marker$($entry.FullName)  ($sizeKB KB)"
    }
    $archive.Dispose()
}
catch {
    Write-Host "  (could not list contents)" -ForegroundColor Gray
}

Write-Host "`nDone." -ForegroundColor Cyan
