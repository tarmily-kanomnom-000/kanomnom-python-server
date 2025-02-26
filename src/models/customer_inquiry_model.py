import logging
from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional, Union

import phonenumbers
from email_validator import (
    EmailNotValidError,
    ValidatedEmail,
    validate_email,
)
from phonenumbers import PhoneNumber
from pydantic import BaseModel, ConfigDict, RootModel, field_validator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class InquiryStatus(str, Enum):
    UNRESOLVED = "unresolved"
    IN_PROGRESS = "in progress"
    RESOLVED = "resolved"


class InquiryType(str, Enum):
    GENERAL_INQUIRY = "General Inquiry"
    ORDER_REQUEST = "Order Request"
    BULK_ORDER_INQUIRY = "Bulk Order Inquiry"


class PreferredContactMethod(str, Enum):
    PHONE = "phone"
    EMAIL = "email"


class Product(str, Enum):
    VELA_CAKE = "vela-cake"
    OTHER = "other"
    L = "L"  # why tf does grist add an L?


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
    products: Optional[List[Product]] = None
    inquiry_type: Optional[InquiryType] = None
    inquiry: str
    last_updated: datetime
    attachments: Optional[str] = None

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


class Inquiries(RootModel[List[Inquiry]]):
    pass
