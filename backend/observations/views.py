"""Widoki API dla danych obserwacyjnych aplikacji NieZmoknij."""

import json  # Moduł JSON pozwala zamienić tekst z API zewnętrznego na struktury Pythona.
from datetime import datetime, timedelta, timezone as datetime_timezone  # Datetime obsługuje zakresy i czas UTC.
from decimal import Decimal  # Decimal zapisuje pomiary bez błędów typowych dla liczb float.
from urllib.error import HTTPError, URLError  # URLError/HTTPError obsługują problemy połączenia z API zewnętrznym.
from urllib.parse import urlencode  # urlencode bezpiecznie buduje query string dla adresów URL.
from urllib.request import Request, urlopen  # Request i urlopen wykonują prosty request HTTP bez dodatkowej biblioteki.

from django.conf import settings  # Ustawienia zawierają konfigurowalny czas życia cache pogody.
from django.core.cache import cache  # Cache ogranicza liczbę zapytań do zewnętrznych API.
from django.shortcuts import get_object_or_404  # Funkcja zwraca 404 bez ujawniania cudzych lokalizacji.
from django.utils import timezone  # timezone daje poprawny czas zgodny z ustawieniami Django.
from drf_spectacular.types import OpenApiTypes  # Ogólny obiekt opisuje starsze odpowiedzi bez osobnego serializera.
from drf_spectacular.utils import extend_schema  # Dekorator opisuje ręczne endpointy w OpenAPI.
from rest_framework import status  # status przechowuje czytelne stałe kodów HTTP.
from rest_framework.decorators import api_view, permission_classes  # Dekoratory zamieniają funkcje w endpointy DRF.
from rest_framework.generics import DestroyAPIView, ListCreateAPIView  # Widoki generyczne realizują standardowe operacje CRUD.
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated  # Uprawnienia rozdzielają publiczne i administracyjne zasoby.
from rest_framework.response import Response  # Response zwraca dane jako odpowiedź API DRF.
from rest_framework.views import APIView  # APIView obsługuje niestandardowe endpointy pogody i historii.

from .models import (  # Modele przechowują dane użytkownika, zdarzenia i logi synchronizacji.
    EarthquakeEvent,
    SavedLocation,
    SyncJob,
    VolcanicEvent,
    WeatherSnapshot,
)
from .serializers import (  # Serializery walidują formularze i dokumentują odpowiedzi API.
    DashboardSummarySerializer,
    EarthquakeEventSerializer,
    EnvironmentalListResponseSerializer,
    LocationWeatherResponseSerializer,
    SavedLocationSerializer,
    SyncJobSerializer,
    SyncTaskAcceptedSerializer,
    VolcanicEventSerializer,
    WeatherHistoryResponseSerializer,
    WeatherSnapshotSerializer,
    saved_locations_queryset,
)
from .dashboard import (  # Dashboard rozdziela cache publiczny od prywatnych danych użytkownika.
    DASHBOARD_ALLOWED_RANGES,
    DASHBOARD_CACHE_TTL,
    build_global_dashboard,
    build_user_dashboard,
    invalidate_user_dashboard_cache,
)
from .sync_services import synchronize_earthquakes, synchronize_volcanic_events  # Pierwsze zasilenie bazy używa tych samych usług co Celery.


OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'  # Publiczne API pogodowe bez klucza.
WORLD_BANK_COUNTRIES_URL = 'https://api.worldbank.org/v2/country?format=json&per_page=400'  # Oficjalne API podaje stolice i ich współrzędne bez klucza.
USGS_EARTHQUAKE_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'  # Oficjalny endpoint zdarzeń USGS.
EONET_EVENTS_URL = 'https://eonet.gsfc.nasa.gov/api/v3/events'  # NASA EONET udostępnia aktywne zdarzenia naturalne.
REQUEST_TIMEOUT = 8  # Limit czasu zabezpiecza backend przed zbyt długim czekaniem na zewnętrzne API.
OPEN_METEO_BATCH_SIZE = 80  # Dzielimy pogodę na paczki, żeby adres URL nie był zbyt długi.
CYCLONE_CATEGORY_ID = 'severeStorms'  # W EONET v3 kategoria severeStorms obejmuje silne burze i cyklony.
STORM_WEATHER_CODES = {95, 96, 99}  # Kody WMO 95-99 oznaczają burzę, w tym burzę z gradem.
CAPITAL_POINTS_CACHE_KEY = 'weather:capital-points:world-bank:v3'  # Klucz świeżej listy stolic jest związany z aktualnym źródłem danych.
CAPITAL_POINTS_FALLBACK_KEY = 'weather:capital-points:world-bank:last-good:v3'  # Ostatnia dobra lista chroni aplikację przed awarią źródła.
GLOBAL_WEATHER_CACHE_KEY = 'weather:current:global-expanded-cities:v6'  # Nowa wersja zawiera więcej miast i lokalną informację dzień/noc.
GLOBAL_WEATHER_FALLBACK_KEY = 'weather:current:global-expanded-cities:last-good:v6'  # Fallback ma ten sam rozszerzony format.
CYCLONE_FALLBACK_KEY = 'cyclones:eonet:last-good:v1'  # Osobny fallback zachowuje ostatnie cyklony podczas krótkiej awarii EONET.
LEGACY_STORM_FALLBACK_KEY = 'storms:active:eonet-openmeteo:last-good:v2'  # Stary cache pozwala płynnie przejść na osobny fallback.
LOCATION_WEATHER_CURRENT_FIELDS = (  # Lista wymaganych pól chroni bazę przed niepełnym pomiarem.
    'temperature_2m',  # Temperatura jest podstawową wartością prezentowaną użytkownikowi.
    'relative_humidity_2m',  # Wilgotność jest wymagana przez specyfikację projektu.
    'pressure_msl',  # Ciśnienie jest wymagane przez model historycznego snapshotu.
    'wind_speed_10m',  # Prędkość wiatru jest wymagana przez specyfikację.
)


WMO_WEATHER_DESCRIPTIONS = {  # Mapa zamienia techniczny kod WMO na krótki polski opis.
    0: 'Bezchmurnie',  # Kod 0 oznacza czyste niebo.
    1: 'Przeważnie bezchmurnie',  # Kod 1 oznacza niewielkie zachmurzenie.
    2: 'Częściowe zachmurzenie',  # Kod 2 oznacza częściowe zachmurzenie.
    3: 'Pochmurno',  # Kod 3 oznacza pełne zachmurzenie.
    45: 'Mgła',  # Kod 45 oznacza mgłę.
    48: 'Mgła osadzająca szadź',  # Kod 48 oznacza mgłę z osadzaniem szadzi.
    51: 'Lekka mżawka',  # Kod 51 opisuje słabą mżawkę.
    53: 'Mżawka',  # Kod 53 opisuje umiarkowaną mżawkę.
    55: 'Silna mżawka',  # Kod 55 opisuje intensywną mżawkę.
    61: 'Lekki deszcz',  # Kod 61 opisuje słaby deszcz.
    63: 'Deszcz',  # Kod 63 opisuje umiarkowany deszcz.
    65: 'Silny deszcz',  # Kod 65 opisuje intensywny deszcz.
    71: 'Lekki śnieg',  # Kod 71 opisuje słabe opady śniegu.
    73: 'Śnieg',  # Kod 73 opisuje umiarkowany śnieg.
    75: 'Silny śnieg',  # Kod 75 opisuje intensywny śnieg.
    77: 'Ziarna śnieżne',  # Kod 77 opisuje ziarna śnieżne.
    80: 'Lekki przelotny deszcz',  # Kod 80 opisuje słaby opad przelotny.
    81: 'Przelotny deszcz',  # Kod 81 opisuje umiarkowany opad przelotny.
    82: 'Silny przelotny deszcz',  # Kod 82 opisuje intensywny opad przelotny.
    85: 'Lekki przelotny śnieg',  # Kod 85 opisuje słaby przelotny śnieg.
    86: 'Silny przelotny śnieg',  # Kod 86 opisuje intensywny przelotny śnieg.
    95: 'Burza',  # Kod 95 oznacza burzę.
    96: 'Burza z lekkim gradem',  # Kod 96 oznacza burzę z gradem.
    99: 'Burza z silnym gradem',  # Kod 99 oznacza silną burzę gradową.
}


POLISH_WEATHER_POINTS = [  # Dla Polski pobieramy 20 największych miast, bo użytkownik chce gęstszą warstwę krajową.
    {'name': 'Warszawa', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 52.2297, 'longitude': 21.0122},  # 1.
    {'name': 'Krakow', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.0647, 'longitude': 19.9450},  # 2.
    {'name': 'Wroclaw', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 51.1079, 'longitude': 17.0385},  # 3.
    {'name': 'Lodz', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 51.7592, 'longitude': 19.4560},  # 4.
    {'name': 'Poznan', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 52.4064, 'longitude': 16.9252},  # 5.
    {'name': 'Gdansk', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 54.3520, 'longitude': 18.6466},  # 6.
    {'name': 'Szczecin', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 53.4285, 'longitude': 14.5528},  # 7.
    {'name': 'Bydgoszcz', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 53.1235, 'longitude': 18.0084},  # 8.
    {'name': 'Lublin', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 51.2465, 'longitude': 22.5684},  # 9.
    {'name': 'Bialystok', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 53.1325, 'longitude': 23.1688},  # 10.
    {'name': 'Katowice', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.2649, 'longitude': 19.0238},  # 11.
    {'name': 'Gdynia', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 54.5189, 'longitude': 18.5305},  # 12.
    {'name': 'Czestochowa', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.8118, 'longitude': 19.1203},  # 13.
    {'name': 'Radom', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 51.4027, 'longitude': 21.1471},  # 14.
    {'name': 'Torun', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 53.0138, 'longitude': 18.5984},  # 15.
    {'name': 'Sosnowiec', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.2863, 'longitude': 19.1041},  # 16.
    {'name': 'Kielce', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.8661, 'longitude': 20.6286},  # 17.
    {'name': 'Rzeszow', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.0413, 'longitude': 21.9990},  # 18.
    {'name': 'Gliwice', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 50.2945, 'longitude': 18.6714},  # 19.
    {'name': 'Olsztyn', 'country': 'Polska', 'group': 'poland_top_20', 'latitude': 53.7784, 'longitude': 20.4801},  # 20.
]


