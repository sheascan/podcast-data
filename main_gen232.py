import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1
from dotenv import load_dotenv

load_dotenv()
VERSION_ID = "Gen 232.3 (Heavyweight & Duration Reporting)"

# --- 1. CONFIG & GLOBALS ---
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
IN, ARCH, OUT_BASE = f"{DATA_DIR}/inputs", f"{DATA_DIR}/archive", f"{DATA_DIR}/outputs"
DRY_RUN = os.getenv("DRY_RUN", "False").lower() == "true"
MODEL_ID = os.getenv("MODEL_ID", "gemini-3.1-flash-lite-preview")
MODEL_ID = "gemini-2.5-flash-lite"

NOW = datetime.datetime.now()
TODAY_STR, RUN_ID = NOW.strftime("%d%b"), NOW.strftime("%H%M")
OUT = f"{OUT_BASE}/{TODAY_STR}"

VOICES = [
    "en-GB-SoniaNeural", "en-US-GuyNeural", "en-AU-NatashaNeural", 
    "en-IE-ConnorNeural", "en-GB-RyanNeural", "en-CA-LiamNeural"
]

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def clean_text_for_audio(text):
    text = text.replace('**', '').replace('*', '')
    text = re.sub(r"(\w+)'ve", r"\1 have", text, flags=re.IGNORECASE)
    text = re.sub(r"(\w+)'s", r"\1s", text, flags=re.IGNORECASE) 
    text = re.sub(r"[#_>\-]", " ", text)
    return text.strip()

async def produce_audio(text, path, title, voice_name):
    if DRY_RUN: return True, 0, 0
    clean = clean_text_for_audio(text)
    start_t = time.time()
    try:
        log(f"   🎙️ TTS ({voice_name}): Synthesizing {len(clean)} chars...")
        comm = edge_tts.Communicate(clean, voice_name)
        await asyncio.wait_for(comm.save(path), timeout=600)
        perf = time.time() - start_t
        
        time.sleep(0.5) 
        try:
            try: audio = ID3(path)
            except: audio = ID3()
            audio.add(TIT2(encoding=3, text=title))
            audio.add(TPE1(encoding=3, text=voice_name))
            audio.save(path, v2_version=3)
        except Exception as tag_err:
            log(f"   ⚠️ Tagging bypassed: {tag_err}")

        return True, perf, len(clean)
    except Exception as e:
        log(f"   ⚠️ TTS Error: {e}"); return False, 0, 0

async def main():
    print("="*60)
    log(f"🚀 {VERSION_ID}")
    log(f"🤖 {MODEL_ID} | 📂 {DATA_DIR}")
    print("="*60)

    for d in [OUT, f"{ARCH}/{TODAY_STR}", IN]: os.makedirs(d, exist_ok=True)
    
    files = [f for f in os.listdir(IN) if f.endswith(('.eml', '.txt'))]
    if not files: 
        log("🛑 No input files. Exiting."); return
        
    all_stories = []
    for f in files:
        with open(f"{IN}/{f}", 'rb') as em:
            msg = email.message_from_binary_file(em, policy=email.policy.default)
            body = msg.get_body(preferencelist=('html', 'plain'))
            if body:
                soup = BeautifulSoup(body.get_content(), "html.parser")
                for a in soup.find_all('a', href=True):
                    txt = a.get_text(strip=True)
                    if len(txt) > 25: all_stories.append({"headline": txt, "url": a['href']})

    log(f"📊 HARVEST: {len(files)} files | {len(all_stories)} URLs found.")

    # --- STEP 2: THEMATIC EDITORIAL ---
    log(f"🧠 EDITORIAL: Asking Gemini to theme and group stories...")
    catalog = "\n".join([f"{i}: {s['headline']}" for i, s in enumerate(all_stories)])
    
    editor_prompt = (
        f"Group these {len(all_stories)} headlines into logical segments by THEME. "
        "CONSTRAINTS: 1) Max 8 stories per segment. 2) Filter out 'Fragmented' or 'Ambiguous' links. "
        "3) Prioritize actual news, finance, tech, and sport. "
        f"Headlines:\n{catalog}\n\n"
        "Return JSON list: [{'segment_title': '...', 'story_indices': [indices]}]"
    )

    try:
        res = client.models.generate_content(
            model=MODEL_ID, contents=editor_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        clusters = json.loads(res.text)
        
        print("\n" + "="*40)
        print(f"🎬 PRODUCTION MAP ({len(clusters)} Segments)")
        print("-"*40)
        for idx, group in enumerate(clusters):
            print(f" {idx+1}. [{len(group['story_indices'])} Stories] -> {group['segment_title']}")
        print("="*40 + "\n")
    except Exception as e:
        log(f"❌ Editorial Failed: {e}"); return

    # --- STEP 3: THEMATIC PRODUCTION ---
    for idx, group in enumerate(clusters):
        seg_stories = [all_stories[i] for i in group['story_indices'] if i < len(all_stories)]
        if not seg_stories: continue
        
        voice = VOICES[idx % len(VOICES)]
        topic_theme = group['segment_title']
        headlines_text = "\n".join([s['headline'] for s in seg_stories])

        log(f"📑 SEGMENT {idx+1}: Theme '{topic_theme}' ({len(seg_stories)} stories)")

        prompt = (
            f"The theme is {topic_theme}. Write a LONG, detailed conversational "
            f"podcast script (approx 1500 words). Deep dive into these headlines:\n{headlines_text}\n\n"
            "Return JSON: {'title': 'Punchy Title', 'script': 'Full Script Content'}"
        )

        try:
            res = client.models.generate_content(
                model=MODEL_ID, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = json.loads(res.text)
            title, script = data.get('title', topic_theme), data.get('script', "")
        except Exception as e:
            log(f"❌ Gemini Scripting Error: {e}"); break

        fname = f"{TODAY_STR}_{RUN_ID}_{idx:02d}.mp3"
        fpath = f"{OUT}/{fname}"
        
        ok, perf, chars = await produce_audio(script, fpath, title, voice)

        if ok:
            # Estimate duration (900 chars per min)
            est_min = chars / 900
            log(f"   ⏱️ TTS Runtime: {perf:.1f}s | Chars: {chars} | Est. Duration: {est_min:.1f} min")
            
            # --- SMART APPEND LOGIC ---
            new_item = {"theme": title, "mp3": fname, "voice": voice, "stories": seg_stories, "duration": round(est_min,1)}
            manifest_path = f"{OUT}/manifest.json"
            current_manifest = []
            
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as f:
                    try: current_manifest = json.load(f)
                    except: current_manifest = []
            
            current_manifest.append(new_item)
            with open(manifest_path, "w") as f:
                json.dump(current_manifest, f, indent=4)

    # --- STEP 4: CLEANUP ---
    for f in files: 
        shutil.move(f"{IN}/{f}", f"{ARCH}/{TODAY_STR}/{f}")
    
    log(f"✅ COMPLETE. All systems synced.")

if __name__ == "__main__":
    asyncio.run(main())