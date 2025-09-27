"""
Category model for the Inventory Management System.
"""

from typing import List, Optional
import uuid

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, ActiveRecordMixin


class Category(BaseModel, ActiveRecordMixin):
    """
    Category model for organizing products hierarchically.

    Attributes:
        name: Category name (unique)
        description: Optional description of the category
        parent_id: ID of parent category (for hierarchy)
        parent: Parent category relationship
        children: Child categories relationship
        products: Products in this category
    """

    __tablename__ = "categories"

    # Basic fields
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hierarchical relationship fields
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )

    children: Mapped[List["Category"]] = relationship(
        "Category", back_populates="parent", cascade="all, delete-orphan"
    )

    # Relationship to products (will be defined in product.py)
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the category."""
        return f"<Category(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.name

    @property
    def full_path(self) -> str:
        """
        Get the full hierarchical path of the category.

        Returns:
            String representation of the category path (e.g., "Electronics > Computers > Laptops")
        """
        path_parts = []
        current = self

        while current:
            path_parts.append(current.name)
            current = current.parent

        return " > ".join(reversed(path_parts))

    @property
    def level(self) -> int:
        """
        Get the level of the category in the hierarchy (0 = root level).

        Returns:
            Integer representing the depth level
        """
        level = 0
        current = self.parent

        while current:
            level += 1
            current = current.parent

        return level

    @property
    def is_root(self) -> bool:
        """Check if this is a root category (no parent)."""
        return self.parent_id is None

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf category (no children)."""
        return len(self.children) == 0

    def get_all_descendants(self) -> List["Category"]:
        """
        Get all descendant categories (children, grandchildren, etc.).

        Returns:
            List of all descendant Category objects
        """
        descendants = []

        for child in self.children:
            if child.is_active:
                descendants.append(child)
                descendants.extend(child.get_all_descendants())

        return descendants

    def get_all_ancestors(self) -> List["Category"]:
        """
        Get all ancestor categories (parent, grandparent, etc.).

        Returns:
            List of all ancestor Category objects
        """
        ancestors = []
        current = self.parent

        while current:
            ancestors.append(current)
            current = current.parent

        return ancestors

    def get_root_category(self) -> "Category":
        """
        Get the root category of this category's hierarchy.

        Returns:
            Root Category object
        """
        current = self

        while current.parent:
            current = current.parent

        return current

    def can_be_parent_of(self, potential_child: "Category") -> bool:
        """
        Check if this category can be a parent of another category.
        Prevents circular references.

        Args:
            potential_child: Category to check

        Returns:
            True if this category can be parent of potential_child
        """
        if potential_child == self:
            return False

        # Check if potential_child is an ancestor of self
        ancestors = self.get_all_ancestors()
        return potential_child not in ancestors

    def move_to_parent(self, new_parent: Optional["Category"]) -> bool:
        """
        Move this category to a new parent.

        Args:
            new_parent: New parent category (None for root level)

        Returns:
            True if move was successful, False if invalid
        """
        if new_parent is None:
            self.parent_id = None
            self.parent = None
            return True

        if new_parent.can_be_parent_of(self):
            self.parent_id = new_parent.id
            self.parent = new_parent
            return True

        return False

    def get_product_count(self, include_descendants: bool = False) -> int:
        """
        Get the number of products in this category.

        Args:
            include_descendants: Whether to include products from descendant categories

        Returns:
            Number of products
        """
        count = len([p for p in self.products if p.is_active])

        if include_descendants:
            for descendant in self.get_all_descendants():
                count += len([p for p in descendant.products if p.is_active])

        return count

    @classmethod
    def get_root_categories(cls, session) -> List["Category"]:
        """
        Get all root categories (categories with no parent).

        Args:
            session: SQLAlchemy session

        Returns:
            List of root Category objects
        """
        return (
            session.query(cls)
            .filter(cls.parent_id.is_(None), cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_by_name(cls, session, name: str) -> Optional["Category"]:
        """
        Get category by name.

        Args:
            session: SQLAlchemy session
            name: Category name

        Returns:
            Category object or None if not found
        """
        return (
            session.query(cls).filter(cls.name == name, cls.is_active == True).first()
        )

    @classmethod
    def search_by_name(cls, session, search_term: str) -> List["Category"]:
        """
        Search categories by name (case-insensitive partial match).

        Args:
            session: SQLAlchemy session
            search_term: Search term

        Returns:
            List of matching Category objects
        """
        return (
            session.query(cls)
            .filter(cls.name.ilike(f"%{search_term}%"), cls.is_active == True)
            .order_by(cls.name)
            .all()
        )

    def to_dict(self, include_relationships: bool = False) -> dict:
        """
        Convert category to dictionary with additional computed fields.

        Args:
            include_relationships: Whether to include relationship data

        Returns:
            Dictionary representation
        """
        result = super().to_dict(include_relationships=False)

        # Add computed fields
        result["full_path"] = self.full_path
        result["level"] = self.level
        result["is_root"] = self.is_root
        result["is_leaf"] = self.is_leaf
        result["product_count"] = self.get_product_count()

        if include_relationships:
            # Include parent info (without full recursion)
            if self.parent:
                result["parent"] = {"id": str(self.parent.id), "name": self.parent.name}

            # Include children info (without full recursion)
            result["children"] = [
                {"id": str(child.id), "name": child.name, "is_active": child.is_active}
                for child in self.children
            ]

        return result


# Import here to avoid circular imports
from .product import Product
