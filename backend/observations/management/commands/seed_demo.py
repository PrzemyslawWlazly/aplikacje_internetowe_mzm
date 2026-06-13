"""Tworzy powtarzalny zestaw danych demonstracyjnych projektu."""

import os  # Zmienne środowiskowe pozwalają zmienić hasła bez edycji kodu.
from datetime import datetime, timedelta, timezone as datetime_timezone  # Klasy budują historię i stały czas logu demo.
from decimal import Decimal  # Decimal odpowiada polom liczbowym modeli.

from django.contrib.auth import get_user_model  # Funkcja zwraca standardowy albo podmieniony model użytkownika.
from django.core.management.base import BaseCommand  # BaseCommand integruje funkcję z manage.py.
from django.db import transaction  # Jedna transakcja zapobiega częściowemu seedowi.
from django.utils import timezone  # Czas świadomy strefowo jest zgodny z ustawieniami Django.

from accounts.models import UserPreference  # Seed tworzy również trwały domyślny zakres Dashboardu.
from observations.models import (  # Modele reprezentują wszystkie zasoby potrzebne podczas prezentacji.
    EarthquakeEvent,
    SavedLocation,
    SyncJob,
    VolcanicEvent,
    WeatherSnapshot,
)


DEMO_LOCATIONS = (  # Stały zestaw pokazuje relację użytkownik-lokalizacje bez ręcznego klikania.
    ('Kraków', '50.064700', '19.945000', 'Polska', 'Małopolskie'),
    ('Tokio', '35.676200', '139.650300', 'Japonia', 'Kanto'),
    ('Reykjavik', '64.146600', '-21.942600', 'Islandia', 'Region stołeczny'),
    ('Neapol', '40.851800', '14.268100', 'Włochy', 'Kampania'),
    ('San Francisco', '37.774900', '-122.419400', 'Stany Zjednoczone', 'Kalifornia'),
)


