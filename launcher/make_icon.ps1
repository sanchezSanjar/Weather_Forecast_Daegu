# Draws the Weather Forecast Daegu logo (sun behind a cloud) and writes assets\weather.ico.
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force (Join-Path $root "assets") | Out-Null
$icoPath = Join-Path $root "assets\weather.ico"

$images = @()
foreach ($size in 16, 24, 32, 48, 64, 128, 256) {
    $s = [single]$size
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    $blue = [System.Drawing.ColorTranslator]::FromHtml("#1d4e89")
    $sun = [System.Drawing.ColorTranslator]::FromHtml("#f4a259")
    $g.FillEllipse((New-Object System.Drawing.SolidBrush $blue), $s * 0.03, $s * 0.03, $s * 0.94, $s * 0.94)
    $g.FillEllipse((New-Object System.Drawing.SolidBrush $sun), $s * 0.40, $s * 0.18, $s * 0.36, $s * 0.36)
    $cloud = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $g.FillEllipse($cloud, $s * 0.18, $s * 0.48, $s * 0.30, $s * 0.26)
    $g.FillEllipse($cloud, $s * 0.32, $s * 0.38, $s * 0.32, $s * 0.32)
    $g.FillEllipse($cloud, $s * 0.50, $s * 0.48, $s * 0.28, $s * 0.26)
    $g.FillRectangle($cloud, $s * 0.30, $s * 0.58, $s * 0.36, $s * 0.16)
    $g.Dispose()

    $stream = New-Object System.IO.MemoryStream
    $bmp.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $images += , @($size, $stream.ToArray())
    $bmp.Dispose()
}

$out = New-Object System.IO.MemoryStream
$w = New-Object System.IO.BinaryWriter $out
$w.Write([UInt16]0); $w.Write([UInt16]1); $w.Write([UInt16]$images.Count)
$offset = 6 + 16 * $images.Count
foreach ($img in $images) {
    $dim = if ($img[0] -ge 256) { 0 } else { $img[0] }
    $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([UInt16]1); $w.Write([UInt16]32)
    $w.Write([UInt32]$img[1].Length); $w.Write([UInt32]$offset)
    $offset += $img[1].Length
}
foreach ($img in $images) { $w.Write($img[1]) }
$w.Flush()
[System.IO.File]::WriteAllBytes($icoPath, $out.ToArray())
Write-Output "Icon written: $icoPath"
