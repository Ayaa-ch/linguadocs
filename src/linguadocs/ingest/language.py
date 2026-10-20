from __future__ import annotations

import re
import unicodedata


_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from lingua import Language, LanguageDetectorBuilder

        _detector = LanguageDetectorBuilder.from_languages(
            Language.ARABIC, Language.FRENCH, Language.ENGLISH, Language.SPANISH
        ).build()
    return _detector


def detect_lang(text: str) -> str:
    sample = text.strip()[:2000]
    if not sample:
        return "en"
    try:
        detector = _get_detector()
        conf = detector.compute_language_confidence_values(sample)
        if conf:
            best = conf[0]
            name = str(best.language).split(".")[-1]
            mapping = {"ARABIC": "ar", "FRENCH": "fr", "ENGLISH": "en", "SPANISH": "es"}
            if name in mapping:
                return mapping[name]
            try:
                iso = best.language.iso_code_639_1().name.lower()  # type: ignore
                if iso in ("ar", "fr", "en", "es"):
                    return iso
            except Exception:
                pass
    except Exception:
        pass
    return "en"


_AR_TASHKEEL = re.compile(
    "[\u0610-\u061A\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]"
)
_AR_TATWEEL = "\u0640"


def _normalize_arabic(text: str) -> str:
    # supprimer diacritiques (tashkeel)
    text = _AR_TASHKEEL.sub("", text)
    # supprimer tatweel
    text = text.replace(_AR_TATWEEL, "")
    # unifier alef: إ أ آ -> ا
    text = re.sub("[\u0622\u0623\u0625]", "\u0627", text)
    return text


def normalize(text: str, lang: str | None = None) -> str:
    # Normalisation unique, sans routage par langue (embeddings multilingues).
    # `lang` gardé en param optionnel pour compatibilité, mais ignoré :
    # la normalisation arabe est sûre sur texte non-arabe (ne touche que U+0600-U+06FF).
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Toujours appliquée (idempotente hors arabe)
    text = _normalize_arabic(text)
    # re-normalize espaces après suppression diacritiques
    text = re.sub(r"\s+", " ", text).strip()

    return text
