# Cuu 4 file .doc bi hong ma ca antiword lan Word deu khong mo duoc binh thuong.
#
# Word bao "unable to read this document. It may be corrupt" va goi y hai cach:
#   1. Open and Repair          — Word tu va lai cau truc file
#   2. Text Recovery converter  — bo qua cau truc, vet lay chu con doc duoc
# Thu lan luot, cach nao ra chu thi dung.
#
#   powershell -ExecutionPolicy Bypass -File cuu_doc_hong.ps1 -InDir <...> -OutDir <...>

param(
  [Parameter(Mandatory=$true)][string]$InDir,
  [Parameter(Mandatory=$true)][string]$OutDir
)

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

function Ghi($path, $txt) {
  [System.IO.File]::WriteAllText($path, $txt, (New-Object System.Text.UTF8Encoding($false)))
}

try {
  foreach ($f in Get-ChildItem -Path $InDir -Filter *.doc) {
    $out = Join-Path $OutDir ($f.BaseName + ".txt")
    if (Test-Path $out) { Write-Output ("BO QUA " + $f.BaseName + " (da co)"); continue }

    $txt = $null; $cach = ""

    # --- cach 1: Open and Repair (tham so thu 13) ---
    try {
      $doc = $word.Documents.Open($f.FullName, $false, $true, $false, "", "", $false,
                                  "", "", 0, 0, $false, $true)
      $txt = $doc.Content.Text
      $doc.Close($false)
      $cach = "Open and Repair"
    } catch { $txt = $null }

    # --- cach 2: bo dinh dang, vet lay chu (Recover Text from Any File) ---
    if (-not $txt -or $txt.Trim().Length -lt 200) {
      try {
        $doc = $word.Documents.Open($f.FullName, $false, $true, $false, "", "", $false,
                                    "", "", "Recover Text from Any File")
        $txt = $doc.Content.Text
        $doc.Close($false)
        $cach = "Text Recovery converter"
      } catch { }
    }

    if ($txt -and $txt.Trim().Length -ge 200) {
      Ghi $out $txt
      Write-Output ("OK   " + $f.BaseName + "  " + $txt.Length + " ky tu  [" + $cach + "]")
    } else {
      Write-Output ("HONG " + $f.BaseName + "  ca hai cach deu khong lay duoc chu")
    }
  }
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
