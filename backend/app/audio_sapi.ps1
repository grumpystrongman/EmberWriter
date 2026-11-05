param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [string]$Voice = "",
  [ValidateRange(-5,5)][int]$Rate = -1,
  [string]$SegmentsPath = ""
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $installed = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
  if ($Voice) {
    if ($Voice -notin $installed) { throw "Selected offline voice is not installed: $Voice" }
    $synth.SelectVoice($Voice)
  }
  $defaultVoice = $synth.Voice.Name
  $synth.Rate = $Rate
  $text = [System.IO.File]::ReadAllText($InputPath, [System.Text.Encoding]::UTF8)
  if ([string]::IsNullOrWhiteSpace($text)) { throw 'The chapter has no readable narration text' }
  $synth.SetOutputToWaveFile($OutputPath)
  if ($SegmentsPath) {
    $raw = [System.IO.File]::ReadAllText($SegmentsPath, [System.Text.Encoding]::UTF8)
    $segments = @(ConvertFrom-Json -InputObject $raw)
    if ($segments.Count -eq 0 -or $segments.Count -gt 1001) { throw 'Invalid chapter casting plan' }
    foreach ($segment in $segments) {
      $speaker = if ([string]::IsNullOrEmpty([string]$segment.voice)) { $defaultVoice } else { [string]$segment.voice }
      if ($speaker -notin $installed) { throw "Selected offline cast voice is not installed: $speaker" }
      if ([string]::IsNullOrEmpty([string]$segment.text)) { throw 'Empty cast segment' }
      if ($synth.Voice.Name -ne $speaker) { $synth.SelectVoice($speaker) }
      $synth.Speak([string]$segment.text)
    }
  } else {
    $synth.Speak($text)
  }
}
finally {
  $synth.Dispose()
}
