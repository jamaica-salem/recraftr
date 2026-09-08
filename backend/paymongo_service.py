"""PayMongo payment gateway integration module for Recraftr.

Handles:
- Server-side package validation (prevents client price/credit tampering)
- PayMongo Hosted Checkout session creation
- Cryptographic webhook signature verification (HMAC-SHA256)
- Mock checkout fallback for local testing prior to live/test key configuration
"""
import os
import hmac
import hashlib
import time
import base64
import logging
from typing import Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger("recraftr.paymongo")

PAYMONGO_SECRET_KEY = os.environ.get("PAYMONGO_SECRET_KEY", "").strip()
PAYMONGO_PUBLIC_KEY = os.environ.get("PAYMONGO_PUBLIC_KEY", "").strip()
PAYMONGO_WEBHOOK_SECRET = os.environ.get("PAYMONGO_WEBHOOK_SECRET", "").strip()

PAYMONGO_API_BASE = "https://api.paymongo.com/v1"

# Authoritative server-side package definitions
# Never trust amounts, currencies, or credits sent by the client.
PACKAGES: Dict[str, Dict[str, Any]] = {
    "single": {
        "id": "single",
        "name": "Single Try",
        "description": "1 Full ATS Optimization & Tailored Application",
        "credits": 1,
        "amount_php": 49.00,
        "amount_centavos": 4900,  # ₱49.00
        "amount_usd": 1.99,
        "amount_centavos_usd": 11500,  # ~$1.99 USD equivalent (~₱115)
        "popular": False,
        "badge": "Trial",
    },
    "starter": {
        "id": "starter",
        "name": "Starter",
        "description": "20 AI Resume Optimizations & ATS Analyses",
        "credits": 20,
        "amount_php": 99.00,
        "amount_centavos": 9900,  # ₱99.00
        "amount_usd": 7.99,
        "amount_centavos_usd": 46300,  # ~$7.99 USD equivalent (~₱463)
        "popular": False,
        "badge": "Budget Favorite",
    },
    "job_hunter": {
        "id": "job_hunter",
        "name": "Job Hunter",
        "description": "60 AI Resume Optimizations + Cover Letters & Bullet Rewriter",
        "credits": 60,
        "amount_php": 249.00,
        "amount_centavos": 24900,  # ₱249.00
        "amount_usd": 14.99,
        "amount_centavos_usd": 86900,  # ~$14.99 USD equivalent (~₱869)
        "popular": True,
        "badge": "Most Popular ⭐",
    },
    "career_hunter": {
        "id": "career_hunter",
        "name": "Career Hunter",
        "description": "150 AI Optimizations + Priority Support & Unlimited Compares",
        "credits": 150,
        "amount_php": 499.00,
        "amount_centavos": 49900,  # ₱499.00
        "amount_usd": 19.99,
        "amount_centavos_usd": 115900,  # ~$19.99 USD equivalent (~₱1,159)
        "popular": False,
        "badge": "Best Value",
    },
}

# In-App Bulk Top-Up / Refill Packages (Convenience pricing with emergency refill premium)
TOPUP_PACKAGES: Dict[str, Dict[str, Any]] = {
    "topup_5": {
        "id": "topup_5",
        "name": "5 Applications",
        "description": "5 AI Resume Optimizations & ATS Analyses",
        "credits": 5,
        "amount_php": 39.00,
        "amount_centavos": 3900,  # ₱39.00 (₱7.80/app)
        "amount_usd": 1.99,
        "amount_centavos_usd": 11500,  # ~$1.99 USD (~₱115)
        "popular": False,
        "badge": "Micro Refill",
    },
    "topup_10": {
        "id": "topup_10",
        "name": "10 Applications",
        "description": "10 AI Resume Optimizations + Cover Letters",
        "credits": 10,
        "amount_php": 69.00,
        "amount_centavos": 6900,  # ₱69.00 (₱6.90/app)
        "amount_usd": 3.49,
        "amount_centavos_usd": 20200,  # ~$3.49 USD (~₱202)
        "popular": False,
        "badge": "Quick Refill",
    },
    "topup_20": {
        "id": "topup_20",
        "name": "20 Applications",
        "description": "20 AI Resume Optimizations, Cover Letters & Rewrites",
        "credits": 20,
        "amount_php": 119.00,
        "amount_centavos": 11900,  # ₱119.00 (₱5.95/app - full Starter pack is ₱99)
        "amount_usd": 5.99,
        "amount_centavos_usd": 34700,  # ~$5.99 USD (~₱347)
        "popular": True,
        "badge": "20 Pack Refill",
    },
    "topup_50": {
        "id": "topup_50",
        "name": "50 Applications",
        "description": "50 AI Optimizations + Priority Processing & Full Suite",
        "credits": 50,
        "amount_php": 249.00,
        "amount_centavos": 24900,  # ₱249.00 (₱4.98/app - gives 50 vs Job Hunter's 60)
        "amount_usd": 11.99,
        "amount_centavos_usd": 69500,  # ~$11.99 USD (~₱695)
        "popular": False,
        "badge": "50 Pack Refill ⭐",
    },
}

