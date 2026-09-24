import sys
import time
from faster_whisper import WhisperModel

path = sys.argv[1]
size = sys.argv[2] if len(sys.argv) > 2 else "small"
model = WhisperModel(size, device="cpu", compute_type="int8")

t0 = time.time()
segments, info = model.transcribe(path, vad_filter=True)
text = " ".join(s.text.strip() for s in segments)
dt = time.time() - t0
print(f"langue={info.language} (p={info.language_probability:.2f}) "
      f"durée={info.duration:.1f}s temps={dt:.1f}s RTF={dt/info.duration:.2f}")
print(text)