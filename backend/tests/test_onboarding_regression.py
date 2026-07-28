import pytest
from fastapi.testclient import TestClient
from tests.conftest import setup_test_db, teardown_test_db, clean_tables, TestingSessionLocal, app

class TestOnboardingRegression:
    @classmethod
    def setup_class(cls):
        setup_test_db()
        cls.client = TestClient(app)

    @classmethod
    def teardown_class(cls):
        teardown_test_db()

    def setup_method(self):
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()

    def test_onboarding_step2_brand_profile_update_and_cors(self):
        # 1. Signup user
        signup_payload = {
            "email": "somusekhar@svsilks.com",
            "name": "Somu Sekhar",
            "password": "Password123!",
            "organization_name": "Sri SiddiVinayaka Silk Sarees"
        }
        signup_res = self.client.post("/api/auth/signup", json=signup_payload)
        assert signup_res.status_code == 201
        
        # 2. Login user and retrieve token
        login_payload = {
            "username": "somusekhar@svsilks.com",
            "password": "Password123!"
        }
        login_res = self.client.post("/api/auth/login", data=login_payload)
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": "https://closely-frontend.onrender.com"
        }

        # 3. GET /api/auth/me check
        me_res = self.client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "somusekhar@svsilks.com"

        # 4. Step 2 Onboarding: PUT /api/brand/profile
        profile_update_payload = {
            "name": "Sri SiddiVinayaka Silk Sarees",
            "whatsapp_number": "+917989888858",
            "address": "4/386, Sivanagar, Dharmavaram, 515671",
            "policies": {
                "shipping": "Free shipping across India. Delivery in 3-5 working days.",
                "returns": "Easy 7 day exchange for genuine manufacturing defects with unboxing video.",
                "faqs": "Dharmavaram pure silk sarees with zari border. Running blouse included."
            }
        }
        put_res = self.client.put("/api/brand/profile", json=profile_update_payload, headers=headers)
        
        # Verify 200 status code (not 500 or CORS failure)
        assert put_res.status_code == 200
        updated_profile = put_res.json()
        assert updated_profile["whatsapp_number"] == "+917989888858"
        assert updated_profile["policies"]["shipping"] == "Free shipping across India. Delivery in 3-5 working days."
        
        # Verify CORS origin header is present
        assert put_res.headers.get("access-control-allow-origin") == "https://closely-frontend.onrender.com"