G20_MAJOR_CITY_POINTS = [  # Dla państw G20 dodajemy po 7 największych miast, żeby mapa była bogatsza niż same stolice.
    {'name': 'Buenos Aires', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -34.6037, 'longitude': -58.3816},
    {'name': 'Cordoba', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -31.4201, 'longitude': -64.1888},
    {'name': 'Rosario', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -32.9442, 'longitude': -60.6505},
    {'name': 'Mendoza', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -32.8895, 'longitude': -68.8458},
    {'name': 'La Plata', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -34.9215, 'longitude': -57.9545},
    {'name': 'San Miguel de Tucuman', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -26.8083, 'longitude': -65.2176},
    {'name': 'Mar del Plata', 'country': 'Argentina', 'group': 'g20_major_city', 'latitude': -38.0055, 'longitude': -57.5426},
    {'name': 'Sydney', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -33.8688, 'longitude': 151.2093},
    {'name': 'Melbourne', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -37.8136, 'longitude': 144.9631},
    {'name': 'Brisbane', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -27.4698, 'longitude': 153.0251},
    {'name': 'Perth', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -31.9523, 'longitude': 115.8613},
    {'name': 'Adelaide', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -34.9285, 'longitude': 138.6007},
    {'name': 'Gold Coast', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -28.0167, 'longitude': 153.4000},
    {'name': 'Canberra', 'country': 'Australia', 'group': 'g20_major_city', 'latitude': -35.2809, 'longitude': 149.1300},
    {'name': 'Sao Paulo', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -23.5505, 'longitude': -46.6333},
    {'name': 'Rio de Janeiro', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -22.9068, 'longitude': -43.1729},
    {'name': 'Brasilia', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -15.7939, 'longitude': -47.8828},
    {'name': 'Salvador', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -12.9777, 'longitude': -38.5016},
    {'name': 'Fortaleza', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -3.7319, 'longitude': -38.5267},
    {'name': 'Belo Horizonte', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -19.9167, 'longitude': -43.9345},
    {'name': 'Manaus', 'country': 'Brazil', 'group': 'g20_major_city', 'latitude': -3.1190, 'longitude': -60.0217},
    {'name': 'Toronto', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 43.6532, 'longitude': -79.3832},
    {'name': 'Montreal', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 45.5017, 'longitude': -73.5673},
    {'name': 'Vancouver', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 49.2827, 'longitude': -123.1207},
    {'name': 'Calgary', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 51.0447, 'longitude': -114.0719},
    {'name': 'Edmonton', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 53.5461, 'longitude': -113.4938},
    {'name': 'Ottawa', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 45.4215, 'longitude': -75.6972},
    {'name': 'Winnipeg', 'country': 'Canada', 'group': 'g20_major_city', 'latitude': 49.8951, 'longitude': -97.1384},
    {'name': 'Shanghai', 'country': 'China', 'group': 'g20_major_city', 'latitude': 31.2304, 'longitude': 121.4737},
    {'name': 'Beijing', 'country': 'China', 'group': 'g20_major_city', 'latitude': 39.9042, 'longitude': 116.4074},
    {'name': 'Guangzhou', 'country': 'China', 'group': 'g20_major_city', 'latitude': 23.1291, 'longitude': 113.2644},
    {'name': 'Shenzhen', 'country': 'China', 'group': 'g20_major_city', 'latitude': 22.5431, 'longitude': 114.0579},
    {'name': 'Chengdu', 'country': 'China', 'group': 'g20_major_city', 'latitude': 30.5728, 'longitude': 104.0668},
    {'name': 'Chongqing', 'country': 'China', 'group': 'g20_major_city', 'latitude': 29.5630, 'longitude': 106.5516},
    {'name': 'Tianjin', 'country': 'China', 'group': 'g20_major_city', 'latitude': 39.3434, 'longitude': 117.3616},
    {'name': 'Paris', 'country': 'France', 'group': 'g20_major_city', 'latitude': 48.8566, 'longitude': 2.3522},
    {'name': 'Marseille', 'country': 'France', 'group': 'g20_major_city', 'latitude': 43.2965, 'longitude': 5.3698},
    {'name': 'Lyon', 'country': 'France', 'group': 'g20_major_city', 'latitude': 45.7640, 'longitude': 4.8357},
    {'name': 'Toulouse', 'country': 'France', 'group': 'g20_major_city', 'latitude': 43.6047, 'longitude': 1.4442},
    {'name': 'Nice', 'country': 'France', 'group': 'g20_major_city', 'latitude': 43.7102, 'longitude': 7.2620},
    {'name': 'Nantes', 'country': 'France', 'group': 'g20_major_city', 'latitude': 47.2184, 'longitude': -1.5536},
    {'name': 'Montpellier', 'country': 'France', 'group': 'g20_major_city', 'latitude': 43.6110, 'longitude': 3.8767},
    {'name': 'Berlin', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 52.5200, 'longitude': 13.4050},
    {'name': 'Hamburg', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 53.5511, 'longitude': 9.9937},
    {'name': 'Munich', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 48.1351, 'longitude': 11.5820},
    {'name': 'Cologne', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 50.9375, 'longitude': 6.9603},
    {'name': 'Frankfurt am Main', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 50.1109, 'longitude': 8.6821},
    {'name': 'Stuttgart', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 48.7758, 'longitude': 9.1829},
    {'name': 'Dusseldorf', 'country': 'Germany', 'group': 'g20_major_city', 'latitude': 51.2277, 'longitude': 6.7735},
    {'name': 'Mumbai', 'country': 'India', 'group': 'g20_major_city', 'latitude': 19.0760, 'longitude': 72.8777},
    {'name': 'Delhi', 'country': 'India', 'group': 'g20_major_city', 'latitude': 28.7041, 'longitude': 77.1025},
    {'name': 'Bengaluru', 'country': 'India', 'group': 'g20_major_city', 'latitude': 12.9716, 'longitude': 77.5946},
    {'name': 'Hyderabad', 'country': 'India', 'group': 'g20_major_city', 'latitude': 17.3850, 'longitude': 78.4867},
    {'name': 'Ahmedabad', 'country': 'India', 'group': 'g20_major_city', 'latitude': 23.0225, 'longitude': 72.5714},
    {'name': 'Chennai', 'country': 'India', 'group': 'g20_major_city', 'latitude': 13.0827, 'longitude': 80.2707},
    {'name': 'Kolkata', 'country': 'India', 'group': 'g20_major_city', 'latitude': 22.5726, 'longitude': 88.3639},
    {'name': 'Jakarta', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -6.2088, 'longitude': 106.8456},
    {'name': 'Surabaya', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -7.2575, 'longitude': 112.7521},
    {'name': 'Bandung', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -6.9175, 'longitude': 107.6191},
    {'name': 'Medan', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': 3.5952, 'longitude': 98.6722},
    {'name': 'Semarang', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -6.9667, 'longitude': 110.4167},
    {'name': 'Makassar', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -5.1477, 'longitude': 119.4327},
    {'name': 'Palembang', 'country': 'Indonesia', 'group': 'g20_major_city', 'latitude': -2.9761, 'longitude': 104.7754},
    {'name': 'Rome', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 41.9028, 'longitude': 12.4964},
    {'name': 'Milan', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 45.4642, 'longitude': 9.1900},
    {'name': 'Naples', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 40.8518, 'longitude': 14.2681},
    {'name': 'Turin', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 45.0703, 'longitude': 7.6869},
    {'name': 'Palermo', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 38.1157, 'longitude': 13.3615},
    {'name': 'Genoa', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 44.4056, 'longitude': 8.9463},
    {'name': 'Bologna', 'country': 'Italy', 'group': 'g20_major_city', 'latitude': 44.4949, 'longitude': 11.3426},
    {'name': 'Tokyo', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 35.6762, 'longitude': 139.6503},
    {'name': 'Yokohama', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 35.4437, 'longitude': 139.6380},
    {'name': 'Osaka', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 34.6937, 'longitude': 135.5023},
    {'name': 'Nagoya', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 35.1815, 'longitude': 136.9066},
    {'name': 'Sapporo', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 43.0618, 'longitude': 141.3545},
    {'name': 'Fukuoka', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 33.5902, 'longitude': 130.4017},
    {'name': 'Kobe', 'country': 'Japan', 'group': 'g20_major_city', 'latitude': 34.6901, 'longitude': 135.1955},
    {'name': 'Mexico City', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 19.4326, 'longitude': -99.1332},
    {'name': 'Guadalajara', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 20.6597, 'longitude': -103.3496},
    {'name': 'Monterrey', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 25.6866, 'longitude': -100.3161},
    {'name': 'Puebla', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 19.0414, 'longitude': -98.2063},
    {'name': 'Tijuana', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 32.5149, 'longitude': -117.0382},
    {'name': 'Leon', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 21.1250, 'longitude': -101.6860},
    {'name': 'Juarez', 'country': 'Mexico', 'group': 'g20_major_city', 'latitude': 31.6904, 'longitude': -106.4245},
    {'name': 'Moscow', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 55.7558, 'longitude': 37.6173},
    {'name': 'Saint Petersburg', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 59.9311, 'longitude': 30.3609},
    {'name': 'Novosibirsk', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 55.0084, 'longitude': 82.9357},
    {'name': 'Yekaterinburg', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 56.8389, 'longitude': 60.6057},
    {'name': 'Kazan', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 55.8304, 'longitude': 49.0661},
    {'name': 'Nizhny Novgorod', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 56.2965, 'longitude': 43.9361},
    {'name': 'Chelyabinsk', 'country': 'Russia', 'group': 'g20_major_city', 'latitude': 55.1644, 'longitude': 61.4368},
    {'name': 'Riyadh', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 24.7136, 'longitude': 46.6753},
    {'name': 'Jeddah', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 21.4858, 'longitude': 39.1925},
    {'name': 'Mecca', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 21.3891, 'longitude': 39.8579},
    {'name': 'Medina', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 24.5247, 'longitude': 39.5692},
    {'name': 'Dammam', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 26.4207, 'longitude': 50.0888},
    {'name': 'Taif', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 21.4373, 'longitude': 40.5127},
    {'name': 'Tabuk', 'country': 'Saudi Arabia', 'group': 'g20_major_city', 'latitude': 28.3835, 'longitude': 36.5662},
    {'name': 'Johannesburg', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -26.2041, 'longitude': 28.0473},
    {'name': 'Cape Town', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -33.9249, 'longitude': 18.4241},
    {'name': 'Durban', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -29.8587, 'longitude': 31.0218},
    {'name': 'Pretoria', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -25.7479, 'longitude': 28.2293},
    {'name': 'Port Elizabeth', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -33.9608, 'longitude': 25.6022},
    {'name': 'Bloemfontein', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -29.0852, 'longitude': 26.1596},
    {'name': 'Pietermaritzburg', 'country': 'South Africa', 'group': 'g20_major_city', 'latitude': -29.6006, 'longitude': 30.3794},
    {'name': 'Seoul', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 37.5665, 'longitude': 126.9780},
    {'name': 'Busan', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 35.1796, 'longitude': 129.0756},
    {'name': 'Incheon', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 37.4563, 'longitude': 126.7052},
    {'name': 'Daegu', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 35.8714, 'longitude': 128.6014},
    {'name': 'Daejeon', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 36.3504, 'longitude': 127.3845},
    {'name': 'Gwangju', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 35.1595, 'longitude': 126.8526},
    {'name': 'Ulsan', 'country': 'South Korea', 'group': 'g20_major_city', 'latitude': 35.5384, 'longitude': 129.3114},
    {'name': 'Istanbul', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 41.0082, 'longitude': 28.9784},
    {'name': 'Ankara', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 39.9334, 'longitude': 32.8597},
    {'name': 'Izmir', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 38.4237, 'longitude': 27.1428},
    {'name': 'Bursa', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 40.1828, 'longitude': 29.0660},
    {'name': 'Antalya', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 36.8969, 'longitude': 30.7133},
    {'name': 'Adana', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 37.0000, 'longitude': 35.3213},
    {'name': 'Konya', 'country': 'Turkey', 'group': 'g20_major_city', 'latitude': 37.8746, 'longitude': 32.4932},
    {'name': 'London', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 51.5072, 'longitude': -0.1276},
    {'name': 'Birmingham', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 52.4862, 'longitude': -1.8904},
    {'name': 'Manchester', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 53.4808, 'longitude': -2.2426},
    {'name': 'Glasgow', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 55.8642, 'longitude': -4.2518},
    {'name': 'Liverpool', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 53.4084, 'longitude': -2.9916},
    {'name': 'Leeds', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 53.8008, 'longitude': -1.5491},
    {'name': 'Sheffield', 'country': 'United Kingdom', 'group': 'g20_major_city', 'latitude': 53.3811, 'longitude': -1.4701},
    {'name': 'New York', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 40.7128, 'longitude': -74.0060},
    {'name': 'Los Angeles', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 34.0522, 'longitude': -118.2437},
    {'name': 'Chicago', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 41.8781, 'longitude': -87.6298},
    {'name': 'Houston', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 29.7604, 'longitude': -95.3698},
    {'name': 'Phoenix', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 33.4484, 'longitude': -112.0740},
    {'name': 'Philadelphia', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 39.9526, 'longitude': -75.1652},
    {'name': 'San Antonio', 'country': 'United States', 'group': 'g20_major_city', 'latitude': 29.4241, 'longitude': -98.4936},
]

# Dodatkowa siatka uzupełnia luki między stolicami i głównymi miastami G20.
SUPPLEMENTAL_WEATHER_POINTS = [
    {'name': 'Barcelona', 'country': 'Spain', 'group': 'supplemental_city', 'latitude': 41.3874, 'longitude': 2.1686},  # Duże miasto śródziemnomorskie.
    {'name': 'Valencia', 'country': 'Spain', 'group': 'supplemental_city', 'latitude': 39.4699, 'longitude': -0.3763},  # Wschodnie wybrzeże Hiszpanii.
    {'name': 'Seville', 'country': 'Spain', 'group': 'supplemental_city', 'latitude': 37.3891, 'longitude': -5.9845},  # Gorące południe Półwyspu Iberyjskiego.
    {'name': 'Bilbao', 'country': 'Spain', 'group': 'supplemental_city', 'latitude': 43.2630, 'longitude': -2.9350},  # Wilgotniejsze wybrzeże Atlantyku.
    {'name': 'Malaga', 'country': 'Spain', 'group': 'supplemental_city', 'latitude': 36.7213, 'longitude': -4.4214},  # Południowe wybrzeże Morza Śródziemnego.
    {'name': 'Las Palmas de Gran Canaria', 'country': 'Spain - Canary Islands', 'group': 'supplemental_city', 'latitude': 28.1235, 'longitude': -15.4363},  # Wschodnie Wyspy Kanaryjskie.
    {'name': 'Santa Cruz de Tenerife', 'country': 'Spain - Canary Islands', 'group': 'supplemental_city', 'latitude': 28.4636, 'longitude': -16.2518},  # Zachodnie Wyspy Kanaryjskie.
    {'name': 'Prague', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 50.0755, 'longitude': 14.4378},  # Stolica Czech pozostaje także punktem zagęszczającym region.
    {'name': 'Brno', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 49.1951, 'longitude': 16.6068},  # Największe miasto Moraw.
    {'name': 'Ostrava', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 49.8209, 'longitude': 18.2625},  # Wschodnia część Czech.
    {'name': 'Plzen', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 49.7384, 'longitude': 13.3736},  # Zachodnia część Czech.
    {'name': 'Liberec', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 50.7663, 'longitude': 15.0543},  # Północny górski region Czech.
    {'name': 'Olomouc', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 49.5938, 'longitude': 17.2509},  # Środkowe Morawy.
    {'name': 'Ceske Budejovice', 'country': 'Czechia', 'group': 'supplemental_city', 'latitude': 48.9745, 'longitude': 14.4743},  # Południowe Czechy.
    {'name': 'Vienna', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 48.2082, 'longitude': 16.3738},  # Stolica Austrii.
    {'name': 'Graz', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 47.0707, 'longitude': 15.4395},  # Południowo-wschodnia Austria.
    {'name': 'Linz', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 48.3069, 'longitude': 14.2858},  # Północna Austria nad Dunajem.
    {'name': 'Salzburg', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 47.8095, 'longitude': 13.0550},  # Region alpejski.
    {'name': 'Innsbruck', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 47.2692, 'longitude': 11.4041},  # Zachodnia dolina alpejska.
    {'name': 'Klagenfurt', 'country': 'Austria', 'group': 'supplemental_city', 'latitude': 46.6247, 'longitude': 14.3053},  # Południowa Austria.
    {'name': 'Bratislava', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 48.1486, 'longitude': 17.1077},  # Zachodnia Słowacja.
    {'name': 'Kosice', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 48.7164, 'longitude': 21.2611},  # Wschodnia Słowacja.
    {'name': 'Presov', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 48.9984, 'longitude': 21.2396},  # Północno-wschodnia Słowacja.
    {'name': 'Zilina', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 49.2231, 'longitude': 18.7394},  # Północno-zachodnia Słowacja.
    {'name': 'Banska Bystrica', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 48.7363, 'longitude': 19.1462},  # Środkowa Słowacja.
    {'name': 'Nitra', 'country': 'Slovakia', 'group': 'supplemental_city', 'latitude': 48.3061, 'longitude': 18.0764},  # Południowo-zachodnia Słowacja.
    {'name': 'Wuhan', 'country': 'China', 'group': 'supplemental_city', 'latitude': 30.5928, 'longitude': 114.3055},  # Centralne Chiny nad Jangcy.
    {'name': 'Xian', 'country': 'China', 'group': 'supplemental_city', 'latitude': 34.3416, 'longitude': 108.9398},  # Północno-środkowe Chiny.
    {'name': 'Hangzhou', 'country': 'China', 'group': 'supplemental_city', 'latitude': 30.2741, 'longitude': 120.1551},  # Wschodnie Chiny.
    {'name': 'Nanjing', 'country': 'China', 'group': 'supplemental_city', 'latitude': 32.0603, 'longitude': 118.7969},  # Delta Jangcy.
    {'name': 'Suzhou', 'country': 'China', 'group': 'supplemental_city', 'latitude': 31.2989, 'longitude': 120.5853},  # Gęsty region wschodniego wybrzeża.
    {'name': 'Harbin', 'country': 'China', 'group': 'supplemental_city', 'latitude': 45.8038, 'longitude': 126.5349},  # Chłodna północno-wschodnia część kraju.
    {'name': 'Shenyang', 'country': 'China', 'group': 'supplemental_city', 'latitude': 41.8057, 'longitude': 123.4315},  # Mandżuria.
    {'name': 'Qingdao', 'country': 'China', 'group': 'supplemental_city', 'latitude': 36.0671, 'longitude': 120.3826},  # Wybrzeże Morza Żółtego.
    {'name': 'Xiamen', 'country': 'China', 'group': 'supplemental_city', 'latitude': 24.4798, 'longitude': 118.0894},  # Subtropikalne południowo-wschodnie wybrzeże.
    {'name': 'Kunming', 'country': 'China', 'group': 'supplemental_city', 'latitude': 25.0389, 'longitude': 102.7183},  # Wyżynny południowy zachód.
    {'name': 'Urumqi', 'country': 'China', 'group': 'supplemental_city', 'latitude': 43.8256, 'longitude': 87.6168},  # Kontynentalny klimat zachodnich Chin.
    {'name': 'Lhasa', 'country': 'China', 'group': 'supplemental_city', 'latitude': 29.6520, 'longitude': 91.1721},  # Wysoko położony Tybet.
    {'name': 'Sanya', 'country': 'China', 'group': 'supplemental_city', 'latitude': 18.2528, 'longitude': 109.5119},  # Tropikalna wyspa Hajnan.
    {'name': 'Lisbon', 'country': 'Portugal', 'group': 'supplemental_city', 'latitude': 38.7223, 'longitude': -9.1393},  # Atlantyckie wybrzeże Europy.
    {'name': 'Porto', 'country': 'Portugal', 'group': 'supplemental_city', 'latitude': 41.1579, 'longitude': -8.6291},  # Północ Portugalii.
    {'name': 'Reykjavik', 'country': 'Iceland', 'group': 'supplemental_city', 'latitude': 64.1466, 'longitude': -21.9426},  # Północny Atlantyk.
    {'name': 'Bergen', 'country': 'Norway', 'group': 'supplemental_city', 'latitude': 60.3913, 'longitude': 5.3221},  # Wilgotne zachodnie wybrzeże Norwegii.
    {'name': 'Tromso', 'country': 'Norway', 'group': 'supplemental_city', 'latitude': 69.6492, 'longitude': 18.9553},  # Arktyczna północ Europy.
    {'name': 'Goteborg', 'country': 'Sweden', 'group': 'supplemental_city', 'latitude': 57.7089, 'longitude': 11.9746},  # Zachodnie wybrzeże Skandynawii.
    {'name': 'Rovaniemi', 'country': 'Finland', 'group': 'supplemental_city', 'latitude': 66.5039, 'longitude': 25.7294},  # Koło podbiegunowe.
    {'name': 'Athens', 'country': 'Greece', 'group': 'supplemental_city', 'latitude': 37.9838, 'longitude': 23.7275},  # Wschodnie Morze Śródziemne.
    {'name': 'Thessaloniki', 'country': 'Greece', 'group': 'supplemental_city', 'latitude': 40.6401, 'longitude': 22.9444},  # Północna Grecja.
    {'name': 'Dubrovnik', 'country': 'Croatia', 'group': 'supplemental_city', 'latitude': 42.6507, 'longitude': 18.0944},  # Adriatyk.
    {'name': 'Sarajevo', 'country': 'Bosnia and Herzegovina', 'group': 'supplemental_city', 'latitude': 43.8563, 'longitude': 18.4131},  # Górzyste Bałkany.
    {'name': 'Tbilisi', 'country': 'Georgia', 'group': 'supplemental_city', 'latitude': 41.7151, 'longitude': 44.8271},  # Kaukaz Południowy.
    {'name': 'Marrakesh', 'country': 'Morocco', 'group': 'supplemental_city', 'latitude': 31.6295, 'longitude': -7.9811},  # Wnętrze północno-zachodniej Afryki.
    {'name': 'Casablanca', 'country': 'Morocco', 'group': 'supplemental_city', 'latitude': 33.5731, 'longitude': -7.5898},  # Atlantyckie wybrzeże Afryki.
    {'name': 'Alexandria', 'country': 'Egypt', 'group': 'supplemental_city', 'latitude': 31.2001, 'longitude': 29.9187},  # Wybrzeże Egiptu.
    {'name': 'Lagos', 'country': 'Nigeria', 'group': 'supplemental_city', 'latitude': 6.5244, 'longitude': 3.3792},  # Zatoka Gwinejska.
    {'name': 'Kano', 'country': 'Nigeria', 'group': 'supplemental_city', 'latitude': 12.0022, 'longitude': 8.5920},  # Sahel.
    {'name': 'Mombasa', 'country': 'Kenya', 'group': 'supplemental_city', 'latitude': -4.0435, 'longitude': 39.6682},  # Równikowe wybrzeże Oceanu Indyjskiego.
    {'name': 'Addis Ababa', 'country': 'Ethiopia', 'group': 'supplemental_city', 'latitude': 8.9806, 'longitude': 38.7578},  # Wyżyna Abisyńska.
    {'name': 'Dar es Salaam', 'country': 'Tanzania', 'group': 'supplemental_city', 'latitude': -6.7924, 'longitude': 39.2083},  # Wschodnia Afryka.
    {'name': 'Luanda', 'country': 'Angola', 'group': 'supplemental_city', 'latitude': -8.8390, 'longitude': 13.2894},  # Zachodnie wybrzeże Afryki.
    {'name': 'Antananarivo', 'country': 'Madagascar', 'group': 'supplemental_city', 'latitude': -18.8792, 'longitude': 47.5079},  # Wyżynne wnętrze Madagaskaru.
    {'name': 'Dubai', 'country': 'United Arab Emirates', 'group': 'supplemental_city', 'latitude': 25.2048, 'longitude': 55.2708},  # Pustynne wybrzeże Zatoki Perskiej.
    {'name': 'Muscat', 'country': 'Oman', 'group': 'supplemental_city', 'latitude': 23.5880, 'longitude': 58.3829},  # Półwysep Arabski nad Oceanem Indyjskim.
    {'name': 'Karachi', 'country': 'Pakistan', 'group': 'supplemental_city', 'latitude': 24.8607, 'longitude': 67.0011},  # Wybrzeże Morza Arabskiego.
    {'name': 'Lahore', 'country': 'Pakistan', 'group': 'supplemental_city', 'latitude': 31.5204, 'longitude': 74.3587},  # Kontynentalna północ Pakistanu.
    {'name': 'Kathmandu', 'country': 'Nepal', 'group': 'supplemental_city', 'latitude': 27.7172, 'longitude': 85.3240},  # Himalaje.
    {'name': 'Dhaka', 'country': 'Bangladesh', 'group': 'supplemental_city', 'latitude': 23.8103, 'longitude': 90.4125},  # Wilgotna delta Gangesu.
    {'name': 'Colombo', 'country': 'Sri Lanka', 'group': 'supplemental_city', 'latitude': 6.9271, 'longitude': 79.8612},  # Tropikalna wyspa Oceanu Indyjskiego.
    {'name': 'Bangkok', 'country': 'Thailand', 'group': 'supplemental_city', 'latitude': 13.7563, 'longitude': 100.5018},  # Tropikalna Azja Południowo-Wschodnia.
    {'name': 'Hanoi', 'country': 'Vietnam', 'group': 'supplemental_city', 'latitude': 21.0278, 'longitude': 105.8342},  # Północny Wietnam.
    {'name': 'Ho Chi Minh City', 'country': 'Vietnam', 'group': 'supplemental_city', 'latitude': 10.8231, 'longitude': 106.6297},  # Południowy Wietnam.
    {'name': 'Manila', 'country': 'Philippines', 'group': 'supplemental_city', 'latitude': 14.5995, 'longitude': 120.9842},  # Zachodni Pacyfik.
    {'name': 'Cebu', 'country': 'Philippines', 'group': 'supplemental_city', 'latitude': 10.3157, 'longitude': 123.8854},  # Środkowe Filipiny.
    {'name': 'Taipei', 'country': 'Taiwan', 'group': 'supplemental_city', 'latitude': 25.0330, 'longitude': 121.5654},  # Subtropikalna wyspa zachodniego Pacyfiku.
    {'name': 'Auckland', 'country': 'New Zealand', 'group': 'supplemental_city', 'latitude': -36.8509, 'longitude': 174.7645},  # Północna Nowa Zelandia.
    {'name': 'Wellington', 'country': 'New Zealand', 'group': 'supplemental_city', 'latitude': -41.2866, 'longitude': 174.7756},  # Wietrzna południowa część Wyspy Północnej.
    {'name': 'Honolulu', 'country': 'United States - Hawaii', 'group': 'supplemental_city', 'latitude': 21.3099, 'longitude': -157.8581},  # Środkowy Pacyfik.
    {'name': 'Anchorage', 'country': 'United States - Alaska', 'group': 'supplemental_city', 'latitude': 61.2181, 'longitude': -149.9003},  # Subarktyczna Alaska.
    {'name': 'Havana', 'country': 'Cuba', 'group': 'supplemental_city', 'latitude': 23.1136, 'longitude': -82.3666},  # Karaiby.
    {'name': 'Panama City', 'country': 'Panama', 'group': 'supplemental_city', 'latitude': 8.9824, 'longitude': -79.5199},  # Przesmyk Ameryki Środkowej.
    {'name': 'Quito', 'country': 'Ecuador', 'group': 'supplemental_city', 'latitude': -0.1807, 'longitude': -78.4678},  # Równikowe Andy.
    {'name': 'Lima', 'country': 'Peru', 'group': 'supplemental_city', 'latitude': -12.0464, 'longitude': -77.0428},  # Suche wybrzeże Pacyfiku.
    {'name': 'La Paz', 'country': 'Bolivia', 'group': 'supplemental_city', 'latitude': -16.4897, 'longitude': -68.1193},  # Wysokie Andy.
    {'name': 'Santiago', 'country': 'Chile', 'group': 'supplemental_city', 'latitude': -33.4489, 'longitude': -70.6693},  # Środkowe Chile.
    {'name': 'Punta Arenas', 'country': 'Chile', 'group': 'supplemental_city', 'latitude': -53.1638, 'longitude': -70.9171},  # Subpolarny kraniec Ameryki Południowej.
    {'name': 'Bogota', 'country': 'Colombia', 'group': 'supplemental_city', 'latitude': 4.7110, 'longitude': -74.0721},  # Wyżynne tropiki.
    {'name': 'Caracas', 'country': 'Venezuela', 'group': 'supplemental_city', 'latitude': 10.4806, 'longitude': -66.9036},  # Północ Ameryki Południowej.
]


def _fetch_json(url):
    """Pobiera JSON z zewnętrznego API i zwraca go jako słownik Pythona."""
    request = Request(url, headers={'User-Agent': 'NieZmoknij/0.1'})  # User-Agent pomaga API rozpoznać klienta.
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # Otwieramy połączenie z limitem czasu.
        payload = response.read().decode('utf-8')  # Odczytujemy odpowiedź bajtową jako tekst UTF-8.
    return json.loads(payload)  # Parsujemy tekst JSON do słownika lub listy.


def _point_key(point):
    """Buduje klucz pozwalający usunąć duplikaty punktów pogodowych."""
    return (  # Klucz zawiera nazwę, kraj i zaokrąglone współrzędne.
        point['name'].lower(),  # Nazwa miasta/stolicy bez rozróżniania wielkości liter.
        point.get('country', '').lower(),  # Kraj pomaga odróżnić miasta o tej samej nazwie.
        round(float(point['latitude']), 3),  # Zaokrąglenie usuwa minimalne różnice źródeł.
        round(float(point['longitude']), 3),  # Zaokrąglenie jest spójne z latitude.
    )


def _valid_capital_points(value):
    """Sprawdza, czy cache zawiera listę poprawnych punktów stolic."""
    if not isinstance(value, list) or not value:  # Słownik błędu ani pusta lista nie mogą udawać poprawnych punktów.
        return False  # Niepoprawny typ wymusza ponowne pobranie danych.
    return all(  # Każdy element musi zawierać komplet pól wymaganych przez mapę i Open-Meteo.
        isinstance(point, dict)  # Punkt powinien być słownikiem.
        and point.get('name')  # Nazwa stolicy nie może być pusta.
        and point.get('country')  # Nazwa kraju nie może być pusta.
        and point.get('latitude') is not None  # Szerokość geograficzna jest obowiązkowa.
        and point.get('longitude') is not None  # Długość geograficzna jest obowiązkowa.
        for point in value  # Walidujemy wszystkie zapisane punkty.
    )


def _capital_points_from_world_bank():
    """Pobiera listę stolic świata z oficjalnego API Banku Światowego."""
    cached = cache.get(CAPITAL_POINTS_CACHE_KEY)  # Stolice zmieniają się rzadko, więc świeżą listę trzymamy w cache.
    if _valid_capital_points(cached):  # Tylko poprawna lista może zostać użyta przez dalszą część algorytmu.
        return cached  # Zwracamy zweryfikowane punkty bez kolejnego requestu.
    if cached is not None:  # Stary albo uszkodzony wpis nie powinien pozostawać w Redisie.
        cache.delete(CAPITAL_POINTS_CACHE_KEY)  # Usuwamy wartość o niewłaściwym kształcie.

    try:
        api_data = _fetch_json(WORLD_BANK_COUNTRIES_URL)  # Pobieramy metadane oraz listę krajów i gospodarek.
        if not isinstance(api_data, list) or len(api_data) < 2 or not isinstance(api_data[1], list):
            raise ValueError('API Banku Swiatowego zwrocilo niepoprawny format listy krajow.')
        countries = api_data[1]  # Drugi element odpowiedzi zawiera właściwe rekordy krajów.
        points = []  # Tu zbieramy rekordy posiadające stolicę i współrzędne.
        for country in countries:  # Iterujemy po wszystkich rekordach zwróconych przez API.
            if not isinstance(country, dict):  # Wadliwy pojedynczy rekord pomijamy bez zatrzymywania całej mapy.
                continue  # Przechodzimy do następnej pozycji.
            region_id = (country.get('region') or {}).get('id')  # Agregaty statystyczne mają region oznaczony jako NA.
            country_name = str(country.get('name') or '').strip()  # Nazwę kraju normalizujemy do tekstu bez spacji.
            capital_name = str(country.get('capitalCity') or '').strip()  # Nazwa stolicy pochodzi z pola capitalCity.
            latitude = country.get('latitude')  # Bank Światowy zwraca szerokość jako tekst.
            longitude = country.get('longitude')  # Długość geograficzna również jest tekstem.
            if region_id == 'NA' or not country_name or not capital_name or latitude in (None, '') or longitude in (None, ''):
                continue  # Pomijamy agregaty i rekordy, których nie można poprawnie umieścić na mapie.
            try:
                latitude = float(latitude)  # Zamieniamy szerokość na liczbę akceptowaną przez Open-Meteo.
                longitude = float(longitude)  # Zamieniamy długość na liczbę akceptowaną przez Leaflet.
            except (TypeError, ValueError):
                continue  # Pojedyncze błędne współrzędne nie powinny zatrzymać całej warstwy.
            points.append(  # Dodajemy poprawnie znormalizowaną stolicę.
                {
                    'name': capital_name,  # Nazwa stolicy będzie widoczna w panelu i popupie.
                    'country': country_name,  # Nazwa kraju daje kontekst punktowi.
                    'group': 'world_capital',  # Grupa pozwala policzyć stolice w metadanych odpowiedzi.
                    'latitude': latitude,  # Szerokość geograficzna stolicy.
                    'longitude': longitude,  # Długość geograficzna stolicy.
                }
            )
        if not points:  # Pusta lista zwykle oznacza zmianę formatu źródła, a nie brak stolic na świecie.
            raise ValueError('API Banku Swiatowego nie zwrocilo zadnych poprawnych stolic.')
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError):
        fallback = cache.get(CAPITAL_POINTS_FALLBACK_KEY)  # Przy awarii próbujemy użyć ostatniej poprawnej listy.
        if _valid_capital_points(fallback):  # Fallback także musi przejść pełną walidację.
            return fallback  # Starsza lista jest bezpieczniejsza niż awaria całego endpointu.
        return []  # Bez fallbacku pozostawiamy działające miasta Polski i G20.

    cache.set(CAPITAL_POINTS_CACHE_KEY, points, timeout=24 * 60 * 60)  # Świeżą listę cacheujemy przez dobę.
    cache.set(CAPITAL_POINTS_FALLBACK_KEY, points, timeout=30 * 24 * 60 * 60)  # Ostatnią dobrą kopię zachowujemy przez miesiąc.
    return points  # Zwracamy gotowe punkty stolic.


