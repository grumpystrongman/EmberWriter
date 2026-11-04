param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [string]$Voice = ""
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  if ($Voice) {
    $installed = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
    if ($Voice -notin $installed) { throw "Selected offline voice is not installed: $Voice" }
    $synth.SelectVoice($Voice)
  }
  $synth.Rate = -1
  $text = [System.IO.File]::ReadAllText($InputPath, [System.Text.Encoding]::UTF8)
  if ([string]::IsNullOrWhiteSpace($text)) { throw 'The chapter has no readable narration text' }
  $synth.SetOutputToWaveFile($OutputPath)
  $synth.Speak($text)
}
finally {
  $synth.Dispose()
}
