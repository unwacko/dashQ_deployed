"""Makes the "it's your turn" alarm sound with plain Python (no sound file needed).
Three short beeps, written as a WAV file in memory."""
import io
import math
import struct
import wave

RATE = 22050


def beep_wav():
    samples = []
    for beep in range(3):
        for i in range(int(RATE * 0.18)):           # 0.18 s of tone
            fade = min(1.0, i / 300, (RATE * 0.18 - i) / 300)
            value = math.sin(2 * math.pi * 880 * i / RATE) * 0.6 * fade
            samples.append(int(value * 32767))
        samples.extend([0] * int(RATE * 0.12))       # 0.12 s of silence
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return buffer.getvalue()
