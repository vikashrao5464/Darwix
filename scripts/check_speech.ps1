param([string]$Language='en-US', [string]$AgentVoice='Microsoft David Desktop', [string]$CustomerVoice='Microsoft Zira Desktop')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$recognizers=[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
$speech=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voices=$speech.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
    $languages=$recognizers | ForEach-Object { $_.Culture.Name }
    @{recognizer_languages=@($languages); voices=@($voices)} | ConvertTo-Json
    if ($Language -notin $languages -or $AgentVoice -notin $voices -or $CustomerVoice -notin $voices) {
        Write-Error 'Install/configure the required Windows desktop speech components before running the voice demo.'
        exit 1
    }
} finally { $speech.Dispose() }
