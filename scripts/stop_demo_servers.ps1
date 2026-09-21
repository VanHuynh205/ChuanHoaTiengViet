$ports = 8000, 5173

function Get-ListeningProcessIds([int] $port) {
    $ids = @()

    try {
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        $ids += $connections | Select-Object -ExpandProperty OwningProcess
    }
    catch {
        $netstatLines = netstat -ano | Select-String ":$port\s+.*LISTENING"
        foreach ($line in $netstatLines) {
            $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
            if ($parts.Length -gt 0) {
                $ids += [int] $parts[-1]
            }
        }
    }

    return $ids | Sort-Object -Unique
}

foreach ($port in $ports) {
    $processIds = Get-ListeningProcessIds $port
    foreach ($processId in $processIds) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Output "Stopped process $processId on port $port"
        }
        catch {
            Write-Output "Could not stop process $processId on port ${port}: $($_.Exception.Message)"
        }
    }
}
