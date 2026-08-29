<#
.SYNOPSIS
  Detects GPU model + VRAM on a Windows lab PC, for picking which Ollama
  models are even worth benchmarking on it.

.NOTES
  WMI's AdapterRAM (Win32_VideoController) is a 32-bit field and silently
  wraps for cards with >=4GB VRAM, so it's not trusted here except as a
  last-resort fallback. nvidia-smi is authoritative when present.
#>

function Get-NvidiaInfo {
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $nvidiaSmi) { return $null }
    $csv = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null
    if (-not $csv) { return $null }
    return $csv | ForEach-Object {
        $parts = $_ -split ',\s*'
        [PSCustomObject]@{
            Vendor        = "NVIDIA"
            Name          = $parts[0]
            VramMB        = [int]$parts[1]
            DriverVersion = $parts[2]
        }
    }
}

function Get-WmiFallbackInfo {
    Get-CimInstance Win32_VideoController | Where-Object { $_.AdapterRAM -gt 0 } | ForEach-Object {
        [PSCustomObject]@{
            Vendor        = "unknown (WMI fallback — AdapterRAM may be wrong above 4GB)"
            Name          = $_.Name
            VramMB        = [int]([int64]$_.AdapterRAM / 1MB)
            DriverVersion = $_.DriverVersion
        }
    }
}

$nvidia = Get-NvidiaInfo
$gpus = if ($nvidia) { $nvidia } else { Get-WmiFallbackInfo }

$result = [PSCustomObject]@{
    hostname = $env:COMPUTERNAME
    gpus     = $gpus
}

$result | ConvertTo-Json -Depth 4
