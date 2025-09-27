"""
Supplier model for the Inventory Management System.
"""

from typing import List, Optional
from decimal import Decimal

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, ActiveRecordMixin


class Supplier(BaseModel, ActiveRecordMixin):
    """
    Supplier model for managing supplier information and relationships.

    Attributes:
        name: Supplier company name
        contact_person: Primary contact person
        email: Contact email address
        phone: Contact phone number
        address: Physical address
        city: City location
        country: Country (defaults to Japan)
        postal_code: Postal/ZIP code
        tax_id: Tax identification number
        payment_terms: Payment terms in days (default 30)
        notes: Additional notes about the supplier
        products: Products supplied by this supplier
    """

    __tablename__ = "suppliers"

    # Basic information
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Contact information
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Address information
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    country: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Japan", server_default="Japan"
    )

    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Business information
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    payment_terms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="supplier"
    )

    def __repr__(self) -> str:
        """String representation of the supplier."""
        return f"<Supplier(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.name

    @property
    def full_address(self) -> str:
        """
        Get the full formatted address.

        Returns:
            Formatted address string
        """
        address_parts = []

        if self.address:
            address_parts.append(self.address)
        if self.city:
            address_parts.append(self.city)
        if self.postal_code:
            address_parts.append(self.postal_code)
        if self.country:
            address_parts.append(self.country)

        return ", ".join(filter(None, address_parts))

    @property
    def display_name(self) -> str:
        """
        Get display name with contact person if available.

        Returns:
            Display name string
        """
        if self.contact_person:
            return f"{self.name} ({self.contact_person})"
        return self.name

    @property
    def has_contact_info(self) -> bool:
        """Check if supplier has contact information."""
        return bool(self.email or self.phone)

    @property
    def product_count(self) -> int:
        """Get the number of active products from this supplier."""
        return len([p for p in self.products if p.is_active])

    def get_products_by_category(self, category_name: str) -> List["Product"]:
        """
        Get products from this supplier filtered by category.

        Args:
            category_name: Name of the category to filter by

        Returns:
            List of Product objects
        """
        return [
            product
            for product in self.products
            if (
                product.is_active
                and product.category
                and product.category.name.lower() == category_name.lower()
            )
        ]

    def get_total_inventory_value(self) -> Decimal:
        """
        Calculate total inventory value for products from this supplier.

        Returns:
            Total value as Decimal
        """
        total = Decimal("0.00")

        for product in self.products:
            if product.is_active and product.unit_cost:
                # Get current inventory quantity
                for inventory in product.inventory:
                    if inventory.quantity_available > 0:
                        total += (
                            Decimal(str(inventory.quantity_available))
                            * product.unit_cost
                        )

        return total

    def get_low_stock_products(self) -> List["Product"]:
        """
        Get products from this supplier that are below reorder point.

        Returns:
            List of Product objects with low stock
        """
        low_stock = []

        for product in self.products:
            if product.is_active:
                for inventory in product.inventory:
                    if inventory.quantity_available <= product.reorder_point:
                        low_stock.append(product)
                        break

        return low_stock

    def update_contact_info(
        self, email: str = None, phone: str = None, contact_person: str = None
    ) -> None:
        """
        Update supplier contact information.

        Args:
            email: New email address
            phone: New phone number
            contact_person: New contact person name
        """
        if email is not None:
            self.email = email
        if phone is not None:
            self.phone = phone
        if contact_person is not None:
            self.contact_person = contact_person

    def update_address(
        self,
        address: str = None,
        city: str = None,
        country: str = None,
        postal_code: str = None,
    ) -> None:
        """
        Update supplier address information.

        Args:
            address: New street address
            city: New city
            country: New country
            postal_code: New postal code
        """
        if address is not None:
            self.address = address
        if city is not None:
            self.city = city
        if country is not None:
            self.country = country
        if postal_code is not None:
            self.postal_code = postal_code

    @classmethod
    def get_by_name(cls, session, name: str) -> Optional["Supplier"]:
        """
        Get supplier by name.

        Args:
            session: SQLAlchemy session
            name: Supplier name

        Returns:
            Supplier object or None if not found
        """
        return (
            session.query(cls).filter(cls.name == name, cls.is_active == True).first()
        )

    @classmethod
    def search_by_name(cls, session, search_term: str) -> List["Supplier"]:
        """
        Search suppliers by name (case-insensitive partial match).

        Args:
            session: SQLAlchemy session
            search_term: Search term

        Returns:
            List of matching Supplier objects
        """
        return (
            session.query(cls)
            .filter(cls.name.ilike(f"%{search_term}%"), cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_by_city(cls, session, city: str) -> List["Supplier"]:
        """
        Get suppliers by city.

        Args:
            session: SQLAlchemy session
            city: City name

        Returns:
            List of Supplier objects
        """
        return (
            session.query(cls)
            .filter(cls.city.ilike(f"%{city}%"), cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_by_country(cls, session, country: str) -> List["Supplier"]:
        """
        Get suppliers by country.

        Args:
            session: SQLAlchemy session
            country: Country name

        Returns:
            List of Supplier objects
        """
        return (
            session.query(cls)
            .filter(cls.country.ilike(f"%{country}%"), cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_with_email(cls, session) -> List["Supplier"]:
        """
        Get suppliers that have email addresses.

        Args:
            session: SQLAlchemy session

        Returns:
            List of Supplier objects with email
        """
        return (
            session.query(cls)
            .filter(cls.email.isnot(None), cls.email != "", cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    def to_dict(self, include_relationships: bool = False) -> dict:
        """
        Convert supplier to dictionary with additional computed fields.

        Args:
            include_relationships: Whether to include relationship data

        Returns:
            Dictionary representation
        """
        result = super().to_dict(include_relationships=False)

        # Add computed fields
        result["full_address"] = self.full_address
        result["display_name"] = self.display_name
        result["has_contact_info"] = self.has_contact_info
        result["product_count"] = self.product_count

        if include_relationships:
            # Include basic product info
            result["products"] = [
                {
                    "id": str(product.id),
                    "sku": product.sku,
                    "name": product.name,
                    "is_active": product.is_active,
                }
                for product in self.products
            ]

        return result


# Import here to avoid circular imports
from .product import Product
