"""Devanagari (Hindi) -> natural Roman Hinglish, e.g. "क्या हाल है" -> "kya haal hai".

Offline engine: a dictionary of common words (Hindi words and English words written in
Devanagari by speech-to-text) plus a rule engine with schwa deletion for everything else.
It is good, not perfect, so captions stay editable. The optional Sarvam API gives
better results for unusual words (see sarvam_line).
"""
import json
import re
import unicodedata
import urllib.request

# ---------------------------------------------------------------- dictionary
# Hindi words -> how people normally type them in Hinglish.
_HINDI = """
है:hai हैं:hain हूँ:hoon हूं:hoon हो:ho था:tha थी:thi थे:the थीं:thin
क्या:kya क्यों:kyun क्यूँ:kyun क्यूं:kyun कैसे:kaise कैसा:kaisa कैसी:kaisi कब:kab कहाँ:kahan कहां:kahan कौन:kaun
कितना:kitna कितनी:kitni कितने:kitne
नहीं:nahi नही:nahi ना:na न:na मत:mat हाँ:haan हां:haan जी:ji
मैं:main मै:main में:mein हम:hum हमें:humein हमारा:hamara हमारी:hamari हमारे:hamare
तुम:tum तुम्हें:tumhe तुम्हारा:tumhara तुम्हारी:tumhari तुम्हारे:tumhare आप:aap आपका:aapka आपकी:aapki आपके:aapke आपको:aapko
मेरा:mera मेरी:meri मेरे:mere मुझे:mujhe मुझको:mujhko मुझसे:mujhse
तू:tu तेरा:tera तेरी:teri तेरे:tere तुझे:tujhe
वो:wo वह:woh वे:ve ये:ye यह:yeh इस:is उस:us इसे:ise उसे:use इसका:iska उसका:uska इसकी:iski उसकी:uski इसके:iske उसके:uske
इन:in उन:un इनका:inka उनका:unka उनकी:unki उनके:unke इन्हें:inhe उन्हें:unhe उन्होंने:unhone इन्होंने:inhone
का:ka की:ki के:ke को:ko से:se पर:par पे:pe तक:tak लिए:liye लिये:liye वाला:wala वाली:wali वाले:wale
और:aur या:ya भी:bhi तो:toh ही:hi सिर्फ:sirf सिर्फ़:sirf बस:bas फिर:phir अब:ab अभी:abhi तब:tab जब:jab
लेकिन:lekin मगर:magar पर:par क्योंकि:kyunki इसलिए:isliye इसलिये:isliye अगर:agar वरना:warna
एक:ek दो:do तीन:teen चार:chaar पांच:paanch पाँच:paanch छह:chhah सात:saat आठ:aath नौ:nau दस:das सौ:sau हज़ार:hazaar हजार:hazaar लाख:laakh करोड़:crore
पहला:pehla पहली:pehli पहले:pehle दूसरा:doosra दूसरी:doosri दूसरे:doosre आखिरी:aakhri
बहुत:bahut ज़्यादा:zyada ज्यादा:zyada कम:kam थोड़ा:thoda थोड़ी:thodi सब:sab सबसे:sabse सभी:sabhi कुछ:kuch कोई:koi किसी:kisi
अच्छा:accha अच्छी:acchi अच्छे:acche बुरा:bura सही:sahi गलत:galat ग़लत:galat ठीक:theek बढ़िया:badhiya बेहतर:behtar
बड़ा:bada बड़ी:badi बड़े:bade छोटा:chhota छोटी:chhoti छोटे:chhote नया:naya नई:nayi नए:naye पुराना:purana
कर:kar करो:karo करें:karein करना:karna करने:karne करते:karte करता:karta करती:karti किया:kiya की:ki किए:kiye करेंगे:karenge करेगा:karega करूँगा:karunga करूंगा:karunga
हो:ho होता:hota होती:hoti होते:hote होना:hona होगा:hoga होगी:hogi होंगे:honge हुआ:hua हुई:hui हुए:hue
रहा:raha रही:rahi रहे:rahe रहता:rehta रहती:rehti रहते:rehte रहना:rehna
गया:gaya गई:gayi गए:gaye जा:ja जाओ:jao जाना:jaana जाता:jaata जाती:jaati जाते:jaate जाएगा:jaayega जाएंगे:jaayenge
आ:aa आओ:aao आना:aana आता:aata आती:aati आते:aate आया:aaya आई:aayi आए:aaye
दे:de दो:do देना:dena देता:deta देती:deti देते:dete दिया:diya दी:di दिए:diye
ले:le लो:lo लेना:lena लेता:leta लेती:leti लेते:lete लिया:liya ली:li
बोल:bol बोलो:bolo बोला:bola बोली:boli बोलते:bolte कहा:kaha कहते:kehte कहना:kehna बात:baat बातें:baatein
देख:dekh देखो:dekho देखा:dekha देखिए:dekhiye देखते:dekhte देखना:dekhna
सकता:sakta सकती:sakti सकते:sakte चाहिए:chahiye चाहता:chahta चाहती:chahti चाहते:chahte
समझ:samajh समझो:samjho समझा:samjha समझना:samajhna पता:pata मालूम:maloom
यार:yaar भाई:bhai दोस्त:dost दोस्तों:doston लोग:log लोगों:logon आदमी:aadmi बंदा:banda
मतलब:matlab यानी:yaani यानि:yaani बिल्कुल:bilkul शायद:shayad ज़रूर:zaroor जरूर:zaroor एकदम:ekdum
आज:aaj कल:kal परसों:parson दिन:din रात:raat सुबह:subah शाम:shaam साल:saal महीना:mahina हफ्ता:hafta वक्त:waqt समय:samay टाइम:time
यहाँ:yahan यहां:yahan वहाँ:wahan वहां:wahan ऊपर:upar नीचे:neeche अंदर:andar बाहर:bahar आगे:aage पीछे:peeche साथ:saath
काम:kaam नाम:naam पैसा:paisa पैसे:paise घर:ghar दुनिया:duniya देश:desh ज़िंदगी:zindagi जिंदगी:zindagi
सवाल:sawaal जवाब:jawaab तरह:tarah तरीका:tareeka वजह:wajah चीज़:cheez चीज:cheez चीज़ें:cheezein
प्यार:pyaar दिल:dil खुश:khush ख़ुश:khush डर:darr शुरू:shuru खत्म:khatam ख़त्म:khatam
अपना:apna अपनी:apni अपने:apne खुद:khud ख़ुद:khud
भारत:Bharat हिंदी:Hindi हिन्दी:Hindi इंडिया:India
ऐसा:aisa ऐसी:aisi ऐसे:aise वैसा:waisa वैसे:waise जैसा:jaisa जैसे:jaise
चलो:chalo चल:chal चलिए:chaliye बताओ:batao बताता:batata बताना:batana बताया:bataya बताइए:bataiye
सुनो:suno सुना:suna सुनिए:suniye
बारे:baare बताऊंगा:bataunga बताऊँगा:bataunga बताएंगे:bataenge बताता:batata दिखाऊंगा:dikhaunga
पूरा:poora पूरी:poori पूरे:poore आधा:aadha
"""

