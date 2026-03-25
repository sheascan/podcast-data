import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1, COMM
from dotenv import load_dotenv

load_dotenv()
VERSION_ID = "Gen 232 (Thematic Clustering & ID3 Fix)"

# --- 1. CONFIG & GLOBALS ---
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
IN, ARCH, OUT_BASE = f"{DATA_DIR}/inputs", f"{DATA_DIR}/archive", f"{DATA_DIR}/outputs"
DRY_RUN = os.getenv("DRY_RUN", "False").lower() == "true"
MODEL_ID = os.getenv("MODEL_ID", "gemini-2.0-flash") # Or your lite preview
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
    """Sanitize text: Expand contractions and strip markdown artifacts."""
    text = text.replace('**', '').replace('*', '')
    text = re.sub(r"(\w+)'ve", r"\1 have", text, flags=re.IGNORECASE)
    text = re.sub(r"(\w+)'s", r"\1s", text, flags=re.IGNORECASE) 
    text = re.sub(r"[#_>\-]", " ", text)
    return text.strip()

async def produce_audio(text, path, title, stories, voice_name):
    if DRY_RUN: return True, 0, 0
    clean = clean_text_for_audio(text)
    start_t = time.time()
    try:
        log(f"   🎙️ TTS ({voice_name}): Synthesizing {len(clean)} chars...")
        comm = edge_tts.Communicate(clean, voice_name)
        await asyncio.wait_for(comm.save(path), timeout=600)
        perf = time.time() - start_t
        
        # Safe ID3 Tagging: Wait briefly for file lock to release
        time.sleep(0.5)
        try:
            try:
                audio = ID3(path)
            except:
                audio = ID3()
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
    log(f"🤖 {MODEL_ID} | 📂 {DATA_DIR} | 🧪 DRY: {DRY_RUN}")
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

# --- 🧠 STEP 2: THEMATIC EDITORIAL (CLUSTERING) ---
    log(f"🧠 EDITORIAL: Asking Gemini to theme and group stories...")
    catalog = "\n".join([f"{i}: {s['headline']}" for i, s in enumerate(all_stories)])
    
    editor_prompt = (
        f"Group these {len(all_stories)} headlines into 3-5 logical segments by THEME. "
        "CONSTRAINT: No single segment should have more than 8 stories. "
        "If a topic is larger, split it into 'Part 1' and 'Part 2'. "
        f"Headlines:\n{catalog}\n\n"
        "Return JSON list: [{'segment_title': '...', 'story_indices': [indices]}]"
    )

    try:
        res = client.models.generate_content(
            model=MODEL_ID, contents=editor_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        clusters = json.loads(res.text)
        
        # --- NEW: PRODUCTION MAP LOGGING ---
        print("\n" + "="*40)
        print(f"🎬 PRODUCTION MAP ({len(clusters)} Segments)")
        print("-"*40)
        for idx, group in enumerate(clusters):
            count = len(group['story_indices'])
            print(f" {idx+1}. [{count} Stories] -> {group['segment_title']}")
        print("="*40 + "\n")
        
    except Exception as e:
        log(f"❌ Editorial Failed: {e}. Falling back to slices."); return

    index_items = []
    
    # --- STEP 3: THEMATIC PRODUCTION ---
    for idx, group in enumerate(clusters):
        # Map indices back to our objects
        seg_stories = [all_stories[i] for i in group['story_indices'] if i < len(all_stories)]
        if not seg_stories: continue
        
        voice = VOICES[idx % len(VOICES)]
        topic_theme = group['segment_title']
        headlines_text = "\n".join([s['headline'] for s in seg_stories])

        log(f"📑 SEGMENT {idx+1}: Theme '{topic_theme}' ({len(seg_stories)} stories)")

        prompt = (
            f"The theme is {topic_theme}. Write a 1500-word conversational briefing script "
            f"for these headlines:\n{headlines_text}\n\n"
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
        
        ok, perf, chars = await produce_audio(script, fpath, title, seg_stories, voice)
        if ok:
            log(f"   ⏱️ TTS Runtime: {perf:.1f}s | Chars: {chars}")
            index_items.append({"theme": title, "mp3": fname, "voice": voice, "stories": seg_stories})
            with open(f"{OUT}/manifest.json", "w") as f:
                json.dump(index_items, f, indent=4)

    # --- STEP 4: CLEANUP ---
    for f in files: 
        shutil.move(f"{IN}/{f}", f"{ARCH}/{TODAY_STR}/{f}")
    log(f"✅ COMPLETE. {len(index_items)} thematic segments secured.")

if __name__ == "__main__": asyncio.run(main())