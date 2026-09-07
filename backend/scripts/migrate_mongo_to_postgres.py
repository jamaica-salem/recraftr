#!/usr/bin/env python3
"""Data migration script: MongoDB -> PostgreSQL / Supabase for Recraftr.

Transfers existing users, resumes, analyses, and applications while preserving
UUID IDs and maintaining foreign key referential integrity.

Usage:
    # Dry run inspection (reads MongoDB and prints what would be migrated):
    python scripts/migrate_mongo_to_postgres.py --dry-run

    # Execute actual migration:
    python scripts/migrate_mongo_to_postgres.py
"""
import os
import sys
import uuid
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path so we can import db
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
import db


def parse_uuid(val: Any) -> uuid.UUID:
    """Safely convert string or UUID to uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except Exception:
        return uuid.uuid4()


def parse_datetime(val: Any) -> datetime:
    """Parse ISO timestamp or datetime to timezone-aware datetime."""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


async def migrate(dry_run: bool = False):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "recraftr")
    database_url = os.environ.get("DATABASE_URL")

    print("=" * 60)
    print("Recraftr: MongoDB -> PostgreSQL / Supabase Migration")
    print("=" * 60)
    print(f"Source MongoDB: {mongo_url} [db: {db_name}]")
    print(f"Target PostgreSQL: {database_url if database_url else '(No DATABASE_URL configured)'}")
    print(f"Mode: {'DRY RUN (read-only inspection)' if dry_run else 'LIVE EXECUTION'}")
    print("-" * 60)

    # 1. Connect to MongoDB
    mongo_client = AsyncIOMotorClient(mongo_url)
    m_db = mongo_client[db_name]

    # Fetch source counts
    users_count = await m_db.users.count_documents({})
    resumes_count = await m_db.resumes.count_documents({})
    analyses_count = await m_db.analyses.count_documents({})
    applications_count = await m_db.applications.count_documents({})

    print(f"Found in MongoDB:")
    print(f"  - Users/Profiles: {users_count}")
    print(f"  - Resumes:        {resumes_count}")
    print(f"  - Analyses:       {analyses_count}")
    print(f"  - Applications:   {applications_count}")
    print("-" * 60)

    if dry_run:
        print("[DRY RUN COMPLETE] Source data inspected successfully.")
        print("To execute real migration, ensure DATABASE_URL is set and run without --dry-run.")
        return

    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required to execute migration.")
        sys.exit(1)

    # 2. Connect to PostgreSQL
    engine = db.engine
    async_session = db.AsyncSessionLocal

    valid_user_ids = set()
    valid_resume_ids = set()

    async with async_session() as session:
        async with session.begin():
            # Migrate Users -> Profiles
            print("\n1. Migrating Users -> Profiles...")
            async for u in m_db.users.find({}):
                uid = parse_uuid(u.get("id") or u.get("_id"))
                email = str(u.get("email", "")).strip().lower()
                name = str(u.get("name", "")).strip() or email.split("@")[0] or "User"
                created_at = parse_datetime(u.get("created_at"))

                # Check if exists
                stmt = select(db.Profile).where(db.Profile.email == email)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    profile = db.Profile(
                        id=uid,
                        email=email,
                        name=name,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                    session.add(profile)
                    valid_user_ids.add(uid)
                    print(f"   [+] Profile: {email} ({uid})")
                else:
                    valid_user_ids.add(existing.id)
                    print(f"   [=] Profile exists: {email}")

            await session.flush()

            # Migrate Resumes
            print("\n2. Migrating Resumes...")
            async for r in m_db.resumes.find({}):
                rid = parse_uuid(r.get("id") or r.get("_id"))
                user_id = parse_uuid(r.get("user_id"))
                if user_id not in valid_user_ids:
                    print(f"   [!] Skipping orphaned resume {rid}: user_id {user_id} not found")
                    continue

                filename = r.get("filename", "resume.pdf")
                text_content = r.get("text", "")
                created_at = parse_datetime(r.get("created_at"))

                stmt = select(db.Resume).where(db.Resume.id == rid)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    resume = db.Resume(
                        id=rid,
                        user_id=user_id,
                        filename=filename,
                        text=text_content,
                        char_count=len(text_content),
                        created_at=created_at,
                    )
                    session.add(resume)
                    valid_resume_ids.add(rid)
                    print(f"   [+] Resume: {filename} ({rid})")
                else:
                    valid_resume_ids.add(existing.id)
                    print(f"   [=] Resume exists: {filename}")

            await session.flush()

            # Migrate Analyses
            print("\n3. Migrating Analyses...")
            async for a in m_db.analyses.find({}):
                aid = parse_uuid(a.get("id") or a.get("_id"))
                user_id = parse_uuid(a.get("user_id"))
                if user_id not in valid_user_ids:
                    print(f"   [!] Skipping orphaned analysis {aid}: user_id {user_id} not found")
                    continue

                raw_resume_id = a.get("resume_id")
                resume_id = parse_uuid(raw_resume_id) if raw_resume_id else None
                if resume_id and resume_id not in valid_resume_ids:
                    resume_id = None

                created_at = parse_datetime(a.get("created_at"))
                updated_at = parse_datetime(a.get("updated_at") or a.get("created_at"))

                stmt = select(db.Analysis).where(db.Analysis.id == aid)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    analysis = db.Analysis(
                        id=aid,
                        user_id=user_id,
                        resume_id=resume_id,
                        resume_filename=a.get("resume_filename"),
                        job_title=a.get("job_title", "Untitled Role"),
                        job_description=a.get("job_description", ""),
                        analysis=a.get("analysis") if isinstance(a.get("analysis"), dict) else None,
                        model=a.get("model", "gemini-3.5-flash"),
                        optimized_resume=a.get("optimized_resume"),
                        predicted_ats_score=a.get("predicted_ats_score"),
                        changes_summary=a.get("changes_summary", []),
                        cover_letter=a.get("cover_letter"),
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                    session.add(analysis)
                    print(f"   [+] Analysis: {a.get('job_title')} ({aid})")

            await session.flush()

            # Migrate Applications
            print("\n4. Migrating Applications...")
            async for app in m_db.applications.find({}):
                appid = parse_uuid(app.get("id") or app.get("_id"))
                user_id = parse_uuid(app.get("user_id"))
                if user_id not in valid_user_ids:
                    print(f"   [!] Skipping orphaned application {appid}: user_id {user_id} not found")
                    continue

                created_at = parse_datetime(app.get("created_at"))
                updated_at = parse_datetime(app.get("updated_at") or app.get("created_at"))

                stmt = select(db.Application).where(db.Application.id == appid)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    application = db.Application(
                        id=appid,
                        user_id=user_id,
                        job_title=app.get("job_title", "Target Role"),
                        company_name=app.get("company_name", "Target Company"),
                        location=app.get("location", ""),
                        status=app.get("status", "applied"),
                        ats_score=app.get("ats_score"),
                        job_description=app.get("job_description", ""),
                        optimized_resume=app.get("optimized_resume", ""),
                        cover_letter=app.get("cover_letter", ""),
                        notes=app.get("notes", ""),
                        resume_filename=app.get("resume_filename", ""),
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                    session.add(application)
                    print(f"   [+] Application: {app.get('job_title')} at {app.get('company_name')} ({appid})")

            await session.flush()

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Recraftr MongoDB to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Inspect source MongoDB data without writing to PostgreSQL")
    args = parser.parse_args()

    asyncio.run(migrate(dry_run=args.dry_run))
