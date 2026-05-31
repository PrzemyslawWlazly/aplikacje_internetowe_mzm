"""Adresy URL API dla modułu observations."""

from django.urls import path  # path łączy konkretną ścieżkę HTTP z widokiem Django.

from . import views  # Importujemy lokalne widoki z endpointami pogodowymi i sejsmicznymi.


urlpatterns = [  # Lista tras jest później podłączana w głównej konfiguracji projektu.
    path('weather/current/', views.current_weather, name='weather-current'),  # Aktualna pogoda dla punktów w Polsce.
    path('earthquakes/', views.earthquake_events, name='earthquake-events'),  # Zdarzenia sejsmiczne z USGS.
    path('storms/active/', views.active_storms, name='active-storms'),  # Cyklony i burze z EONET/Open-Meteo.
]
