import os, json, datetime

PROJECT_DIR = os.path.expanduser("~/podcast_studio")
DATA_DIR = os.path.expanduser("~/podcast_data")
BASE_URL = "https://sheascan.github.io/my-daily-briefing"
RSS_OUTPUT = os.path.join(PROJECT_DIR, "briefing_2.xml")

def generate_rss():
    date_folder = datetime.datetime.now().strftime("%d%b")
    manifest_path = os.path.join(DATA_DIR, "outputs", date_folder, "manifest.json")

    if not os.path.exists(manifest_path): return

    with open(manifest_path, 'r') as f:
        segments = json.load(f)

    rss_items = ""
    for segment in segments:
        title = segment.get('theme', 'Daily Update')
        audio_filename = segment.get('mp3')
        voice = segment.get('voice', 'Emily')
        
        # Build HTML Show Notes for Links
        html_desc = f"<p><strong>Presenter:</strong> {voice}</p><ul>"
        for story in segment.get('stories', []):
            html_desc += f"<li><a href='{story.get('url', '#')}'>{story.get('headline', 'Link')}</a></li>"
        html_desc += "</ul>"

        audio_url = f"{BASE_URL}/outputs/{date_folder}/{audio_filename}"
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

        rss_items += f"""
    <item>
      <title>{title}</title>
      <description><![CDATA[{html_desc}]]></description>
      <enclosure url="{audio_url}" type="audio/mpeg" length="0" />
      <guid isPermaLink="false">{audio_filename}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:author>{voice}</itunes:author>
    </item>"""

    full_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>My Daily Briefing</title>
    <link>{BASE_URL}</link>
    <itunes:author>Emily & Guy</itunes:author>
{rss_items}
  </channel>
</rss>"""

    with open(RSS_OUTPUT, "w") as f: f.write(full_xml.strip())
    print(f"🚀 SUCCESS: Feed with links updated at {RSS_OUTPUT}")

if __name__ == "__main__": generate_rss()