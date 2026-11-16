# windows_ocr.ps1 - OCR anh bang Windows.Media.Ocr (WinRT), hoan toan offline.
#
#   powershell -ExecutionPolicy Bypass -File windows_ocr.ps1 -Anh "trang1.png"
#   powershell -ExecutionPolicy Bypass -File windows_ocr.ps1 -Anh "a.png","b.png" -Ra "out.txt"
#
# Luu y: Windows OCR chi nhan ANH, khong nhan PDF -> phai render truoc.

param(
    [Parameter(Mandatory = $true)][string[]]$Anh,
    [string]$Ra = "",
    [string]$NgonNgu = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

# WinRT tra ve IAsyncOperation; PowerShell 5.1 khong await duoc truc tiep -> doi sang Task.
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

function Cho($op, $kieu) {
    $t = $asTaskGeneric.MakeGenericMethod($kieu).Invoke($null, @($op))
    $t.Wait(-1) | Out-Null
    $t.Result
}

# Chon engine
if ($NgonNgu) {
    $lang = New-Object Windows.Globalization.Language $NgonNgu
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    if (-not $engine) { throw "Khong tao duoc engine cho ngon ngu '$NgonNgu'" }
}
else {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) {
        $l = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages[0]
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($l)
    }
}
Write-Host ("Engine: {0}" -f $engine.RecognizerLanguage.LanguageTag) -ForegroundColor Cyan

$tatCa = New-Object System.Collections.Generic.List[string]
foreach ($p in $Anh) {
    $full = (Resolve-Path -LiteralPath $p).Path
    $file = Cho ([Windows.Storage.StorageFile]::GetFileFromPathAsync($full)) ([Windows.Storage.StorageFile])
    $stream = Cho ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Cho ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Cho ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $kq = Cho ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    # OcrResult.Text gop het thanh 1 dong -> dung Lines de giu xuong dong
    $dong = foreach ($l in $kq.Lines) { $l.Text }
    $tatCa.Add(($dong -join "`n"))
    Write-Host ("  {0}: {1} dong, {2} ky tu" -f (Split-Path $full -Leaf), $kq.Lines.Count, $kq.Text.Length)
    $stream.Dispose()
}

$text = $tatCa -join "`n`n"
if ($Ra) {
    # -Ra co the la duong dan tuyet doi -> Join-Path se hong. Chi ghep khi la duong dan tuong doi.
    $duongRa = if ([System.IO.Path]::IsPathRooted($Ra)) { $Ra } else { Join-Path (Get-Location) $Ra }
    [System.IO.File]::WriteAllText($duongRa, $text, (New-Object System.Text.UTF8Encoding $false))
    $Ra = $duongRa
    Write-Host ("Da ghi: {0} ({1} ky tu)" -f $Ra, $text.Length) -ForegroundColor Green
}
else {
    Write-Output $text
}
