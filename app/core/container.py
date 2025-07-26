"""
Dependency injection container for managing service instances.

This module provides a simple service container that eliminates the need for
global variables and provides centralized service management.
"""

from contextlib import contextmanager
from typing import Any, TypeVar

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container for managing service instances."""

    def __init__(self) -> None:
        self._services: dict[type[Any], Any] = {}
        self._is_locked = False

    def register(self, service_type: type[T], instance: T) -> None:
        """Register a service instance in the container.

        Args:
            service_type: The type/class of the service
            instance: The service instance to register

        Raises:
            RuntimeError: If container is locked or service already registered
        """
        if self._is_locked:
            raise RuntimeError("Cannot register services after container is locked")

        if service_type in self._services:
            raise RuntimeError(f"Service {service_type.__name__} is already registered")

        self._services[service_type] = instance

    def get(self, service_type: type[T]) -> T:
        """Get a service instance from the container.

        Args:
            service_type: The type/class of the service to retrieve

        Returns:
            The service instance

        Raises:
            RuntimeError: If service is not registered
        """
        if service_type not in self._services:
            raise RuntimeError(f"Service {service_type.__name__} is not registered")

        return self._services[service_type]

    def is_registered(self, service_type: type[T]) -> bool:
        """Check if a service type is registered.

        Args:
            service_type: The type/class to check

        Returns:
            True if service is registered, False otherwise
        """
        return service_type in self._services

    def lock(self) -> None:
        """Lock the container to prevent further service registration.

        This is typically called after application startup to ensure
        service configuration is immutable during runtime.
        """
        self._is_locked = True

    def unlock(self) -> None:
        """Unlock the container to allow service registration.

        This is primarily for testing purposes.
        """
        self._is_locked = False

    def clear(self) -> None:
        """Clear all registered services.

        This is primarily for testing purposes.
        """
        if self._is_locked:
            raise RuntimeError("Cannot clear services when container is locked")
        self._services.clear()

    @contextmanager
    def test_context(self):
        """Context manager for testing that unlocks/locks container."""
        was_locked = self._is_locked
        self.unlock()
        try:
            yield self
        finally:
            if was_locked:
                self.lock()


# Global container instance
container = ServiceContainer()