# Aliases for backward compatibility with earlier package IDs
PACKAGE_ALIASES = {
    "pro": "job_hunter",
    "booster": "career_hunter",
    "topup_25": "topup_20",
}


def calculate_custom_topup(credits: int, currency: str = "PHP") -> Dict[str, Any]:
    """
    Calculate authoritative server-side pricing for custom credit purchases.
    Enforces minimum 5 credits, maximum 500 credits.
    """
    count = max(5, min(500, int(credits)))
    is_usd = currency.upper() == "USD"

    # Convenience tiered rate per application
    if count < 10:
        rate_php = 7.80
        rate_usd = 0.40
    elif count < 20:
        rate_php = 6.90
        rate_usd = 0.35
    elif count < 50:
        rate_php = 5.95
        rate_usd = 0.30
    else:
        rate_php = 4.95
        rate_usd = 0.24

    total_php = round(count * rate_php, 2)
    total_usd = round(count * rate_usd, 2)
    centavos_php = int(total_php * 100)
    centavos_usd_settle = int(round(total_usd * 58.0 * 100))

    if is_usd:
        amount = total_usd
        curr = "USD"
        amount_centavos = centavos_usd_settle
        amount_php_settle = centavos_usd_settle / 100.0
        effective = f"${rate_usd:.2f}/app"
    else:
        amount = total_php
        curr = "PHP"
        amount_centavos = centavos_php
        amount_php_settle = total_php
        effective = f"₱{rate_php:.2f}/app"

    return {
        "id": f"custom_{count}",
        "name": f"{count} Custom Applications",
        "description": f"{count} AI Resume Optimizations & ATS Applications (Custom Refill)",
        "credits": count,
        "amount": amount,
        "currency": curr,
        "amount_centavos": amount_centavos,
        "amount_php_settle": amount_php_settle,
        "effective_price": effective,
        "popular": False,
        "badge": "Custom Refill",
        "is_topup": True,
        "is_custom": True,
    }


