param(
  [string]$ZipPath = "",
  [int]$Parallel = 12
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ZipPath)) {
  $localZip = Join-Path $PSScriptRoot 'opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL.zip'
  $docZip = 'C:\Users\melafrit\Documents\opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip'
  if (Test-Path -LiteralPath $localZip) { $ZipPath = $localZip } else { $ZipPath = $docZip }
}
$ExpectedSha = 'e8acad28dea5a531c21171db570b60d612993edd91db8f893e58c187c226696a'
$Endpoint = 'https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/asv2-payload-ingest'
$StatusUrl = 'https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation/status'
$Secret = 'lWV63_tTSLR7EG2m3tzIDFnpAqS4QXn-'

if (-not (Test-Path -LiteralPath $ZipPath)) { throw "Fichier introuvable : $ZipPath" }
Write-Host "1/4  Verification du paquet..." -ForegroundColor Cyan
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
if ($sha -ne $ExpectedSha) { throw "Empreinte incorrecte. Attendu: $ExpectedSha ; obtenu: $sha" }
Write-Host "     Paquet exact confirme." -ForegroundColor Green

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromMinutes(10)
function Invoke-Init {
  $req = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, "$Endpoint?init=1")
  [void]$req.Headers.TryAddWithoutValidation('x-ingest-secret',$Secret)
  $resp = $client.SendAsync($req).GetAwaiter().GetResult(); $txt = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult(); $req.Dispose()
  if (-not $resp.IsSuccessStatusCode) { $resp.Dispose(); throw "Initialisation impossible: $txt" }; $resp.Dispose()
}
function New-UploadTask([string]$Path,[byte[]]$Bytes,[string]$ContentType) {
  $req = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, $Endpoint)
  [void]$req.Headers.TryAddWithoutValidation('x-ingest-secret',$Secret); [void]$req.Headers.TryAddWithoutValidation('x-object-path',$Path)
  $content = New-Object System.Net.Http.ByteArrayContent(,$Bytes); $content.Headers.ContentType = New-Object System.Net.Http.Headers.MediaTypeHeaderValue($ContentType); $req.Content = $content
  [pscustomobject]@{ Path=$Path; Request=$req; Task=$client.SendAsync($req) }
}
function Finish-Batch([System.Collections.ArrayList]$Batch) {
  if ($Batch.Count -eq 0) { return }; $tasks=@($Batch|ForEach-Object{$_.Task}); [System.Threading.Tasks.Task]::WaitAll([System.Threading.Tasks.Task[]]$tasks)
  foreach($x in $Batch){$resp=$x.Task.Result;$txt=$resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();if(-not $resp.IsSuccessStatusCode){$resp.Dispose();$x.Request.Dispose();throw "Echec upload $($x.Path): $txt"};$resp.Dispose();$x.Request.Dispose()};$Batch.Clear()
}
Invoke-Init
Write-Host "2/4  Chargement securise des donnees de l'experience..." -ForegroundColor Cyan
$zip=[System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $entries=@($zip.Entries|Where-Object{($_.FullName -eq 'as2_full_environment_prompt_v2.md') -or ($_.FullName -eq 'as2_full_environment_output_schema_v2.json') -or ($_.FullName -like 'voter_batches/*/*/*.json') -or ($_.FullName -like 'contexts/*/*/*.json')}|Where-Object{$_.Length -gt 0})
  if($entries.Count -ne 1842){throw "Nombre de fichiers inattendu: $($entries.Count) au lieu de 1842."}
  $batch=New-Object System.Collections.ArrayList;$done=0
  foreach($entry in $entries){$stream=$entry.Open();try{$ms=New-Object System.IO.MemoryStream;$stream.CopyTo($ms);$bytes=$ms.ToArray();$ms.Dispose()}finally{$stream.Dispose()};$ct=if($entry.FullName.EndsWith('.json')){'application/json'}else{'text/plain'};[void]$batch.Add((New-UploadTask $entry.FullName $bytes $ct));if($batch.Count -ge $Parallel){Finish-Batch $batch};$done++;if(($done%100)-eq 0 -or $done -eq $entries.Count){Write-Progress -Activity 'Chargement de la societe' -Status "$done / $($entries.Count)" -PercentComplete ([math]::Round(100*$done/$entries.Count))}}
  Finish-Batch $batch;Write-Progress -Activity 'Chargement de la societe' -Completed
} finally {$zip.Dispose()}
Write-Host "3/4  Gel et ouverture de l'experience..." -ForegroundColor Cyan
$ready=[ordered]@{status='READY';source_sha256=$ExpectedSha;files=1842;work_items=2944;created_at_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Compress;$bytes=[Text.Encoding]::UTF8.GetBytes($ready);$b=New-Object System.Collections.ArrayList;[void]$b.Add((New-UploadTask '_READY.json' $bytes 'application/json'));Finish-Batch $b
Write-Host "4/4  Verification publique..." -ForegroundColor Cyan
$status=$client.GetStringAsync($StatusUrl).GetAwaiter().GetResult();$client.Dispose();$handler.Dispose();$obj=$status|ConvertFrom-Json;if(-not $obj.ready){throw "Le service ne se declare pas pret: $status"}
Write-Host '';Write-Host 'READY TO LAUNCH' -ForegroundColor Green;Write-Host 'La Societe artificielle du Maroc est ouverte aux participations.' -ForegroundColor Green