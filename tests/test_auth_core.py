from auth import hash_password, verify_password, generate_token

def test_password_round_trip():
    pw = "correct-horse-battery"
    assert verify_password(pw, hash_password(pw))

def test_wrong_password_fails():
    assert not verify_password("wrong", hash_password("right"))

def test_generate_token_is_unique():
    assert generate_token() != generate_token()

def test_generate_token_is_64_chars():
    # 32 bytes as hex = 64 characters
    assert len(generate_token()) == 64