# English words that speech-to-text often writes in Devanagari -> English spelling.
_ENGLISH = """
वीडियो:video विडियो:video वीडियोज़:videos वीडियोस:videos चैनल:channel सब्सक्राइब:subscribe लाइक:like शेयर:share कमेंट:comment कमेंट्स:comments
बेल:bell आइकन:icon नोटिफिकेशन:notification लिंक:link डिस्क्रिप्शन:description फॉलो:follow इंस्टाग्राम:Instagram यूट्यूब:YouTube फेसबुक:Facebook
ऑफिस:office ऑफ़िस:office फ़ोन:phone फोन:phone मोबाइल:mobile लैपटॉप:laptop कंप्यूटर:computer इंटरनेट:internet ऐप:app ऐप्स:apps वेबसाइट:website
प्रॉब्लम:problem प्रोब्लम:problem सॉल्यूशन:solution आइडिया:idea प्लान:plan टिप्स:tips टिप:tip ट्रिक:trick ट्रिक्स:tricks
बेसिकली:basically एक्चुअली:actually ओके:okay ओके:okay हेलो:hello हैलो:hello थैंक:thank थैंक्स:thanks थैंक्यू:thank-you प्लीज:please प्लीज़:please सॉरी:sorry
सो:so लाइक:like यू:you नो:know आई:I मीन:mean राइट:right वेल:well एंड:and बट:but ऑर:or द:the इज़:is इज:is दिस:this दैट:that
बिज़नेस:business बिजनेस:business मार्केट:market मार्केटिंग:marketing मनी:money इनकम:income कंपनी:company ब्रांड:brand प्रोडक्ट:product
कंटेंट:content क्रिएटर:creator एडिटिंग:editing एडिट:edit कैमरा:camera शूट:shoot शूटिंग:shooting रील:reel रील्स:reels शॉर्ट्स:shorts
स्टार्ट:start स्टार्टअप:startup फ्री:free प्राइस:price ऑफर:offer डील:deal ऑनलाइन:online ऑफलाइन:offline
गाइज़:guys गाइस:guys गाइज:guys टॉपिक:topic पॉइंट:point पॉइंट्स:points स्टेप:step स्टेप्स:steps सिंपल:simple इम्पोर्टेंट:important इंपॉर्टेंट:important
गवर्नमेंट:government सरकार:sarkaar पॉलिसी:policy लॉन्च:launch रुपये:rupaye रुपए:rupaye रुपया:rupaya प्रोसेस:process सिस्टम:system डेटा:data
एआई:AI टेक्नोलॉजी:technology टेक:tech फीचर:feature फीचर्स:features अपडेट:update सेटिंग:setting सेटिंग्स:settings
टीम:team मीटिंग:meeting क्लाइंट:client प्रोजेक्ट:project स्कूल:school कॉलेज:college जॉब:job करियर:career
"""


