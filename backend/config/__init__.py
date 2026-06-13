"""Pakiet konfiguracyjny Django i Celery."""

from .celery import app as celery_app  # Import podczas startu Django rejestruje aplikację Celery.


__all__ = ('celery_app',)  # Jawny eksport upraszcza wykrywanie instancji przez polecenie celery.
