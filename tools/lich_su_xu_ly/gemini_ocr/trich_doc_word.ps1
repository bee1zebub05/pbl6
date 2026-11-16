# Trich text tu file .doc bang chinh Microsoft Word (COM).
#
# antiword doc duoc 1/5 file, 4 file con lai no bao "is not a Word Document" du ben
# trong VAN co luong WordDocument — nhieu kha nang la ban Word doi moi hon antiword
# ho tro. Dung chinh Word thi khong con van de tuong thich, va chu lay ra la chu THAT
# do may tao chu khong phai OCR nen chinh xac tuyet doi.
#
#   powershell -ExecutionPolicy Bypass -File trich_doc_word.ps1 -InDir <thu muc .doc> -OutDir <thu muc .txt>

param(
  [Parameter(Mandatory=$true)][string]$InDir,
  [Parameter(Mandatory=$true)][string]$OutDir
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

$ok = 0; $hong = 0
try {
  foreach ($f in Get-ChildItem -Path $InDir -Filter *.doc) {
    try {
      # ReadOnly + khong sua doi: khong dung gi den file goc
      $doc = $word.Documents.Open($f.FullName, $false, $true)
      $txt = $doc.Content.Text
      $doc.Close($false)
      $out = Join-Path $OutDir ($f.BaseName + ".txt")
      # -Encoding utf8 cua Out-File o Windows PowerShell 5.1 co BOM; dung .NET de khong BOM
      [System.IO.File]::WriteAllText($out, $txt, (New-Object System.Text.UTF8Encoding($false)))
      Write-Output ("OK   " + $f.BaseName + "  " + $txt.Length + " ky tu")
      $ok++
    } catch {
      Write-Output ("HONG " + $f.BaseName + "  " + $_.Exception.Message)
      $hong++
    }
  }
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output ("--- xong: $ok thanh cong, $hong hong ---")