def _all_weather_points():
    """Łączy stolice świata, miasta G20, Polskę i dodatkową reprezentatywną siatkę."""
    points = []  # Lista wynikowa zachowa kolejność priorytetów.
    seen = set()  # Zbiór kluczy chroni przed duplikatami.
    for point in [  # Kolejność zachowuje priorytet miast Polski i dużych ośrodków przed automatycznymi stolicami.
        *POLISH_WEATHER_POINTS,
        *G20_MAJOR_CITY_POINTS,
        *SUPPLEMENTAL_WEATHER_POINTS,
        *_capital_points_from_world_bank(),
    ]:
        key = _point_key(point)  # Dla każdego punktu liczymy klucz deduplikacji.
        if key in seen:  # Jeśli punkt już istnieje, nie dodajemy go drugi raz.
            continue  # Przechodzimy do kolejnego miasta.
        seen.add(key)  # Zapamiętujemy nowy punkt.
        points.append(point)  # Dodajemy punkt do listy dla Open-Meteo.
    return points  # Zwracamy pełny zestaw lokalizacji pogodowych.


def _weather_url(points):
    """Buduje adres Open-Meteo dla paczki punktów pogodowych."""
    query = urlencode(  # Parametry są kodowane, żeby URL był poprawny i czytelny.
        {
            'latitude': ','.join(str(point['latitude']) for point in points),  # Open-Meteo przyjmuje listę szerokości.
            'longitude': ','.join(str(point['longitude']) for point in points),  # Długości muszą mieć tę samą kolejność.
            'current': 'temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_gusts_10m,precipitation,weather_code,cloud_cover,is_day',
            'timezone': 'auto',  # Open-Meteo dobiera lokalną strefę każdego punktu i wyznacza dzień względem wschodu i zachodu.
        }
    )
    return f'{OPEN_METEO_URL}?{query}'  # Łączymy bazowy adres API z parametrami.


