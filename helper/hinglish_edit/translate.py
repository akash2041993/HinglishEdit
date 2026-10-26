"""Translate caption lines (Hindi / Hinglish) to English.

Sarvam AI (with the user's key) is used when available: it is built for Indian languages and
code-mixed speech. Without a key, the free MyMemory API is used (about 5,000 characters a day)."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SARVAM_URL = os.environ.get("HINGLISH_SARVAM_TRANSLATE_URL", "https://api.sarvam.ai/translate")
MYMEMORY_URL = os.environ.get("HINGLISH_MYMEMORY_URL", "https://api.mymemory.translated.net/get")


class TranslateError(Exception):
    pass


def _is_hindi(text):
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def _sarvam(text, key):
    body = json.dumps({"input": text[:1000], "source_language_code": "hi-IN", "target_language_code": "en-IN",
                       "model": "mayura:v1", "mode": "formal"}).encode("utf-8")
    req = urllib.request.Request(SARVAM_URL, data=body, method="POST", headers={
        "api-subscription-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return (json.loads(r.read().decode("utf-8")).get("translated_text") or "").strip()


def _mymemory(text):
    q = urllib.parse.urlencode({"q": text[:480], "langpair": "hi|en"})
    with urllib.request.urlopen(MYMEMORY_URL + "?" + q, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if str(data.get("responseStatus")) not in ("200", "None") and data.get("responseStatus") is not None:
        raise TranslateError(f"Free translation service: {data.get('responseDetails') or data.get('responseStatus')}")
    out = ((data.get("responseData") or {}).get("translatedText") or "").strip()
    if "MYMEMORY WARNING" in out.upper():
        raise TranslateError("The free translation limit for today is used up. Add a Sarvam key in Settings for more.")
    return out


def translate_lines(lines, sarvam_key=None, cache=None):
    """English for each line. Lines already in English are kept."""
    out = []
    for text in lines:
        t = (text or "").strip()
        if not t or not _is_hindi(t):
            out.append(t)
            continue
        key = ("sv:" if sarvam_key else "mm:") + t
        if cache is not None and key in cache:
            out.append(cache[key])
            continue
        try:
            en = _sarvam(t, sarvam_key) if sarvam_key else _mymemory(t)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise TranslateError("The Sarvam key was rejected. Check it in Settings.")
            raise TranslateError(f"Translation failed (HTTP {e.code}).")
        except urllib.error.URLError as e:
            raise TranslateError(f"Could not reach the translation service: {e.reason}")
        en = en or t
        if cache is not None:
            cache[key] = en
        out.append(en)
    return out
