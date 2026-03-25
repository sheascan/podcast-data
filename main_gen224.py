import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1, COMM
from dotenv import load_dotenv

# 1. LOAD CONFIG
load_dotenv()
VERSION_ID = "Gen 224.3 (Vault Edition)"

# 2. PATHS (Pointing to the Vault)
PROJECT_DIR = os.path.expanduser(os.getenv("PROJECT_DIR", "~/podcast_studio"))
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))

IN = f"{DATA_DIR}/inputs"
ARCH = f"{DATA_DIR}/archive"
OUT_BASE = f"{DATA_DIR}/outputs"

# 3. THE DRY RUN FIX (Ensures 'False' string isn't treated as True)
DRY_RUN = os.getenv("DRY_RUN", "False").lower() == "true"

# 4. RUN METADATA
NOW = datetime.datetime.now()
TODAY_STR, RUN_ID = NOW.strftime("%d%b"), NOW.strftime("%H%M")
OUT = f"{OUT_BASE}/{TODAY_STR}"

# Create Vault structure if missing
for d in [OUT, ARCH, IN]: os.makedirs(d, exist_ok=True)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_ID = os.getenv("MODEL_ID", "gemini-3.1-flash-lite-preview")

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

async def produce_audio(text, path, title, stories):
    # This is the "Guardian" that stops the TTS during Dry Run
    if DRY_RUN:
        log(f"   🌵 [DRY RUN] Skipping TTS synthesis for: {title}")
        return True
    
    clean = re.sub(r'[^\x00-\x7F]+', ' ', text)
    notes = f"Ep: {title}\nSOURCES:\n" + "\n".join([f"• {s['headline']}\n  {s['url']}" for s in stories])
    
    try:
        log(f"   🎙️ TTS: Synthesizing {len(text)} chars...")
        comm = edge_tts.Communicate(clean, os.getenv("VOICE_NAME", "en-GB-SoniaNeural"))
        await asyncio.wait_for(comm.save(path), timeout=600) # 10-min safety
        
        audio = ID3(path) if os.path.exists(path) else ID3()
        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text="Alice & Bob"))
        audio.add(COMM(encoding=3, lang='eng', desc='desc', text=[notes]))
        audio.save(path, v2_version=3)
        return True
    except Exception as e:
        log(f"   ⚠️ TTS Failed: {e}")
        return False

async def main():
    log(f"🎬 Starting {VERSION_ID} " + ("(DRY RUN MODE)" if DRY_RUN else ""))
    
    files = [f for f in os.listdir(IN) if f.endswith(('.eml', '.txt'))]
    if not files:
        log("📭 No new files in Vault 'inputs'. Check email_harvest.py targets.")
        return

    all_stories = []
    for f in files:
        with open(f"{IN}/{f}", 'rb') as em:
            msg = email.message_from_binary_file(em, policy=email.policy.default)
            body = msg.get_body(preferencelist=('html', 'plain'))
            if body: all_stories.extend(get_stories(body.get_content()))
    
    log(f"📊 Clean Harvest: {len(all_stories)} stories. Hard-Binning...")

    LIMIT, index_items = 10, []
    for i in range(0, len(all_stories), LIMIT):
        seg = all_stories[i : i + LIMIT]
        ep_num = (i // LIMIT) + 1
        titles = "\n".join([s['headline'] for s in seg])
        
        # Get a clean title without bullet points
        t_res = client.models.generate_content(
            model=MODEL_ID, 
            contents=f"Provide a single 5-word title for these stories. No bullets. No intro:\n{titles}"
        )
        topic = t_res.text.strip().split('\n')[0].replace('"', '').replace('*', '')
        
        fname = f"{TODAY_STR}_{RUN_ID}_{ep_num-1:02d}.mp3"
        fpath, p_title = f"{OUT}/{fname}", f"EP {ep_num}: {topic}"
        
        log(f"🚀 Episode {ep_num}: {topic}")
        
        if DRY_RUN:
            script = "Dry run: No script generated."
        else:
            prompt = f"Write a 5,000-word tech dialogue (Alice & Bob) about {topic}. Stories:\n{titles}"
            script = client.models.generate_content(
                model=MODEL_ID, 
                contents=prompt, 
                config=types.GenerateContentConfig(max_output_tokens=8192)
            ).text.strip()
        
        if await produce_audio(script, fpath, p_title, seg):
            index_items.append({"topic": topic, "filename": fname, "stories": [s['headline'] for s in seg]})
        
        if not DRY_RUN: 
            log("💤 CPU Cooldown (15s)...")
            await asyncio.sleep(15)

    # Save manifest for gen_feed.py
    with open(f"{OUT}/manifest_{RUN_ID}.json", "w") as f:
        json.dump(index_items, f, indent=4)
    
    if not DRY_RUN:
        arch_sub = f"{ARCH}/{TODAY_STR}"
        os.makedirs(arch_sub, exist_ok=True)
        for f in files: shutil.move(f"{IN}/{f}", f"{arch_sub}/{f}")
        log(f"📦 Inputs archived to {arch_sub}")

    log(f"✅ COMPLETE. Run ID: {RUN_ID}")

if __name__ == "__main__":
    asyncio.run(main())