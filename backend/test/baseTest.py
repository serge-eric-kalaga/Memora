import unittest
from werkzeug.security import generate_password_hash
from fastapi.testclient import TestClient
from faker import Faker
from api.database import User

fake = Faker()


class BaseTest(unittest.TestCase):
    """
    Class de base pour les tests unitaires
    """

    def createTestUser(self):
        """Create a test user"""
        fake_password = fake.password()
        test_user = User(
            username=fake.user_name(),
            password=generate_password_hash(fake_password),
            telephone=fake.basic_phone_number(),
        ).saveWithCommit(self.db)
        test_user.password = fake_password
        return test_user

    def getTokens(self) -> dict:
        """Get the token of the test user"""
        req = self.client.post(
            "/api/auth/login",
            json={
                "username": self.test_user.username,
                "password": self.test_user.password,
            },
        )
        return req.json()["data"]["token"]

    def auth(self):
        """Add Authorization header to the client"""
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def assertBase(self, request, status_code=200, status=1, status_code_=200):
        """Assert the base of the response"""
        assert request.status_code == status_code
        assert request.json()["status"] == status
        assert request.json()["status_code"] == status_code

    @classmethod
    def setUpClass(cls):
        from api.database import engine, Base

        Base.metadata.drop_all(engine)

    def setUp(self):
        from api import createApp
        from api.database import engine, init_database
        from api.configs import SETTINGS
        from sqlalchemy.orm import sessionmaker

        TESTING = SETTINGS()
        app = createApp(TESTING)
        self.db = sessionmaker(bind=engine)()
        init_database(engine)
        self.addCleanup(self.db.close)
        self.client = self.enterContext(TestClient(app=app))

        self.test_user = self.createTestUser()
        self.token = self.getTokens()
        self.fake = fake

    # def tearDown(self):
    #     from api.database import engine, Base

    #     Base.metadata.drop_all(engine)
