import re
from typing import Optional, Tuple
import phonenumbers
from phonenumbers import PhoneNumberFormat

COUNTRY_CODE_MAP = {
    "IN": "91",
    "US": "1",
    "GB": "44",
    "BR": "55",
    "AE": "971",
    "CA": "1",
    "AU": "61",
    "SG": "65",
    "ID": "62",
    "MX": "52"
}

def normalize_phone_number(raw_phone: str, default_country: str = "IN") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Normalizes phone number to international E.164 format without leading '+' for WhatsApp JIDs.
    Handles: +91 9XXXXXXXXX, 0919XXXXXXXXX, 919XXXXXXXXX, 9XXXXXXXXX.
    """
    if not raw_phone or not str(raw_phone).strip():
        return False, None, "Phone number is empty"

    cleaned = re.sub(r"[^\d+]", "", str(raw_phone).strip())
    default_cc = COUNTRY_CODE_MAP.get(default_country.upper(), "91")

    # Handle leading 091...
    if cleaned.startswith(f"0{default_cc}") and len(cleaned) == (len(default_cc) + 11):
        cleaned = cleaned[1:]
    elif cleaned.startswith("00"):
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        # e.g. 09876543210 -> 919876543210
        cleaned = f"{default_cc}{cleaned[1:]}"

    if cleaned.startswith("+"):
        parsed_str = cleaned
    else:
        if len(cleaned) == 10:
            parsed_str = f"+{default_cc}{cleaned}"
        elif cleaned.startswith(default_cc):
            parsed_str = f"+{cleaned}"
        else:
            parsed_str = f"+{default_cc}{cleaned}"

    try:
        parsed_number = phonenumbers.parse(parsed_str, default_country)
        if not phonenumbers.is_valid_number(parsed_number):
            digits_only = re.sub(r"[^\d]", "", parsed_str)
            if len(digits_only) >= 10:
                return True, digits_only, None
            return False, None, "Invalid phone number format"
        
        formatted_e164 = phonenumbers.format_number(parsed_number, PhoneNumberFormat.E164)
        normalized = formatted_e164.lstrip("+")
        return True, normalized, None
    except Exception as e:
        digits_only = re.sub(r"[^\d]", "", str(raw_phone))
        if len(digits_only) == 10:
            return True, f"{default_cc}{digits_only}", None
        elif len(digits_only) in [11, 12, 13]:
            return True, digits_only.lstrip("0"), None
        return False, None, f"Failed to parse phone number: {str(e)}"
