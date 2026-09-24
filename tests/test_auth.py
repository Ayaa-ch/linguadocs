import uuid


def test_register(client):
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "Secret1234"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_doublon(client):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    r1 = client.post("/auth/register", json={"email": email, "password": "Secret1234"})
    assert r1.status_code == 201
    r2 = client.post("/auth/register", json={"email": email, "password": "Secret1234"})
    assert r2.status_code == 400


def test_login_correct(client):
    email = f"login_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "Secret1234"
    client.post("/auth/register", json={"email": email, "password": pwd})
    r = client.post("/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


def test_login_mauvais_mot_de_passe(client):
    email = f"badpwd_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/auth/register", json={"email": email, "password": "Secret1234"})
    r = client.post("/auth/login", json={"email": email, "password": "WrongPass"})
    assert r.status_code == 401


def test_protected_sans_token(client):
    r = client.get("/documents")
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


def test_protected_token_invalide(client):
    r = client.get("/documents", headers={"Authorization": "Bearer invalidtoken123"})
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"
