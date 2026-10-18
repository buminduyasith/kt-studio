# Premixes every sound effect of the v3 promo into one track (assets/audio/sfx.wav).
# Times match index.html: keep the two in step.
import subprocess, numpy as np, wave, sys, random
P = sys.argv[1]
SR = 48000
END = 53.0

def load(name):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{P}/assets/sfx/{name}.mp3", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)

out = np.zeros((int(SR * END) + SR, 2), dtype=np.float32)
cache = {}
def at(t, name, vol, rate=1.0):
    if name not in cache: cache[name] = load(name)
    s = cache[name]
    if rate != 1.0:  # small pitch change so repeated keys don't sound like a machine gun
        idx = np.arange(0, len(s) - 1, rate)
        s = np.stack([np.interp(idx, np.arange(len(s)), s[:, c]) for c in (0, 1)], axis=1)
    i = int(t * SR)
    n = min(len(s), len(out) - i)
    out[i:i + n] += s[:n] * vol

rnd = random.Random(7)
def keys(times, vol):
    for t in times:
        at(t, "key-press", vol * rnd.uniform(0.75, 1.0), rnd.uniform(0.92, 1.1))

# 1 · the command: "/kt-studio" then a beat, then " appointment-booking", then Enter
cmd = "/kt-studio appointment-booking"
ktimes = [0.5 + i * 0.07 if i < 10 else 1.5 + (i - 10) * 0.055 for i in range(len(cmd))]
keys(ktimes, 0.9)
at(2.85, "click", 0.8); at(2.85, "impact-bass-1", 0.3)
at(3.05, "whoosh-short", 0.35); at(4.0, "whoosh-short", 0.3)
for t in (5.0, 5.3, 5.6): at(t, "pop", 0.25)
for t in (5.9, 6.05, 6.2): at(t, "pop", 0.2)
# 2 · the storyboard
at(7.35, "whoosh", 0.5); at(7.7, "impact-bass-2", 0.15); at(8.4, "whoosh-short", 0.4)
for t in (9.65, 10.65, 11.55, 12.35): at(t, "whoosh-short", 0.22)
at(13.4, "click", 0.8); at(13.6, "impact-bass-1", 0.25); at(13.65, "chime", 0.35)
# 3 · the code tour
at(15.75, "whoosh", 0.5)
for t in (16.8, 18.75, 21.3): at(t, "pop", 0.25)
# 4 · the real app (clicks land with the take's own clicks)
at(23.75, "whoosh", 0.45)
for t in (24.93, 28.23): at(t, "click", 0.55)
for t in (28.6, 28.9): at(t, "ping", 0.22)
# 5 · the big picture
at(29.75, "whoosh", 0.45); at(33.0, "whoosh-short", 0.3)
# 6 · any language
at(35.37, "riser", 0.14)
at(35.75, "whoosh", 0.45)
for t in (36.15, 36.4, 36.52, 36.64): at(t, "pop", 0.32)
for k in range(7): at(37.4 + k * 0.08, "click-soft", 0.22)
at(38.3, "ping", 0.3)
# 7 · updates
at(40.35, "whoosh", 0.45); at(41.9, "whoosh-short", 0.35); at(42.35, "pop", 0.45)
for t in (42.8, 43.0): at(t, "pop", 0.3)
# 8 · end card
at(45.2, "whoosh", 0.4); at(45.6, "impact-bass-1", 0.3); at(46.8, "sparkle", 0.12)
inst = "/plugin install kt-studio@kt-studio"
keys([49.3 + i * 0.04 for i in range(len(inst))], 0.55)

out = out[: int(SR * END)]
peak = np.abs(out).max()
if peak > 0.98: out *= 0.98 / peak
pcm = (out * 32767).astype("<i2")
with wave.open(f"{P}/assets/audio/sfx.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("sfx ok, peak", round(float(peak), 3))
