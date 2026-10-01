param(
    [Parameter(Mandatory=$true)][ValidateSet('synthesize', 'transcribe')][string]$Action,
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [string]$Voice = 'Microsoft David Desktop',
    [string]$Language = 'en-US'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
if ($Action -eq 'synthesize') {
    $speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $speech.SelectVoice($Voice)
        $speech.SetOutputToWaveFile($OutputPath)
        $speech.Speak([IO.File]::ReadAllText($InputPath, [Text.Encoding]::UTF8))
    } finally { $speech.Dispose() }
} else {
    $culture = New-Object Globalization.CultureInfo($Language)
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
    try {
        $recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
        $recognizer.SetInputToWaveFile($InputPath)
        $results = @()
        while ($null -ne ($recognized = $recognizer.Recognize())) {
            $results += [PSCustomObject]@{text=$recognized.Text; confidence=[double]$recognized.Confidence}
            # SAPI clears AudioFormat after consuming a WAV. A further Recognize
            # call would throw 'No audio input' rather than return null.
            if ($null -eq $recognizer.AudioFormat) { break }
        }
        $text = ($results | ForEach-Object { $_.text }) -join ' '
        $confidence = if ($results.Count -gt 0) { ($results | Measure-Object confidence -Minimum).Minimum } else { 0.0 }
        @{text=$text; confidence=$confidence} | ConvertTo-Json -Compress | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    } finally { $recognizer.Dispose() }
}
