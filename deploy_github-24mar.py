import os
import subprocess
from datetime import datetime

# Define both critical paths
STUDIO_DIR = os.path.expanduser("~/podcast_studio")
DATA_DIR = os.path.expanduser("~/podcast_data")

def sync_repo(repo_path, commit_msg):
    """Syncs a specific repository folder with GitHub."""
    if not os.path.exists(repo_path):
        print(f"⚠️ Warning: Path {repo_path} not found.")
        return
    
    print(f"🚀 Syncing Repository: {repo_path}")
    os.chdir(repo_path)
    
    # 1. Stage everything (XML, MP3s, and Dashboard files)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", commit_msg, "--allow-empty"], capture_output=True)

    # 2. Pull with Rebase (Handles Pipedream news updates without mess)
    subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True)

    # 3. Push to the cloud
    subprocess.run(["git", "push", "origin", "main"], check=True)

if __name__ == "__main__":
    now_str = datetime.now().strftime('%d %b %H:%M')
    
    # Sync Audio Assets first
    sync_repo(DATA_DIR, f"Production Assets: {now_str}")
    
    # Sync RSS Feed & Web Dashboard second
    sync_repo(STUDIO_DIR, f"Feed & Dashboard Update: {now_str}")
    
    print(f"✅ SUCCESS: All systems synced at {now_str}")