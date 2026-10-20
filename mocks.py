"""
Données simulées pour les fonctions dont l'API n'existe pas encore.

Chaque fonction renvoie EXACTEMENT le contrat JSON décrit dans api.py.
Quand vos vraies routes existeront, passez USE_MOCK_* à false : ce fichier
ne sera plus appelé.

>>> COMING SOON <<<
Les fonctions suivantes sont des placeholders (stubs) en attendant les vraies routes :
- Résumé (summary)
- Quiz
- Flashcards
- Traduction (translate)
"""

import time

DELAY = 1.2  # secondes, pour tester les états de chargement


def _wait():
    time.sleep(DELAY)


# --------------------------------------------------------------------------
# Résumé — COMING SOON
# --------------------------------------------------------------------------
def summarize(doc_id, filename, n_pages, length, language, page_from, page_to):
    """Placeholder : le résumé arrive bientôt."""
    _wait()
    return {
        "summary": "Résumé à venir (coming soon).",
        "bullets": [],
        "sources": [],
        "language": language,
        "status": "coming_soon",
    }


# --------------------------------------------------------------------------
# Quiz — COMING SOON
# --------------------------------------------------------------------------
def generate_quiz(doc_id, filename, n_questions, difficulty, language):
    """Placeholder : le quiz arrive bientôt."""
    _wait()
    return {
        "questions": [],
        "status": "coming_soon",
    }


# --------------------------------------------------------------------------
# Flashcards — COMING SOON
# --------------------------------------------------------------------------
def generate_flashcards(doc_id, filename, n_cards, language):
    """Placeholder : les flashcards arrivent bientôt."""
    _wait()
    return {
        "cards": [],
        "status": "coming_soon",
    }


# --------------------------------------------------------------------------
# Traduction — COMING SOON
# --------------------------------------------------------------------------
def translate(doc_id, filename, source_lang, target_lang, page_from, page_to):
    """Placeholder : la traduction arrive bientôt."""
    _wait()
    return {
        "original": "",
        "translation": "Traduction à venir (coming soon).",
        "source": {"filename": filename, "pages": ""},
        "status": "coming_soon",
    }
