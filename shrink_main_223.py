import os, sys, json, asyncio, edge_tts, re, datetime, shutil, email, email.policy, time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from mutagen.id3 import ID3, TIT2, TPE1, COMM

# --- Setup & Config ---
VERSION = "Gen 223.2 (Optimized)"
BASE = os.path.expanduser("~/podcast_studio/data")
IN, ARCH, OUT = f"{BASE}/inputs", f"{BASE}/archive", f"{BASE}/outputs/{datetime.datetime.now().strftime('%d%b')}"
for d in [IN, ARCH, OUT]: os.makedirs(d, exist_ok=True)
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

def log(m): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {m}")

def get_stories(html):
    soup, stories, seen = BeautifulSoup(html, "html.parser"), [], set()
    junk = {'facebook', 'twitter', 'instagram', 'linkedin', 'unsubscribe', 'view', 'privacy'}
    for a in soup.find_all('a', href=True):
        txt, url = a.get_text(strip=True), a['href']
        if len(txt) > 20 and not any(j in url.lower() or j in txt.lower() for j in junk):
            if txt.lower() not in seen:
                stories.append({"headline": txt, "url": url}); seen.add(txt.lower())
    return stories

async def tts_with_meta(text, path, title, stories):
    clean = re.sub(r'[^\x00-\x7F]+', ' ', text)
    notes = f"Episode: {title}\nSOURCES:\n" + "\n".join([f"• {s['headline']}\n  {s['url']}" for s in stories])
    for i in range(3):
        try:
            comm = edge_tts.Communicate(clean, "en-GB-SoniaNeural")
            await asyncio.wait_for(comm.save(path), timeout=600)
            tag = ID3(path); tag.add(TIT2(encoding=3, text=title))
            tag.add(TPE1(encoding=3, text="Alice & Bob")); tag.add(COMM(encoding=3, lang='eng', desc='desc', text=[notes]))
            tag.save(path); return True
        except Exception as e: log(f"Retry {i+1} due to: {e}"); await asyncio.sleep(10)
    return False

def draft(topic, stories):
    log(f"🧠 Drafting: {topic} ({len(stories)} stories)")
    prompt = f"Write a 6,000-word tech dialogue (Alice & Bob) about {topic}. Depth: Architect Alice, Critic Bob. Stories:\n" + "\n".join([f"- {s['headline']}" for s in stories])
    cfg = types.GenerateContentConfig(max_output_tokens=8192, temperature=0.7)
    return client.models.generate_content(model="gemini-3.1-flash-lite-preview", contents=prompt, config=cfg).text.strip()

async def main():
    log(f"🎬 {VERSION}"); files = [f for f in os.listdir(IN) if f.endswith(('.eml', '.txt'))]
    if not files: return
    
    data = []
    for f in files:
        with open(f"{IN}/{f}", 'rb') as em:
            msg = email.message_from_binary_file(em, policy=email.policy.default)
            data.extend(get_stories(msg.get_body(preferencelist=('html', 'plain')).get_content()))
    
    log(f"📊 {len(data)} headlines found. Clustering...")
    sumry = "\n".join([f"ID:{i} | {s['headline']}" for i, s in enumerate(data)])
    prompt = f"Group into episodes (MAX 10 stories each). Return JSON: [{{'topic': '...', 'indices': [int...]}}]\n\n{sumry}"
    ep_res = client.models.generate_content(model="gemini-3.1-flash-lite-preview", contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
    episodes = json.loads(ep_res.text.strip().replace("```json", "").replace("```", ""))

    for i, ep in enumerate(episodes):
        fname, segs = f"{OUT}/{OUT.split('/')[-1]}_{i:02d}.mp3", [data[idx] for idx in ep['indices'] if idx < len(data)]
        log(f"🚀 Episode {i+1}: {ep['topic']}"); script = draft(ep['topic'], segs)
        await tts_with_meta(script, fname, ep['topic'], segs); await asyncio.sleep(5)

    os.makedirs(f"{ARCH}/{OUT.split('/')[-1]}", exist_ok=True)
    for f in files: shutil.move(f"{IN}/{f}", f"{ARCH}/{OUT.split('/')[-1]}/{f}")
    log("✅ COMPLETE.")

if __name__ == "__main__": asyncio.run(main())