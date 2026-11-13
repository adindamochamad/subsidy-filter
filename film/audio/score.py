#!/usr/bin/env python3
"""Editorial bed: low D drone, scene ticks, two harmonic lifts. No melody."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SR = 48000
DUR = 64.0
N = int(SR * DUR)


def sine(i: int, hz: float, amp: float) -> float:
    return amp * math.sin(2 * math.pi * hz * i / SR)


samples = [0.0] * N

for i in range(N):
    t = i / SR
    fade_in = min(1.0, t / 2.4)
    fade_out = 1.0 if t < DUR - 3.6 else max(0.0, (DUR - 0.25 - t) / 3.35)
    fade = fade_in * fade_out
    bed = (
        sine(i, 73.42, 0.10)
        + sine(i, 146.83, 0.032)
        + sine(i, 110.00, 0.018)
    )
    bed *= 0.86 + 0.14 * math.sin(2 * math.pi * 0.065 * t)
    samples[i] += bed * fade * 0.48

TICKS = [0.04, 9.40, 17.20, 26.20, 36.20, 50.20, 60.80]
for tt in TICKS:
    start = int(tt * SR)
    length = int(0.10 * SR)
    for k in range(length):
        j = start + k
        if j >= N:
            break
        e = math.exp(-k / (0.022 * SR))
        samples[j] += e * 0.10 * math.sin(2 * math.pi * 1568 * k / SR)
        samples[j] += e * 0.07 * math.sin(2 * math.pi * 196 * k / SR)

for t0, freqs in (
    (36.20, (220.00, 329.63)),
    (50.20, (220.00, 293.66, 329.63)),
):
    start = int(t0 * SR)
    length = int(3.6 * SR)
    for k in range(length):
        j = start + k
        if j >= N:
            break
        e = min(1.0, k / (0.45 * SR)) * math.exp(-k / (2.6 * SR))
        for f in freqs:
            samples[j] += e * 0.038 * math.sin(2 * math.pi * f * j / SR)

beat = 60.0 / 76.0
t = 17.20
while t < 58.0:
    start = int(t * SR)
    length = int(0.11 * SR)
    for k in range(length):
        j = start + k
        if j >= N:
            break
        e = math.exp(-k / (0.038 * SR))
        samples[j] += e * 0.042 * math.sin(2 * math.pi * 55 * k / SR)
    t += beat

peak = max(1e-9, max(abs(x) for x in samples))
gain = 0.82 / peak if peak > 0.82 else 1.0

out = Path(__file__).with_name("score.wav")
with wave.open(str(out), "w") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    buf = bytearray()
    for x in samples:
        v = int(max(-1.0, min(1.0, x * gain)) * 32767)
        buf += struct.pack("<hh", v, v)
    w.writeframes(buf)

print("WROTE", out, f"{DUR:.1f}s")
