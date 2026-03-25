import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1, COMM
from dotenv import load_dotenv

load_dotenv()
VERSION_ID = "Gen 230 (Voice & Link Edition)"

DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
IN, ARCH, OUT_BASE = f"{DATA_DIR}/inputs", f"{DATA_DIR}/archive", f"{DATA_DIR}/outputs"
DRY_RUN = os.getenv("DRY_RUN", "False").lower() == "true"
NOW = datetime.datetime.now()
TODAY_STR, RUN_ID = NOW.strftime("%d%b"), NOW.strftime("%H%M")
OUT = f"{OUT_BASE}/{TODAY_STR}"

for d in [OUT, ARCH, IN]: os.makedirs(d, exist_ok=True)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_ID = os.getenv("MODEL_ID", "gemini-2.5-flash-lite")

def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_stories(html):
    soup, stories, seen = BeautifulSoup(html, "html.parser"), [], set()
    junk = {'facebook', 'twitter', 'instagram', 'linkedin', 'unsubscribe', 'privacy'}
    for a in soup.find_all('a', href=True):
        url, txt = a['href'], a.get_text(separator=" ", strip=True)
        if len(txt) > 25 and not any(j in url.lower() or j in txt.lower() for j in junk):
            if txt.lower() not in seen:
                stories.append({"headline": txt, "url": url}); seen.add(txt.lower())
    return stories

async def produce_audio(text, path, title, stories, voice_name):
    if DRY_RUN:
        log(f"   🌵 [DRY RUN] Skipping TTS for: {title}")
        return True
    
    clean = re.sub(r'[^\x00-\x7F]+', ' ', text)
    notes = f"Ep: {title}\nSOURCES:\n" + "\n".join([f"• {s['headline']}\n  {s['url']}" for s in stories])
    
    try:
        log(f"   🎙️ TTS ({voice_name}): Synthesizing {len(text)} chars...")
        comm = edge_tts.Communicate(clean, voice_name)
        await asyncio.wait_for(comm.save(path), timeout=600)
        
        # --- THE FIX STARTS HERE ---
        from mutagen.id3 import ID3, TIT2, TPE1, COMM
        
        # Check if file has tags; if not, create them fresh
        try:
            audio = ID3(path)
        except Exception:
            # This handles the "doesn't start with an ID3 tag" error
            audio = ID3() 
            
        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=voice_name.split('-')[2])) # Sonia or Ryan
        audio.add(COMM(encoding=3, lang='eng', desc='desc', text=[notes]))
        
        # Save explicitly to the path
        audio.save(path, v2_version=3)
        # --- THE FIX ENDS HERE ---
        
        return True
    except Exception as e:
        log(f"   ⚠️ TTS Metadata Failed: {e}")
        # Return True anyway because the audio file WAS likely created 
        # even if the metadata tagging hit a snag.
        return os.path.exists(path)

async def main():
    log(f"🎬 Starting {VERSION_ID}")
    files = [f for f in os.listdir(IN) if f.endswith(('.eml', '.txt'))]
    if not files: return
    all_stories = []
    for f in files:
        with open(f"{IN}/{f}", 'rb') as em:
            msg = email.message_from_binary_file(em, policy=email.policy.default)
            body = msg.get_body(preferencelist=('html', 'plain'))
            if body: all_stories.extend(get_stories(body.get_content()))
    
    index_items = []
    # VOICES: Toggle between Female (Sonia) and Male (Ryan)
    VOICES = ["en-GB-SoniaNeural", "en-GB-RyanNeural"]
    
    for i in range(0, len(all_stories), 10):
        seg = all_stories[i : i + 10]
        ep_idx = i // 10
        voice = VOICES[ep_idx % 2] # Toggle logic
        
        titles = "\n".join([s['headline'] for s in seg])
        t_res = client.models.generate_content(model=MODEL_ID, contents=f"Provide a 5-word title. No bullets: {titles}")
        topic = t_res.text.strip().split('\n')[0].replace('"', '')
        
        fname = f"{TODAY_STR}_{RUN_ID}_{ep_idx:02d}.mp3"
        fpath = f"{OUT}/{fname}"
        
        prompt = f"Write a 1,500-word deep dive script about {topic}. Stories: {titles}"
        script = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
        
        if await produce_audio(script, fpath, topic, seg, voice):
            index_items.append({
                "theme": topic, 
                "mp3": fname, 
                "voice": voice.split('-')[2],
                "stories": seg # Now including URLs for the feed
            })
        await asyncio.sleep(5)

    with open(f"{OUT}/manifest.json", "w") as f: # Fixed filename for easier discovery
        json.dump(index_items, f, indent=4)
    
    arch_sub = f"{ARCH}/{TODAY_STR}"
    os.makedirs(arch_sub, exist_ok=True)
    for f in files: shutil.move(f"{IN}/{f}", f"{arch_sub}/{f}")
    log(f"✅ COMPLETE. Manifest saved to {OUT}/manifest.json")

if __name__ == "__main__": asyncio.run(main())