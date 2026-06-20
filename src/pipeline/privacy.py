"""
Deterministic PII scrubber — Principle of Least Privilege (PoLP).

All text MUST pass through scrub_text() before it touches any LLM call.
This module is a pure function with no side effects and no external dependencies
beyond the standard library, so it can be imported and tested in isolation.

Patterns covered:
  - Email addresses
  - Phone numbers (E.164, US, international)
  - Employee / user IDs (internal account patterns)
  - Indian Aadhaar numbers (12-digit national ID)
  - Credit / debit card numbers (Luhn-checkable patterns)
  - AWS access keys and secret keys
  - IP addresses (v4 and v6)
  - Partial SSN patterns
"""

from __future__ import annotations

import re
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Pattern registry
# Each entry: (compiled_regex, replacement_placeholder)
# Order matters — more specific patterns must come before more general ones.
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # AWS Secret Access Key (40-char base64, always follows "aws_secret")
    (
        re.compile(
            r"(?i)(aws_secret_access_key\s*[:=]\s*)([A-Za-z0-9/+=]{40})",
            re.IGNORECASE,
        ),
        r"\1[AWS_SECRET_KEY]",
    ),
    # AWS Access Key ID (AKIA... 20 chars)
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[AWS_ACCESS_KEY_ID]",
    ),
    # Credit card numbers (13–19 digits, optionally space/dash separated)
    (
        re.compile(
            r"\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6(?:011|5[0-9]{2}))"
            r"[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{1,7}\b"
        ),
        "[CREDIT_CARD]",
    ),
    # Aadhaar number (12 digits, optionally space/dash separated, not starting with 0 or 1)
    (
        re.compile(r"\b[2-9][0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b"),
        "[AADHAAR]",
    ),
    # US SSN (xxx-xx-xxxx)
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN]",
    ),
    # International phone numbers: E.164 (+1-415-555-0192 / +44 20 7946 0958)
    (
        re.compile(
            r"\+?(?:1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
            r"(?:\s?(?:x|ext)\.?\s?\d{1,5})?"
        ),
        "[PHONE]",
    ),
    # Email addresses
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_ADDR]",
    ),
    # Internal employee / account IDs (ACC-USER-NNNNN pattern)
    (
        re.compile(r"\bACC-USER-\d{4,10}\b", re.IGNORECASE),
        "[EMPLOYEE_ID]",
    ),
    # Internal account IDs (ACC-NNNN)
    (
        re.compile(r"\bACC-\d{4,10}\b", re.IGNORECASE),
        "[ACCOUNT_ID]",
    ),
    # IPv4 addresses
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "[IP_ADDR]",
    ),
    # IPv6 addresses (abbreviated check — full colons pattern)
    (
        re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
            r"|\b(?:[0-9a-fA-F]{1,4}:)*:(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}\b"
        ),
        "[IP_ADDR_V6]",
    ),
]

# Fields that should be fully scrubbed to a placeholder when found in dicts
_SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "phone",
        "mobile",
        "contact_number",
        "personal_email",
        "home_address",
        "national_id",
        "aadhaar",
        "ssn",
        "credit_card",
        "card_number",
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
    }
)


def scrub_text(text: str) -> str:
    """
    Apply all PII patterns to ``text`` and return the scrubbed version.

    This function is pure and deterministic — identical inputs always
    produce identical outputs. Safe to call in hot paths (no I/O).
    """
    if not isinstance(text, str):
        return text
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def scrub_dict(data: Dict[str, Any], *, deep: bool = True) -> Dict[str, Any]:
    """
    Recursively scrub all string values in a dict.

    Fields whose names match _SENSITIVE_FIELD_NAMES are replaced wholesale
    with ``[REDACTED]`` regardless of content.  All other string values are
    passed through ``scrub_text``.

    Args:
        data: The input dictionary (mutated copy is returned; original unchanged).
        deep: If True, recurse into nested dicts and lists.

    Returns:
        A new dict with PII-scrubbed values.
    """
    if not isinstance(data, dict):
        return data

    result: Dict[str, Any] = {}
    for key, value in data.items():
        lower_key = key.lower().replace("-", "_")
        if lower_key in _SENSITIVE_FIELD_NAMES:
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = scrub_text(value)
        elif deep and isinstance(value, dict):
            result[key] = scrub_dict(value, deep=True)
        elif deep and isinstance(value, list):
            result[key] = [
                scrub_dict(item, deep=True) if isinstance(item, dict)
                else scrub_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result
