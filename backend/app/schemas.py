import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class LayoutBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page: int
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    page_width: float
    page_height: float
    unit: str
    ocr_confidence: float


class DocumentSummary(BaseModel):
    """Lightweight shape for list views (no heavy text/blocks)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    status: str
    source_method: str
    page_count: int
    uploaded_at: datetime


class ExtractedLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    description: str
    quantity: float | None
    unit_price: float | None
    amount: float | None


class FieldProvenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_key: str
    value_text: str
    matched: bool
    match_method: str
    confidence: float
    page: int
    x0: float
    top: float
    x1: float
    bottom: float
    page_width: float
    page_height: float


class ExtractionOut(BaseModel):
    # protected_namespaces=() so the legitimate field `model_name` doesn't trip
    # Pydantic's "model_" guard.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    vendor: str | None
    invoice_number: str | None
    invoice_date: str | None
    currency: str | None
    subtotal: float | None
    tax: float | None
    discount: float | None
    total: float | None
    attempts: int
    validation_passed: bool
    model_name: str
    line_items: list[ExtractedLineItemOut]
    provenance: list[FieldProvenanceOut]
    # Stored as JSON text on the model; excluded from output in favor of the
    # decoded `issues` list below.
    issues_json: str = Field(exclude=True)

    @computed_field
    @property
    def issues(self) -> list[dict]:
        """Decode stored issues so the UI gets a list, not a JSON string."""
        try:
            return json.loads(self.issues_json)
        except (ValueError, TypeError):
            return []


class DocumentDetail(DocumentSummary):
    raw_text: str
    error: str
    blocks: list[LayoutBlockOut]
    extraction: ExtractionOut | None = None


class QueryRequest(BaseModel):
    # Either a natural-language question, or an explicit structured filter.
    q: str | None = None
    vendor: str | None = None
    invoice_number: str | None = None
    min_total: float | None = None
    max_total: float | None = None
    date_from: str | None = None
    date_to: str | None = None


class QueryResultItem(BaseModel):
    document_id: int
    filename: str
    vendor: str | None
    invoice_number: str | None
    invoice_date: str | None
    currency: str | None
    total: float | None


class QueryResponse(BaseModel):
    # The filter actually applied, echoed back so the translation is transparent.
    applied_filter: dict
    interpreted_from: str | None
    count: int
    results: list[QueryResultItem]