def _parse(block):
    d = {}
    for tok in block.split():
        if ":" in tok:
            k, v = tok.split(":", 1)
            d[k] = v.replace("-", " ")
    return d


DICTIONARY = _parse(_HINDI)
DICTIONARY.update(_parse(_ENGLISH))

# ---------------------------------------------------------------- rule engine
_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "ऩ": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ऱ": "r", "ल": "l", "ळ": "l", "ऴ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}
# consonant + nukta (either precomposed or with U+093C)
_NUKTA = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f", "य": "y", "र": "r", "न": "n"}
_PRECOMPOSED = {"क़": "क", "ख़": "ख", "ग़": "ग", "ज़": "ज", "ड़": "ड", "ढ़": "ढ", "फ़": "फ", "य़": "य"}

_MATRA = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
    "ृ": "ri", "ॄ": "ri", "ॅ": "e", "ॆ": "e", "े": "e", "ै": "ai",
    "ॉ": "o", "ॊ": "o", "ो": "o", "ौ": "au", "ॢ": "li", "ॣ": "li",
}
_INDEP = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri", "ॠ": "ri",
    "ऌ": "li", "ऍ": "e", "ऎ": "e", "ए": "e", "ऐ": "ai", "ऑ": "o", "ऒ": "o", "ओ": "o", "औ": "au",
}
_VIRAMA = "्"
_NUKTA_SIGN = "़"
_ANUSVARA = "ं"
_CHANDRA = "ँ"
_VISARGA = "ः"
_DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}
_LABIAL = {"p", "ph", "b", "bh", "m", "f"}


class _Unit:
    __slots__ = ("c", "v", "inherent", "nasal", "visarga", "deleted")

    def __init__(self, c, v, inherent):
        self.c = c
        self.v = v
        self.inherent = inherent
        self.nasal = False
        self.visarga = False
        self.deleted = False

    def has_vowel(self):
        return bool(self.v) and not self.deleted


def _units(word):
    units = []
    i = 0
    s = word
    while i < len(s):
        ch = s[i]
        if s.startswith("\u091c\u094d\u091e", i):  # ज्ञ is said "gy" (gyaan)
            units.append(_Unit("gy", "a", True))
            i += 3
        elif ch in _PRECOMPOSED:
            ch_base = _PRECOMPOSED[ch]
            units.append(_Unit(_NUKTA.get(ch_base, _CONS[ch_base]), "a", True))
            i += 1
        elif ch in _CONS:
            c = _CONS[ch]
            if i + 1 < len(s) and s[i + 1] == _NUKTA_SIGN:
                c = _NUKTA.get(ch, c)
                i += 1
            units.append(_Unit(c, "a", True))
            i += 1
        elif ch in _MATRA and units:
            units[-1].v = _MATRA[ch]
            units[-1].inherent = False
            i += 1
        elif ch == _VIRAMA and units:
            units[-1].v = ""
            units[-1].inherent = False
            i += 1
        elif ch in _INDEP:
            units.append(_Unit("", _INDEP[ch], False))
            i += 1
        elif ch in (_ANUSVARA, _CHANDRA) and units:
            units[-1].nasal = True
            i += 1
        elif ch == _VISARGA and units:
            units[-1].visarga = True
            i += 1
        elif ch in _DIGITS:
            units.append(_Unit(_DIGITS[ch], "", False))
            i += 1
        else:
            i += 1  # ZWJ, ZWNJ, avagraha, unknown marks
    return units


