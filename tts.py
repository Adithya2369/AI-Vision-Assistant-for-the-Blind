# =============================================================================
# tts.py — Text-to-Speech (gTTS)
# =============================================================================
# Uses gTTS to generate natural-sounding speech and plays it with pygame.
# Thread-safe: a Lock prevents overlapping speech.
# =============================================================================

import os
import threading
import tempfile
from gtts import gTTS
import config

# ── Lazy-import pygame mixer (only needed at runtime) ─────────────────────────
_mixer_ready = False

def _ensure_mixer():
    global _mixer_ready
    if not _mixer_ready:
        import pygame
        pygame.mixer.init()
        _mixer_ready = True


class Speaker:
    """Thread-safe TTS speaker using gTTS + pygame."""

    def __init__(self):
        self._lock = threading.Lock()

    def speak(self, text: str, block: bool = True):
        """Convert text to speech and play it.

        Args:
            text:  The string to speak.
            block: If True (default), wait until speech finishes.
                   If False, play in a background thread (fire-and-forget).
        """
        if block:
            self._play(text)
        else:
            t = threading.Thread(target=self._play, args=(text,), daemon=True)
            t.start()

    def _play(self, text: str):
        with self._lock:
            try:
                import pygame
                _ensure_mixer()

                # Generate speech to a temporary mp3 file
                tts = gTTS(text=text, lang=config.TTS_LANG, slow=config.TTS_SLOW)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = f.name
                tts.save(tmp_path)

                # Play using pygame mixer
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

                # Cleanup temp file
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            except Exception as e:
                # Fallback: print to console if audio fails
                print(f"[TTS] (audio error: {e}) >> {text}")

    def stop(self):
        """Immediately stop any ongoing speech."""
        try:
            import pygame
            if _mixer_ready:
                pygame.mixer.music.stop()
        except Exception:
            pass


# Module-level singleton — import and use directly:  from tts import speaker
speaker = Speaker()
