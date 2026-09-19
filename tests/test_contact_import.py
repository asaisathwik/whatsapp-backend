import io
from app.services.contact_importer import ContactImportService

def test_csv_import_preview_and_execution(db_session, org_a_setup):
    org_id = org_a_setup["org"].id

    csv_data = """name,phone,email,city
John Doe,+91 9876543211,john@example.com,Mumbai
Jane Smith,0919876543212,jane@example.com,Delhi
Invalid User,12345,invalid@example.com,Bangalore
Duplicate User,9876543211,dup@example.com,Mumbai
"""

    preview = ContactImportService.parse_file(
        file_bytes=csv_data.encode("utf-8"),
        filename="contacts.csv",
        default_country="IN"
    )

    assert preview.total_rows == 4
    assert preview.valid_count == 2
    assert preview.invalid_count == 1
    assert preview.duplicate_count == 1

    # Execute import
    res = ContactImportService.execute_import(
        db=db_session,
        organization_id=org_id,
        rows=preview.sample_rows,
        source="CSV"
    )

    assert res.total == 4
    assert res.imported == 2
    assert res.failed == 1
    assert res.duplicates == 1