def _storm_weather_url(points):
    """Buduje adres Open-Meteo dla danych potrzebnych do potencjału burzowego."""
    query = urlencode(  # Parametry kodujemy ze słownika, żeby URL był poprawny.
        {
            'latitude': ','.join(str(point['latitude']) for point in points),  # Lista szerokości dla paczki punktów.
            'longitude': ','.join(str(point['longitude']) for point in points),  # Lista długości w tej samej kolejności.
            'current': 'temperature_2m,precipitation,wind_gusts_10m,weather_code,cloud_cover',  # Zmiennie burzowe.
            'timezone': 'Europe/Warsaw',  # Czas wyników ustawiamy spójnie z resztą aplikacji.
        }
    )
    return f'{OPEN_METEO_URL}?{query}'  # Zwracamy pełny adres zapytania.


def _chunked(items, size):
    """Dzieli listę na mniejsze paczki."""
    for index in range(0, len(items), size):  # Przesuwamy indeks co rozmiar paczki.
        yield items[index:index + size]  # Zwracamy fragment listy.


def _normalize_weather(point, api_data):
    """Ujednolica odpowiedź Open-Meteo do formatu wygodnego dla frontendu."""
    current = api_data.get('current', {})  # Open-Meteo zwraca bieżące wartości w polu current.
    return {
        'name': point['name'],  # Nazwa punktu wyświetlana w panelu i popupie mapy.
        'country': point.get('country', ''),  # Kraj pomaga zrozumieć globalną mapę pogodową.
        'group': point.get('group', 'weather_point'),  # Grupa opisuje pochodzenie punktu.
        'latitude': point['latitude'],  # Współrzędna potrzebna Leafletowi.
        'longitude': point['longitude'],  # Współrzędna potrzebna Leafletowi.
        'temperature': current.get('temperature_2m'),  # Temperatura przy gruncie w stopniach Celsjusza.
        'humidity': current.get('relative_humidity_2m'),  # Wilgotność względna w procentach.
        'pressure': current.get('pressure_msl'),  # Ciśnienie na poziomie morza.
        'wind_speed': current.get('wind_speed_10m'),  # Prędkość wiatru na wysokości 10 metrów.
        'wind_gusts': current.get('wind_gusts_10m'),  # Porywy są potrzebne do obliczenia potencjału burzowego.
        'precipitation': current.get('precipitation'),  # Aktualny opad pozwala ocenić intensywność burzy.
        'weather_code': current.get('weather_code'),  # Kod warunków, później można mapować go na opisy.
        'cloud_cover': current.get('cloud_cover'),  # Całkowite zachmurzenie nieba w procentach.
        'is_day': current.get('is_day'),  # Wartość 1 oznacza czas od lokalnego wschodu do zachodu słońca.
        'measured_at': current.get('time'),  # Czas pomiaru zwracany przez API.
        'source': 'Open-Meteo',  # Źródło danych jest jawne dla użytkownika i prezentacji.
    }


