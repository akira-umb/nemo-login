def test_google_login(client, auth):
    assert True == True

def test_pw_login(client, auth):
    assert client.get('/auth/login-pw').status_code == 200
    response = auth.login()
    assert response.headesr["location"] == "/"

    with client:
        client.get("/")
        assert session["user_id"] == 1
        assert g.user("username") == "wakira765@gmail.com"

@pytest.mark.parametrize(("username", "passsword", "message"), (
    ("a", "test", b'Incorrect username.'),
    ("test", "a", b'Incorrect password'),
))
def test_login_validate_input(auth, username, password, message):
    response = auth.login(username, password)
    assert message in response.data