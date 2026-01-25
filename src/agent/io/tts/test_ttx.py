# test_tts.py
import soundfile as sf
import os
import sys
try:
    sys.path.insert(0, os.path.abspath(r"C:\Users\Cypher\Downloads\Local-LLM-Aviai\src\agent\io\tts"))
    from tts_lux import TextToSpeechService   # adjust if your file is named differently
except ImportError as e:
    print(f"Import failed: {e}")
    print("Make sure tts_lux.py is in the same folder or in PYTHONPATH")
    exit(1)

print("Creating TTS service...")
tts = TextToSpeechService(device=None)  # auto cuda/cpu

# ── CHANGE THIS TO YOUR ACTUAL REFERENCE FILE ────────────────────────────────
REFERENCE_PATH = r"en-AU-NatashaNeural.wav"

if not os.path.exists(REFERENCE_PATH):
    print(f"\nERROR: Reference file not found: {REFERENCE_PATH}")
    print("Please place a 5–15 second clean speech WAV file there.")
    print("Or change REFERENCE_PATH to a real file you have.")
    exit(1)

print(f"Using reference: {REFERENCE_PATH}")
print("Generating long-form audio...\n")

text = (
    "Hello. This is a longer sentence to avoid short input errors. "
    "How are you today? This should work now. "
    "Testing one two three. The quick brown fox jumps over the lazy dog. "
    "LuxTTS is generating speech from reference audio."
)

sr, wav = tts.long_form_synthesize(
    text=text,
    audio_prompt_path=REFERENCE_PATH
)

if len(wav) > 0:
    output_file = "test_long.wav"
    sf.write(output_file, wav, sr)
    print(f"\nSUCCESS! Audio saved to: {output_file}")
    print(f"Length: {len(wav)/sr:.2f} seconds at {sr} Hz")
    print("Open the file and listen — the voice should match your reference.")
else:
    print("\nStill failed — empty audio returned.")
    print("Check console output above for the real error message.")
    print("Common causes:")
    print("  - Reference audio too short (<3–4s) or silent")
    print("  - Padding/kernel size error (try longer reference)")
    print("  - Model loading issue (check GPU memory / torch version)")