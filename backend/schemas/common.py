import datetime
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with standard ORM mode enabled."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampedSchema(BaseSchema):
    """Schema mixin that includes id and timestamps."""

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PaginatedResponse(BaseSchema, Generic[T]):
    """Standard paginated container response."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseSchema):
    """Simple status / acknowledgement response."""

    message: str
    status: str = "success"
    details: Optional[dict] = None
