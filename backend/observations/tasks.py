"""Zadania Celery uruchamiające cykliczne synchronizacje danych środowiskowych."""

from celery import shared_task  # Dekorator rejestruje funkcje w workerze bez wiązania z instancją aplikacji.

from .sync_services import (  # Usługi zawierają właściwą logikę i są używane także poza Celery.
    synchronize_earthquakes,
    synchronize_saved_location_weather,
    synchronize_volcanic_events,
)


@shared_task(name='observations.sync_earthquakes')
def sync_earthquakes_task():
    """Synchronizuje ostatnie 30 dni zdarzeń sejsmicznych."""

    return synchronize_earthquakes()  # Zwracamy licznik zapisanych rekordów do wyniku zadania.


@shared_task(name='observations.sync_volcanic_events')
def sync_volcanic_events_task():
    """Synchronizuje katalog wulkanów i historię erupcji Smithsonian GVP."""

    return synchronize_volcanic_events()  # Usługa zapisuje dane oraz rekord SyncJob.


@shared_task(name='observations.sync_saved_location_weather')
def sync_saved_location_weather_task():
    """Odświeża pogodę wszystkich lokalizacji obserwowanych przez użytkowników."""

    return synchronize_saved_location_weather()  # Wyniki trafiają do historii pogody i Redisa.
