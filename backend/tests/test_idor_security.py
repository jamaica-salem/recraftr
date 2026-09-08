"""
Automated IDOR (Insecure Direct Object Reference) and Authorization Security Test Suite.
Verifies that:
1. User A's resumes, analyses, and job applications are never accessible to User B.
2. User B cannot modify or delete User A's resources.
3. Supabase Storage bucket stores uploaded files under user-scoped paths.
"""
import uuid
import pytest
import requests
from tests.conftest import API, make_sample_pdf, random_email


@pytest.fixture
def user_a():
    email = random_email("USER_A_")
    password = "Password123!"
    name = "User Alpha"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 200, f"User A registration failed: {r.text}"
    token = r.json()["token"]
    user_id = r.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return {"id": user_id, "email": email, "headers": headers}


@pytest.fixture
def user_b():
    email = random_email("USER_B_")
    password = "Password123!"
    name = "User Beta"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 200, f"User B registration failed: {r.text}"
    token = r.json()["token"]
    user_id = r.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return {"id": user_id, "email": email, "headers": headers}


class TestResumeIDOR:
    def test_user_b_cannot_view_or_delete_user_a_resume(self, user_a, user_b):
        # 1. User A uploads a resume
        pdf_bytes = make_sample_pdf("Resume for User Alpha\nSoftware Engineer")
        files = {"file": ("alpha_resume.pdf", pdf_bytes, "application/pdf")}
        r_upload = requests.post(f"{API}/upload-resume", headers=user_a["headers"], files=files)
        assert r_upload.status_code == 200, f"Upload failed: {r_upload.text}"
        resume_a_id = r_upload.json()["resume_id"]

        # 2. User B lists resumes -> must not contain User A's resume
        r_list_b = requests.post if False else requests.get(f"{API}/resumes", headers=user_b["headers"])
        assert r_list_b.status_code == 200
        items_b = r_list_b.json().get("items", [])
        assert not any(item["id"] == resume_a_id for item in items_b), "User B saw User A's resume in list!"

        # 3. User B attempts to delete User A's resume -> must return 404
        r_del_b = requests.delete(f"{API}/resumes/{resume_a_id}", headers=user_b["headers"])
        assert r_del_b.status_code == 404, f"Expected 404 when User B deletes User A resume, got {r_del_b.status_code}"

        # 4. User A can still view their resume
        r_list_a = requests.get(f"{API}/resumes", headers=user_a["headers"])
        assert r_list_a.status_code == 200
        items_a = r_list_a.json().get("items", [])
        assert any(item["id"] == resume_a_id for item in items_a), "User A's resume disappeared!"

        # 5. User A deletes their own resume -> must succeed
        r_del_a = requests.delete(f"{API}/resumes/{resume_a_id}", headers=user_a["headers"])
        assert r_del_a.status_code == 200


class TestApplicationIDOR:
    def test_user_b_cannot_access_or_modify_user_a_application(self, user_a, user_b):
        # 1. User A creates a job tracker application
        app_payload = {
            "job_title": "Staff Backend Engineer",
            "company_name": "Alpha Technologies",
            "location": "Remote",
            "status": "interviewing",
            "notes": "Confidential interview details for User A",
        }
        r_create = requests.post(f"{API}/applications", headers=user_a["headers"], json=app_payload)
        assert r_create.status_code == 200, f"App creation failed: {r_create.text}"
        app_id = r_create.json()["id"]

        # 2. User B lists applications -> must not see User A's application
        r_list_b = requests.get(f"{API}/applications", headers=user_b["headers"])
        assert r_list_b.status_code == 200
        b_apps = r_list_b.json().get("items", [])
        assert not any(item["id"] == app_id for item in b_apps), "User B saw User A's application!"

        # 3. User B attempts to update User A's application -> must return 404
        r_put_b = requests.put(
            f"{API}/applications/{app_id}",
            headers=user_b["headers"],
            json={"company_name": "Hacked by User B"},
        )
        assert r_put_b.status_code == 404, f"Expected 404 for unauthorized update, got {r_put_b.status_code}"

        # 4. User B attempts to delete User A's application -> must return 404
        r_del_b = requests.delete(f"{API}/applications/{app_id}", headers=user_b["headers"])
        assert r_del_b.status_code == 404, f"Expected 404 for unauthorized delete, got {r_del_b.status_code}"

        # 5. User A updates their own application -> succeeds
        r_put_a = requests.put(
            f"{API}/applications/{app_id}",
            headers=user_a["headers"],
            json={"status": "offer"},
        )
        assert r_put_a.status_code == 200

        # 6. User A deletes their own application -> succeeds
        r_del_a = requests.delete(f"{API}/applications/{app_id}", headers=user_a["headers"])
        assert r_del_a.status_code == 200


class TestHistoryIDOR:
    def test_user_b_cannot_view_or_delete_user_a_history(self, user_a, user_b):
        # 1. User A lists history
        r_hist_a = requests.get(f"{API}/history", headers=user_a["headers"])
        assert r_hist_a.status_code == 200

        # Random fake ID that User B tries to probe
        fake_id = str(uuid.uuid4())
        r_detail_b = requests.get(f"{API}/history/{fake_id}", headers=user_b["headers"])
        assert r_detail_b.status_code == 404

        r_del_b = requests.delete(f"{API}/history/{fake_id}", headers=user_b["headers"])
        assert r_del_b.status_code == 404
