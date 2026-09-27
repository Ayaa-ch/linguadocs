# shim pour compatibilité : dense.py -> retrieval.py
from linguadocs.retrieval.retrieval import *  # noqa: F401,F403
from linguadocs.retrieval.retrieval import (
    COL,
    DIM,
    client,
    delete_user_doc,
    get_user_chunks,
    index,
    init,
    model,
    rerank,
    search,
    search_hybrid,
    search_sparse,
)
