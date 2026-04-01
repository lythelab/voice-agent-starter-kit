import glob
import random
import threading
from pathlib import Path
import soundfile as sf
import sounddevice as sd

# Resolve the project root assuming this file is under app/audio_playback/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FILLERS_DIR = PROJECT_ROOT / "fillers"

# Preload filler clips into memory
filler_clips = []
if FILLERS_DIR.exists():
    for f in FILLERS_DIR.glob("*.wav"):
        try:
            data, fs = sf.read(str(f))
            filler_clips.append((data, fs))
        except Exception as e:
            print(f"Failed to load filler {f}: {e}")

last_played = -1

def play_audio(data, fs):
    sd.play(data, fs)
    # Don't natively wait since we want it backgrounded, 
    # but the thread will stay alive while playing. 
    sd.wait()

def play_random_filler():
    """Plays a random non-repeating filler phrase in a background thread."""
    global last_played
    
    if not filler_clips:
        print("[Warning] No filler clips found to play.")
        return

    available = [i for i in range(len(filler_clips)) if i != last_played]
    if not available:
        idx = 0
    else:
        idx = random.choice(available)
        
    last_played = idx
    
    # Non-blocking playback
    data, fs = filler_clips[idx]
    threading.Thread(
        target=play_audio,
        args=(data, fs),
        daemon=True
    ).start()
