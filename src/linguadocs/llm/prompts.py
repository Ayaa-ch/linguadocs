from __future__ import annotations


def _system_prompt(lang: str) -> str:
    if lang == "ar":
        return (
            "أنت مساعد LinguaDocs. اتبع القواعد التالية بدقة:\n"
            "- أجب فقط باستخدام المعلومات الموجودة في السياق المقدم\n"
            "- اذكر المصادر على الشكل [اسم_الملف، صفحة X]\n"
            "- أجب بلغة السؤال (العربية)\n"
            '- إذا لم تكن الإجابة في السياق، قل فقط: "Je ne trouve pas de réponse dans vos documents."\n'
            "- لا تخترع معلومات"
        )
    if lang == "en":
        return (
            "You are LinguaDocs assistant. Follow strictly:\n"
            "- Answer ONLY using the provided context\n"
            "- Cite sources as [filename, page X]\n"
            "- Answer in the language of the question (English)\n"
            '- If the answer is not in the context, say: "Je ne trouve pas de réponse dans vos documents."\n'
            "- Do NOT invent information"
        )
    # fr par défaut (et es -> on répond en français/ langue question mais prompt en français)
    if lang == "es":
        return (
            "Eres asistente LinguaDocs. Sigue estrictamente:\n"
            "- Responde SOLO con la información del contexto proporcionado\n"
            "- Cita fuentes como [nombre_archivo, página X]\n"
            "- Responde en el idioma de la pregunta (español)\n"
            '- Si la respuesta no está en el contexto, di: "Je ne trouve pas de réponse dans vos documents."\n'
            "- NO inventes información"
        )
    return (
        "Tu es l'assistant LinguaDocs. Règles strictes :\n"
        "- Réponds UNIQUEMENT avec les informations du contexte fourni\n"
        "- Cite les sources : [nom_fichier, page X]\n"
        "- Réponds dans la langue de la question (français)\n"
        '- Si la réponse n\'est pas dans le contexte : dis "Je ne trouve pas de réponse dans vos documents."\n'
        "- NE PAS inventer d'informations"
    )


def build_prompt(question: str, chunks: list[dict], question_lang: str) -> str:
    system = _system_prompt(question_lang)
    # contexte numéroté
    ctx_lines = []
    for i, ch in enumerate(chunks, 1):
        fname = ch.get("filename") or ch.get("doc_title") or "doc"
        page = ch.get("page")
        page_str = f", page {page}" if page is not None else ""
        text = (ch.get("text") or "").strip()
        ctx_lines.append(f"[{i}] [{fname}{page_str}]\n{text}")

    context = "\n\n".join(ctx_lines) if ctx_lines else "(aucun contexte)"

    # le LLM ne reçoit jamais user_id
    prompt = (
        f"{system}\n\n"
        f"Contexte:\n{context}\n\n"
        f"Question ({question_lang}): {question}\n"
        f"Réponse:"
    )
    return prompt
