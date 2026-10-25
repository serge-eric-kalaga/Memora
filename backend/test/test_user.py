from test.baseTest import BaseTest


class TestUser(BaseTest):
    """
    Test des routes de l'utilisateur
    """

    def test_create_user(self):
        payload = {
            "username": "sergakalaga",
            "password": "12345678",
            "telephone": self.fake.basic_phone_number(),
        }
        request = self.client.post("/api/auth/register", json=payload)

        self.assertBase(request=request)
        assert request.json()["data"]["username"] == payload["username"]

    def test_update_user(self):
        self.auth()
        test_user = self.createTestUser()
        own_username = self.test_user.username
        other_username = test_user.username
        self.db.close()
        request = self.client.put(
            f"/api/user/{other_username}", json={"username": "testuserupdated"}
        )

        assert request.status_code == 403
        request = self.client.put(
            f"/api/user/{own_username}", json={"username": "testuserupdated"}
        )
        self.assertBase(request=request)
        assert request.json()["data"]["username"] == "testuserupdated"
