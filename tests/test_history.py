def test_history_isolation(client, token_alice, token_bob):
    doc = "doc-test-123"
    r = client.post("/history", headers={"Authorization": f"Bearer {token_alice}"},
                    json={"doc_id": doc, "role": "user", "content": "bonjour"})
    assert r.status_code == 200, r.text
    r = client.post("/history", headers={"Authorization": f"Bearer {token_alice}"},
                    json={"doc_id": doc, "role": "bot", "content": "salut",
                          "sources": [], "question_lang": "fr"})
    assert r.status_code == 200, r.text
    g1 = client.get(f"/history?doc_id={doc}", headers={"Authorization": f"Bearer {token_alice}"})
    assert g1.status_code == 200
    assert len(g1.json()) == 2
    g2 = client.get(f"/history?doc_id={doc}", headers={"Authorization": f"Bearer {token_bob}"})
    assert g2.status_code == 200
    assert len(g2.json()) == 0
    d = client.delete(f"/history?doc_id={doc}", headers={"Authorization": f"Bearer {token_alice}"})
    assert d.status_code == 200
    g1b = client.get(f"/history?doc_id={doc}", headers={"Authorization": f"Bearer {token_alice}"})
    assert len(g1b.json()) == 0