def _normalize_weather_batch(points, api_data):
    """Normalizuje odpowiedź Open-Meteo dla paczki punktów."""
    responses = api_data if isinstance(api_data, list) else [api_data]  # Przy wielu lokalizacjach API zwraca listę.
    return [  # Łączymy każdy punkt wejściowy z odpowiadającym mu wynikiem pogodowym.
        _normalize_weather(point, response)  # Normalizacja pojedynczego punktu pozostaje w jednym miejscu.
        for point, response in zip(points, responses)  # Kolejność odpowiedzi odpowiada kolejności współrzędnych.
    ]


def _saved_location_weather_url(location):
    """Buduje adres Open-Meteo dla jednej lokalizacji zapisanej przez użytkownika."""

    # Parametry pochodzą z modelu, więc nie sklejamy ich ręcznie z adresem URL.
    query = urlencode(
        {
            'latitude': location.latitude,  # Decimal zachowuje dokładność współrzędnej zapisanej w bazie.
            'longitude': location.longitude,  # Długość geograficzna wskazuje ten sam punkt co formularz użytkownika.
            'current': (
                'temperature_2m,relative_humidity_2m,pressure_msl,'
                'wind_speed_10m,weather_code,cloud_cover'
            ),  # Pobieramy wszystkie pola wymagane przez snapshot i interfejs.
            'timezone': 'UTC',  # UTC upraszcza jednoznaczne zapisywanie czasu pomiaru w bazie.
        }
    )
    # Zwracamy pełny adres używany przez wspólną funkcję _fetch_json.
    return f'{OPEN_METEO_URL}?{query}'


def _saved_location_cache_key(location):
    """Tworzy stabilny klucz cache zależny od współrzędnych lokalizacji."""

    # Normalizacja do sześciu miejsc jest zgodna z dokładnością pól DecimalField modelu.
    latitude = f'{location.latitude:.6f}'
    # Długość otrzymuje ten sam sposób formatowania, aby identyczne punkty miały identyczny klucz.
    longitude = f'{location.longitude:.6f}'
    # Wersja v2 rozróżnia neutralny pomiar od starszego cache zawierającego id konkretnego snapshotu.
    return f'weather:saved-location:v2:{latitude}:{longitude}'


def _weather_description(weather_code):
    """Zwraca polski opis kodu pogody WMO."""

    # Brak kodu nie powinien tworzyć mylącego opisu warunków.
    if weather_code is None:
        return 'Brak opisu'
    # Nieznany przyszły kod zachowujemy w opisie diagnostycznym zamiast zgadywać warunki.
    return WMO_WEATHER_DESCRIPTIONS.get(int(weather_code), f'Kod pogody WMO: {weather_code}')


def _parse_open_meteo_time(value):
    """Zamienia tekst czasu Open-Meteo na świadomy strefowo datetime UTC."""

    # Jeśli źródło nie poda czasu, używamy momentu pobrania jako bezpiecznego fallbacku.
    if not value:
        return timezone.now()
    # fromisoformat obsługuje format minutowy zwracany przez Open-Meteo.
    parsed_time = datetime.fromisoformat(value.replace('Z', '+00:00'))
    # Przy timezone=UTC API może zwrócić tekst bez sufiksu strefy.
    if parsed_time.tzinfo is None:
        parsed_time = parsed_time.replace(tzinfo=datetime_timezone.utc)
    # Zapisujemy jednolity czas UTC niezależnie od formatu odpowiedzi.
    return parsed_time.astimezone(datetime_timezone.utc)


def _create_weather_snapshot(location, api_data):
    """Waliduje odpowiedź Open-Meteo i zapisuje nowy historyczny pomiar."""

    # Wszystkie bieżące wartości Open-Meteo znajdują się w obiekcie current.
    current = api_data.get('current') or {}
    # Zbieramy nazwy pól, których brak uniemożliwia utworzenie kompletnego snapshotu.
    missing_fields = [
        field_name
        for field_name in LOCATION_WEATHER_CURRENT_FIELDS
        if current.get(field_name) is None
    ]
    # Nie zapisujemy częściowego rekordu, bo model i dashboard oczekują pełnego pomiaru.
    if missing_fields:
        raise ValueError(f'Brak wymaganych pól Open-Meteo: {", ".join(missing_fields)}')

    # Kod pogody może być pusty, dlatego normalizujemy go warunkowo.
    weather_code = current.get('weather_code')
    # Zachmurzenie również pozostaje opcjonalne dla zgodności z ewentualnymi innymi źródłami.
    cloud_cover = current.get('cloud_cover')
    # Tworzenie modelu odbywa się w jednym miejscu, aby endpoint i przyszłe zadanie Celery używały tej samej logiki.
    return WeatherSnapshot.objects.create(
        location=location,  # Relacja wskazuje właściciela historii przez lokalizację.
        temperature=Decimal(str(current['temperature_2m'])),  # Decimal zachowuje wartość temperatury bez błędu float.
        humidity=int(round(float(current['relative_humidity_2m']))),  # Wilgotność zapisujemy jako pełny procent.
        pressure=int(round(float(current['pressure_msl']))),  # Model przechowuje ciśnienie jako dodatnią liczbę całkowitą.
        wind_speed=Decimal(str(current['wind_speed_10m'])),  # Prędkość wiatru zachowuje część dziesiętną.
        cloud_cover=int(round(float(cloud_cover))) if cloud_cover is not None else None,  # Opcjonalny procent chmur.
        weather_code=int(weather_code) if weather_code is not None else None,  # Opcjonalny kod WMO.
        description=_weather_description(weather_code),  # Polski opis ułatwia użycie danych bez tabeli kodów.
        source='Open-Meteo',  # Jawne źródło jest wymagane przez model i dokumentację projektu.
        measured_at=_parse_open_meteo_time(current.get('time')),  # Czas pomiaru pochodzi z odpowiedzi API.
    )


def _weather_cache_payload(snapshot):
    """Buduje neutralny pomiar cache bez identyfikatora rekordu konkretnego użytkownika."""

    # Cache współdzielony po współrzędnych nie może przechowywać id snapshotu należącego do pierwszej lokalizacji.
    return {
        'temperature': str(snapshot.temperature),  # Tekst zachowuje dokładność Decimal w Redisie.
        'humidity': snapshot.humidity,  # Procent wilgotności jest prostą liczbą całkowitą.
        'pressure': snapshot.pressure,  # Ciśnienie pozostaje liczbą całkowitą hPa.
        'wind_speed': str(snapshot.wind_speed),  # Prędkość zachowuje część dziesiętną.
        'cloud_cover': snapshot.cloud_cover,  # Zachmurzenie może pozostać wartością null.
        'weather_code': snapshot.weather_code,  # Kod WMO może pozostać wartością null.
        'description': snapshot.description,  # Polski opis jest wspólny dla tych samych danych źródłowych.
        'source': snapshot.source,  # Źródło pozostaje jawne po odczycie z cache.
        'measured_at': snapshot.measured_at.isoformat(),  # Czas jednoznacznie identyfikuje pomiar w okresie TTL.
    }


def _snapshot_from_cached_measurement(location, cached_measurement):
    """Zwraca własny snapshot lokalizacji dla pomiaru współdzielonego w Redisie."""

    # Czas z cache służy do znalezienia istniejącego rekordu i uniknięcia duplikatu po kolejnym kliknięciu.
    measured_at = _parse_open_meteo_time(cached_measurement.get('measured_at'))
    # Najpierw szukamy pomiaru tej konkretnej lokalizacji z tym samym czasem źródłowym.
    existing_snapshot = location.weather_snapshots.filter(measured_at=measured_at).first()
    # Istniejący rekord oznacza, że użytkownik już otrzymał ten pomiar w bieżącym okresie cache.
    if existing_snapshot is not None:
        return existing_snapshot
    # Drugi użytkownik lub druga lokalizacja tych samych współrzędnych otrzymuje własny rekord historii.
    return WeatherSnapshot.objects.create(
        location=location,  # Relacja zachowuje izolację historii między użytkownikami.
        temperature=Decimal(str(cached_measurement['temperature'])),  # Wartość pochodzi z neutralnego payloadu cache.
        humidity=int(cached_measurement['humidity']),  # Wilgotność zachowuje walidowany zakres.
        pressure=int(cached_measurement['pressure']),  # Ciśnienie jest zgodne z typem modelu.
        wind_speed=Decimal(str(cached_measurement['wind_speed'])),  # Prędkość zachowuje dokładność dziesiętną.
        cloud_cover=cached_measurement.get('cloud_cover'),  # Opcjonalne zachmurzenie może być puste.
        weather_code=cached_measurement.get('weather_code'),  # Opcjonalny kod WMO może być pusty.
        description=cached_measurement.get('description', ''),  # Opis jest już znormalizowany podczas pobrania.
        source=cached_measurement.get('source', 'Open-Meteo'),  # Fallback zachowuje jawne źródło.
        measured_at=measured_at,  # Wszystkie lokalizacje korzystają z tego samego czasu danych źródłowych.
    )


def _user_location_or_404(user, location_id):
    """Pobiera lokalizację właściciela albo zwraca neutralne 404."""

    # Filtrowanie po użytkowniku zapobiega odczytaniu cudzego punktu przez zmianę identyfikatora w URL.
    return get_object_or_404(SavedLocation, pk=location_id, user=user)


class SavedLocationListCreateView(ListCreateAPIView):
    """Udostępnia listę własnych lokalizacji oraz formularz dodawania punktu."""

    serializer_class = SavedLocationSerializer  # Jeden serializer obsługuje walidację wejścia i odpowiedź.
    permission_classes = (IsAuthenticated,)  # Niezalogowany użytkownik otrzyma odpowiedź 401.

    def get_queryset(self):
        # Queryset zawsze zależy od request.user i pobiera ostatnią pogodę bez zapytań N+1.
        return saved_locations_queryset(self.request.user)

    def perform_create(self, serializer):
        # Użytkownik nie może przesłać user_id; właściciel jest brany wyłącznie z poprawnego JWT.
        serializer.save(user=self.request.user)
        # Nowa lokalizacja zmienia licznik i listę prywatnego Dashboardu.
        invalidate_user_dashboard_cache(self.request.user.pk)


class SavedLocationDestroyView(DestroyAPIView):
    """Usuwa pojedynczą lokalizację należącą do zalogowanego użytkownika."""

    serializer_class = SavedLocationSerializer  # Serializer dokumentuje typ usuwanego zasobu.
    permission_classes = (IsAuthenticated,)  # Usuwanie jest operacją chronioną JWT.

    def get_queryset(self):
        # Ograniczony queryset sprawia, że cudza lokalizacja wygląda jak nieistniejąca.
        return SavedLocation.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Zapamiętujemy właściciela przed kaskadowym usunięciem lokalizacji i historii.
        user_id = instance.user_id
        # Standardowa operacja usuwa rekord oraz powiązane snapshoty.
        instance.delete()
        # Lista i licznik Dashboardu muszą zostać policzone ponownie.
        invalidate_user_dashboard_cache(user_id)


