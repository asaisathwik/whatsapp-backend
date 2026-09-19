from app.services.phone_normalizer import normalize_phone_number

def test_phone_normalization_formats():
    # 1. Standard +91 format with spaces
    valid, num, err = normalize_phone_number("+91 9876543210", default_country="IN")
    assert valid is True
    assert num == "919876543210"

    # 2. Leading 091
    valid, num, err = normalize_phone_number("0919876543210", default_country="IN")
    assert valid is True
    assert num == "919876543210"

    # 3. Direct 91...
    valid, num, err = normalize_phone_number("919876543210", default_country="IN")
    assert valid is True
    assert num == "919876543210"

    # 4. 10 digit without country code (default IN -> prepends 91)
    valid, num, err = normalize_phone_number("9876543210", default_country="IN")
    assert valid is True
    assert num == "919876543210"

    # 5. US phone number format
    valid, num, err = normalize_phone_number("+1 (415) 555-2671", default_country="US")
    assert valid is True
    assert num == "14155552671"

    # 6. Invalid / empty number
    valid, num, err = normalize_phone_number("", default_country="IN")
    assert valid is False
    assert err is not None
