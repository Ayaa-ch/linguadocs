from __future__ import annotations

import re

from linguadocs.ingest.parsers import Page


def _split_paragraphs(text: str) -> list[str]:
    # double newline = paragraphe
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    # découpe par . ! ? + arabe ؟ ٫ et newline
    # garde la ponctuation
    sentences = re.split(r"(?<=[.!?؟۔])\s+|\n+", paragraph)
    return [s.strip() for s in sentences if s.strip()]


def _tokens(text: str) -> list[str]:
    # token simple = mot séparé par whitespace
    return text.split()


def chunk_pages(
    pages: list[Page],
    chunk_size: int = 400,
    overlap: int = 50,
    doc_title: str = "",
) -> list[dict]:
    chunks: list[dict] = []
    current_tokens: list[str] = []
    current_page: int | None = None
    chunk_idx = 0

    def flush():
        nonlocal current_tokens, current_page, chunk_idx
        if not current_tokens:
            return
        text = " ".join(current_tokens)
        chunks.append(
            {
                "chunk_key": f"{doc_title}#{chunk_idx}" if doc_title else f"chunk#{chunk_idx}",
                "text": text,
                "page": current_page,
                "doc_title": doc_title,
            }
        )
        # chevauchement: garder overlap derniers tokens
        if overlap > 0 and len(current_tokens) > overlap:
            current_tokens = current_tokens[-overlap:]
        else:
            current_tokens = []
        chunk_idx += 1

    for page in pages:
        # découpage récursif: paragraphes -> phrases -> tokens
        paragraphs = _split_paragraphs(page.text)
        if not paragraphs:
            # texte sans paragraphes clairs -> traiter comme un seul paragraphe
            paragraphs = [page.text]

        for para in paragraphs:
            sentences = _split_sentences(para)
            if not sentences:
                sentences = [para]

            for sent in sentences:
                toks = _tokens(sent)
                if not toks:
                    continue

                # si une phrase dépasse chunk_size, on la découpe en dur
                pos = 0
                while pos < len(toks):
                    remaining = chunk_size - len(current_tokens)
                    # si current vide, on prend jusqu'à chunk_size
                    # sinon on complète le chunk courant
                    if remaining <= 0:
                        flush()
                        remaining = chunk_size - len(current_tokens)

                    # si phrase trop longue, couper par chunk_size
                    take = min(remaining, len(toks) - pos)
                    # init page au premier chunk
                    if current_page is None:
                        current_page = page.page_number

                    current_tokens.extend(toks[pos : pos + take])
                    pos += take

                    if len(current_tokens) >= chunk_size:
                        flush()
                        # après flush, current_page reste la page courante pour overlap
                        # mais on met à jour si nouveau chunk
                        if current_tokens:
                            current_page = page.page_number
                        else:
                            current_page = page.page_number

                # après chaque phrase, si on a atteint la taille, flush déjà fait

        # entre pages, on peut flush pour garder cohérence page, mais on garde overlap
        # on ne force pas flush inter-page pour respecter chevauchement inter-page
        # on met juste à jour current_page pour prochain chunk
        if current_tokens:
            # garder page du chunk en cours (première page du chunk)
            pass
        else:
            current_page = page.page_number

    # dernier chunk
    if current_tokens:
        # flush sans overlap final
        text = " ".join(current_tokens)
        chunks.append(
            {
                "chunk_key": f"{doc_title}#{chunk_idx}" if doc_title else f"chunk#{chunk_idx}",
                "text": text,
                "page": current_page,
                "doc_title": doc_title,
            }
        )

    return chunks
