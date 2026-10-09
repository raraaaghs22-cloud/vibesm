"""Live AI grading tests for the new SYSTEM_PROMPT / N/A rubric behaviour.

Flow verified:
- Public YouTube link -> graded via url mode, letter grade in A/B/C/D, strengths/weaknesses non-empty,
  rubric sub-scores null.
- Private/nonexistent YouTube -> N/A with the exact Indonesian privacy weakness message, score 0,
  extraction_ok False, no AI call succeeded (video_mode None), rubric sub-scores null.
- Instagram unreachable URL -> same N/A result (yt-dlp download fails).

Grading is serialized server-side (LLM_LOCK) and may take ~60-120s. Each test polls up to 180s.
"""
import os
import re
import time
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
load_dotenv(Path(__file__).parent.parent.parent / 'frontend' / '.env')

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
PRIVACY_MSG = "Sistem gagal mengekstrak video (akun diprivasi/diblokir). Mohon tonton link secara manual."

db = MongoClient(MONGO_URL)[DB_NAME]


def _submit(payload):
    r = requests.post(f"{BASE_URL}/api/submissions", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _wait(name, timeout=180):
    end = time.time() + timeout
    rec = None
    while time.time() < end:
        rec = db.submissions.find_one({"full_name": name})
        if rec and rec.get("status") in ("draft", "failed", "final"):
            return rec
        time.sleep(5)
    return rec


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    db.submissions.delete_many({"full_name": {"$regex": "^TEST_LIVE_"}})


def test_public_youtube_grades_real_rubric():
    """Public first-ever YouTube video (Me at the zoo) must grade in A/B/C/D with non-empty IDN text."""
    name = "TEST_LIVE_YT_Public"
    _submit({"full_name": name, "class_name": "XI 2", "attendance_number": 5,
             "video_link": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    rec = _wait(name, timeout=200)
    assert rec is not None
    status = rec.get("status")
    # Must land as draft (graded) - processing/pending means timeout
    assert status == "draft", f"Expected draft, got {status}; error={rec.get('error')}"
    ai = rec.get("ai") or {}
    assert ai.get("video_mode") == "url", f"video_mode={ai.get('video_mode')}"
    grade = rec.get("ai_letter_grade")
    assert grade in ("A", "B", "C", "D"), f"Grade should be A/B/C/D, got {grade}"
    score = rec.get("ai_score")
    # Grade must match the server's letter_grade rule
    expected = "A" if score > 90 else "B" if score >= 80 else "C" if score >= 70 else "D"
    assert grade == expected, f"grade {grade} inconsistent with score {score} (expected {expected})"
    strengths = (rec.get("ai_strengths") or "").strip()
    weaknesses = (rec.get("ai_weaknesses") or "").strip()
    assert len(strengths) > 5 and strengths != "-"
    assert len(weaknesses) > 5 and weaknesses != "-"
    # Rubric sub-scores must be null after AI grading
    assert rec.get("content_score") is None
    assert rec.get("delivery_score") is None
    assert rec.get("technical_score") is None
    # final_score mirrors ai_score
    assert rec.get("final_score") == score
    assert rec.get("final_grade") == grade
    # Must look like Indonesian (contain at least one common ID word)
    blob = (strengths + " " + weaknesses).lower()
    assert re.search(r"\b(dan|yang|video|musik|siswa|penjelasan|tidak|lebih|sudah|bisa)\b", blob), \
        f"Strengths/weaknesses don't look like Indonesian: {blob[:200]}"


def test_private_youtube_returns_na():
    """Nonexistent YouTube id -> N/A, score 0, no AI call."""
    name = "TEST_LIVE_YT_Private"
    _submit({"full_name": name, "class_name": "XI 2", "attendance_number": 6,
             "video_link": "https://www.youtube.com/watch?v=aaaaaaaaaaa"})
    rec = _wait(name, timeout=120)
    assert rec is not None and rec.get("status") == "draft", f"status={rec and rec.get('status')}"
    assert rec.get("ai_score") == 0
    assert rec.get("ai_letter_grade") == "N/A"
    assert rec.get("final_score") == 0
    assert rec.get("final_grade") == "N/A"
    assert rec.get("ai_strengths") == "-"
    assert rec.get("ai_weaknesses") == PRIVACY_MSG
    assert rec.get("extraction_ok") is False
    ai = rec.get("ai") or {}
    assert ai.get("video_mode") is None
    assert rec.get("content_score") is None
    assert rec.get("delivery_score") is None
    assert rec.get("technical_score") is None


def test_instagram_unreachable_returns_na():
    """Instagram URL that yt-dlp cannot download -> same N/A result."""
    name = "TEST_LIVE_IG_Private"
    _submit({"full_name": name, "class_name": "XI 2", "attendance_number": 7,
             "video_link": "https://www.instagram.com/reel/DOES_NOT_EXIST_zzz/"})
    rec = _wait(name, timeout=240)
    assert rec is not None and rec.get("status") == "draft", f"status={rec and rec.get('status')}, err={rec and rec.get('error')}"
    assert rec.get("ai_score") == 0
    assert rec.get("ai_letter_grade") == "N/A"
    assert rec.get("ai_weaknesses") == PRIVACY_MSG
    assert rec.get("extraction_ok") is False
    assert (rec.get("ai") or {}).get("video_mode") is None
