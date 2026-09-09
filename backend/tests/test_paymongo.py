"""Unit and integration tests for PayMongo payment integration (Phase 18)."""
import time
import hmac
import hashlib
import json
import pytest
from paymongo_service import (
    PACKAGES,
    TOPUP_PACKAGES,
    get_package,
    get_packages_list,
    get_topups_list,
    verify_webhook_signature,
)


def test_package_catalog():
    """Verify package definitions, prices, and centavo conversions in both PHP and USD."""
    expected_tiers = ["single", "starter", "job_hunter", "career_hunter"]
    for tier in expected_tiers:
        assert tier in PACKAGES
        pkg_php = get_package(tier, currency="PHP")
        assert pkg_php is not None
        assert pkg_php["credits"] > 0
        assert pkg_php["currency"] == "PHP"
        assert pkg_php["amount"] > 0
        assert pkg_php["amount_centavos"] == int(pkg_php["amount"] * 100)

        pkg_usd = get_package(tier, currency="USD")
        assert pkg_usd is not None
        assert pkg_usd["credits"] == pkg_php["credits"]
        assert pkg_usd["currency"] == "USD"
        assert pkg_usd["amount"] > 0
        assert pkg_usd["amount_centavos"] > 0

    # Test backward compatibility aliases
    assert get_package("pro")["id"] == "job_hunter"
    assert get_package("booster")["id"] == "career_hunter"
    assert get_package("topup_25")["id"] == "topup_20"


def test_topup_packages():
    """Verify in-app convenience top-up packages in both PHP and USD."""
    expected_topups = ["topup_5", "topup_10", "topup_20", "topup_50"]
    for tid in expected_topups:
        assert tid in TOPUP_PACKAGES
        pkg_php = get_package(tid, currency="PHP")
        assert pkg_php is not None
        assert pkg_php["credits"] > 0
        assert pkg_php["amount"] > 0
        assert pkg_php["currency"] == "PHP"

        pkg_usd = get_package(tid, currency="USD")
        assert pkg_usd is not None
        assert pkg_usd["credits"] == pkg_php["credits"]
        assert pkg_usd["currency"] == "USD"
        assert pkg_usd["amount"] > 0

    topups_php = get_topups_list(currency="PHP")
    assert len(topups_php) == 4
    assert all(t["is_topup"] is True for t in topups_php)

    topups_usd = get_topups_list(currency="USD")
    assert len(topups_usd) == 4
    assert all(t["currency"] == "USD" for t in topups_usd)

    # Verify convenience pricing logic: 20-app topup (₱119) is more expensive than 20-app full Starter (₱99)
    starter = get_package("starter", currency="PHP")
    topup_20 = get_package("topup_20", currency="PHP")
    assert topup_20["amount"] > starter["amount"]


def test_custom_topup_calculator():
    """Verify custom topup dynamic pricing, bounds, and rate tiers."""
    from paymongo_service import calculate_custom_topup

    # 1. Bounds enforcement (min 5, max 500)
    min_res = calculate_custom_topup(1, currency="PHP")
    assert min_res["credits"] == 5
    assert min_res["amount"] == 39.00  # 5 * 7.80

    max_res = calculate_custom_topup(600, currency="PHP")
    assert max_res["credits"] == 500

    # 2. Tier checks PHP
    # 15 apps: 15 * 6.90 = 103.50
    t15_php = calculate_custom_topup(15, currency="PHP")
    assert t15_php["credits"] == 15
    assert t15_php["amount"] == 103.50
    assert t15_php["currency"] == "PHP"

    # 3. Tier checks USD
    # 15 apps: 15 * 0.35 = 5.25
    t15_usd = calculate_custom_topup(15, currency="USD")
    assert t15_usd["credits"] == 15
    assert t15_usd["amount"] == 5.25
    assert t15_usd["currency"] == "USD"

    # 4. Integration with get_package
    pkg_custom_str = get_package("custom_30", currency="PHP")
    assert pkg_custom_str["credits"] == 30
    assert pkg_custom_str["amount"] == round(30 * 5.95, 2)

    pkg_custom_param = get_package("custom", custom_credits=50, currency="USD")
    assert pkg_custom_param["credits"] == 50
    assert pkg_custom_param["amount"] == round(50 * 0.24, 2)


def test_get_packages_list():
    """Verify list formatting for public API in both currencies."""
    # PHP list
    pkgs_php = get_packages_list(currency="PHP")
    assert len(pkgs_php) == 4
    ids = [p["id"] for p in pkgs_php]
    assert "single" in ids
    assert "starter" in ids
    assert "job_hunter" in ids
    assert "career_hunter" in ids
    assert all(p["currency"] == "PHP" for p in pkgs_php)
    assert any("₱" in p["effective_price"] for p in pkgs_php)

    # USD list
    pkgs_usd = get_packages_list(currency="USD")
    assert len(pkgs_usd) == 4
    assert all(p["currency"] == "USD" for p in pkgs_usd)
    assert any("$" in p["effective_price"] for p in pkgs_usd)


def test_webhook_signature_verification():
    """Test cryptographic HMAC-SHA256 signature verification."""
    secret = "whsec_test_secret_12345"
    payload = json.dumps({"data": {"id": "evt_test", "attributes": {"type": "checkout_session.payment.paid"}}}).encode("utf-8")
    timestamp = int(time.time())

    signed_content = f"{timestamp}.".encode("utf-8") + payload
    valid_sig = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()

    header_valid = f"t={timestamp},te={valid_sig}"

    # 1. Valid signature
    assert verify_webhook_signature(payload, header_valid, webhook_secret=secret) is True

    # 2. Tampered payload
    tampered_payload = payload + b" "
    assert verify_webhook_signature(tampered_payload, header_valid, webhook_secret=secret) is False

    # 3. Wrong secret
    assert verify_webhook_signature(payload, header_valid, webhook_secret="wrong_secret") is False

    # 4. Outdated timestamp (replay attack defense)
    old_timestamp = timestamp - 400
    old_signed = f"{old_timestamp}.".encode("utf-8") + payload
    old_sig = hmac.new(secret.encode("utf-8"), old_signed, hashlib.sha256).hexdigest()
    old_header = f"t={old_timestamp},te={old_sig}"
    assert verify_webhook_signature(payload, old_header, webhook_secret=secret, tolerance_seconds=300) is False


@pytest.mark.anyio
async def test_mock_checkout_session_creation():
    """Verify PayMongo checkout session generation and URL formatting."""
    from paymongo_service import create_checkout_session

    res = await create_checkout_session(
        user_id="user_test_123",
        user_email="test@example.com",
        user_name="Test User",
        package_id="topup_10",
        success_url="http://localhost:3001/checkout/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:3001/pricing?status=cancelled",
        currency="PHP",
    )

    assert res is not None
    assert "checkout_session_id" in res
    assert "checkout_url" in res
    assert res["credits"] == 10
    assert res["currency"] == "PHP"
    assert res["amount"] == 69.00
    assert res["is_mock"] is True


@pytest.mark.anyio
async def test_invalid_package_checkout():
    """Verify invalid package requests are safely rejected."""
    from paymongo_service import create_checkout_session

    with pytest.raises(ValueError, match="Invalid package selected"):
        await create_checkout_session(
            user_id="user_test_123",
            user_email="test@example.com",
            user_name="Test User",
            package_id="non_existent_pkg_id",
            success_url="http://localhost:3001/success",
            cancel_url="http://localhost:3001/cancel",
        )

