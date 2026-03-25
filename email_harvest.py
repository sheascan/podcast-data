import imaplib
import email
import os
import datetime
from email.header import decode_header
from dotenv import load_dotenv
load_dotenv()

# Universal Vault Resolution
DATA_DIR = os.path.expanduser(os.getenv("DATA_DIR", "~/podcast_data"))
INPUT_DIR = f"{DATA_DIR}/inputs"
OUTPUT_DIR = f"{DATA_DIR}/outputs"
ARCHIVE_DIR = f"{DATA_DIR}/archive"

# --- CONFIGURATION ---
IMAP_SERVER = "imap.gmail.com"
EMAIL_USER = "mike.mcconigley@gmail.com"
EMAIL_PASS = "rizj dfcd hywm pflx" 

# WHERE TO SAVE
SAVE_DIR = INPUT_DIR
# ARCHIVE SETTINGS
DESTINATION_LABEL = "A_podcast_Studio" 

# TARGET LIST
TARGETS = [
    {"sender": "info@editorial.theguardian.com", "subject": None},
    {"sender": "newsletters@theguardian.com", "subject": "First Edition"},
    {"sender": "nytdirect@nytimes.com", "subject": "The World:"}, 
    {"sender": "techpresso@dupple.com", "subject": None},   
    {"sender": "@comms.irishtimes.com", "subject": None},
    # {"sender": "irishtimesinsidepolitics@comms.irishtimes.com", "subject": None},
    # {"sender": "irishtimesmorningbriefing@comms.irishtimes.com", "subject": None},
    # {"sender": "irishtimessportsbriefing@comms.irishtimes.com","subject": None},
    # {"sender": "onthemoneytheirishtimes@comms.irishtimes.com","subject": None},
    {"sender": "newsletter@news.metro.co.uk","subject":None},
    # {"sender": "@news.theregister.co.uk","subject":None},
    {"sender": "@news.theregister.co","subject":None},
    {"sender": "nytdirect@nytimes.com","subject":None},
    {"sender": "newsletter@givemesport.com","subject":None},
    {"sender": "thecounterrucktheirishtimes@comms.irishtimes.com","subject":None},
    {"sender": "newsletter@unitedinfocus.com","subject":None},
]

def clean_filename(subject):
    return "".join(c if c.isalnum() else "_" for c in subject)[:50]

def fetch_emails():
    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)

    # Connect
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")
        
        # 1. ROBUST LABEL CREATION
        # We try to create it and print the result so we aren't flying blind.
        try:
            status, response = mail.create(DESTINATION_LABEL)
            if status == 'OK':
                print(f"   ✅ Created new label/folder: '{DESTINATION_LABEL}'")
            else:
                # If status is NO, it usually means it exists, which is fine.
                print(f"   ℹ️  Label check: '{DESTINATION_LABEL}' (Status: {status})")
        except imaplib.IMAP4.error as e:
            # Only ignore 'already exists' errors
            if "exists" in str(e).lower() or "existing" in str(e).lower():
                print(f"   ℹ️  Label '{DESTINATION_LABEL}' already exists.")
            else:
                print(f"   ⚠️  CRITICAL: Could not create label '{DESTINATION_LABEL}': {e}")
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    today = datetime.datetime.now().strftime("%d-%b-%Y")
    print(f"📨 Scanning Inbox for {today}...")

    for target in TARGETS:
        # Searching for emails 'SINCE' yesterday
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
        
        query = f'(SINCE "{yesterday}" FROM "{target["sender"]}")'
        status, messages = mail.search(None, query)
        
        if status != "OK": continue
        
        email_ids = messages[0].split()
        if email_ids:
            print(f"   -> Found {len(email_ids)} emails from {target['sender']}")

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # Filter by subject if required
                    if target["subject"] and target["subject"].lower() not in subject.lower():
                        continue

                    # Save File
                    safe_sub = clean_filename(subject)
                    filename = f"{today}_{safe_sub}.eml"
                    filepath = os.path.join(SAVE_DIR, filename)
                    
                    try:
                        with open(filepath, "wb") as f:
                            f.write(response_part[1])
                        print(f"      ✅ Saved: {filename}")
                        
                        # 2. DEBUGGED ARCHIVE LOGIC
                        copy_res = mail.copy(e_id, DESTINATION_LABEL)
                        
                        if copy_res[0] == 'OK':
                            # Mark original as Deleted
                            mail.store(e_id, '+FLAGS', '\\Deleted')
                            print(f"      📦 Archived to '{DESTINATION_LABEL}'")
                        else:
                            # PRINT THE ERROR so we know why it failed
                            print(f"      ⚠️ Failed to label. Server Response: {copy_res}")

                    except Exception as e:
                        print(f"      ❌ Error processing email: {e}")

    # 3. Final Cleanup
    mail.expunge()
    mail.close()
    mail.logout()

if __name__ == "__main__":
    fetch_emails()