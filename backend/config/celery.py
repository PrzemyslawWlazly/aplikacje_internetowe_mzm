"""Konfiguracja Celery dla zadań asynchronicznych projektu."""

import os  # Zmienna środowiskowa wskazuje moduł ustawień Django.

from celery import Celery  # Główna klasa tworzy aplikację workera i schedulera.


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # Worker używa tej samej konfiguracji co backend HTTP.

app = Celery('matka_ziemia_monitor')  # Czytelna nazwa pojawia się w logach procesów Celery.
app.config_from_object('django.conf:settings', namespace='CELERY')  # Ustawienia z prefiksem CELERY_ trafiają do aplikacji.
app.autodiscover_tasks()  # Celery wyszukuje pliki tasks.py we wszystkich aplikacjach Django.
