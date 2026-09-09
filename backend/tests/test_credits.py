"""Unit and integration tests for Credits System (Phase 19).

Verifies:
- Server-side credit balance calculation
- Atomic credit deduction & negative balance prevention
- Concurrency race condition protection (2 requests on 1 credit -> exactly 1 succeeds)
- Automated credit refund on failed AI operations
- Credit transaction history ledger
"""
import pytest
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from db import Base, Profile, Purchase, CreditTransaction
from server import get_user_credits, deduct_user_credit, refund_user_credit

# Use in-memory SQLite for fast, isolated credit ledger tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def async_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.anyio
async def test_server_side_balance_calculation(async_session: AsyncSession):
    """Verify get_user_credits queries the latest credit transaction ledger balance."""
    user_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user_id)

    # Initially 0 balance
    bal = await get_user_credits(user_id, async_session)
    assert bal == 0

    # Add initial transaction (3 welcome credits)
    tx1 = CreditTransaction(
        id=uuid.uuid4(),
        user_id=user_uuid,
        amount=3,
        action_type="welcome_bonus",
        balance_after=3,
        metadata_json={},
    )
    async_session.add(tx1)
    await async_session.commit()

    bal = await get_user_credits(user_id, async_session)
    assert bal == 3


@pytest.mark.anyio
async def test_atomic_credit_deduction_and_negative_prevention(async_session: AsyncSession):
    """Verify atomic credit deduction and prevention of negative balance."""
    user_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user_id)

    # Profile setup
    profile = Profile(id=user_uuid, email="test_deduct@example.com", name="Deduct Test")
    tx_init = CreditTransaction(
        id=uuid.uuid4(),
        user_id=user_uuid,
        amount=2,
        action_type="purchase",
        balance_after=2,
    )
    async_session.add_all([profile, tx_init])
    await async_session.commit()

    # 1. First deduction (2 -> 1)
    ok, new_bal, msg = await deduct_user_credit(user_id, "analyze", async_session)
    assert ok is True
    assert new_bal == 1

    # 2. Second deduction (1 -> 0)
    ok2, new_bal2, msg2 = await deduct_user_credit(user_id, "optimize", async_session)
    assert ok2 is True
    assert new_bal2 == 0

    # 3. Third deduction attempt when 0 balance (Must fail & prevent negative)
    ok3, new_bal3, msg3 = await deduct_user_credit(user_id, "cover_letter", async_session)
    assert ok3 is False
    assert new_bal3 == 0
    assert "Insufficient AI credits" in msg3


@pytest.mark.anyio
async def test_failed_request_refund(async_session: AsyncSession):
    """Verify failed AI requests restore 1 credit to user balance."""
    user_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user_id)

    tx = CreditTransaction(
        id=uuid.uuid4(),
        user_id=user_uuid,
        amount=5,
        action_type="topup",
        balance_after=5,
    )
    async_session.add(tx)
    await async_session.commit()

    # Deduct 1 credit for AI task
    ok, new_bal, _ = await deduct_user_credit(user_id, "analyze", async_session)
    assert ok is True
    assert new_bal == 4

    # Simulate AI failure -> Refund
    ok_ref, refunded_bal = await refund_user_credit(user_id, "analyze", async_session, reason="AI Timeout")
    assert ok_ref is True
    assert refunded_bal == 5


@pytest.mark.anyio
async def test_concurrent_credit_deduction_protection():
    """
    CRITICAL PHASE 19 CONCURRENCY TEST:
    User has 1 credit. Two requests arrive simultaneously.
    Result: Exactly ONE succeeds, and ONE fails due to credit lock / balance check.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    user_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user_id)

    # Setup 1 initial credit
    async with session_factory() as session:
        profile = Profile(id=user_uuid, email="race@example.com", name="Race Test")
        tx = CreditTransaction(
            id=uuid.uuid4(),
            user_id=user_uuid,
            amount=1,
            action_type="topup",
            balance_after=1,
        )
        session.add_all([profile, tx])
        await session.commit()

    # Run 2 concurrent deductions
    async def task_deduct():
        async with session_factory() as session:
            return await deduct_user_credit(user_id, "ai_task", session)

    res_a, res_b = await asyncio.gather(task_deduct(), task_deduct())

    successes = [r for r in (res_a, res_b) if r[0] is True]
    failures = [r for r in (res_a, res_b) if r[0] is False]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"
    assert failures[0][1] == 0

    # Final balance must be 0
    async with session_factory() as session:
        final_bal = await get_user_credits(user_id, session)
        assert final_bal == 0

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
