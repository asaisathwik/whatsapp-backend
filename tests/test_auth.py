def test_register_and_login_flow(client):
    # 1. Register new user and organization
    reg_payload = {
        "email": "fresh_user@saas.com",
        "full_name": "Fresh User",
        "password": "SecurePassword123!",
        "organization_name": "Apex Enterprise"
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 200
    token_data = reg_resp.json()
    assert "access_token" in token_data
    assert token_data["organization"]["name"] == "Apex Enterprise"
    assert token_data["organization"]["role"] == "OWNER"

    token = token_data["access_token"]

    # 2. Call /auth/me with bearer token
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "fresh_user@saas.com"

    # 3. Login with credentials
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "fresh_user@saas.com",
        "password": "SecurePassword123!"
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

def test_unauthorized_and_invalid_token(client):
    # No auth
    resp = client.get("/api/v1/contacts")
    assert resp.status_code == 401

    # Invalid auth
    resp2 = client.get("/api/v1/contacts", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert resp2.status_code == 401