class SavedLocationWeatherView(APIView):
    """Pobiera lub odczytuje z cache aktualną pogodę i zapisuje snapshot."""

    permission_classes = (IsAuthenticated,)  # Pogoda dotyczy prywatnej listy lokalizacji użytkownika.

    @extend_schema(
        responses={200: LocationWeatherResponseSerializer},  # Swagger pokazuje lokalizację, pomiar i informacje cache.
        summary='Aktualna pogoda zapisanej lokalizacji',  # Krótka nazwa pojawia się w dokumentacji API.
    )
    def get(self, request, location_id):
        # Lokalizacja jest wyszukiwana wyłącznie wśród zasobów bieżącego użytkownika.
        location = _user_location_or_404(request.user, location_id)
        # Klucz zależy od współrzędnych, więc zmiana nazwy nie wymusza nowego requestu pogodowego.
        cache_key = _saved_location_cache_key(location)
        # Redis może zawierać już zserializowany snapshot utworzony przez wcześniejszy request.
        cached_measurement = cache.get(cache_key)

        # Trafienie cache omija Open-Meteo i nie tworzy duplikatu w historii.
        if cached_measurement is not None:
            # Każda lokalizacja otrzymuje własny snapshot, nawet jeśli pomiar pobrał wcześniej inny użytkownik.
            snapshot = _snapshot_from_cached_measurement(location, cached_measurement)
            # Nowy własny snapshot zmienia ostatnią pogodę widoczną na Dashboardzie.
            invalidate_user_dashboard_cache(request.user.pk)
            return Response(
                {
                    'location': SavedLocationSerializer(location).data,  # Zwracamy aktualne dane opisowe punktu.
                    'weather': WeatherSnapshotSerializer(snapshot).data,  # Odpowiedź zawiera własny rekord historii.
                    'cached': True,  # Flaga pozwala pokazać działanie Redisa podczas prezentacji.
                    'cache_ttl_seconds': settings.LOCATION_WEATHER_CACHE_TTL,  # Odpowiedź ujawnia przyjętą strategię TTL.
                }
            )

        try:
            # Przy braku cache wykonujemy pojedynczy request do Open-Meteo.
            api_data = _fetch_json(_saved_location_weather_url(location))
            # Poprawna odpowiedź zostaje zapisana jako nowy historyczny rekord.
            snapshot = _create_weather_snapshot(location, api_data)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
            # Problem z zależnością zewnętrzną zwracamy jako 502 bez tworzenia częściowego rekordu.
            return Response(
                {
                    'detail': 'Nie udało się pobrać pogody dla zapisanej lokalizacji.',
                    'error': str(error),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Serializujemy snapshot do odpowiedzi zawierającej lokalny identyfikator rekordu.
        weather_data = WeatherSnapshotSerializer(snapshot).data
        # Redis otrzymuje neutralny pomiar bez id należącego do konkretnego użytkownika.
        cache.set(
            cache_key,
            _weather_cache_payload(snapshot),
            timeout=settings.LOCATION_WEATHER_CACHE_TTL,
        )
        # Świeży pomiar powinien być widoczny przy następnym wejściu na Dashboard.
        invalidate_user_dashboard_cache(request.user.pk)
        # Pierwsza odpowiedź informuje frontend, że dane zostały pobrane z API zewnętrznego.
        return Response(
            {
                'location': SavedLocationSerializer(location).data,  # Dane lokalizacji ułatwiają powiązanie odpowiedzi.
                'weather': weather_data,  # Świeżo utworzony snapshot trafia do interfejsu.
                'cached': False,  # False oznacza rzeczywisty request do Open-Meteo.
                'cache_ttl_seconds': settings.LOCATION_WEATHER_CACHE_TTL,  # Informacja jest przydatna diagnostycznie.
            }
        )


class DashboardSummaryView(APIView):
    """Zwraca publiczne agregacje i opcjonalne dane prywatne użytkownika."""

    permission_classes = (AllowAny,)  # Podstawowy Dashboard jest dostępny również bez logowania.

    @extend_schema(
        responses={200: DashboardSummarySerializer},  # Swagger pokazuje statystyki, wykres i status synchronizacji.
        summary='Podsumowanie Dashboardu',  # Nazwa odpowiada trasie opisanej w specyfikacji.
    )
    def get(self, request):
        # Użytkownik zalogowany otrzymuje zakres zapisany w relacyjnych preferencjach.
        if request.user.is_authenticated:
            preferences = getattr(request.user, 'preferences', None)
            range_hours = preferences.dashboard_range_hours if preferences else 24
        else:
            # Publiczny klient może jawnie wybrać jeden z trzech bezpiecznych zakresów.
            try:
                range_hours = int(request.query_params.get('hours', 24))
            except ValueError:
                range_hours = 24  # Niepoprawny tekst nie powinien wywracać publicznego Dashboardu.
        # Wartość spoza specyfikacji wraca do domyślnego zakresu jednej doby.
        range_hours = range_hours if range_hours in DASHBOARD_ALLOWED_RANGES else 24
        # Część globalna może zostać współdzielona przez wszystkich odwiedzających.
        global_payload, global_cached = build_global_dashboard(range_hours)
        # Część prywatna zależy od request.user odtworzonego opcjonalnie z JWT.
        user_payload, user_cached = build_user_dashboard(request.user)
        # Łączymy dwa niezależne fragmenty bez zapisywania prywatnych danych w globalnym kluczu.
        return Response(
            {
                **global_payload,
                **user_payload,
                'cache': {
                    'global_data': global_cached,
                    'user_data': user_cached,
                    'ttl_seconds': DASHBOARD_CACHE_TTL,
                },
            }
        )


class SavedLocationWeatherHistoryView(APIView):
    """Zwraca historyczne snapshoty jednej lokalizacji użytkownika."""

    permission_classes = (IsAuthenticated,)  # Historia pomiarów jest częścią prywatnego dashboardu.

    @extend_schema(
        responses={200: WeatherHistoryResponseSerializer},  # Dokumentujemy listę pomiarów i jej licznik.
        summary='Historia pogody zapisanej lokalizacji',  # Nazwa opisuje relację lokalizacja-snapshoty.
    )
    def get(self, request, location_id):
        # Użycie wspólnego helpera gwarantuje identyczną ochronę jak endpoint aktualnej pogody.
        location = _user_location_or_404(request.user, location_id)
        # Ograniczamy odpowiedź do 100 najnowszych rekordów, aby historia nie rosła bez kontroli w jednym requeście.
        snapshots = location.weather_snapshots.order_by('-measured_at')[:100]
        # Serializujemy queryset dopiero po zastosowaniu sortowania i limitu.
        history_data = WeatherSnapshotSerializer(snapshots, many=True).data
        # Odpowiedź ma jawny licznik i metadane lokalizacji.
        return Response(
            {
                'location': SavedLocationSerializer(location).data,  # Punkt geograficzny opisuje kontekst historii.
                'results': history_data,  # Lista zawiera maksymalnie 100 najnowszych pomiarów.
                'count': len(history_data),  # Licznik dotyczy rekordów zwróconych w tej odpowiedzi.
            }
        )


def _storm_score(current):
    """Liczy prosty wynik potencjału burzowego z danych Open-Meteo."""
    wind_gust = float(current.get('wind_gusts_10m') or 0)  # Porywy wiatru są ważnym objawem groźnej burzy.
    precipitation = float(current.get('precipitation') or 0)  # Opad pomaga odróżnić aktywną konwekcję od samego wiatru.
    weather_code = int(current.get('weather_code') or 0)  # Kod pogody pozwala wykryć burzę według WMO.
    cloud_cover = float(current.get('cloud_cover') or 0)  # Zachmurzenie pomaga odsiać suche, bezchmurne porywy.
    code_bonus = 45 if weather_code in STORM_WEATHER_CODES else 0  # Burzowy kod WMO mocno podnosi wynik.
    cloud_bonus = 10 if cloud_cover >= 70 else 0  # Duże zachmurzenie wzmacnia podejrzenie burzy.
    return round((wind_gust * 1.2) + (precipitation * 18) + code_bonus + cloud_bonus, 1)  # Wynik porządkuje markery.


def _normalize_storm_point(point, api_data):
    """Zamienia pogodę punktową na kandydat burzowy dla frontendu."""
    current = api_data.get('current', {})  # Dane bieżące z Open-Meteo są w polu current.
    return {
        'external_id': (
            f"storm-{point['name']}-{point.get('country', '')}-"
            f"{float(point['latitude']):.4f}-{float(point['longitude']):.4f}"
        ),  # Współrzędne zapobiegają kolizji miasta obecnego w dwóch grupach źródłowych.
        'name': point['name'],  # Nazwa miasta lub stolicy.
        'country': point.get('country', ''),  # Kraj pomaga opisać marker.
        'latitude': point['latitude'],  # Szerokość geograficzna markera.
        'longitude': point['longitude'],  # Długość geograficzna markera.
        'temperature': current.get('temperature_2m'),  # Temperatura jest informacją pomocniczą.
        'precipitation': current.get('precipitation'),  # Aktualny opad.
        'wind_gusts': current.get('wind_gusts_10m'),  # Porywy wiatru.
        'weather_code': current.get('weather_code'),  # Kod WMO aktualnej pogody.
        'cloud_cover': current.get('cloud_cover'),  # Zachmurzenie w procentach.
        'storm_score': _storm_score(current),  # Nasza prosta miara potencjału burzowego.
        'source': 'Open-Meteo',  # Źródło danych punktowych.
        'kind': 'storm',  # Typ pozwala frontendowi dobrać ikonę.
    }


def _normalize_storm_batch(points, api_data):
    """Normalizuje paczkę punktów potencjału burzowego."""
    responses = api_data if isinstance(api_data, list) else [api_data]  # Open-Meteo zwraca listę przy wielu punktach.
    return [  # Łączymy punkty wejściowe z odpowiadającymi im danymi.
        _normalize_storm_point(point, response)  # Normalizujemy pojedynczy punkt.
        for point, response in zip(points, responses)  # Kolejność odpowiedzi odpowiada kolejności query.
    ]


def _storm_candidates_from_weather_cache(weather_payload):
    """Buduje kandydatów burzowych z pomiarów pobranych już dla mapy pogody."""
    if not isinstance(weather_payload, dict):  # Cache musi zawierać pełny obiekt odpowiedzi pogodowej.
        return []  # Brak poprawnego obiektu oznacza konieczność użycia osobnego requestu.
    weather_results = weather_payload.get('results')  # Lista wyników zawiera wszystkie potrzebne współrzędne.
    if not isinstance(weather_results, list) or not weather_results:  # Pusta lub błędna lista nie nadaje się do ponownego użycia.
        return []  # Warstwa burzowa pobierze wtedy własne dane.
    return [  # Każdy punkt pogodowy zamieniamy na standardowy obiekt kandydata burzowego.
        _normalize_storm_point(
            point,  # Znormalizowany punkt posiada nazwę, kraj i współrzędne.
            {
                'current': {
                    'temperature_2m': point.get('temperature'),  # Przywracamy nazwę pola używaną przez normalizator burz.
                    'precipitation': point.get('precipitation'),  # Opad pochodzi z tego samego pomiaru Open-Meteo.
                    'wind_gusts_10m': point.get('wind_gusts'),  # Porywy wiatru nie wymagają kolejnego requestu.
                    'weather_code': point.get('weather_code'),  # Kod WMO zachowujemy bez zmian.
                    'cloud_cover': point.get('cloud_cover'),  # Zachmurzenie uzupełnia opis punktu.
                }
            },
        )
        for point in weather_results  # Przetwarzamy kompletną globalną warstwę pogodową.
    ]


def _eonet_cyclone_url():
    """Buduje adres EONET dla aktywnych severe storms."""
    query = urlencode(  # Parametry EONET ograniczają wynik do aktywnych zdarzeń.
        {
            'status': 'open',  # Interesują nas tylko trwające zdarzenia.
            'category': CYCLONE_CATEGORY_ID,  # Severe storms obejmuje cyklony tropikalne.
            'days': 30,  # Ostatnie 30 dni wystarcza dla aktywnych systemów.
            'limit': 50,  # Limit chroni dashboard przed zbyt dużą odpowiedzią.
        }
    )
    return f'{EONET_EVENTS_URL}?{query}'  # Zwracamy pełny URL EONET.


def _normalize_cyclone_event(event):
    """Zamienia zdarzenie EONET na marker cyklonu."""
    geometry = (event.get('geometry') or [])[-1] if event.get('geometry') else {}  # Bierzemy najnowszą geometrię zdarzenia.
    coordinates = geometry.get('coordinates') or [None, None]  # EONET trzyma współrzędne jako [lon, lat].
    return {
        'external_id': event.get('id'),  # Id zdarzenia z EONET.
        'name': event.get('title') or 'Aktywny cyklon',  # Tytuł zdarzenia jest nazwą systemu.
        'latitude': coordinates[1],  # Drugi element to szerokość geograficzna.
        'longitude': coordinates[0],  # Pierwszy element to długość geograficzna.
        'event_time': geometry.get('date'),  # Data najnowszej geometrii.
        'source': 'NASA EONET',  # Źródło danych cyklonów.
        'kind': 'cyclone',  # Typ pozwala frontendowi dobrać ikonę cyclone.
    }


def _valid_cyclones(value):
    """Sprawdza, czy wartość zawiera użyteczne markery cyklonów."""
    if not isinstance(value, list) or not value:  # Brak listy albo pusta lista nie zapewniają danych awaryjnych.
        return False  # W takim przypadku próbujemy kolejnego źródła fallbacku.
    return all(  # Każdy marker musi mieć nazwę i obie współrzędne.
        isinstance(cyclone, dict)  # Pojedynczy cyklon jest słownikiem.
        and cyclone.get('name')  # Nazwa systemu jest wymagana w panelu.
        and cyclone.get('latitude') is not None  # Szerokość jest wymagana przez Leaflet.
        and cyclone.get('longitude') is not None  # Długość jest wymagana przez Leaflet.
        for cyclone in value  # Walidujemy kompletną zapisaną listę.
    )


def _cached_cyclone_fallback():
    """Zwraca ostatnią dobrą listę cyklonów, również ze starszej wersji cache."""
    cached_cyclones = cache.get(CYCLONE_FALLBACK_KEY)  # Najpierw używamy nowego, niezależnego klucza EONET.
    if _valid_cyclones(cached_cyclones):  # Poprawna lista może od razu wrócić do endpointu.
        return cached_cyclones  # Zwracamy sprawdzony fallback.
    legacy_payload = cache.get(LEGACY_STORM_FALLBACK_KEY)  # Przy pierwszym wdrożeniu sprawdzamy wcześniejszą pełną odpowiedź.
    legacy_cyclones = legacy_payload.get('cyclones') if isinstance(legacy_payload, dict) else None  # Bezpiecznie wyciągamy listę.
    if _valid_cyclones(legacy_cyclones):  # Stare dane także muszą mieć kompletny format.
        cache.set(CYCLONE_FALLBACK_KEY, legacy_cyclones, timeout=7 * 24 * 60 * 60)  # Migrujemy je do nowego klucza na tydzień.
        return legacy_cyclones  # Zwracamy ostatni poprawny zestaw.
    return []  # Bez poprawnej kopii warstwa cyklonów pozostaje pusta, ale endpoint nadal działa.


@extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Aktualna pogoda punktów globalnych')
@api_view(['GET'])
@permission_classes([AllowAny])
def current_weather(request):
    """Zwraca pogodę dla stolic, miast G20, Polski i dodatkowej siatki świata."""
    cache_key = GLOBAL_WEATHER_CACHE_KEY  # Jeden współdzielony klucz opisuje pełną globalną warstwę pogody.
    fallback_key = GLOBAL_WEATHER_FALLBACK_KEY  # Ostatnia dobra pogoda ratuje UI przy 429.
    cached = cache.get(cache_key)  # Najpierw próbujemy oddać gotową odpowiedź z cache.
    if cached is not None:  # Jeśli dane są świeże, nie wykonujemy requestów do Open-Meteo.
        return Response(cached)  # Zwracamy pełną zapamiętaną odpowiedź.

    try:
        points = _all_weather_points()  # Budujemy zestaw lokalizacji ze wszystkich czterech grup.
        results = []  # Tu zbierzemy pogodę z kolejnych paczek Open-Meteo.
        for chunk in _chunked(points, OPEN_METEO_BATCH_SIZE):  # Pytamy Open-Meteo paczkami po kilkadziesiąt punktów.
            results.extend(_normalize_weather_batch(chunk, _fetch_json(_weather_url(chunk))))  # Pobieramy i dokładamy wyniki.
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError) as error:  # Obsługujemy błędy sieci i formatu.
        fallback = cache.get(fallback_key)  # Szukamy ostatniej dobrej odpowiedzi pogodowej.
        if fallback is not None:  # Jeśli ją mamy, lepiej pokazać starsze dane niż pustą mapę.
            stale_payload = {**fallback, 'stale': True, 'source_errors': [str(error)]}  # Nie zmieniamy obiektu zapisanego w cache.
            return Response(stale_payload)  # Odpowiadamy 200, bo aplikacja ma użyteczny zestaw danych.
        return Response(  # Zwracamy czytelny błąd zamiast niekontrolowanego wyjątku.
            {'detail': 'Nie udalo sie pobrac globalnych danych pogodowych.', 'error': str(error)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    payload = {  # Odpowiedź zawiera dane i metadane przydatne w UI.
        'results': results,  # Lista punktów pogodowych dla mapy Leaflet.
        'source': 'Open-Meteo + World Bank',  # Jawnie opisujemy aktualne źródła warstwy.
        'stale': False,  # Świeże dane nie są fallbackiem.
        'source_errors': [],  # Brak błędów źródeł przy normalnej odpowiedzi.
        'cache_ttl_seconds': 1800,  # Globalną pogodę cacheujemy przez 30 minut.
        'counts': {  # Liczniki pomagają sprawdzić, czy zakres danych jest zgodny z wymaganiem.
            'all_points': len(results),  # Łączna liczba punktów na mapie.
            'poland_top_20': sum(1 for point in results if point.get('group') == 'poland_top_20'),  # Punkty Polski.
            'g20_major_cities': sum(1 for point in results if point.get('group') == 'g20_major_city'),  # Miasta G20.
            'supplemental_cities': sum(1 for point in results if point.get('group') == 'supplemental_city'),  # Dodatkowa siatka świata.
            'world_capitals': sum(1 for point in results if point.get('group') == 'world_capital'),  # Stolice świata.
        },
    }
    cache.set(cache_key, payload, timeout=30 * 60)  # Cache ogranicza koszt pobierania setek lokalizacji.
    cache.set(fallback_key, payload, timeout=6 * 60 * 60)  # Ostatnią dobrą pogodę trzymamy dłużej.
    return Response(payload)  # Oddajemy globalną warstwę pogody frontendowi.


def _earthquake_url(hours, min_magnitude):
    """Buduje adres USGS GeoJSON dla zakresu czasu i minimalnej magnitudy."""
    start_time = timezone.now() - timedelta(hours=hours)  # Zakres zaczyna się np. 24 godziny temu.
    query = urlencode(  # Query string tworzymy ze słownika, żeby uniknąć ręcznego sklejania URL.
        {
            'format': 'geojson',  # GeoJSON jest wygodny dla map i danych punktowych.
            'starttime': start_time.isoformat(),  # USGS przyjmuje czas ISO.
            'minmagnitude': min_magnitude,  # Minimalna magnituda jest filtrem z UI/API.
            'orderby': 'time',  # Najnowsze zdarzenia mają być pierwsze.
            'limit': 80,  # Limit chroni frontend przed zbyt dużą liczbą markerów na starcie.
        }
    )
    return f'{USGS_EARTHQUAKE_URL}?{query}'  # Łączymy adres bazowy USGS z parametrami.


def _normalize_earthquake(feature):
    """Ujednolica pojedynczy obiekt GeoJSON USGS do formatu aplikacji."""
    properties = feature.get('properties', {})  # Dane opisowe USGS są w properties.
    coordinates = feature.get('geometry', {}).get('coordinates', [None, None, None])  # GeoJSON trzyma lon/lat/depth.
    event_time = properties.get('time')  # USGS podaje czas jako timestamp w milisekundach.
    return {
        'external_id': feature.get('id'),  # Identyfikator zdarzenia z USGS.
        'place': properties.get('place') or 'Nieznana lokalizacja',  # Tekstowe miejsce zdarzenia.
        'title': properties.get('title') or properties.get('place') or 'Trzesienie ziemi',  # Tytuł do panelu.
        'magnitude': properties.get('mag'),  # Magnituda steruje kolorem i rozmiarem markera.
        'longitude': coordinates[0],  # Pierwszy element GeoJSON to długość geograficzna.
        'latitude': coordinates[1],  # Drugi element GeoJSON to szerokość geograficzna.
        'depth_km': coordinates[2],  # Trzeci element GeoJSON to głębokość w kilometrach.
        'event_time': datetime.fromtimestamp(event_time / 1000, tz=datetime_timezone.utc).isoformat() if event_time else None,
        'source': 'USGS',  # Źródło danych jest pokazywane w UI.
        'detail_url': properties.get('url'),  # Link do szczegółów zostawiamy pod przyszły widok.
    }


@extend_schema(
    responses={200: EnvironmentalListResponseSerializer},  # Swagger pokazuje obudowę listy odczytywanej z bazy.
    summary='Zdarzenia sejsmiczne zapisane w bazie',  # Tytuł podkreśla warstwę persystencji.
    operation_id='earthquake_event_list',  # Jawna nazwa nie koliduje z endpointem szczegółów.
)
@api_view(['GET'])
@permission_classes([AllowAny])
def earthquake_events(request):
    """Zwraca najnowsze trzęsienia ziemi zapisane podczas synchronizacji USGS."""
    try:
        hours = int(request.query_params.get('hours', 24))  # Domyślnie pokazujemy ostatnie 24 godziny.
        min_magnitude = float(request.query_params.get('min_magnitude', 2.5))  # Domyślnie ukrywamy bardzo małe zdarzenia.
        max_depth = float(request.query_params.get('max_depth', 1000))  # Opcjonalny filtr pozwala pokazać płytkie zdarzenia.
    except ValueError:
        return Response(  # Niepoprawne filtry są błędem użytkownika, więc zwracamy 400.
            {'detail': 'Parametry hours, min_magnitude i max_depth muszą być liczbami.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    hours = max(1, min(hours, 720))  # Ograniczamy zakres od 1 godziny do 30 dni.
    min_magnitude = max(0, min(min_magnitude, 10))  # Magnituda powinna zostać w realistycznym zakresie.
    max_depth = max(0, min(max_depth, 1000))  # Głębokość ograniczamy do zakresu użytecznego dla UI.
    region = str(request.query_params.get('region') or '').strip()  # Region jest opcjonalnym fragmentem nazwy miejsca.
    start_time = timezone.now() - timedelta(hours=hours)  # Granica czasu trafia bezpośrednio do zapytania SQL.
    queryset = EarthquakeEvent.objects.filter(  # PostgreSQL wykonuje filtrowanie zamiast zewnętrznego API.
        event_time__gte=start_time,
        magnitude__gte=min_magnitude,
        depth_km__lte=max_depth,
    )
    if region:  # Pusty region nie powinien dodawać zbędnego warunku.
        queryset = queryset.filter(place__icontains=region)  # Wyszukiwanie tekstowe nie rozróżnia wielkości liter.

    if not queryset.exists() and not EarthquakeEvent.objects.exists():  # Pusta świeża baza wymaga pierwszego zasilenia.
        try:
            synchronize_earthquakes()  # Importujemy szerszy zakres, aby kolejne filtry nie wymagały requestu USGS.
        except Exception as error:
            return Response(  # Zwracamy odpowiedź 502, bo problem jest po stronie zależności zewnętrznej.
                {'detail': 'Nie udalo sie pobrac danych sejsmicznych.', 'error': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        queryset = EarthquakeEvent.objects.filter(  # Po synchronizacji ponawiamy identyczne filtry bazodanowe.
            event_time__gte=start_time,
            magnitude__gte=min_magnitude,
            depth_km__lte=max_depth,
        )
        if region:  # Region nadal obowiązuje po pierwszym imporcie.
            queryset = queryset.filter(place__icontains=region)

    results = EarthquakeEventSerializer(queryset.order_by('-event_time')[:200], many=True).data  # Serializujemy ograniczoną listę.
    return Response(  # Odpowiedź zawiera też metadane potrzebne do panelu informacyjnego.
        {
            'results': results,  # Rekordy pochodzą z relacyjnej bazy danych.
            'source': 'PostgreSQL / USGS',  # Jawnie pokazujemy źródło pierwotne i warstwę persystencji.
            'hours': hours,
            'min_magnitude': min_magnitude,
            'max_depth': max_depth,  # Metadane odzwierciedlają zastosowany filtr.
            'region': region,  # Frontend może pokazać aktywny filtr tekstowy.
            'count': len(results),  # Licznik dotyczy faktycznie zwróconych rekordów.
        }
    )


@extend_schema(
    responses={200: EarthquakeEventSerializer},
    summary='Szczegóły zdarzenia sejsmicznego',
    operation_id='earthquake_event_detail',
)
@api_view(['GET'])
@permission_classes([AllowAny])
def earthquake_event_detail(request, event_id):
    """Zwraca pojedyncze zdarzenie sejsmiczne z relacyjnej bazy."""

    event = get_object_or_404(EarthquakeEvent, pk=event_id)  # Brak lokalnego id daje standardową odpowiedź 404.
    return Response(EarthquakeEventSerializer(event).data)  # Serializer zapewnia ten sam format co lista.


@extend_schema(
    responses={200: EnvironmentalListResponseSerializer},  # Dokumentujemy listę i jej metadane.
    summary='Pełny katalog wulkanów holoceńskich zapisany w bazie',
    operation_id='volcanic_event_list',  # Nazwa odróżnia listę od szczegółów pojedynczego rekordu.
)
@api_view(['GET'])
@permission_classes([AllowAny])
def volcanic_events(request):
    """Zwraca wszystkie wulkany holoceńskie zsynchronizowane ze Smithsonian GVP."""

    region = str(request.query_params.get('region') or '').strip()  # Region pozwala zawęzić listę tekstowo.
    country = str(request.query_params.get('country') or '').strip()  # Kraj jest wygodnym filtrem katalogowym.
    has_vei = str(request.query_params.get('has_vei') or '').strip().lower() in {'1', 'true', 'yes'}  # Flaga wybiera rekordy z poznanym VEI.
    try:
        min_vei = int(request.query_params.get('min_vei', 0))  # Minimalne VEI odnosi się do maksimum znanego dla wulkanu.
    except ValueError:
        return Response({'detail': 'Parametr min_vei musi być liczbą.'}, status=status.HTTP_400_BAD_REQUEST)
    min_vei = max(0, min(min_vei, 8))  # Skala VEI jest ograniczona do klasycznego zakresu 0-8.
    queryset = VolcanicEvent.objects.all()  # Domyślnie zwracamy cały katalog, zgodnie z charakterem warstwy.
    if region:  # Pusty filtr nie wpływa na zapytanie.
        queryset = queryset.filter(region__icontains=region)  # Region nie rozróżnia wielkości liter.
    if country:  # Pusty kraj pozostawia globalny katalog.
        queryset = queryset.filter(country__icontains=country)  # Fragment tekstu obsługuje nazwy złożone.
    if has_vei:  # Warstwa mapy może świadomie pominąć wulkany bez sklasyfikowanej erupcji.
        queryset = queryset.filter(max_vei__isnull=False)  # Maksymalne VEI istnieje, jeśli co najmniej jedna erupcja ma indeks.
    if min_vei > 0:  # Zero oznacza brak ograniczenia i zachowuje wulkany bez sklasyfikowanej erupcji.
        queryset = queryset.filter(max_vei__gte=min_vei)  # Porównujemy najwyższe znane VEI w historii wulkanu.

    if not queryset.exists() and not VolcanicEvent.objects.exists():  # Pierwszy start może mieć pustą bazę.
        try:
            synchronize_volcanic_events()  # Pierwsze zasilenie pobiera pełny katalog wulkanów oraz erupcji.
        except Exception as error:
            return Response(
                {'detail': 'Nie udało się pobrać katalogu wulkanów.', 'error': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        queryset = VolcanicEvent.objects.all()  # Po imporcie ponawiamy odczyt pełnego katalogu.
        if region:
            queryset = queryset.filter(region__icontains=region)  # Zachowujemy filtr regionu.
        if country:
            queryset = queryset.filter(country__icontains=country)  # Zachowujemy filtr kraju.
        if has_vei:
            queryset = queryset.filter(max_vei__isnull=False)  # Zachowujemy wymóg dostępnego VEI.
        if min_vei > 0:
            queryset = queryset.filter(max_vei__gte=min_vei)  # Zachowujemy minimalne znane VEI.

    results = VolcanicEventSerializer(queryset.order_by('volcano_name')[:2000], many=True).data  # Limit mieści pełny katalog.
    return Response(
        {
            'results': results,  # Lista pochodzi z modelu VolcanicEvent.
            'source': 'PostgreSQL / Smithsonian GVP',  # Informacja opisuje persystencję oraz źródło naukowe.
            'region': region,  # Metadane pomagają odtworzyć filtr.
            'country': country,  # Kraj pozostaje pusty dla globalnego katalogu.
            'has_vei': has_vei,  # Flaga informuje, czy lista pomija brakujące indeksy.
            'min_vei': min_vei,  # Frontend może pokazać zastosowany próg.
            'count': len(results),  # Licznik ułatwia dashboardowi agregację.
        }
    )


@extend_schema(
    responses={200: VolcanicEventSerializer},
    summary='Szczegóły zdarzenia wulkanicznego',
    operation_id='volcanic_event_detail',
)
@api_view(['GET'])
@permission_classes([AllowAny])
def volcanic_event_detail(request, event_id):
    """Zwraca pojedynczy wulkan wraz z podsumowaniem erupcji z bazy."""

    event = get_object_or_404(VolcanicEvent, pk=event_id)  # Lokalne id jednoznacznie wskazuje rekord.
    return Response(VolcanicEventSerializer(event).data)  # Format odpowiada elementowi listy.


class AdminSyncStartView(APIView):
    """Dodaje wybrane zadanie synchronizacji do kolejki Celery."""

    permission_classes = (IsAdminUser,)  # Tylko użytkownik staff może uruchamiać kosztowne synchronizacje.
    serializer_class = SyncTaskAcceptedSerializer  # Generator OpenAPI otrzymuje jawny kształt odpowiedzi.
    task_map = {}  # Konkretne zadania są ładowane leniwie w metodzie post.

    @extend_schema(
        responses={202: SyncTaskAcceptedSerializer},  # Swagger pokazuje id zadania i typ synchronizacji.
        summary='Ręczne uruchomienie synchronizacji',
    )
    def post(self, request, job_type):
        from .tasks import (  # Import lokalny nie obciąża procesu HTTP podczas zwykłych requestów.
            sync_earthquakes_task,
            sync_saved_location_weather_task,
            sync_volcanic_events_task,
        )

        task_map = {  # Adres URL wybiera wyłącznie zadania z jawnej białej listy.
            'earthquakes': (SyncJob.JobType.EARTHQUAKE, sync_earthquakes_task),
            'weather': (SyncJob.JobType.WEATHER, sync_saved_location_weather_task),
            'volcanoes': (SyncJob.JobType.VOLCANO, sync_volcanic_events_task),
        }
        selected = task_map.get(job_type)  # Nieznany typ nie może uruchomić dowolnej funkcji.
        if selected is None:
            return Response({'detail': 'Nieznany typ synchronizacji.'}, status=status.HTTP_404_NOT_FOUND)
        sync_job_type, task = selected  # Rozdzielamy etykietę domenową i funkcję Celery.
        try:
            async_result = task.delay()  # Zadanie trafia do Redisa bez blokowania requestu HTTP.
        except Exception as error:
            return Response(
                {'detail': 'Nie udało się dodać zadania do kolejki.', 'error': str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {'task_id': async_result.id, 'job_type': sync_job_type, 'status': 'queued'},  # Odpowiedź potwierdza przyjęcie.
            status=status.HTTP_202_ACCEPTED,
        )


class AdminSyncStatusView(APIView):
    """Zwraca ostatnie logi synchronizacji dla panelu administratora."""

    permission_classes = (IsAdminUser,)  # Logi błędów i operacje administracyjne nie są publiczne.

    @extend_schema(responses={200: SyncJobSerializer(many=True)}, summary='Status synchronizacji danych')
    def get(self, request):
        jobs = SyncJob.objects.order_by('-started_at')[:50]  # Ostatnie 50 wpisów wystarcza do prostego panelu.
        return Response({'results': SyncJobSerializer(jobs, many=True).data, 'count': len(jobs)})  # Zwracamy listę i licznik.


@extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Aktywne burze i cyklony')
@api_view(['GET'])
@permission_classes([AllowAny])
def active_storms(request):
    """Zwraca dwie warstwy: cyklony z EONET i potencjał burzowy z Open-Meteo."""
    cache_key = 'storms:active:eonet-openmeteo:v3'  # Nowa wersja wykorzystuje dane pogodowe bez powtarzania requestów.
    fallback_key = 'storms:active:eonet-openmeteo:last-good:v3'  # Drugi klucz trzyma ostatnią dobrą odpowiedź.
    cached = cache.get(cache_key)  # Najpierw próbujemy użyć cache.
    if cached is not None:  # Jeśli cache istnieje, nie odpytujemy zewnętrznych API.
        return Response(cached)  # Zwracamy zapamiętaną odpowiedź.

    cyclones = []  # Domyślnie cyklony mogą być puste, jeśli EONET chwilowo ograniczy requesty.
    cyclones_stale = False  # Flaga odróżnia świeże zdarzenia EONET od awaryjnej kopii.
    storm_candidates = []  # Domyślnie punkty burzowe mogą być puste, jeśli Open-Meteo chwilowo odmówi.
    source_errors = []  # Lista błędów źródeł trafi do odpowiedzi diagnostycznej.

    try:
        eonet_data = _fetch_json(_eonet_cyclone_url())  # Pobieramy aktywne severe storms z NASA EONET.
        if not isinstance(eonet_data, dict):  # Odpowiedź musi być obiektem zawierającym tablicę events.
            raise ValueError('EONET zwrocil niepoprawny format odpowiedzi.')
        cyclones = [  # Normalizujemy tylko zdarzenia z poprawną geometrią punktową.
            cyclone
            for cyclone in (_normalize_cyclone_event(event) for event in eonet_data.get('events', []))
            if cyclone.get('latitude') is not None and cyclone.get('longitude') is not None
        ]
        if cyclones:  # Nie nadpisujemy dobrej kopii pustą listą z dnia bez aktywnych systemów.
            cache.set(CYCLONE_FALLBACK_KEY, cyclones, timeout=7 * 24 * 60 * 60)  # Aktywne systemy zachowujemy na tydzień.
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError) as error:  # EONET może zwrócić błąd formatu lub sieci.
        source_errors.append(f'EONET: {error}')  # Zapisujemy błąd, ale nie przerywamy całego endpointu.
        cyclones = _cached_cyclone_fallback()  # Przy awarii próbujemy pokazać ostatnie poprawne zdarzenia.
        cyclones_stale = bool(cyclones)  # Flaga jest prawdziwa tylko wtedy, gdy faktycznie użyto starszych danych.

    weather_payload = cache.get(GLOBAL_WEATHER_CACHE_KEY)  # Najpierw szukamy danych pobranych podczas startu aplikacji.
    storm_candidates = _storm_candidates_from_weather_cache(weather_payload)  # Ponownie wykorzystujemy opad i porywy wiatru.
    if not storm_candidates:  # Osobne requesty są potrzebne tylko bez gotowej globalnej pogody.
        try:
            for chunk in _chunked(_all_weather_points(), OPEN_METEO_BATCH_SIZE):  # Używamy tych samych punktów co mapa pogody.
                storm_candidates.extend(_normalize_storm_batch(chunk, _fetch_json(_storm_weather_url(chunk))))  # Pobieramy zmienne burzowe.
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError) as error:  # Open-Meteo może zwrócić błąd formatu lub sieci.
            source_errors.append(f'Open-Meteo: {error}')  # Zapisujemy błąd źródła punktów burzowych.

    if source_errors and not cyclones and not storm_candidates:  # Jeśli oba źródła zawiodły, szukamy ostatniej dobrej odpowiedzi.
        fallback = cache.get(fallback_key)  # Ostatnia dobra odpowiedź pozwala UI nadal działać.
        if fallback is not None:  # Jeśli fallback istnieje, zwracamy go z informacją diagnostyczną.
            stale_payload = {**fallback, 'stale': True, 'source_errors': source_errors}  # Tworzymy kopię zamiast modyfikować cache.
            return Response(stale_payload)  # Nie zwracamy 502, bo mamy użyteczne dane.
        return Response(  # Błąd zewnętrznego API oznacza 502.
            {'detail': 'Nie udalo sie pobrac danych burzowych.', 'errors': source_errors},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    storms = [  # Odsiewamy tylko sensowne kandydaty burzowe.
        storm
        for storm in storm_candidates
        if storm['storm_score'] >= 55 or storm.get('weather_code') in STORM_WEATHER_CODES
    ]
    storms = sorted(storms, key=lambda storm: storm['storm_score'], reverse=True)[:80]  # Pokazujemy najsilniejsze punkty.
    payload = {  # Budujemy odpowiedź dla frontendu.
        'cyclones': cyclones,  # Warstwa cyklonów z EONET.
        'storms': storms,  # Warstwa burz/potencjału burzowego z Open-Meteo.
        'source': 'NASA EONET + Open-Meteo',  # Jawna informacja o źródłach.
        'source_errors': source_errors,  # Jeśli jedno źródło padło, UI może to pokazać bez awarii.
        'cyclones_stale': cyclones_stale,  # Frontend może ostrzec, że cyklony pochodzą z fallbacku.
        'stale': False,  # Świeża odpowiedź nie jest fallbackiem.
        'cache_ttl_seconds': 900,  # Dane burzowe cacheujemy krócej niż globalną pogodę.
        'counts': {'cyclones': len(cyclones), 'storms': len(storms)},  # Liczniki pomagają UI i debugowaniu.
    }
    cache.set(cache_key, payload, timeout=15 * 60)  # Cache ogranicza liczbę cięższych requestów.
    cache.set(fallback_key, payload, timeout=6 * 60 * 60)  # Ostatnią dobrą odpowiedź trzymamy dłużej jako awaryjną.
    return Response(payload)  # Zwracamy gotową warstwę burzową.
