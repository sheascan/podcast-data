import subprocess
import os
import sys
from datetime import datetime

# --- CONFIGURATION ---
SCRIPT_1_HARVEST = "email_harvest.py"
SCRIPT_2_PRODUCE = "main.py"
SCRIPT_3_FEED    = "gen_feed.py"      # <--- NEW: Updates the briefing.xml
SCRIPT_4_DEPLOY  = "deploy_github.py"

def run_step(script_name, step_name):
    print(f"\n▶️  STARTING STEP: {step_name} ({script_name})...")
    if not os.path.exists(script_name):
        print(f"❌ ERROR: File '{script_name}' not found.")
        return False
    try:
        subprocess.run([sys.executable, script_name], check=True)
        print(f"✅ {step_name} COMPLETE.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {step_name} FAILED (Exit Code {e.returncode})")
        return False

def run_production_pipeline():
    start_time = datetime.now()
    print("="*60)
    print(f"🎬 PRODUCTION STARTED: {start_time.strftime('%H:%M:%S')}")
    print("="*60)

    if not run_step(SCRIPT_1_HARVEST, "Email Harvesting"): return
    if not run_step(SCRIPT_2_PRODUCE, "AI Production"): return
    if not run_step(SCRIPT_3_FEED, "RSS Feed Generation"): return # Bridges AI to Web
    if not run_step(SCRIPT_4_DEPLOY, "GitHub Deployment"): return

    duration = datetime.now() - start_time
    print(f"\n🎉 SUCCESS! Total Run Time: {duration}")

if __name__ == "__main__":
    run_production_pipeline()