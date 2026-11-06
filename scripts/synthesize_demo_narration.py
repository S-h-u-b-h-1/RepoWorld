"""Synthesize RepoWorld's demo narration with local open-weights Kokoro.

No paid APIs or account keys. No synthetic video claims and no use of private code.
Generated voice is synthetic, although designed to sound naturally spoken.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf

BEATS = [
    {
        "scene": "opening",
        "text": "RepoWorld. The City of Code. A project by Shubhaang Kataruka.",
        "pause": 0.42,
    },
    {
        "scene": "problem",
        "text": "Opening an unfamiliar GitHub repository can feel like entering a maze. With hundreds of files and folders, finding where to begin can take longer than the task itself.",
        "pause": 0.34,
    },
    {
        "scene": "city-overview",
        "text": "RepoWorld turns a public GitHub repository into a three-dimensional city. Districts represent related code areas. And every building represents a real, indexed source module.",
        "pause": 0.30,
    },
    {
        "scene": "explore",
        "text": "Move between districts, explore the structure, and follow the connections between modules. Those connections come from sampled static imports, not imagined runtime activity.",
        "pause": 0.31,
    },
    {
        "scene": "module-inspector",
        "text": "Select a building to inspect its source path, file count, and observed import connections. Then jump directly from the city to the source.",
        "pause": 0.31,
    },
    {
        "scene": "find-code",
        "text": "Looking for something specific? Find Code searches indexed paths and filenames, then points you to a relevant module.",
        "pause": 0.30,
    },
    {
        "scene": "issue-radar",
        "text": "Issue Radar brings open GitHub issues into context. It distinguishes file references from suggested locations, and keeps issues unplaced when the evidence isn't strong enough.",
        "pause": 0.32,
    },
    {
        "scene": "issue-investigation",
        "text": "Open an issue to read the original report, inspect available public source, and prepare investigation notes. RepoWorld doesn't execute code or pretend a bug has been fixed.",
        "pause": 0.34,
    },
    {
        "scene": "developer-assistant",
        "text": "The Developer Console offers optional Bharat Code assistance, grounded in available source evidence when inference succeeds. If the model is unavailable, RepoWorld clearly labels its non-AI fallback.",
        "pause": 0.30,
    },
    {
        "scene": "offline",
        "text": "It's read-only, requires no account, and can save a sanitized public map for offline exploration.",
        "pause": 0.31,
    },
    {
        "scene": "closing-value",
        "text": "The result is a clearer starting point for understanding unfamiliar codebases and finding somewhere useful to contribute.",
        "pause": 0.40,
    },
    {
        "scene": "ending",
        "text": "RepoWorld. The City of Code. Created by Shubhaang Kataruka. Explore it live, or discover the source on GitHub.",
        "pause": 0.22,
    },
]


def trim_edge_silence(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Remove only excessive digital lead/tail while keeping natural sentence releases."""
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if not samples.size:
        raise ValueError("Model produced empty audio")
    power = np.abs(samples)
    active = np.flatnonzero(power > 0.0020)
    if active.size == 0:
        raise ValueError("Model produced silence")
    lead = int(sample_rate * 0.055)
    tail = int(sample_rate * 0.12)
    start = max(0, int(active[0]) - lead)
    stop = min(len(samples), int(active[-1]) + tail + 1)
    return samples[start:stop]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--voices", required=True)
    parser.add_argument("--output", default="evidence/demo-narration")
    parser.add_argument("--voice", default="am_michael")
    args = parser.parse_args()

    from kokoro_onnx import Kokoro

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(args.model, args.voices)
    available = set(kokoro.get_voices())
    if args.voice not in available:
        raise RuntimeError(f"Selected voice {args.voice} absent from model voice list")
    rate = None
    pcm = []
    cue_sheet = []
    cursor = 0
    try:
        for idx, beat in enumerate(BEATS, start=1):
            audio, sr = kokoro.create(
                beat["text"], voice=args.voice, speed=0.98, lang="en-us"
            )
            if rate is None:
                rate = sr
            if sr != rate:
                raise RuntimeError("Unexpected sample rate changed between phrases")
            audio = trim_edge_silence(audio, sr)
            if not np.isfinite(audio).all():
                raise RuntimeError("Audio contains invalid samples")
            peak = float(np.max(np.abs(audio)))
            if peak > 1.0:
                audio = audio / (peak + 0.01)
            beat_file = output / f"phrase-{idx:02d}.wav"
            sf.write(beat_file, audio, sr, subtype="PCM_24")
            beginning = cursor / sr
            pcm.append(audio)
            cursor += len(audio)
            ending = cursor / sr
            pause_samples = np.zeros(int(round(sr * beat["pause"])), dtype=np.float32)
            pcm.append(pause_samples)
            cursor += len(pause_samples)
            cue_sheet.append({
                "index": idx,
                "scene": beat["scene"],
                "text": beat["text"],
                "begin": round(beginning, 3),
                "end": round(ending, 3),
                "pause": beat["pause"],
                "duration": round(ending - beginning, 3),
                "file": beat_file.name,
            })
            print(f"PASS phrase {idx:02d} {beat['scene']} duration={ending-beginning:.2f}s", flush=True)
    finally:
        # Works with kokoro-onnx versions where the style archive supports close().
        close = getattr(getattr(kokoro, "voices", None), "close", None)
        if callable(close):
            close()

    output_audio = np.concatenate(pcm).astype(np.float32)
    # Leave a small amount of level headroom before final dialogue mastering.
    true_peak = float(np.max(np.abs(output_audio)))
    if true_peak < 0.025 or not np.isfinite(true_peak):
        raise RuntimeError("Generated narration is anomalously quiet")
    if true_peak > 0.94:
        output_audio *= 0.94 / true_peak

    final = output / "RepoWorld_Natural_Voiceover.wav"
    sf.write(final, output_audio, rate, subtype="PCM_24")
    length = len(output_audio) / rate
    if not (55.0 <= length <= 175.0):
        raise RuntimeError(f"Narration duration {length:.1f}s outside safe expected bounds")
    summary = {
        "title": "RepoWorld: The City of Code",
        "creator": "Shubhaang Kataruka",
        "voice": args.voice,
        "model": "Kokoro 1.0 ONNX (Apache-2.0 open weights)",
        "disclosure": "AI-synthesized voice, not a recording of an actual person",
        "model_api_credits_spent": 0,
        "sample_rate": rate,
        "channels": 1,
        "duration_seconds": round(length, 3),
        "max_abs_peak": round(float(np.max(np.abs(output_audio))), 4),
        "beats": cue_sheet,
    }
    (output / "narration-timeline.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (output / "narration-script.txt").write_text(
        "\n\n".join(x["text"] for x in BEATS), encoding="utf-8"
    )
    print(f"SUCCESS total={length:.2f}s sample_rate={rate} peak={summary['max_abs_peak']}", flush=True)


if __name__ == "__main__":
    main()
