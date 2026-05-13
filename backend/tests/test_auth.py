import auth
import jwt as pyjwt


def test_create_and_decode_token():
    token = auth.create_token("admin", "admin", mfa_verified=False)
    payload = pyjwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
