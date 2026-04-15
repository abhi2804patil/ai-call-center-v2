import io
import logging

import pandas as pd
import phonenumbers

logger = logging.getLogger(__name__)


def validate_phone_number(number: str, country_code: str = "IN") -> tuple[bool, str]:
    try:
        cleaned = number.strip().replace(" ", "").replace("-", "")

        if cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = "+91" + cleaned[1:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = "+" + cleaned
        elif len(cleaned) == 10 and cleaned.isdigit():
            cleaned = "+91" + cleaned
        elif not cleaned.startswith("+"):
            cleaned = "+91" + cleaned

        parsed = phonenumbers.parse(cleaned, country_code)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            return True, formatted
        else:
            return False, f"Invalid phone number: {number}"

    except phonenumbers.NumberParseException as e:
        return False, f"Cannot parse phone number '{number}': {e}"


def validate_csv_file(file_content: bytes) -> tuple[bool, list[str], list[dict]]:
    errors = []
    parsed_rows = []

    try:
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as e:
        return False, [f"Cannot parse CSV file: {e}"], []

    if "phone_number" not in df.columns:
        return False, ["CSV must have a 'phone_number' column"], []

    df = df.dropna(subset=["phone_number"])
    df["phone_number"] = df["phone_number"].astype(str)

    seen_numbers = set()
    duplicates = 0

    for idx, row in df.iterrows():
        raw_phone = row["phone_number"]
        is_valid, result = validate_phone_number(raw_phone)

        if not is_valid:
            errors.append(f"Row {idx + 2}: {result}")
            continue

        if result in seen_numbers:
            duplicates += 1
            continue
        seen_numbers.add(result)

        customer_data = {}
        for col in df.columns:
            if col != "phone_number":
                val = row[col]
                if pd.notna(val):
                    customer_data[col] = str(val) if not isinstance(val, (int, float)) else val

        parsed_rows.append({
            "phone_number": result,
            "customer_data": customer_data,
        })

    if not parsed_rows and not errors:
        errors.append("No valid phone numbers found in CSV")
        return False, errors, []

    logger.info(
        f"CSV validation: {len(parsed_rows)} valid, {len(errors)} invalid, {duplicates} duplicates"
    )
    return True, errors, parsed_rows
