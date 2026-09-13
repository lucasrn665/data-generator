from dataclasses import fields

import pyarrow as pa

from banking_data_generator.domain.models import (
    Account,
    Address,
    Customer,
    DebitCard,
    Merchant,
)
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CARD_SCHEMA,
    CUSTOMER_SCHEMA,
    MERCHANT_SCHEMA,
)


def test_schemas_match_domain_model_fields() -> None:
    assert CUSTOMER_SCHEMA.names == [field.name for field in fields(Customer)]
    assert ADDRESS_SCHEMA.names == [field.name for field in fields(Address)]
    assert ACCOUNT_SCHEMA.names == [field.name for field in fields(Account)]
    assert CARD_SCHEMA.names == [field.name for field in fields(DebitCard)]
    assert MERCHANT_SCHEMA.names == [field.name for field in fields(Merchant)]


def test_required_fields_are_non_nullable() -> None:
    for schema in (
        CUSTOMER_SCHEMA,
        ADDRESS_SCHEMA,
        ACCOUNT_SCHEMA,
        CARD_SCHEMA,
        MERCHANT_SCHEMA,
    ):
        for field in schema:
            if field.name == "complement":
                assert field.nullable
            else:
                assert not field.nullable


def test_schema_uses_domain_appropriate_types() -> None:
    assert CUSTOMER_SCHEMA.field("birth_date").type == pa.date32()
    assert CUSTOMER_SCHEMA.field("created_date").type == pa.date32()
    assert ACCOUNT_SCHEMA.field("opened_date").type == pa.date32()
    assert ACCOUNT_SCHEMA.field("opening_balance").type == pa.decimal128(18, 2)
    assert CARD_SCHEMA.field("issued_date").type == pa.date32()
    assert CARD_SCHEMA.field("expiration_date").type == pa.date32()
    assert CARD_SCHEMA.field("daily_purchase_limit").type == pa.decimal128(18, 2)

    for schema in (
        CUSTOMER_SCHEMA,
        ADDRESS_SCHEMA,
        ACCOUNT_SCHEMA,
        CARD_SCHEMA,
        MERCHANT_SCHEMA,
    ):
        assert schema.field(schema.names[0]).type == pa.string()
