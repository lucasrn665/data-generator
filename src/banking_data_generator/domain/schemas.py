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

LEDGER_ENTRY_SCHEMA = pa.schema(
    [
        pa.field("entry_id", pa.string(), nullable=False),
        pa.field("account_id", pa.string(), nullable=False),
        pa.field("entry_type", pa.string(), nullable=False),
        pa.field("direction", pa.string(), nullable=False),
        pa.field("amount", pa.decimal128(18, 2), nullable=False),
        pa.field("currency", pa.string(), nullable=False),
        pa.field("effective_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("reference_id", pa.string(), nullable=False),
        pa.field("sequence_number", pa.int64(), nullable=False),
    ]
)

MERCHANT_SCHEMA = pa.schema(
    [
        pa.field("merchant_id", pa.string(), nullable=False),
        pa.field("synthetic_name", pa.string(), nullable=False),
        pa.field("category", pa.string(), nullable=False),
        pa.field("category_code", pa.string(), nullable=False),
        pa.field("city", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        pa.field("country", pa.string(), nullable=False),
        pa.field("risk_profile", pa.string(), nullable=False),
        pa.field("created_date", pa.date32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
    ]
)

CARD_SCHEMA = pa.schema(
    [
        pa.field("card_id", pa.string(), nullable=False),
        pa.field("account_id", pa.string(), nullable=False),
        pa.field("card_type", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("issued_date", pa.date32(), nullable=False),
        pa.field("expiration_date", pa.date32(), nullable=False),
        pa.field("daily_purchase_limit", pa.decimal128(18, 2), nullable=False),
        pa.field("currency", pa.string(), nullable=False),
    ]
)

TRANSACTION_SCHEMA = pa.schema(
    [
        pa.field("transaction_id", pa.string(), nullable=False),
        pa.field("account_id", pa.string(), nullable=False),
        pa.field("card_id", pa.string(), nullable=False),
        pa.field("merchant_id", pa.string(), nullable=False),
        pa.field("transaction_type", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("amount", pa.decimal128(18, 2), nullable=False),
        pa.field("currency", pa.string(), nullable=False),
        pa.field("effective_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("event_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("decline_reason", pa.string(), nullable=True),
        pa.field("original_transaction_id", pa.string(), nullable=True),
    ]
)
