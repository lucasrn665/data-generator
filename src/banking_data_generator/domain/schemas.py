"""Schemas PyArrow explícitos do domínio inicial."""

import pyarrow as pa

CUSTOMER_SCHEMA = pa.schema(
    [
        pa.field("customer_id", pa.string(), nullable=False),
        pa.field("synthetic_name", pa.string(), nullable=False),
        pa.field("birth_date", pa.date32(), nullable=False),
        pa.field("synthetic_email", pa.string(), nullable=False),
        pa.field("created_date", pa.date32(), nullable=False),
        pa.field("activity_profile", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
    ]
)

ADDRESS_SCHEMA = pa.schema(
    [
        pa.field("address_id", pa.string(), nullable=False),
        pa.field("customer_id", pa.string(), nullable=False),
        pa.field("street", pa.string(), nullable=False),
        pa.field("number", pa.string(), nullable=False),
        pa.field("complement", pa.string(), nullable=True),
        pa.field("neighborhood", pa.string(), nullable=False),
        pa.field("city", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        pa.field("synthetic_postal_code", pa.string(), nullable=False),
        pa.field("country", pa.string(), nullable=False),
        pa.field("is_primary", pa.bool_(), nullable=False),
    ]
)

ACCOUNT_SCHEMA = pa.schema(
    [
        pa.field("account_id", pa.string(), nullable=False),
        pa.field("customer_id", pa.string(), nullable=False),
        pa.field("account_type", pa.string(), nullable=False),
        pa.field("currency", pa.string(), nullable=False),
        pa.field("opening_balance", pa.decimal128(18, 2), nullable=False),
        pa.field("opened_date", pa.date32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
    ]
)