class Command(BaseCommand):
    """Wypełnia pustą bazę bez duplikowania rekordów przy kolejnym uruchomieniu."""

    help = 'Tworzy użytkowników, lokalizacje i przykładowe dane środowiskowe do demonstracji.'

    @transaction.atomic
    def handle(self, *args, **options):
        # Pobieramy aktywny model użytkownika zgodnie z konfiguracją Django.
        user_model = get_user_model()
        # Dane logowania można nadpisać w środowisku uruchomieniowym.
        demo_password = os.getenv('DEMO_USER_PASSWORD', 'demo-change-me')
        # Hasło administratora również ma osobną zmienną.
        admin_password = os.getenv('DEMO_ADMIN_PASSWORD', 'admin-change-me')

        # Konto zwykłego użytkownika pokazuje izolację prywatnych lokalizacji.
        demo_user, _ = user_model.objects.get_or_create(
            username='demo',
            defaults={'email': 'demo@example.com', 'first_name': 'Demo'},
        )
        # Ustawiamy znane hasło przy każdym seedzie lokalnego środowiska.
        demo_user.set_password(demo_password)
        # Konto demonstracyjne nie otrzymuje uprawnień administratora.
        demo_user.is_staff = False
        # Zapisujemy pola zmieniane przez komendę.
        demo_user.save(update_fields=('password', 'is_staff'))

        # Administrator umożliwia pokazanie Django Admin oraz chronionych endpointów synchronizacji.
        admin_user, _ = user_model.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@example.com', 'first_name': 'Administrator'},
        )
        # Hasło jest przeznaczone wyłącznie do lokalnego demo.
        admin_user.set_password(admin_password)
        # is_staff otwiera panel, a is_superuser pozwala zarządzać wszystkimi modelami.
        admin_user.is_staff = True
        admin_user.is_superuser = True
        # Aktywne konto może od razu zalogować się do panelu.
        admin_user.is_active = True
        # Utrwalamy uprawnienia i hasło.
        admin_user.save(update_fields=('password', 'is_staff', 'is_superuser', 'is_active'))

        # Preferencje zwykłego użytkownika pokazują relację jeden do jednego podczas demo.
        UserPreference.objects.get_or_create(
            user=demo_user,
            defaults={'dashboard_range_hours': UserPreference.DashboardRange.DAY},
        )
        # Administrator również otrzymuje kompletny profil wymagany przez frontend.
        UserPreference.objects.get_or_create(
            user=admin_user,
            defaults={'dashboard_range_hours': UserPreference.DashboardRange.WEEK},
        )

        # Aktualny czas jest wspólną bazą dla przykładowej historii.
        now = timezone.now().replace(second=0, microsecond=0)
        # Iterujemy po pięciu lokalizacjach opisanych w specyfikacji.
        for index, (name, latitude, longitude, country, region) in enumerate(DEMO_LOCATIONS):
            # Współrzędne i właściciel są naturalnym kluczem lokalizacji.
            location, _ = SavedLocation.objects.get_or_create(
                user=demo_user,
                latitude=Decimal(latitude),
                longitude=Decimal(longitude),
                defaults={
                    'name': name,
                    'country': country,
                    'region': region,
                    'description': 'Przykładowa lokalizacja utworzona przez seed_demo.',
                },
            )
            # Aktualizujemy dane opisowe również po zmianie stałego zestawu demo.
            location.name = name
            # Kraj i region zapewniają czytelne dane w panelu.
            location.country = country
            location.region = region
            # Zapisujemy ewentualne zmiany etykiet.
            location.save(update_fields=('name', 'country', 'region', 'updated_at'))

            # Trzy pomiary dają wykresowi widoczną historię.
            for hours_ago in (2, 1, 0):
                # Temperatura jest lekko różna dla lokalizacji i kolejnych godzin.
                temperature = Decimal('14.50') + Decimal(index * 2) + Decimal(hours_ago) / Decimal('2')
                # Czas źródłowy jest częścią ograniczenia unikalności.
                measured_at = now - timedelta(hours=hours_ago)
                # update_or_create czyni komendę bezpieczną przy wielokrotnym uruchomieniu.
                WeatherSnapshot.objects.update_or_create(
                    location=location,
                    source='Seed demo',
                    measured_at=measured_at,
                    defaults={
                        'temperature': temperature,
                        'humidity': 55 + index,
                        'pressure': 1010 + index,
                        'wind_speed': Decimal('8.20') + Decimal(index),
                        'cloud_cover': 20 + index * 5,
                        'weather_code': 2,
                        'description': 'Częściowe zachmurzenie',
                    },
                )

        # Przykładowe trzęsienie pozwala pokazać bazę nawet bez dostępu do internetu.
        EarthquakeEvent.objects.update_or_create(
            external_id='demo-earthquake-1',
            defaults={
                'title': 'M4.8 - przykładowe zdarzenie sejsmiczne',
                'magnitude': Decimal('4.8'),
                'depth_km': Decimal('12.50'),
                'latitude': Decimal('37.774900'),
                'longitude': Decimal('-122.419400'),
                'place': 'San Francisco, California',
                'event_time': now - timedelta(hours=3),
                'source': 'Seed demo',
                'detail_url': '',
            },
        )

        # Dane wulkaniczne muszą zawsze pochodzić z prawdziwego katalogu, więc usuwamy dawny rekord demonstracyjny.
        VolcanicEvent.objects.filter(external_id='demo-volcano-1').delete()

        # Stała data tworzy naturalny klucz technicznego logu demonstracyjnego.
        demo_sync_started_at = datetime(2026, 1, 1, 12, 0, tzinfo=datetime_timezone.utc)
        # Przykładowy log wyjaśnia strukturę panelu synchronizacji.
        SyncJob.objects.get_or_create(
            job_type=SyncJob.JobType.EARTHQUAKE,
            status=SyncJob.Status.SUCCESS,
            started_at=demo_sync_started_at,
            defaults={
                'finished_at': demo_sync_started_at + timedelta(minutes=1),
                'items_fetched': 1,
                'error_message': '',
            },
        )

        # Komunikat końcowy jest widoczny w terminalu uruchamiającym komendę.
        self.stdout.write(self.style.SUCCESS('Dane demonstracyjne zostały przygotowane.'))
