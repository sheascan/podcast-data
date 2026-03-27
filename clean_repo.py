import os, time, shutil

# Path to your outputs
OUTPUTS_DIR = os.path.expanduser("~/podcast_data/outputs")
DAYS_TO_KEEP = 7
seconds_in_day = 86400

now = time.time()

for folder in os.listdir(OUTPUTS_DIR):
    folder_path = os.path.join(OUTPUTS_DIR, folder)
    if os.path.isdir(folder_path):
        # Check folder age
        if os.stat(folder_path).st_mtime < now - (DAYS_TO_KEEP * seconds_in_day):
            print(f"🧹 Archiving old production: {folder}")
            # Move to a non-git 'long_term_archive' or just delete
            shutil.rmtree(folder_path)