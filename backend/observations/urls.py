"""Adresy URL API dla modułu observations."""

from django.urls import path  # path łączy konkretną ścieżkę HTTP z widokiem Django.

from . import views  # Importujemy lokalne widoki z endpointami pogodowymi i sejsmicznymi.


urlpatterns = [  # Lista tras jest później podłączana w głównej konfiguracji projektu.
    path(
        'locations/',
        views.SavedLocationListCreateView.as_view(),
        name='saved-location-list-create',
    ),  # GET zwraca własne punkty, a POST zapisuje nową lokalizację.
    path(
        'locations/<int:pk>/',
        views.SavedLocationDestroyView.as_view(),
        name='saved-location-delete',
    ),  # DELETE usuwa wyłącznie lokalizację należącą do użytkownika z JWT.
    path(
        'locations/<int:location_id>/weather/',
        views.SavedLocationWeatherView.as_view(),
        name='saved-location-weather',
    ),  # GET pobiera pogodę z Redisa albo Open-Meteo i zapisuje snapshot.
    path(
        'locations/<int:location_id>/weather/history/',
        views.SavedLocationWeatherHistoryView.as_view(),
        name='saved-location-weather-history',
    ),  # GET zwraca maksymalnie 100 najnowszych pomiarów zapisanej lokalizacji.
    path('weather/current/', views.current_weather, name='weather-current'),  # Aktualna pogoda dla punktów w Polsce.
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),  # Publiczne agregacje i prywatne lokalizacje.
    path('earthquakes/', views.earthquake_events, name='earthquake-events'),  # Zdarzenia sejsmiczne odczytywane z bazy.
    path('earthquakes/<int:event_id>/', views.earthquake_event_detail, name='earthquake-event-detail'),  # Szczegóły rekordu USGS.
    path('volcanoes/events/', views.volcanic_events, name='volcanic-events'),  # Pełny katalog wulkanów Smithsonian z bazy.
    path('volcanoes/events/<int:event_id>/', views.volcanic_event_detail, name='volcanic-event-detail'),  # Szczegóły wulkanu.
    path('storms/active/', views.active_storms, name='active-storms'),  # Cyklony i burze z EONET/Open-Meteo.
    path('admin/sync/status/', views.AdminSyncStatusView.as_view(), name='admin-sync-status'),  # Chronione logi synchronizacji.
    path('admin/sync/<str:job_type>/', views.AdminSyncStartView.as_view(), name='admin-sync-start'),  # Chronione uruchomienie zadania.
]
