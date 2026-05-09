# =============================================================================
# stt.py — Speech-to-Text (SpeechRecognition + Google STT)
# =============================================================================
# Records audio from the USB microphone and transcribes via Google STT.
# Falls back to a text prompt if microphone is unavailable (useful for testing).
# =============================================================================

import speech_recognition as sr
import config


def listen_and_transcribe(prompt: str = None) -> str:
    """Record from mic and return transcribed text (lowercase, stripped).

    Args:
        prompt: Optional text to speak/print before listening.

    Returns:
        Transcribed string, or empty string on failure.
    """
    recognizer = sr.Recognizer()

    if prompt:
        print(f"\n[STT] {prompt}")

    try:
        with sr.Microphone() as source:
            print("[STT] Listening... (speak now)")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(
                source,
                timeout=config.RECORD_TIMEOUT,
                phrase_time_limit=config.PHRASE_TIME_LIMIT,
            )

        print("[STT] Processing speech...")
        text = recognizer.recognize_google(audio, language=config.STT_LANGUAGE)
        text = text.strip().lower()
        print(f"[STT] Heard: \"{text}\"")
        return text

    except sr.WaitTimeoutError:
        print("[STT] No speech detected within timeout.")
        return ""
    except sr.UnknownValueError:
        print("[STT] Could not understand the audio.")
        return ""
    except sr.RequestError as e:
        print(f"[STT] Google STT error: {e}")
        return ""
    except OSError as e:
        # Microphone not available — fall back to text input
        print(f"[STT] Microphone unavailable ({e}). Falling back to text input.")
        if prompt:
            return input(f"  >> Type your response: ").strip().lower()
        return input("  >> Type your response: ").strip().lower()
