"""Konfiguracja panelu administracyjnego dla modeli obserwacyjnych."""

from django.contrib import admin  # admin udostępnia dekorator rejestrujący modele w panelu Django.

from .models import (  # Importujemy modele, które mają być widoczne w panelu administratora.
    EarthquakeEvent,  # Model trzęsień ziemi.
    SavedLocation,  # Model lokalizacji zapisanych przez użytkowników.
    SyncJob,  # Model logów synchronizacji.
    VolcanicEvent,  # Model zdarzeń wulkanicznych.
    WeatherSnapshot,  # Model historycznych pomiarów pogody.
)


@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    """Ustawienia listy lokalizacji zapisanych w panelu admina."""

    list_display = ('name', 'user', 'country', 'region', 'latitude', 'longitude', 'created_at')  # Kolumny tabeli.
    list_filter = ('country', 'region', 'created_at')  # Filtry po prawej stronie panelu.
    search_fields = ('name', 'country', 'region', 'user__username', 'user__email')  # Pola przeszukiwane tekstowo.


@admin.register(WeatherSnapshot)
class WeatherSnapshotAdmin(admin.ModelAdmin):
    """Ustawienia listy snapshotów pogodowych w panelu admina."""

    list_display = (  # Kolumny dobrane pod szybkie sprawdzenie pomiaru.
        'location',  # Lokalizacja, dla której zapisano pogodę.
        'temperature',  # Temperatura z API.
        'humidity',  # Wilgotność z API.
        'pressure',  # Ciśnienie z API.
        'wind_speed',  # Prędkość wiatru z API.
        'source',  # Źródło danych.
        'measured_at',  # Czas pomiaru.
    )
    list_filter = ('source', 'measured_at')  # Filtry pozwalają zawęzić wyniki po źródle i czasie.
    search_fields = ('location__name', 'description')  # Szukanie po nazwie lokalizacji i opisie.


@admin.register(EarthquakeEvent)
class EarthquakeEventAdmin(admin.ModelAdmin):
    """Ustawienia listy zdarzeń sejsmicznych w panelu admina."""

    list_display = ('external_id', 'magnitude', 'place', 'event_time', 'source')  # Najważniejsze dane sejsmiczne.
    list_filter = ('source', 'event_time')  # Filtrowanie po źródle i czasie zdarzenia.
    search_fields = ('external_id', 'title', 'place')  # Szukanie po id, tytule i lokalizacji tekstowej.


@admin.register(VolcanicEvent)
class VolcanicEventAdmin(admin.ModelAdmin):
    """Ustawienia listy zdarzeń wulkanicznych w panelu admina."""

    list_display = ('external_id', 'title', 'volcano_name', 'region', 'event_time', 'source', 'status')  # Kolumny listy.
    list_filter = ('source', 'region', 'status', 'event_time')  # Filtry pasują do przeglądania zdarzeń.
    search_fields = ('external_id', 'title', 'volcano_name', 'region')  # Szukanie obejmuje nazwę i region.


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    """Ustawienia listy zadań synchronizacji w panelu admina."""

    list_display = ('job_type', 'status', 'started_at', 'finished_at', 'items_fetched')  # Kolumny statusu zadania.
    list_filter = ('job_type', 'status', 'started_at')  # Filtry pomagają znaleźć błędy i ostatnie zadania.
    search_fields = ('error_message',)  # Szukanie po treści błędu ułatwia debugowanie.
