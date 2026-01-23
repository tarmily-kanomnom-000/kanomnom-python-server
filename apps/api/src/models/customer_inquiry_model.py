import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Optional, Union

import phonenumbers
from email_validator import EmailNotValidError, ValidatedEmail, validate_email
from phonenumbers import PhoneNumber, PhoneNumberFormat
from pydantic import BaseModel, ConfigDict, RootModel, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class InquiryStatus(str, Enum):
    UNRESOLVED = "unresolved"
    IN_PROGRESS = "in progress"
    RESOLVED = "resolved"


class InquiryType(str, Enum):
    BULK_ORDER_INQUIRY = "Bulk Order Inquiry"
    CATERING = "Catering"
    CUSTOM = "Custom"
    GENERAL_INQUIRY = "General Inquiry"
    ORDER_REQUEST = "Order Request"


class PreferredContactMethod(str, Enum):
    TEXT = "text"
    EMAIL = "email"


class Inquiry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int
    manualSort: int
    date: datetime
    date_needed_by: Optional[datetime] = None
    status: InquiryStatus
    customer_first_name: str
    customer_last_name: str
    email: Optional[Union[ValidatedEmail, str]] = None
    phone_number: Optional[Union[PhoneNumber, str]] = None
    preferred_contact_method: Optional[PreferredContactMethod] = None
    inquiry_type: Optional[InquiryType] = None
    inquiry: str
    last_updated: datetime
    location: str
    medusa_order_id: Optional[str] = None
    attachments: Optional[list] = None

    @field_validator("preferred_contact_method", mode="before")
    @classmethod
    def clean_preferred_contact_method(cls, v):
        if v == "":
            return None
        return v

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_field(cls, v):
        try:
            return validate_email(v, check_deliverability=False)
        except EmailNotValidError:
            logger.warning(f"⚠️ Warning: Invalid email received: {v}")
        return v

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, v):
        try:
            phone = phonenumbers.parse(str(v), "US")
            if not phonenumbers.is_valid_number(phone):
                logger.warning(f"⚠️ Warning: Invalid phone number received: {v}")
                return str(v)
            return phone
        except Exception:
            logger.warning(f"⚠️ Warning: Invalid phone number received: {v}")
            return str(v)

    @field_validator("date", "last_updated", "date_needed_by", mode="before")
    @classmethod
    def convert_timestamp(cls, v):
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=UTC)
        return v

    @field_validator("inquiry_type", mode="before")
    @classmethod
    def clean_inquiry_type(cls, v):
        if v == "":
            return None
        return v

    @field_validator("inquiry", mode="before")
    @classmethod
    def clean_inquiry(cls, v):
        if v is None:
            return ""
        return v

    @field_validator("attachments", mode="before")
    @classmethod
    def normalize_attachments(cls, value):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            if not value:
                return []
            first_item = value[0]
            if isinstance(first_item, (list, tuple, dict)):
                return list(value)
            return [value]
        raise TypeError(f"Unsupported attachments payload: {type(value)!r}")


class Inquiries(RootModel[list[Inquiry]]):
    pass


def format_phone_number(value: PhoneNumber | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, PhoneNumber):
        phone = value
    else:
        try:
            phone = phonenumbers.parse(str(value), "US")
        except Exception:
            return str(value)
    if not phonenumbers.is_valid_number(phone):
        return str(value)
    if phone.country_code == 1:
        national = phonenumbers.format_number(phone, PhoneNumberFormat.NATIONAL)
        return f"+{phone.country_code} {national}"
    return phonenumbers.format_number(phone, PhoneNumberFormat.INTERNATIONAL)
