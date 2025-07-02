import re
import string

def clean_text(text):
    # Convert to lowercase
    text = text.lower()

    # Replace hyphens/dashes with space
    text = text.replace("-", " ")

    # Remove all punctuation using regex
    text = re.sub(rf"[{re.escape(string.punctuation)}]", "", text)

    # Normalize extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text

def contains_keywords(text, keywords):
    return any(kw in text for kw in keywords)

def classify_intent(user_input):
    input_clean = clean_text(user_input)

    power_theft_keywords = [
        "power theft", "stealing electricity", "electricity theft", "illegal connection",
        "unauthorized connection", "tampering", "meter bypass", "energy theft", "hooking",
        "unbilled", "tapping", "fraudulent", "pilferage", "bypass the meter", "bypassed the meter",
        "bypassing meter", "bypass meter"
    ]

    load_change_keywords = [
        "load change", "increase load", "decrease load", "reduce sanctioned load",
        "enhance capacity", "upgrade load", "lower load", "modify load", "adjust load", "load enhancement",

    ]

    new_connection_keywords = [
        "new connection", "apply for connection", "fresh connection", "get a meter",
        "power connection request", "request new line", "electricity application",
        "install new line", "new line installation", "connection for new house"
    ]

    power_outage_keywords = [
        "power outage", "no electricity", "power cut", "blackout", "power failure",
        "electricity gone", "current gone", "trip", "supply down", "no power"
    ]

    if contains_keywords(input_clean, power_theft_keywords):
        return "power_theft"
    elif contains_keywords(input_clean, load_change_keywords):
        return "load_change"
    elif contains_keywords(input_clean, new_connection_keywords):
        return "new_connection"
    elif contains_keywords(input_clean, power_outage_keywords):
        return "power_outage"
    else:
        return "unknown"
