import os, subprocess, datetime

STUDIO_DIR = os.path.expanduser("~/podcast_studio")
DATA_DIR = os.path.expanduser("~/podcast_data")

def sync(path, msg):
    print(f"📦 Syncing: {path}")
    os.chdir(path)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg, "--allow-empty"], capture_output=True)
    subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)

if __name__ == "__main__":
    ts = datetime.datetime.now().strftime('%d %b %H:%M')
    sync(DATA_DIR, f"Gen 230 Assets: {ts}")
    sync(STUDIO_DIR, f"Gen 230 Feed Update: {ts}")
    print("✅ All systems synced.")