from __future__ import annotations

import atexit
import base64
import json
import subprocess
import sys
import threading

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_voice_cache: list[str] | None = None
_engine = None
_engine_lock = threading.Lock()


def _ps(command: str) -> str:
    return subprocess.check_output(
        ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    ).strip()


def list_voices(refresh: bool = False) -> list[str]:
    """Return installed Windows SAPI voices, with Thai voices listed first."""
    global _voice_cache
    if _voice_cache is not None and not refresh:
        return list(_voice_cache)
    if sys.platform != "win32":
        _voice_cache = ["System default"]
        return list(_voice_cache)

    script = r'''
$s = New-Object -ComObject SAPI.SpVoice
$items = @()
foreach($v in @($s.GetVoices())) {
  $lang = ""
  try { $lang = $v.GetAttribute("Language") } catch {}
  $items += [PSCustomObject]@{ Description=$v.GetDescription(); Language=$lang }
}
$items | ConvertTo-Json -Compress
'''
    try:
        raw = _ps(script)
        data = json.loads(raw) if raw else []
        if isinstance(data, dict):
            data = [data]
        # Thai Windows LCID = 0x041E. Some engines return 41E;041E variants.
        thai, other = [], []
        for item in data:
            name = str(item.get("Description", "")).strip()
            lang = str(item.get("Language", "")).upper().replace("0X", "")
            if not name:
                continue
            (thai if "41E" in lang else other).append(name)
        names = thai + other
        _voice_cache = names or ["System default"]
    except Exception:
        _voice_cache = ["System default"]
    return list(_voice_cache)


class _FastSapiEngine:
    """Keeps one PowerShell/SAPI process alive so speech starts without process startup delay."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()

    def _start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self.proc is not None and self.proc.poll() is None:
            return True

        # Input protocol: base64(text) TAB base64(voice) TAB rate TAB volume
        # Speak flag 3 = SVSFlagsAsync (1) + SVSFPurgeBeforeSpeak (2), so a new
        # UI response starts immediately instead of waiting behind old speech.
        script = r'''
$s = New-Object -ComObject SAPI.SpVoice
$utf8 = [System.Text.Encoding]::UTF8
while (($line = [Console]::In.ReadLine()) -ne $null) {
  try {
    $p = $line -split "`t", 4
    if ($p.Count -lt 4) { continue }
    $text = $utf8.GetString([Convert]::FromBase64String($p[0]))
    $voiceName = $utf8.GetString([Convert]::FromBase64String($p[1]))
    $s.Rate = [Math]::Max(-10, [Math]::Min(10, [int]$p[2]))
    $s.Volume = [Math]::Max(0, [Math]::Min(100, [int]$p[3]))
    if ($voiceName -and $voiceName -ne "System default") {
      $v = @($s.GetVoices()) | Where-Object { $_.GetDescription() -eq $voiceName } | Select-Object -First 1
      if ($v) { $s.Voice = $v }
    }
    [void]$s.Speak($text, 3)
  } catch {}
}
'''
        try:
            self.proc = subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=_CREATE_NO_WINDOW,
            )
            return True
        except Exception:
            self.proc = None
            return False

    def speak(self, text: str, voice_name: str = "", rate: int = 1, volume: int = 100) -> bool:
        with self.lock:
            if not self._start() or self.proc is None or self.proc.stdin is None:
                return False
            try:
                enc = lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii")
                self.proc.stdin.write(f"{enc(str(text))}\t{enc(str(voice_name))}\t{int(rate)}\t{int(volume)}\n")
                self.proc.stdin.flush()
                return True
            except Exception:
                self.close()
                return False

    def close(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass


def _get_engine() -> _FastSapiEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = _FastSapiEngine()
        return _engine


def speak(text: str, voice_name: str = "", rate: int = 1, volume: int = 100) -> bool:
    """Fast asynchronous Windows speech. Does not block the Qt UI thread."""
    if not text:
        return True
    return _get_engine().speak(text, voice_name, rate, volume)


def shutdown() -> None:
    global _engine
    if _engine is not None:
        _engine.close()
        _engine = None


atexit.register(shutdown)
