import io
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.models import Contact, Tag, ContactTag, ContactStatus
from app.schemas.schemas import ContactImportRow, ContactImportPreview, ContactImportResult
from app.services.phone_normalizer import normalize_phone_number

class ContactImportService:
    @staticmethod
    def parse_file(file_bytes: bytes, filename: str, default_country: str = "IN") -> ContactImportPreview:
        """Parse CSV or Excel file and return structured preview with validation."""
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
        elif filename.endswith((".xls", ".xlsx")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            raise ValueError("Unsupported file format. Please upload CSV or Excel (.xlsx) file.")

        df = df.fillna("")
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

        # Detect columns
        name_col = next((c for c in df.columns if c in ["name", "full_name", "contact_name", "first_name"]), None)
        phone_col = next((c for c in df.columns if c in ["phone", "mobile", "whatsapp", "phone_number", "contact_number"]), None)
        email_col = next((c for c in df.columns if c in ["email", "email_address"]), None)

        if not phone_col:
            raise ValueError("Could not find a phone number column in the uploaded file.")

        total_rows = len(df)
        sample_rows: List[ContactImportRow] = []
        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        seen_phones = set()

        for idx, row in df.iterrows():
            row_num = idx + 1
            raw_name = str(row[name_col]).strip() if name_col and name_col in row else f"Contact {row_num}"
            raw_phone = str(row[phone_col]).strip()
            raw_email = str(row[email_col]).strip() if email_col and email_col in row else None
            
            # Extract custom fields
            custom_fields = {}
            for col in df.columns:
                if col not in [name_col, phone_col, email_col]:
                    val = str(row[col]).strip()
                    if val:
                        custom_fields[col] = val

            is_valid, normalized, err = normalize_phone_number(raw_phone, default_country=default_country)
            is_dup = False

            if not is_valid:
                invalid_count += 1
            else:
                if normalized in seen_phones:
                    is_dup = True
                    duplicate_count += 1
                else:
                    seen_phones.add(normalized)
                    valid_count += 1

            sample_rows.append(ContactImportRow(
                row_number=row_num,
                name=raw_name or f"Contact {row_num}",
                raw_phone=raw_phone,
                normalized_phone=normalized,
                email=raw_email if raw_email else None,
                custom_fields=custom_fields,
                is_valid=is_valid,
                is_duplicate=is_dup,
                error=err
            ))

        return ContactImportPreview(
            total_rows=total_rows,
            valid_count=valid_count,
            invalid_count=invalid_count,
            duplicate_count=duplicate_count,
            sample_rows=sample_rows
        )

    @staticmethod
    def execute_import(
        db: Session,
        organization_id: str,
        rows: List[ContactImportRow],
        tag_ids: Optional[List[str]] = None,
        source: str = "CSV",
        overwrite_existing: bool = False
    ) -> ContactImportResult:
        imported = 0
        failed = 0
        duplicates = 0
        errors = []

        # Get existing numbers in organization
        existing_contacts = {c.phone: c for c in db.query(Contact).filter(Contact.organization_id == organization_id).all()}

        for row in rows:
            if not row.is_valid or not row.normalized_phone:
                failed += 1
                errors.append(f"Row {row.row_number}: {row.error or 'Invalid phone number'}")
                continue

            phone = row.normalized_phone
            if phone in existing_contacts:
                if overwrite_existing:
                    contact = existing_contacts[phone]
                    contact.name = row.name
                    if row.email:
                        contact.email = row.email
                    contact.custom_fields = {**contact.custom_fields, **row.custom_fields}
                    imported += 1
                else:
                    duplicates += 1
                continue

            # Create new contact
            try:
                new_contact = Contact(
                    organization_id=organization_id,
                    name=row.name,
                    phone=phone,
                    email=row.email,
                    status=ContactStatus.ACTIVE.value,
                    source=source,
                    custom_fields=row.custom_fields or {}
                )
                db.add(new_contact)
                db.flush()

                # Add tags
                if tag_ids:
                    for tag_id in tag_ids:
                        db.add(ContactTag(
                            organization_id=organization_id,
                            contact_id=new_contact.id,
                            tag_id=tag_id
                        ))

                existing_contacts[phone] = new_contact
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(f"Row {row.row_number} ({row.name}): {str(e)}")

        db.commit()
        return ContactImportResult(
            total=len(rows),
            imported=imported,
            failed=failed,
            duplicates=duplicates,
            errors=errors[:50]
        )
