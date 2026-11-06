"""Produce a conversational, natural British-English narration with local Kokoro open weights."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import soundfile as sf

BEATS = [
 ("opening", "RepoWorld. The City of Code. A project by Shubhaang Kataruka."),
 ("problem", "When you open an unfamiliar GitHub repository, finding where to begin is often the hardest part. Hundreds of files, dependencies, and open issues can hide the bigger picture."),
 ("city-overview", "RepoWorld changes that. Paste a public repository, and it becomes an interactive three-dimensional city. Districts group related code, while buildings represent real indexed modules."),
 ("links", "Explore the districts and switch between city views. The connections you see come from sampled static imports. They're clues to the structure, not claims about live execution."),
 ("module", "Click a building, and you can inspect its source paths, file counts, and observed connections, without leaving the map."),
 ("source-evidence", "You can also look deeper into the indexed files, so the visualization always leads back to actual source."),
 ("find-code", "Need to locate a feature? Find Code searches the imported module and file names, then shows you where to start investigating."),
 ("issues", "Issue Radar brings open GitHub issues into context. It separates direct references from suggestions, and keeps an issue unplaced when the evidence isn't strong enough."),
 ("issue-details", "Open any reported issue to read the original report and inspect the available source evidence. No unverified bug or fix is passed off as a confirmed result."),
 ("assistant", "The Developer Console includes an optional BharatCode assistant for source-scoped guidance when inference is available. When it isn't, RepoWorld clearly labels its local fallback."),
 ("portability", "No account is required. You can even save a sanitized public city map for offline exploration."),
 ("closing", "RepoWorld makes complex codebases easier to explore, understand, and contribute to. I'm Shubhaang Kataruka. Explore the City of Code."),
]
PAUSES = [.30,.30,.32,.28,.28,.24,.30,.32,.30,.28,.26,.35]

def trim(samples, rate):
    arr=np.asarray(samples,dtype=np.float32).reshape(-1)
    nonzero=np.flatnonzero(abs(arr)>.0015)
    if not nonzero.size: raise ValueError("Empty speech")
    return arr[max(0,int(nonzero[0]) - int(.07*rate)):min(arr.size,int(nonzero[-1])+int(.13*rate))]

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--voices",required=True)
    parser.add_argument("--out",default="evidence/demo-voice")
    args=parser.parse_args()
    from kokoro_onnx import Kokoro
    synth=Kokoro(args.model,args.voices)
    voice="bm_fable" # natural British male; professional, warm product-narration delivery.
    allowed=set(synth.get_voices())
    if voice not in allowed:
        raise RuntimeError("Desired British voice is not in downloaded Kokoro voice library")
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True)
    sr=None
    tracks=[]
    cues=[]
    cursor=0
    for i,(scene,text) in enumerate(BEATS):
        wav,rate=synth.create(text,voice=voice,speed=1.04,lang="en-gb")
        if sr is None:sr=rate
        if sr!=rate:raise RuntimeError("Rate changed")
        wav=trim(wav,rate)
        if not np.all(np.isfinite(wav)):raise RuntimeError("Bad audio")
        peak=np.max(np.abs(wav))
        if peak>.95:wav*=.92/peak
        start=cursor/rate
        sf.write(folder/f"voice-{i+1:02d}-{scene}.wav",wav,rate,subtype="PCM_24")
        tracks.append(wav);cursor+=len(wav)
        end=cursor/rate
        gap=np.zeros(round(PAUSES[i]*rate),dtype=np.float32)
        tracks.append(gap);cursor+=len(gap)
        cues.append({"scene":scene,"text":text,"start_s":round(start,3),"end_s":round(end,3),"duration_s":round(end-start,3),"pause_s":PAUSES[i],"file":f"voice-{i+1:02d}-{scene}.wav"})
        print(f"PASS VOICE {i+1:02d} {scene} duration={end-start:.2f}s",flush=True)
    total=np.concatenate(tracks)
    if np.max(np.abs(total))>.94:total*=.94/np.max(np.abs(total))
    if not (65 < len(total)/rate < 160):raise ValueError("Unexpected narration length")
    sf.write(folder/"RepoWorld_Conversational_British_Narration.wav",total,rate,subtype="PCM_24")
    meta={"voice":voice,"lang":"en-gb","model":"Kokoro-onnx (Apache-2.0 open weights)","synthetic_voice":True,
          "credits":0,"sample_rate":rate,"duration_s":round(len(total)/rate,3),"cues":cues}
    (folder/"voice-timeline.json").write_text(json.dumps(meta,indent=2),encoding="utf8")
    (folder/"narration-script.txt").write_text("\n\n".join(t for _,t in BEATS),encoding="utf8")
    print("PASS final natural narration",meta["duration_s"],"seconds",flush=True)

if __name__=="__main__":main()
