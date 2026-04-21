from __future__ import annotations

import re

PHONE_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw_phone: str | None) -> str | None:
    if not raw_phone:
        return None

    phone = raw_phone.split("@", 1)[0].strip()
    phone = PHONE_DIGITS_RE.sub("", phone)
    return phone or None