def get_package(
    package_id: str,
    currency: str = "PHP",
    custom_credits: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve package specification from authoritative catalog with currency & custom credits support."""
    if not package_id:
        return None
    clean_id = package_id.lower().strip()

    # Detect if currency is embedded in ID (e.g. starter_usd, job_hunter_intl)
    is_usd = currency.upper() == "USD"
    if clean_id.endswith("_usd") or clean_id.endswith("_intl"):
        clean_id = clean_id.rsplit("_", 1)[0]
        is_usd = True

    # Handle custom credits request
    if clean_id.startswith("custom"):
        cnt = custom_credits
        if not cnt:
            parts = clean_id.split("_")
            if len(parts) > 1 and parts[1].isdigit():
                cnt = int(parts[1])
            else:
                cnt = 10
        return calculate_custom_topup(cnt, currency="USD" if is_usd else "PHP")

    canonical_id = PACKAGE_ALIASES.get(clean_id, clean_id)
    base_pkg = PACKAGES.get(canonical_id) or TOPUP_PACKAGES.get(canonical_id)
    if not base_pkg:
        return None

    pkg = dict(base_pkg)
    if is_usd:
        pkg["currency"] = "USD"
        pkg["amount"] = base_pkg["amount_usd"]
        pkg["amount_centavos"] = base_pkg["amount_centavos_usd"]
        pkg["amount_php_settle"] = base_pkg["amount_centavos_usd"] / 100.0
    else:
        pkg["currency"] = "PHP"
        pkg["amount"] = base_pkg["amount_php"]
        pkg["amount_centavos"] = base_pkg["amount_centavos"]
        pkg["amount_php_settle"] = base_pkg["amount_php"]

    return pkg


def get_packages_list(currency: str = "PHP") -> list:
    """Return all public packages formatted for frontend display according to currency."""
    is_usd = currency.upper() == "USD"
    result = []
    for p in PACKAGES.values():
        if is_usd:
            amount = p["amount_usd"]
            curr = "USD"
            effective = f"${(amount / p['credits']):.2f}/app"
        else:
            amount = p["amount_php"]
            curr = "PHP"
            per_app = amount / p["credits"]
            effective = f"₱{per_app:.2f}/app" if per_app < 10 else f"₱{int(per_app)}/app"

        result.append({
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "credits": p["credits"],
            "amount": amount,
            "currency": curr,
            "effective_price": effective,
            "popular": p["popular"],
            "badge": p["badge"],
            "is_topup": False,
        })
    return result


def get_topups_list(currency: str = "PHP") -> list:
    """Return all in-app top-up packages formatted for frontend display according to currency."""
    is_usd = currency.upper() == "USD"
    result = []
    for p in TOPUP_PACKAGES.values():
        if is_usd:
            amount = p["amount_usd"]
            curr = "USD"
            effective = f"${(amount / p['credits']):.2f}/app"
        else:
            amount = p["amount_php"]
            curr = "PHP"
            per_app = amount / p["credits"]
            effective = f"₱{per_app:.2f}/app" if per_app < 10 else f"₱{int(per_app)}/app"

        result.append({
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "credits": p["credits"],
            "amount": amount,
            "currency": curr,
            "effective_price": effective,
            "popular": p["popular"],
            "badge": p["badge"],
            "is_topup": True,
        })
    return result


async def create_checkout_session(
    user_id: str,
    user_email: str,
    user_name: str,
    package_id: str,
    success_url: str,
    cancel_url: str,
    currency: str = "PHP",
    custom_credits: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Creates a PayMongo Checkout Session for the specified package.
    If PAYMONGO_SECRET_KEY is not configured or in sandbox mock mode,
    returns a local simulation URL so testing can proceed seamlessly.
    """
    pkg = get_package(package_id, currency=currency, custom_credits=custom_credits)
    if not pkg:
        raise ValueError(f"Invalid package selected: '{package_id}'")

    # If secret key is not configured or contains placeholder, return a test simulator URL
    is_mock = (
        not PAYMONGO_SECRET_KEY
        or "your_live" in PAYMONGO_SECRET_KEY
        or "your_test" in PAYMONGO_SECRET_KEY
    )

    if is_mock:
        logger.info(f"Using PayMongo Mock Checkout for user {user_id}, package {pkg['id']} ({pkg['currency']})")
        mock_session_id = f"cs_mock_{user_id[:8]}_{int(time.time())}"
        clean_success = success_url.replace("{CHECKOUT_SESSION_ID}", mock_session_id)
        sep = "&" if "?" in clean_success else "?"
        mock_checkout_url = f"{clean_success}{sep}mock=true&pkg={pkg['id']}&curr={pkg['currency']}"

        return {
            "checkout_session_id": mock_session_id,
            "checkout_url": mock_checkout_url,
            "amount": pkg["amount"],
            "currency": pkg["currency"],
            "credits": pkg["credits"],
            "is_mock": True,
        }

    # Live or Test PayMongo API Request
    auth_header = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_header}",
        "Accept": "application/json",
    }

    item_desc = (
        f"Recraftr {pkg['name']} ({pkg['credits']} Credits - ${pkg['amount']:.2f} USD)"
        if pkg["currency"] == "USD"
        else f"Recraftr {pkg['name']} ({pkg['credits']} Credits - ₱{pkg['amount']:.2f} PHP)"
    )

    payload = {
        "data": {
            "attributes": {
                "billing": {
                    "name": user_name or "Valued Customer",
                    "email": user_email or "customer@example.com",
                },
                "send_email_receipt": True,
                "show_description": True,
                "show_line_items": True,
                "description": item_desc,
                "line_items": [
                    {
                        "currency": "PHP",
                        "amount": pkg["amount_centavos"],
                        "description": pkg["description"],
                        "name": f"Recraftr {pkg['name']}",
                        "quantity": 1,
                    }
                ],
                "payment_method_types": ["card", "gcash", "paymaya", "grab_pay"],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "user_id": str(user_id),
                    "package_id": pkg["id"],
                    "credits": str(pkg["credits"]),
                    "currency": pkg["currency"],
                },
            }
        }
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{PAYMONGO_API_BASE}/checkout_sessions",
                json=payload,
                headers=headers,
            )
        except Exception as exc:
            logger.error(f"PayMongo connection error: {exc}")
            raise RuntimeError(f"Could not connect to payment gateway: {exc}")

    if resp.status_code not in (200, 201):
        err_detail = resp.text
        try:
            err_json = resp.json()
            errors = err_json.get("errors", [])
            if errors:
                err_detail = errors[0].get("detail", err_detail)
        except Exception:
            pass
        logger.error(f"PayMongo API returned {resp.status_code}: {err_detail}")
        raise RuntimeError(f"PayMongo error: {err_detail}")

    data = resp.json().get("data", {})
    session_id = data.get("id")
    attributes = data.get("attributes", {})
    checkout_url = attributes.get("checkout_url")

    if not checkout_url:
        raise RuntimeError("No checkout URL returned from PayMongo.")

    return {
        "checkout_session_id": session_id,
        "checkout_url": checkout_url,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "amount_php": pkg["amount_php_settle"],
        "credits": pkg["credits"],
        "is_mock": False,
    }


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    webhook_secret: Optional[str] = None,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verifies the Paymongo-Signature header against the raw request payload.
    Header format: t=timestamp,te=test_signature,li=live_signature
    Expected signature: HMAC-SHA256(secret, f"{t}.{raw_body}")
    """
    secret = (webhook_secret or PAYMONGO_WEBHOOK_SECRET).strip()
    if not secret or not signature_header:
        # If no webhook secret is configured, reject for security
        return False

    parts = {}
    for item in signature_header.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            parts[k] = v

    timestamp_str = parts.get("t")
    if not timestamp_str:
        return False

    try:
        ts = int(timestamp_str)
        # Verify timestamp tolerance to defend against replay attacks
        if abs(time.time() - ts) > tolerance_seconds:
            logger.warning("PayMongo webhook timestamp out of tolerance")
            return False
    except ValueError:
        return False

    # Check test signature (te) or live signature (li)
    provided_signature = parts.get("te") or parts.get("li")
    if not provided_signature:
        return False

    signed_payload = f"{timestamp_str}.".encode("utf-8") + raw_body
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, provided_signature)
