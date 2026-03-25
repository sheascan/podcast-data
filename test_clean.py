import re

def clean_text_for_audio(text):
    # The Gen 231.7 Logic
    text = text.replace('**', '').replace('*', '')
    text = re.sub(r"(\w+)'ve", r"\1 have", text, flags=re.IGNORECASE)
    text = re.sub(r"(\w+)'s", r"\1s", text, flags=re.IGNORECASE) 
    text = re.sub(r"[#_>\-]", " ", text)
    return text.strip()

# Test Cases
sample = "**Bob** says: we've got a #new-topic! *Asterisks* are gone."
print(f"ORIGINAL: {sample}")
print(f"CLEANED:  {clean_text_for_audio(sample)}")