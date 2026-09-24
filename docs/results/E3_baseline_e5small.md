\# E3 — Baseline embeddings : multilingual-e5-small

\- Date : jour 5

\- Modèle : intfloat/multilingual-e5-small

\- Corpus : UN devset, 412 paires par langue

\- Chunks indexés : 1648



| Query → Target | n   | recall@5 | ci95            | mrr   |

|----------------|-----|----------|-----------------|-------|

| ar → en        | 412 | 0.653    | \[0.604, 0.697]  | 0.256 |

| ar → es        | 412 | 0.512    | \[0.459, 0.563]  | 0.162 |

| ar → fr        | 412 | 0.621    | \[0.570, 0.663]  | 0.222 |

| en → ar        | 412 | 0.910    | \[0.881, 0.937]  | 0.252 |

| en → es        | 412 | 0.976    | \[0.961, 0.990]  | 0.408 |

| en → fr        | 412 | 0.944    | \[0.920, 0.966]  | 0.363 |

| es → ar        | 412 | 0.665    | \[0.619, 0.711]  | 0.173 |

| es → en        | 412 | 0.966    | \[0.949, 0.983]  | 0.416 |

| es → fr        | 412 | 0.956    | \[0.937, 0.973]  | 0.361 |

| fr → ar        | 412 | 0.837    | \[0.799, 0.874]  | 0.237 |

| fr → en        | 412 | 0.930    | \[0.900, 0.954]  | 0.352 |

| fr → es        | 412 | 0.973    | \[0.956, 0.988]  | 0.416 |



\## Observations

\- Langues européennes entre elles : excellent (>0.93)

\- Arabe comme cible : correct (0.84 à 0.91)

\- Arabe comme source : point faible (0.51 à 0.65)

\- À comparer avec bge-m3 (expérience E3 complète)

