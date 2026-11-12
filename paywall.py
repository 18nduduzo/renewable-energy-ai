"""Unlock codes for paid downloads. No Streamlit and no database needed.

How it works
------------
You (the owner) generate a signed code for a customer with `make_codes.py`, using a secret
only you know (UNLOCK_SECRET). The app verifies the signature, so nobody can invent a valid
code without that secret. A code carries a tier, a customer id and an expiry date.

Code format:   TIER-CUSTOMER-YYYYMMDD-SIGNATURE        e.g.  PACK-ACME-20261231-9F2C41D07AB3

Tiers
  SLD   single line diagram PDF only
  PACK  complete drawing pack (cover, SLD, layout, mounting detail, BOM and schedules)

Limits you should know about (stateless codes)
  - A code can be shared with other people until it expires. Use short expiries (for example
    30 days for a monthly subscription) and put a customer id in REVOKED_CODES to cut one off.
  - It cannot count downloads. If you need per-download credits or automatic card payments,
    move to a small database (for example Supabase) and a payment provider that supports
    Eswatini. This module is the simple first step so you can start charging by EFT / mobile money.
"""

from __future__ import annotations

import datetime as _dt
import hmac
import re
from dataclasses import dataclass
from hashlib import sha256

TIER_SLD = "SLD"
TIER_PACK = "PACK"
TIERS = (TIER_SLD, TIER_PACK)

_CODE_RE = re.compile(r"^(SLD|PACK)-([A-Z0-9]{2,12})-(\d{8})-([0-9A-F]{12})$")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    tier: str | None = None
    customer: str | None = None
    expires: _dt.date | None = None
    reason: str = ""

    def can(self, sheet_set: str) -> bool:
        """sheet_set is 'sld' (SLD PDF) or 'pack' (complete pack)."""
        if not self.ok:
            return False
        if sheet_set == "sld":
            return self.tier in (TIER_SLD, TIER_PACK)
        if sheet_set == "pack":
            return self.tier == TIER_PACK
        return False


def clean_customer(name: str) -> str:
    """Letters and digits only, upper-case, 2 to 12 characters."""
    c = re.sub(r"[^A-Za-z0-9]", "", name or "").upper()[:12]
    if len(c) < 2:
        raise ValueError("Customer id needs at least 2 letters or digits.")
    return c


def _sign(secret: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), sha256).hexdigest()[:12].upper()


def make_code(secret: str, tier: str, customer: str, expires: _dt.date) -> str:
    if not secret:
        raise ValueError("A secret is required to make codes.")
    tier = tier.upper()
    if tier not in TIERS:
        raise ValueError(f"Tier must be one of {', '.join(TIERS)}.")
    body = f"{tier}-{clean_customer(customer)}-{expires:%Y%m%d}"
    return f"{body}-{_sign(secret, body)}"


def parse_revoked(text: str) -> frozenset[str]:
    """REVOKED_CODES: comma/space/newline separated customer ids or full codes."""
    return frozenset(t.strip().upper() for t in re.split(r"[,\s;]+", text or "") if t.strip())


def verify_code(secret: str, code: str, today: _dt.date | None = None, revoked: frozenset[str] = frozenset()) -> Verdict:
    if not secret:
        return Verdict(False, reason="Paid downloads are not switched on for this app yet.")
    code = (code or "").strip().upper().replace(" ", "")
    m = _CODE_RE.match(code)
    if not m:
        return Verdict(False, reason="That code is not in the right format.")
    tier, customer, ymd, sig = m.groups()
    body = f"{tier}-{customer}-{ymd}"
    if not hmac.compare_digest(sig, _sign(secret, body)):
        return Verdict(False, reason="That code is not valid.")
    try:
        expires = _dt.datetime.strptime(ymd, "%Y%m%d").date()
    except ValueError:
        return Verdict(False, reason="That code is not valid.")
    if code in revoked or customer in revoked:
        return Verdict(False, reason="That code has been withdrawn. Please contact us.")
    if (today or _dt.date.today()) > expires:
        return Verdict(False, tier, customer, expires, "That code has expired.")
    return Verdict(True, tier, customer, expires, "")
