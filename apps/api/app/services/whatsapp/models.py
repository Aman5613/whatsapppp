"""Pydantic schemas for Meta WhatsApp Cloud API webhook payloads."""

from pydantic import BaseModel, Field


class TextPayload(BaseModel):
    """Text content of incoming WhatsApp message."""

    body: str


class InboundMessage(BaseModel):
    """Single incoming message item in Meta webhook payload."""

    id: str  # wa_message_id (e.g. wamid.HBgM...)
    from_: str = Field(alias="from")  # Customer's phone number without +
    timestamp: str
    type: str = "text"
    text: TextPayload | None = None


class InboundStatus(BaseModel):
    """Status callback item (sent, delivered, read, failed)."""

    id: str  # wa_message_id
    status: str
    timestamp: str
    recipient_id: str


class ContactProfile(BaseModel):
    """Customer profile info provided by WhatsApp."""

    name: str | None = None


class Contact(BaseModel):
    """Contact entry."""

    wa_id: str
    profile: ContactProfile | None = None


class Metadata(BaseModel):
    """Phone number metadata identifying the recipient business account."""

    display_phone_number: str | None = None
    phone_number_id: str


class Value(BaseModel):
    """Inner value object in Meta change array."""

    messaging_product: str = "whatsapp"
    metadata: Metadata
    contacts: list[Contact] = Field(default_factory=list)
    messages: list[InboundMessage] = Field(default_factory=list)
    statuses: list[InboundStatus] = Field(default_factory=list)


class Change(BaseModel):
    """Individual field change container."""

    field: str = "messages"
    value: Value


class Entry(BaseModel):
    """Entry wrapper inside Meta webhook payload."""

    id: str  # WABA ID
    changes: list[Change] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    """Root Meta WhatsApp webhook event payload."""

    object: str = "whatsapp_business_account"
    entry: list[Entry] = Field(default_factory=list)
