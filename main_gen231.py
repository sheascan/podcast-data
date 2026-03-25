import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1, COMM
from dotenv import load_dotenv

load_dotenv()
VERSION_ID = "Gen 231.7 (Auto-Archive & Quota Guard)"

# --- CONFIG & GLOBALS ---
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
IN, ARCH, OUT_BASE = f"{DATA_DIR}/inputs", f"{DATA_DIR}/archive", f"{DATA_DIR}/outputs"
DRY_RUN = os.getenv("DRY_RUN", "False").lower() == "true"
MODEL_ID = os.getenv("MODEL_ID", "gemini-2.0-flash")
NOW = datetime.datetime.now()
TODAY_STR, RUN_ID = NOW.strftime("%d%b"), NOW.strftime("%H%M")
OUT = f"{OUT_BASE}/{TODAY_STR}"

# Global Voice Library (Alternating Global Accents)
VOICES = [
    "en-GB-SoniaNeural", "en-US-GuyNeural", "en-AU-NatashaNeural", 
    "en-IE-ConnorNeural", "en-GB-RyanNeural", "en-CA-LiamNeural"
]

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def clean_text_for_audio(text):
    """Fixes 'we v e', strips asterisks, and removes markdown artifacts."""
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
        
        # IMPROVED ID3 LOGIC: Handle fresh files safely
        try:
            from mutagen.id3 import ID3, TIT2, TPE1
            # Wait a heartbeat for the OS to finalize the file
            time.sleep(0.5) 
            try:
                audio = ID3(path)
            except Exception:
                audio = ID3() # Create new tags if none exist
            
            audio.add(TIT2(encoding=3, text=title))
            audio.add(TPE1(encoding=3, text=voice_name))
            audio.save(path, v2_version=3)
        except Exception as id3_err:
            log(f"   ⚠️ Tagging Note: {id3_err} (Audio is likely still fine)")
            
        return True, perf, len(clean)
    except Exception as e:
        log(f"   ⚠️ TTS Error: {e}"); return False, 0, 0


async def main():
    # STARTUP TELEMETRY
    print("="*60)
    log(f"🚀 STARTING: {VERSION_ID}")
    log(f"🤖 MODEL:    {MODEL_ID}")
    log(f"📂 DATA DIR: {DATA_DIR}")
    log(f"🔊 VOICES:   {len(VOICES)} in rotation")
    print("="*60)

    # Ensure TODAY'S archive folder exists before we even start
    os.makedirs(f"{ARCH}/{TODAY_STR}", exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    
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

    log(f"📊 HARVEST: {len(files)} files | {len(all_stories)} URLs")
    
    index_items = []
    for i in range(0, len(all_stories), 10):
        seg = all_stories[i : i + 10]
        idx = i // 10
        voice = VOICES[idx % len(VOICES)]
        headlines = "\n".join([s['headline'] for s in seg])

        log(f"📑 SEGMENT {idx+1}: Clustering {len(seg)} items...")

        # SINGLE-CALL JSON (Protects your 20-request daily limit)
        prompt = f"Summarize:\n{headlines}\nReturn JSON: {{'title': '5-word title', 'script': '1500-word script'}}"

        try:
            res = client.models.generate_content(
                model=MODEL_ID, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = json.loads(res.text)
            topic, script = data.get('title'), data.get('script')
        except Exception as e:
            log(f"❌ Gemini Error: {e}"); break

        fname = f"{TODAY_STR}_{RUN_ID}_{idx:02d}.mp3"
        fpath = f"{OUT}/{fname}"
        
        ok, perf, chars = await produce_audio(script, fpath, topic, seg, voice)
        if ok:
            log(f"   ⏱️ TTS: {perf:.1f}s for {chars} chars.")
            index_items.append({"theme": topic, "mp3": fname, "voice": voice, "stories": seg})
            with open(f"{OUT}/manifest.json", "w") as f:
                json.dump(index_items, f, indent=4)

    # Automated Archive Move
    for f in files: 
        shutil.move(f"{IN}/{f}", f"{ARCH}/{TODAY_STR}/{f}")
    
    log(f"✅ COMPLETE. All items archived and secured.")

if __name__ == "__main__": asyncio.run(main())