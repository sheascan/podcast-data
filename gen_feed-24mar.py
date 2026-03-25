import os
import json
from datetime import datetime

# --- CONFIGURATION ---
# Using absolute paths to ensure we hit the "Rightful Home"
PROJECT_DIR = os.path.expanduser("~/podcast_studio")
DATA_DIR = os.path.expanduser("~/podcast_data")
BASE_URL = "https://sheascan.github.io/my-daily-briefing"
RSS_OUTPUT = os.path.join(PROJECT_DIR, "briefing_2.xml")

def generate_rss():
    print(f"📡 Starting Gen 227 RSS Generation...")
    
    # 1. Locate the Manifest (The 287KB file we verified)
    manifest_path = os.path.join(DATA_DIR, "manifest.json")
    date_folder = datetime.now().strftime("%d%b") # e.g., 24Mar

    if not os.path.exists(manifest_path):
        print(f"❌ Error: manifest.json not found at {manifest_path}")
        return

    # 2. Load the Manifest Data
    try:
        with open(manifest_path, 'r') as f:
            segments = json.load(f)
    except Exception as e:
        print(f"❌ Error reading manifest: {e}")
        return

    print(f"✅ Found {len(segments)} segments in manifest.")

    # 3. Build the RSS Items
    rss_items = ""
    for segment in segments:
        # ALIGNMENT FIXES:
        # Match manifest.json keys: 'theme' and 'mp3'
        title = segment.get('theme', 'Daily Update')
        audio_filename = segment.get('mp3') 
        
        # Descriptions live inside the 'stories' list in your new format
        stories = segment.get('stories', [])
        if stories:
            # Take the body of the first story as the podcast description
            description_text = stories[0].get('body', '')[:500]
        else:
            description_text = "Daily briefing segment."

        # Construct the URL pointing to your GitHub Pages path
        audio_url = f"{BASE_URL}/outputs/{date_folder}/{audio_filename}"
        
        # Current time for the pubDate
        pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

        rss_items += f"""
    <item>
      <title>{title}</title>
      <description><![CDATA[{description_text}...]]></description>
      <enclosure url="{audio_url}" type="audio/mpeg" length="0" />
      <guid isPermaLink="false">{audio_filename}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:author>Emily & Guy</itunes:author>
    </item>"""

    # 4. Wrap in RSS Header/Footer
    full_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>My Daily Briefing</title>
    <link>{BASE_URL}</link>
    <language>en-us</language>
    <itunes:author>Emily & Guy</itunes:author>
    <itunes:summary>AI-generated deep dives from your daily news harvest.</itunes:summary>
    <description>Your automated daily news briefing.</description>
{rss_items}
  </channel>
</rss>"""

    # 5. Write to File
    try:
        with open(RSS_OUTPUT, "w", encoding="utf-8") as f:
            f.write(full_xml.strip())
        print(f"🚀 SUCCESS: Feed updated at {RSS_OUTPUT}")
    except Exception as e:
        print(f"❌ Failed to write RSS file: {e}")

if __name__ == "__main__":
    generate_rss()