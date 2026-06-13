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
        'cloud_cover',  # Zachmurzenie uzupełnia zestaw danych pogodowych.
        'weather_code',  # Kod WMO pomaga diagnozować opis warunków.
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
    """Ustawienia listy katalogu wulkanów w panelu admina."""

    list_display = (  # Kolumny pokazują najważniejsze dane katalogowe i erupcyjne.
        'external_id',  # Oficjalny numer Smithsonian GVP.
        'volcano_name',  # Podstawowa nazwa wulkanu.
        'country',  # Kraj ułatwia szybkie rozpoznanie.
        'volcano_type',  # Typ morfologiczny wulkanu.
        'last_eruption_year',  # Rok ostatniej znanej erupcji.
        'vei',  # VEI ostatniej erupcji, jeśli jest znane.
        'max_vei',  # Najwyższe VEI w historii katalogowej.
        'source',  # Jawne źródło danych.
    )
    list_filter = ('source', 'country', 'region', 'volcano_type', 'max_vei')  # Filtry odpowiadają polom katalogu.
    search_fields = ('external_id', 'title', 'volcano_name', 'country', 'region')  # Szukanie obejmuje nazwę i położenie.


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    """Ustawienia listy zadań synchronizacji w panelu admina."""

    list_display = ('job_type', 'status', 'started_at', 'finished_at', 'items_fetched')  # Kolumny statusu zadania.
    list_filter = ('job_type', 'status', 'started_at')  # Filtry pomagają znaleźć błędy i ostatnie zadania.
    search_fields = ('error_message',)  # Szukanie po treści błędu ułatwia debugowanie.
