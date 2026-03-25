import os, json, email, email.policy, re, datetime
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()

# Universal Vault Resolution
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
INPUT_DIR = f"{DATA_DIR}/inputs"
OUTPUT_DIR = f"{DATA_DIR}/outputs"
ARCHIVE_DIR = f"{DATA_DIR}/archive"

# --- CONFIG ---
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)
# INPUT_DIR = os.path.expanduser("~/podcast_studio/data/inputs")
# Change to archive if you've already moved files:
# INPUT_DIR = os.path.expanduser("~/podcast_studio/data/archive/20Mar")

def get_editorial_stories(html_content):
    """Filters trackers and returns only headlines > 20 chars."""
    soup = BeautifulSoup(html_content, "html.parser")
    stories = []
    seen = set()
    junk = {'facebook', 'twitter', 'instagram', 'linkedin', 'unsubscribe', 'privacy', 'terms', 'view in browser'}
    
    for a in soup.find_all('a', href=True):
        headline = a.get_text(strip=True)
        url = a['href']
        # Filter for actual headlines (Editorial usually has substantial text)
        if len(headline) > 20 and not any(j in url.lower() or j in headline.lower() for j in junk):
            if headline.lower() not in seen:
                stories.append({"headline": headline, "url": url})
                seen.add(headline.lower())
    return stories

def main():
    print(f"--- 🕵️ GEN 223.1 PRE-FLIGHT AUDIT ---")
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.eml', '.txt'))]
    if not files:
        print("📭 No files found in inputs. Check archive or harvest.")
        return

    all_stories = []
    for f in files:
        with open(os.path.join(INPUT_DIR, f), 'rb') as em:
            msg = email.message_from_binary_file(em, policy=email.policy.default)
            body = msg.get_body(preferencelist=('html', 'plain'))
            if body:
                stories = get_editorial_stories(body.get_content())
                all_stories.extend(stories)

    print(f"✅ Filtered {len(all_stories)} Editorial Stories from raw noise.")

    # Clustering without script generation
    summary = "\n".join([f"ID:{i} | {s['headline']}" for i, s in enumerate(all_stories)])
    prompt = f"""
    Group these {len(all_stories)} headlines into podcast episodes.
    STRICT LIMIT: Max 10 distinct topics/stories per episode.
    Group closely related stories into one 'Topic'.
    Return ONLY JSON: [{{"episode": 1, "topic": "Name", "stories": ["Headline 1", "Headline 2"]}}]
    
    DATA:
    {summary}
    """
    
    print("📂 AI is clustering headlines into episodes...")
    res = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview", 
        contents=prompt, 
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    episodes = json.loads(res.text.strip().replace("```json", "").replace("```", ""))

    print("\n--- 📋 PROPOSED PRODUCTION PLAN ---")
    for ep in episodes:
        print(f"\n🎧 EPISODE {ep['episode']}: {ep['topic']}")
        for i, s in enumerate(ep['stories']):
            print(f"   {i+1}. {s}")
    
    print("\n--- AUDIT COMPLETE ---")

if __name__ == "__main__":
    main()