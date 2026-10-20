"""Test du viewer latéral : GET /documents/{id}/chunks."""

import io


def _upload_txt(client, token, name="viewer.txt", body=None):
    body = body or ("Ceci est un test du viewer. " * 60)
    r = client.post(
        "/documents",
        files={"file": (name, io.BytesIO(body.encode("utf-8")), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_chunks_ok(client, token_alice):
    doc = _upload_txt(client, token_alice)
    assert doc["status"] == "indexed", doc  # synchrone sous pytest
    r = client.get(
        f"/documents/{doc['id']}/chunks",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert r.status_code == 200, r.text
    chunks = r.json()
    assert len(chunks) > 0
    assert all("chunk_key" in c and "text" in c for c in chunks)
    # triés par index croissant
    idx = [int(c["chunk_key"].rsplit("#", 1)[1]) for c in chunks]
    assert idx == sorted(idx), idx


def test_chunks_404(client, token_alice):
    r = client.get(
        "/documents/00000000-0000-0000-0000-000000000000/chunks",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert r.status_code == 404, r.text


def test_chunks_forbidden_cross_user(client, token_alice, token_bob):
    doc = _upload_txt(client, token_alice)
    r = client.get(
        f"/documents/{doc['id']}/chunks",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert r.status_code == 404, r.text  # même comportement que GET document


def _upload_pdf(client, token, name="pages.pdf", n_pages=3):
    from fpdf import FPDF

    pdf = FPDF()
    for i in range(1, n_pages + 1):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, f"MARQUEUR_PAGE_{i} " + ("Contenu de test. " * 30))
    buf = io.BytesIO(pdf.output())
    r = client.post(
        "/documents",
        files={"file": (name, buf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_pages_pdf_order(client, token_alice):
    doc = _upload_pdf(client, token_alice, n_pages=3)
    assert doc["status"] == "indexed", doc
    assert doc["n_pages"] == 3
    r = client.get(
        f"/documents/{doc['id']}/pages",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["filename"].endswith(".pdf")
    pages = data["pages"]
    assert [p["page"] for p in pages] == [1, 2, 3]  # ordre physique, pas de mélange
    for i, p in enumerate(pages, start=1):
        assert f"MARQUEUR_PAGE_{i}" in p["text"], f"marqueur page {i} absent"
    # chaque page ne contient que son propre marqueur
    assert "MARQUEUR_PAGE_2" not in pages[0]["text"]
    assert "MARQUEUR_PAGE_1" not in pages[1]["text"]


def test_pages_txt_single(client, token_alice):
    doc = _upload_txt(client, token_alice)
    r = client.get(
        f"/documents/{doc['id']}/pages",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["pages"]) == 1


def test_pages_404(client, token_alice):
    r = client.get(
        "/documents/00000000-0000-0000-0000-000000000000/pages",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert r.status_code == 404, r.text
