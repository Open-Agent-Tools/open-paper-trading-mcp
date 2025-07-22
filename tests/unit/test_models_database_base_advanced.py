"""
Advanced tests for database base model patterns.

Comprehensive test coverage for base database model functionality,
SQLAlchemy patterns, and declarative base implementation.
"""

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.database.base import Base


class TestBaseModel:
    """Test the declarative base model."""

    def test_base_exists(self):
        """Test that Base exists and is a declarative base."""
        assert Base is not None
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")

    def test_base_is_declarative_base(self):
        """Test that Base is a proper declarative base."""
        # Should have the required attributes from declarative_base
        assert hasattr(Base, "__mapper_registry__")
        assert hasattr(Base, "metadata")

    def test_base_registry_type(self):
        """Test that Base has the correct registry type."""
        # The registry should be a DeclarativeRegistry
        assert Base.registry is not None
        assert hasattr(Base.registry, "mappers")

    def test_base_metadata_properties(self):
        """Test metadata properties."""
        metadata = Base.metadata
        assert metadata is not None
        assert hasattr(metadata, "tables")
        assert hasattr(metadata, "create_all")
        assert hasattr(metadata, "drop_all")

    def test_base_can_be_subclassed(self):
        """Test that Base can be properly subclassed."""

        class TestModel(Base):
            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        # Should create without errors
        assert TestModel.__tablename__ == "test_model"
        assert hasattr(TestModel, "id")
        assert hasattr(TestModel, "name")
        assert hasattr(TestModel, "__mapper__")

    def test_base_table_registration(self):
        """Test that subclassed models register with metadata."""

        class TestRegistration(Base):
            __tablename__ = "test_registration"
            id = Column(Integer, primary_key=True)
            value = Column(String(100))

        # Table should be registered in metadata
        assert "test_registration" in Base.metadata.tables
        table = Base.metadata.tables["test_registration"]
        assert table.name == "test_registration"

    def test_base_multiple_inheritance(self):
        """Test multiple model inheritance from Base."""

        class Model1(Base):
            __tablename__ = "model_1"
            id = Column(Integer, primary_key=True)

        class Model2(Base):
            __tablename__ = "model_2"
            id = Column(Integer, primary_key=True)

        # Both should be registered
        assert "model_1" in Base.metadata.tables
        assert "model_2" in Base.metadata.tables

    def test_base_column_inspection(self):
        """Test that Base allows proper column inspection."""

        class InspectionModel(Base):
            __tablename__ = "inspection_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50), nullable=False)
            description = Column(String(200), nullable=True)

        # Should be able to inspect columns
        mapper = InspectionModel.__mapper__
        columns = mapper.columns

        assert "id" in columns
        assert "name" in columns
        assert "description" in columns

        # Test column properties
        id_col = columns["id"]
        name_col = columns["name"]
        desc_col = columns["description"]

        assert id_col.primary_key
        assert not name_col.nullable
        assert desc_col.nullable

    def test_base_relationship_support(self):
        """Test that Base supports relationships."""
        from sqlalchemy import ForeignKey
        from sqlalchemy.orm import relationship

        class Parent(Base):
            __tablename__ = "parent"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            children = relationship("Child", back_populates="parent")

        class Child(Base):
            __tablename__ = "child"
            id = Column(Integer, primary_key=True)
            parent_id = Column(Integer, ForeignKey("parent.id"))
            name = Column(String(50))
            parent = relationship("Parent", back_populates="children")

        # Relationships should be configured
        parent_mapper = Parent.__mapper__
        child_mapper = Child.__mapper__

        assert "children" in parent_mapper.relationships
        assert "parent" in child_mapper.relationships

    def test_base_with_async_support(self):
        """Test that Base works with async SQLAlchemy."""
        # This tests that our Base is compatible with async operations
        # We're not actually running async operations here, just testing setup

        class AsyncModel(Base):
            __tablename__ = "async_model"
            id = Column(Integer, primary_key=True)
            data = Column(String(100))

        # Should work with async engine creation (we're not connecting)
        async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        assert async_engine is not None

    def test_base_table_args_support(self):
        """Test that Base supports __table_args__."""
        from sqlalchemy import Index

        class TableArgsModel(Base):
            __tablename__ = "table_args_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            category = Column(String(30))

            __table_args__ = (
                Index("idx_name_category", "name", "category"),
                {"mysql_engine": "InnoDB"},
            )

        table = Base.metadata.tables["table_args_model"]

        # Check that index was created
        index_names = [idx.name for idx in table.indexes]
        assert "idx_name_category" in index_names

    def test_base_with_constraints(self):
        """Test Base with various constraints."""
        from sqlalchemy import CheckConstraint, UniqueConstraint

        class ConstraintModel(Base):
            __tablename__ = "constraint_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50), unique=True, nullable=False)
            age = Column(Integer)
            email = Column(String(100))

            __table_args__ = (
                CheckConstraint("age >= 0", name="check_positive_age"),
                UniqueConstraint("name", "email", name="unique_name_email"),
            )

        table = Base.metadata.tables["constraint_model"]

        # Check constraints
        constraint_names = [c.name for c in table.constraints]
        assert "check_positive_age" in constraint_names
        assert "unique_name_email" in constraint_names

    def test_base_with_custom_types(self):
        """Test Base with custom column types."""
        from sqlalchemy import Boolean, DateTime, Numeric, Text
        from sqlalchemy.sql import func

        class CustomTypesModel(Base):
            __tablename__ = "custom_types_model"
            id = Column(Integer, primary_key=True)
            created_at = Column(DateTime, server_default=func.now())
            updated_at = Column(DateTime, onupdate=func.now())
            is_active = Column(Boolean, default=True)
            description = Column(Text)
            price = Column(Numeric(10, 2))

        table = Base.metadata.tables["custom_types_model"]

        # Verify column types
        columns = table.columns
        assert str(columns["created_at"].type) in ["DATETIME", "TIMESTAMP"]
        assert str(columns["is_active"].type) in ["BOOLEAN", "BOOL"]
        assert str(columns["description"].type) in ["TEXT", "CLOB"]

    def test_base_inheritance_patterns(self):
        """Test different inheritance patterns with Base."""

        # Table inheritance (each class has its own table)
        class BaseEntity(Base):
            __tablename__ = "base_entities"
            id = Column(Integer, primary_key=True)
            type = Column(String(50))
            name = Column(String(100))

        # This would be joined table inheritance, but we'll just test
        # that the base class works properly
        assert "base_entities" in Base.metadata.tables

    def test_base_event_listeners(self):
        """Test that Base supports SQLAlchemy event listeners."""
        from sqlalchemy import event

        class EventModel(Base):
            __tablename__ = "event_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            processed = Column(Boolean, default=False)

        # Event listener should be attachable
        @event.listens_for(EventModel, "before_insert")
        def before_insert_listener(mapper, connection, target):
            target.processed = True

        # Just test that the event system works with our Base
        listeners = event.contains(EventModel, "before_insert", before_insert_listener)
        assert listeners

    def test_base_query_support(self):
        """Test that Base works with modern SQLAlchemy query patterns."""
        from sqlalchemy import select

        class QueryModel(Base):
            __tablename__ = "query_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            active = Column(Boolean, default=True)

        # Test that we can create modern select statements
        stmt = select(QueryModel).where(QueryModel.active)
        assert stmt is not None
        assert hasattr(stmt, "where")
        assert hasattr(stmt, "order_by")

    def test_base_hybrid_properties(self):
        """Test that Base supports hybrid properties."""
        from sqlalchemy.ext.hybrid import hybrid_property

        class HybridModel(Base):
            __tablename__ = "hybrid_model"
            id = Column(Integer, primary_key=True)
            first_name = Column(String(50))
            last_name = Column(String(50))

            @hybrid_property
            def full_name(self):
                return f"{self.first_name} {self.last_name}"

        # Should be able to access hybrid property
        assert hasattr(HybridModel, "full_name")
        assert HybridModel.full_name.is_attribute

    def test_base_serialization_support(self):
        """Test that Base models can support serialization."""

        class SerializableModel(Base):
            __tablename__ = "serializable_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            value = Column(Integer)

            def to_dict(self):
                return {"id": self.id, "name": self.name, "value": self.value}

        # Should be able to add custom methods
        model = SerializableModel(id=1, name="test", value=42)
        result = model.to_dict()

        assert result == {"id": 1, "name": "test", "value": 42}

    def test_base_validation_hooks(self):
        """Test that Base supports validation hooks."""
        from sqlalchemy.orm import validates

        class ValidationModel(Base):
            __tablename__ = "validation_model"
            id = Column(Integer, primary_key=True)
            email = Column(String(100))
            age = Column(Integer)

            @validates("email")
            def validate_email(self, key, email):
                if "@" not in email:
                    raise ValueError("Invalid email format")
                return email

            @validates("age")
            def validate_age(self, key, age):
                if age < 0:
                    raise ValueError("Age must be positive")
                return age

        # Test validation works
        model = ValidationModel()

        # Valid values should work
        model.email = "test@example.com"
        model.age = 25
        assert model.email == "test@example.com"
        assert model.age == 25

        # Invalid values should raise errors
        with pytest.raises(ValueError, match="Invalid email format"):
            model.email = "invalid-email"

        with pytest.raises(ValueError, match="Age must be positive"):
            model.age = -5

    def test_base_mixin_support(self):
        """Test that Base supports mixin classes."""
        from sqlalchemy import DateTime
        from sqlalchemy.sql import func

        class TimestampMixin:
            created_at = Column(DateTime, server_default=func.now())
            updated_at = Column(DateTime, onupdate=func.now())

        class MixinModel(TimestampMixin, Base):
            __tablename__ = "mixin_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        # Should inherit mixin columns
        assert hasattr(MixinModel, "created_at")
        assert hasattr(MixinModel, "updated_at")
        assert hasattr(MixinModel, "id")
        assert hasattr(MixinModel, "name")

    def test_base_with_polymorphic_identity(self):
        """Test Base with polymorphic inheritance setup."""

        class PolymorphicBase(Base):
            __tablename__ = "polymorphic_base"
            id = Column(Integer, primary_key=True)
            type = Column(String(20))
            name = Column(String(50))

            __mapper_args__ = {
                "polymorphic_identity": "base",
                "polymorphic_on": type,
                "with_polymorphic": "*",
            }

        # Should create polymorphic configuration
        mapper = PolymorphicBase.__mapper__
        assert mapper.polymorphic_on is not None
        assert mapper.polymorphic_identity == "base"

    def test_base_metadata_operations(self):
        """Test metadata operations with Base."""

        # Create test model
        class MetadataTestModel(Base):
            __tablename__ = "metadata_test"
            id = Column(Integer, primary_key=True)
            data = Column(String(100))

        # Test metadata contains our table
        assert "metadata_test" in Base.metadata.tables

        # Test we can get table info
        table = Base.metadata.tables["metadata_test"]
        assert table.name == "metadata_test"
        assert "id" in table.columns
        assert "data" in table.columns

        # Test column details
        id_col = table.columns["id"]
        data_col = table.columns["data"]

        assert id_col.primary_key
        assert not data_col.primary_key

    def test_base_with_database_functions(self):
        """Test Base with database functions."""
        from sqlalchemy import DateTime, func

        class FunctionModel(Base):
            __tablename__ = "function_model"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            created_at = Column(DateTime, server_default=func.now())
            random_value = Column(Integer, server_default=func.random())

        table = Base.metadata.tables["function_model"]

        # Should have server defaults
        created_col = table.columns["created_at"]
        random_col = table.columns["random_value"]

        assert created_col.server_default is not None
        assert random_col.server_default is not None
