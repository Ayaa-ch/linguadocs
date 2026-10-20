from __future__ import annotations


def _system_prompt(lang: str | None = None) -> str:
    # Prompt unique multilingue : plus de routage par langue.
    # `lang` gardé pour compatibilité mais ignoré.
    # Le cross-lingue est géré par les embeddings, la réponse suit la langue de la question.
    return (
        "You are LinguaDocs assistant. Follow strictly:\n"
        "- Answer ONLY using the provided context\n"
        "- Cite sources as [filename, page X]\n"
        "- Answer in the language of the question (same language the user used)\n"
        '- If the answer is not in the context, say: "Je ne trouve pas de réponse dans vos documents."\n'
        "- Do NOT invent information\n"
        "- Give the final answer DIRECTLY, without describing your reasoning or process\n"
        "- Never use emojis in your responses\n"
        "- N'utilise jamais d'emojis dans tes reponses\n"
        '- If the context contains NO information related to the question, say: "Je ne trouve pas de réponse dans vos documents."\n'
        "- Otherwise, answer at best by synthesising or deducing from the context, even if the question wording differs\n"
        "- The context may be in another language than the question: translate and answer in the question language"
    )


def build_prompt(question: str, chunks: list[dict], question_lang: str) -> str:
    system, user = build_messages(question, chunks, question_lang)
    # le LLM ne reçoit jamais user_id
    return f"{system}\n\n{user}"


def build_messages(question: str, chunks: list[dict], question_lang: str) -> tuple[str, str]:
    """Sépare system (règles) et user (contexte + question).

    Utilisé par l'API /api/chat d'Ollama : le template de chat encadre
    le system avec une autorité que le mode completion brut (/api/generate)
    ne donne pas — c'est ce cadrage qui empêche qwen3 de raisonner à voix haute.
    """
    system = _system_prompt(question_lang)
    ctx_lines = []
    for i, ch in enumerate(chunks, 1):
        fname = ch.get("filename") or ch.get("doc_title") or "doc"
        page = ch.get("page")
        page_str = f", page {page}" if page is not None else ""
        text = (ch.get("text") or "").strip()
        ctx_lines.append(f"[{i}] [{fname}{page_str}]\n{text}")

    context = "\n\n".join(ctx_lines) if ctx_lines else "(aucun contexte)"

    # le LLM ne reçoit jamais user_id
    # Rappel final placé juste avant la réponse (effet de récence).
    user = (
        f"Contexte:\n{context}\n\n"
        f"Question ({question_lang}): {question}\n"
        f"RAPPEL FINAL : commence immédiatement par la réponse elle-même. "
        f"Aucun préambule, aucun raisonnement visible, aucune analyse des sources. "
        f"Réponse:"
    )
    return system, user