def _delete_schwas(u):
    n = len(u)
    if n == 0:
        return
    # Word-final schwa: dropped, except single-syllable words and clusters ending in y/r/v ("satya", "mitra").
    last = u[-1]
    if last.inherent and n > 1 and not last.nasal:
        cluster = n >= 2 and u[-2].v == "" and u[-2].c != ""
        if not (cluster and last.c in ("y", "r", "v")):
            last.deleted = True
    # Medial schwa deletion (V C a C V -> V C C V), scanning right to left.
    for i in range(n - 2, 0, -1):
        cur = u[i]
        if not cur.inherent or cur.deleted or cur.nasal or not cur.c:
            continue
        prev, nxt = u[i - 1], u[i + 1]
        if not prev.has_vowel():
            continue
        if not (nxt.c and nxt.has_vowel()):
            continue
        if prev.c == "" and i - 1 == 0 and prev.v == "a":
            continue  # keep "a" after initial अ, e.g. अगर -> agar
        cur.deleted = True


def _render(u):
    out = []
    n = len(u)
    for i, x in enumerate(u):
        c = x.c
        if c == "v":
            # Hinglish usually writes व as "w" before a / aa / o sounds (wo, wala, sawaal).
            nxt_v = x.v if x.has_vowel() else ""
            c = "w" if nxt_v in ("a", "aa", "o", "") or (i > 0 and u[i - 1].v == "") else "v"
        v = x.v if x.has_vowel() else ""
        final = (i == n - 1) or all((not y.has_vowel() and not y.c) for y in u[i + 1:])
        closed = (i + 1 < n) and (not u[i + 1].has_vowel()) and u[i + 1].c != ""
        if v == "aa":
            if x.c == "" and i == 0:
                v = "aa"
            elif final and not x.nasal:
                v = "a"
            elif closed or x.nasal:
                v = "aa"
            else:
                v = "a"
        elif v == "ii":
            v = "i" if (final and not x.nasal) else "ee"
        elif v == "uu":
            v = "u" if (final and not x.nasal) else "oo"
        if x.nasal:
            nxt_c = u[i + 1].c if i + 1 < n else ""
            if v == "e" and final:
                v = "ein"
            elif nxt_c in _LABIAL and v == "a":
                v = v + "m"
            elif v:
                v = v + "n"
            else:
                v = "n"
        if x.visarga:
            v += "h"
        out.append(c + v)
    s = "".join(out)
    return s.replace("chchh", "cch")


_DEVA_RE = re.compile(r"[ऀ-ॿ]")
_TOKEN_RE = re.compile("([\u0900-\u0963\u0966-\u097F\u200c\u200d]+)")


def is_devanagari(text):
    return bool(_DEVA_RE.search(text or ""))


def word_to_roman(word):
    """Transliterate one word (punctuation around it is kept)."""
    if not is_devanagari(word):
        return word

    def conv(m):
        w = unicodedata.normalize("NFC", m.group(1)).replace("‌", "").replace("‍", "")
        if w in DICTIONARY:
            return DICTIONARY[w]
        u = _units(w)
        _delete_schwas(u)
        return _render(u)

    out = _TOKEN_RE.sub(conv, word)
    return out.replace("।", ".").replace("॥", ".")


def text_to_roman(text):
    return " ".join(word_to_roman(w) for w in (text or "").split())


# ---------------------------------------------------------------- Sarvam (optional, better)
SARVAM_URL = "https://api.sarvam.ai/transliterate"


def sarvam_line(text, api_key, timeout=30):
    """Transliterate a whole line with Sarvam AI (hi-IN -> en-IN). Returns None on failure."""
    body = json.dumps({
        "input": text,
        "source_language_code": "hi-IN",
        "target_language_code": "en-IN",
    }).encode("utf-8")
    req = urllib.request.Request(SARVAM_URL, data=body, method="POST", headers={
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("transliterated_text")
    except Exception:
        return None


def words_to_roman(words, sarvam_key=None, cache=None):
    """Transliterate a list of word strings. Uses Sarvam per line when a key is given and the
    word count matches, otherwise the offline engine. Keeps one output per input word."""
    offline = [word_to_roman(w) for w in words]
    if not sarvam_key or not any(is_devanagari(w) for w in words):
        return offline
    line = " ".join(words)
    key = "sarvam:" + line
    res = cache.get(key) if cache is not None else None
    if res is None:
        res = sarvam_line(line, sarvam_key)
        if res and cache is not None:
            cache[key] = res
    if not res:
        return offline
    parts = res.split()
    if len(parts) != len(words):
        return offline
    # Keep English words exactly as the transcript had them.
    return [p if is_devanagari(w) else w for p, w in zip(parts, words)]
