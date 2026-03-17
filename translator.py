# ============================================================
#  translator.py  —  AI Translation Engine (Groq)
#  Free · Fast · No credit card needed
#  Get key: console.groq.com
# ============================================================

from groq import Groq
import streamlit as st
from config import GROQ_API_KEY, GROQ_MODEL, DOMAINS, TONES

DOMAIN_PROMPTS = {
    "General":
        "You are an expert Bangla-English and English-Bangla translator. "
        "Provide natural, fluent translations preserving the original meaning and style.",
    "Medical":
        "You are a professional medical translator. Translate clinical terms accurately. "
        "When a medical term has no Bangla equivalent, keep it in English with a Bangla explanation in parentheses.",
    "Legal":
        "You are a certified legal translator. Use precise legal terminology. "
        "Preserve the formal structure of legal language. Do not simplify legal terms.",
    "Business":
        "You are a professional business translator. Use appropriate business vocabulary "
        "and maintain a professional tone throughout.",
    "Academic":
        "You are an academic translator. Translate with precision, "
        "preserving technical terminology and scholarly tone.",
    "News":
        "You are a news translator. Translate clearly and accurately. "
        "Preserve proper nouns unless they have standard equivalents. Use active voice.",
    "Casual / SMS":
        "You are a friendly translator for everyday conversations and SMS. "
        "Translate naturally and conversationally. Keep it short and natural.",
}

TONE_INSTRUCTIONS = {
    "Formal":       "Use formal, polite language appropriate for official communication.",
    "Informal":     "Use natural, conversational language as spoken between friends.",
    "Simple":       "Use the simplest possible words. Avoid complex vocabulary.",
    "Professional": "Use professional corporate language. Precise and business-appropriate.",
}


@st.cache_resource(show_spinner=False)
def _get_client():
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY.strip())


def translate_text(
    text: str,
    direction: str,
    domain: str = "General",
    tone: str = "Formal",
    preserve_formatting: bool = True,
) -> dict:
    """
    Translate text. Returns {success, translation, tokens_used, error}.
    """
    client = _get_client()
    if client is None:
        return {
            "success": False, "translation": "", "tokens_used": 0,
            "error": "GROQ_API_KEY not found. Add it to your .env file."
        }
    if not text or not text.strip():
        return {"success": False, "translation": "", "tokens_used": 0, "error": "No text provided."}

    src = "Bangla (Bengali)" if direction == "Bangla → English" else "English"
    tgt = "English"          if direction == "Bangla → English" else "Bangla (Bengali)"

    system = (
        f"{DOMAIN_PROMPTS.get(domain, DOMAIN_PROMPTS['General'])}\n"
        f"TONE: {TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS['Formal'])}\n\n"
        "RULES — follow strictly:\n"
        "1. Translate ONLY the given text. No commentary or explanation.\n"
        "2. Preserve paragraph breaks and blank lines exactly.\n"
        "3. Preserve all numbers, dates, names, and proper nouns.\n"
        "4. If a word has no equivalent, keep original with a [brief note].\n"
        f"5. {'Preserve bullet points, numbering, and formatting.' if preserve_formatting else 'Output as plain text.'}\n"
        "6. Output ONLY the translation — no preamble."
    )
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Translate from {src} to {tgt}:\n\n{text}"}
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        return {
            "success":     True,
            "translation": resp.choices[0].message.content.strip(),
            "tokens_used": resp.usage.total_tokens if resp.usage else 0,
            "error":       None,
        }
    except Exception as e:
        msg = str(e)
        if "rate_limit" in msg.lower() or "429" in msg:
            msg = "Rate limit reached. Please wait 60 seconds and try again."
        elif "invalid" in msg.lower() and "key" in msg.lower():
            msg = "Invalid Groq API key. Check console.groq.com."
        elif "connection" in msg.lower():
            msg = "Connection error. Check your internet connection."
        return {"success": False, "translation": "", "tokens_used": 0, "error": msg}


def detect_language(text: str) -> str:
    """Detect Bangla vs English using Unicode range. Free, no API needed."""
    if not text:
        return "unknown"
    bangla  = sum(1 for c in text if "\u0980" <= c <= "\u09FF")
    letters = sum(1 for c in text if c.isalpha())
    if not letters:
        return "unknown"
    r = bangla / letters
    return "Bangla" if r > 0.5 else ("Mixed" if r > 0.1 else "English")


def improve_translation(
    original: str, current: str, direction: str, feedback: str
) -> dict:
    client = _get_client()
    if not client:
        return {"success": False, "translation": "", "error": "No API key"}
    src, tgt = ("Bangla","English") if direction=="Bangla → English" else ("English","Bangla")
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content":
                f"Improve this {src}→{tgt} translation based on feedback.\n"
                f"Original {src}: {original}\n"
                f"Current translation: {current}\n"
                f"Feedback: {feedback}\n"
                "Output ONLY the improved translation."
            }],
            temperature=0.3, max_tokens=4000,
        )
        return {
            "success":     True,
            "translation": resp.choices[0].message.content.strip(),
            "tokens_used": resp.usage.total_tokens if resp.usage else 0,
        }
    except Exception as e:
        return {"success": False, "translation": "", "error": str(e)}


def explain_translation(src_text: str, trans_text: str, direction: str) -> str:
    client = _get_client()
    if not client:
        return "Explanation not available."
    src, tgt = ("Bangla","English") if direction=="Bangla → English" else ("English","Bangla")
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content":
                f"Briefly explain 2-3 interesting translation choices between this "
                f"{src} original and its {tgt} translation in 3 simple sentences.\n"
                f"Original: {src_text[:400]}\nTranslation: {trans_text[:400]}"
            }],
            temperature=0.5, max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "Explanation not available."
