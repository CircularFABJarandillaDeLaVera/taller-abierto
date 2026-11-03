"""Modelo relacional inicial. Las reglas de negocio vivirán fuera de la interfaz."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(StrEnum):
    VISITOR = "visitor"
    STUDENT = "student"
    TEACHER = "teacher"


class OrderKind(StrEnum):
    PRODUCT_INQUIRY = "product_inquiry"
    CUSTOM_FIGURE = "custom_figure"


class OrderStatus(StrEnum):
    RECEIVED = "received"
    IN_CONVERSATION = "in_conversation"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttachmentSource(StrEnum):
    REQUESTER = "requester"
    RECIPIENT = "recipient"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alias: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    presentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    products: Mapped[list["Product"]] = relationship(back_populates="creator")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[str] = mapped_column(String(160), nullable=False)
    indicative_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    creator: Mapped[User] = relationship(back_populates="products")
    orders: Mapped[list["Order"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[OrderKind] = mapped_column(Enum(OrderKind), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.RECEIVED, nullable=False)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requester_alias: Mapped[str | None] = mapped_column(String(80), nullable=True)
    offer_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visitor_access_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    recipient: Mapped[User | None] = relationship(foreign_keys=[recipient_id])
    product: Mapped[Product | None] = relationship(back_populates="orders")
    messages: Mapped[list["Message"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    order: Mapped[Order] = relationship(back_populates="messages")
    author: Mapped[User] = relationship()


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source: Mapped[AttachmentSource] = mapped_column(Enum(AttachmentSource), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    consent_id: Mapped[int | None] = mapped_column(ForeignKey("photo_consents.id", ondelete="RESTRICT"), nullable=True)
    order: Mapped[Order] = relationship(back_populates="attachments")
    uploader: Mapped[User] = relationship()
    consent: Mapped["PhotoConsent | None"] = relationship()


class PhotoConsent(Base):
    __tablename__ = "photo_consents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    accepted_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    text_version: Mapped[str] = mapped_column(String(40), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    order: Mapped[Order] = relationship()
    accepted_by: Mapped[User] = relationship()


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user: Mapped[User] = relationship()


class RecoveryToken(Base):
    __tablename__ = "recovery_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order: Mapped[Order] = relationship()

