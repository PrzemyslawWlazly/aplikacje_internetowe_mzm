"""Widoki API dla danych obserwacyjnych aplikacji Matka Ziemia Monitor."""

import json  # Moduł JSON pozwala zamienić tekst z API zewnętrznego na struktury Pythona.
from datetime import datetime, timedelta, timezone as datetime_timezone  # Datetime obsługuje zakresy i czas UTC.
from urllib.error import HTTPError, URLError  # URLError/HTTPError obsługują problemy połączenia z API zewnętrznym.
from urllib.parse import urlencode  # urlencode bezpiecznie buduje query string dla adresów URL.
from urllib.request import Request, urlopen  # Request i urlopen wykonują prosty request HTTP bez dodatkowej biblioteki.

from django.core.cache import cache  # Cache ogranicza liczbę zapytań do zewnętrznych API.
from django.utils import timezone  # timezone daje poprawny czas zgodny z ustawieniami Django.
from rest_framework import status  # status przechowuje czytelne stałe kodów HTTP.
from rest_framework.decorators import api_view, permission_classes  # Dekoratory zamieniają funkcje w endpointy DRF.
from rest_framework.permissions import AllowAny  # AllowAny pozwala udostępnić publiczne dane bez logowania.
from rest_framework.response import Response  # Response zwraca dane jako odpowiedź API DRF.


OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'  # Publiczne API pogodowe bez klucza.
REST_COUNTRIES_URL = 'https://restcountries.com/v3.1/all?fields=name,capital,capitalInfo,cca2,independent'  # API z listą państw i stolic.
USGS_EARTHQUAKE_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'  # Oficjalny endpoint zdarzeń USGS.
EONET_EVENTS_URL = 'https://eonet.gsfc.nasa.gov/api/v3/events'  # NASA EONET udostępnia aktywne zdarzenia naturalne.
REQUEST_TIMEOUT = 8  # Limit czasu zabezpiecza backend przed zbyt długim czekaniem na zewnętrzne API.
OPEN_METEO_BATCH_SIZE = 80  # Dzielimy pogodę na paczki, żeby adres URL nie był zbyt długi.
CYCLONE_CATEGORY_ID = 'severeStorms'  # W EONET v3 kategoria severeStorms obejmuje silne burze i cyklony.
STORM_WEATHER_CODES = {95, 96, 99}  # Kody WMO 95-99 oznaczają burzę, w tym burzę z gradem.


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


def _fetch_json(url):
    """Pobiera JSON z zewnętrznego API i zwraca go jako słownik Pythona."""
    request = Request(url, headers={'User-Agent': 'MatkaZiemiaMonitor/0.1'})  # User-Agent pomaga API rozpoznać klienta.
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


def _capital_points_from_rest_countries():
    """Pobiera listę stolic świata z REST Countries."""
    cached = cache.get('weather:capital-points:v2')  # Stolice zmieniają się rzadko, więc trzymamy je w cache.
    if cached is not None:  # Jeśli cache istnieje, nie pytamy ponownie REST Countries.
        return cached  # Zwracamy gotową listę punktów.

    countries = _fetch_json(REST_COUNTRIES_URL)  # Pobieramy państwa wraz z metadanymi stolic.
    points = []  # Tu zbieramy stolice, które mają współrzędne.
    for country in countries:  # Iterujemy po każdym państwie zwróconym przez REST Countries.
        country_name = country.get('name', {}).get('common')  # Nazwa common jest najbardziej czytelna w UI.
        independent = country.get('independent')  # Flaga mówi, czy rekord dotyczy państwa niepodległego.
        capitals = country.get('capital') or []  # REST Countries trzyma stolice jako listę.
        latlng = country.get('capitalInfo', {}).get('latlng') or []  # Współrzędne stolicy są w capitalInfo.
        if independent is False:  # Pomijamy terytoria zależne, bo wymaganie dotyczy stolic państw.
            continue  # Przechodzimy do kolejnego rekordu API.
        if not country_name or not capitals or len(latlng) < 2:  # Pomijamy rekordy bez pełnych danych.
            continue  # Nie dodajemy punktu, którego nie da się pokazać na mapie.
        points.append(  # Dodajemy pierwszy punkt stolicy do mapy pogodowej.
            {
                'name': capitals[0],  # Nazwa stolicy.
                'country': country_name,  # Nazwa kraju do panelu szczegółów.
                'group': 'world_capital',  # Grupa pozwala frontendowi rozróżnić typ punktu.
                'latitude': latlng[0],  # Szerokość geograficzna stolicy.
                'longitude': latlng[1],  # Długość geograficzna stolicy.
            }
        )

    cache.set('weather:capital-points:v2', points, timeout=24 * 60 * 60)  # Listę stolic cacheujemy przez dobę.
    return points  # Zwracamy punkty stolic.


def _all_weather_points():
    """Łączy stolice świata, miasta G20 i 20 największych miast Polski."""
    points = []  # Lista wynikowa zachowa kolejność priorytetów.
    seen = set()  # Zbiór kluczy chroni przed duplikatami.
    for point in [*POLISH_WEATHER_POINTS, *G20_MAJOR_CITY_POINTS, *_capital_points_from_rest_countries()]:
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
            'current': 'temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,weather_code,cloud_cover',
            'timezone': 'Europe/Warsaw',  # Czas wyników ustawiamy pod prezentację w Polsce.
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
        'weather_code': current.get('weather_code'),  # Kod warunków, później można mapować go na opisy.
        'cloud_cover': current.get('cloud_cover'),  # Całkowite zachmurzenie nieba w procentach.
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
        'external_id': f"storm-{point['name']}-{point.get('country', '')}",  # Id jest stabilne dla listy Reacta.
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


@api_view(['GET'])
@permission_classes([AllowAny])
def current_weather(request):
    """Zwraca aktualną pogodę dla stolic świata, miast G20 i 20 największych miast Polski."""
    cache_key = 'weather:current:global-capitals-g20-poland:v4'  # Jeden klucz opisuje pełną globalną warstwę pogody.
    fallback_key = 'weather:current:global-capitals-g20-poland:last-good:v4'  # Ostatnia dobra pogoda ratuje UI przy 429.
    cached = cache.get(cache_key)  # Najpierw próbujemy oddać gotową odpowiedź z cache.
    if cached is not None:  # Jeśli dane są świeże, nie wykonujemy requestów do Open-Meteo.
        return Response(cached)  # Zwracamy pełną zapamiętaną odpowiedź.

    try:
        points = _all_weather_points()  # Budujemy zestaw lokalizacji z trzech źródeł.
        results = []  # Tu zbierzemy pogodę z kolejnych paczek Open-Meteo.
        for chunk in _chunked(points, OPEN_METEO_BATCH_SIZE):  # Pytamy Open-Meteo paczkami po kilkadziesiąt punktów.
            results.extend(_normalize_weather_batch(chunk, _fetch_json(_weather_url(chunk))))  # Pobieramy i dokładamy wyniki.
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:  # Obsługujemy typowe błędy sieci i parsowania.
        fallback = cache.get(fallback_key)  # Szukamy ostatniej dobrej odpowiedzi pogodowej.
        if fallback is not None:  # Jeśli ją mamy, lepiej pokazać starsze dane niż pustą mapę.
            fallback['stale'] = True  # Flaga informuje frontend, że dane są awaryjne.
            fallback['source_errors'] = [str(error)]  # Zachowujemy przyczynę fallbacku.
            return Response(fallback)  # Odpowiadamy 200, bo aplikacja ma użyteczny zestaw danych.
        return Response(  # Zwracamy czytelny błąd zamiast niekontrolowanego wyjątku.
            {'detail': 'Nie udalo sie pobrac globalnych danych pogodowych.', 'error': str(error)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    payload = {  # Odpowiedź zawiera dane i metadane przydatne w UI.
        'results': results,  # Lista punktów pogodowych dla mapy Leaflet.
        'source': 'Open-Meteo + REST Countries',  # Jawnie opisujemy źródła warstwy.
        'stale': False,  # Świeże dane nie są fallbackiem.
        'source_errors': [],  # Brak błędów źródeł przy normalnej odpowiedzi.
        'cache_ttl_seconds': 1800,  # Globalną pogodę cacheujemy przez 30 minut.
        'counts': {  # Liczniki pomagają sprawdzić, czy zakres danych jest zgodny z wymaganiem.
            'all_points': len(results),  # Łączna liczba punktów na mapie.
            'poland_top_20': sum(1 for point in results if point.get('group') == 'poland_top_20'),  # Punkty Polski.
            'g20_major_cities': sum(1 for point in results if point.get('group') == 'g20_major_city'),  # Miasta G20.
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


@api_view(['GET'])
@permission_classes([AllowAny])
def earthquake_events(request):
    """Zwraca najnowsze trzęsienia ziemi z USGS."""
    try:
        hours = int(request.query_params.get('hours', 24))  # Domyślnie pokazujemy ostatnie 24 godziny.
        min_magnitude = float(request.query_params.get('min_magnitude', 2.5))  # Domyślnie ukrywamy bardzo małe zdarzenia.
    except ValueError:
        return Response(  # Niepoprawne filtry są błędem użytkownika, więc zwracamy 400.
            {'detail': 'Parametry hours i min_magnitude musza byc liczbami.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    hours = max(1, min(hours, 720))  # Ograniczamy zakres od 1 godziny do 30 dni.
    min_magnitude = max(0, min(min_magnitude, 10))  # Magnituda powinna zostać w realistycznym zakresie.
    cache_key = f'earthquakes:{hours}:{min_magnitude}'  # Cache zależy od filtrów zapytania.
    cached = cache.get(cache_key)  # Najpierw sprawdzamy cache backendu.

    if cached is None:  # Gdy cache wygasł, pobieramy świeże dane z USGS.
        try:
            api_data = _fetch_json(_earthquake_url(hours, min_magnitude))  # Pobieramy GeoJSON z USGS.
        except (URLError, TimeoutError, json.JSONDecodeError) as error:  # Obsługujemy awarię API zewnętrznego.
            return Response(  # Zwracamy odpowiedź 502, bo problem jest po stronie zależności zewnętrznej.
                {'detail': 'Nie udalo sie pobrac danych sejsmicznych.', 'error': str(error)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        cached = [_normalize_earthquake(feature) for feature in api_data.get('features', [])]  # Normalizujemy listę.
        cache.set(cache_key, cached, timeout=5 * 60)  # Dane sejsmiczne cacheujemy krótko, bo zmieniają się dynamicznie.

    return Response(  # Odpowiedź zawiera też metadane potrzebne do panelu informacyjnego.
        {
            'results': cached,
            'source': 'USGS',
            'hours': hours,
            'min_magnitude': min_magnitude,
            'cache_ttl_seconds': 300,
        }
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def active_storms(request):
    """Zwraca dwie warstwy: cyklony z EONET i potencjał burzowy z Open-Meteo."""
    cache_key = 'storms:active:eonet-openmeteo:v2'  # Jeden klucz cache przechowuje gotową odpowiedź burzową.
    fallback_key = 'storms:active:eonet-openmeteo:last-good:v2'  # Drugi klucz trzyma ostatnią dobrą odpowiedź.
    cached = cache.get(cache_key)  # Najpierw próbujemy użyć cache.
    if cached is not None:  # Jeśli cache istnieje, nie odpytujemy zewnętrznych API.
        return Response(cached)  # Zwracamy zapamiętaną odpowiedź.

    cyclones = []  # Domyślnie cyklony mogą być puste, jeśli EONET chwilowo ograniczy requesty.
    storm_candidates = []  # Domyślnie punkty burzowe mogą być puste, jeśli Open-Meteo chwilowo odmówi.
    source_errors = []  # Lista błędów źródeł trafi do odpowiedzi diagnostycznej.

    try:
        eonet_data = _fetch_json(_eonet_cyclone_url())  # Pobieramy aktywne severe storms z NASA EONET.
        cyclones = [  # Normalizujemy tylko zdarzenia z poprawną geometrią punktową.
            cyclone
            for cyclone in (_normalize_cyclone_event(event) for event in eonet_data.get('events', []))
            if cyclone.get('latitude') is not None and cyclone.get('longitude') is not None
        ]
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:  # EONET może zwrócić rate limit lub błąd sieci.
        source_errors.append(f'EONET: {error}')  # Zapisujemy błąd, ale nie przerywamy całego endpointu.

    try:
        for chunk in _chunked(_all_weather_points(), OPEN_METEO_BATCH_SIZE):  # Używamy tych samych punktów co mapa pogody.
            storm_candidates.extend(_normalize_storm_batch(chunk, _fetch_json(_storm_weather_url(chunk))))  # Pobieramy zmienne burzowe.
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:  # Open-Meteo także może chwilowo ograniczyć requesty.
        source_errors.append(f'Open-Meteo: {error}')  # Zapisujemy błąd źródła punktów burzowych.

    if source_errors and not cyclones and not storm_candidates:  # Jeśli oba źródła zawiodły, szukamy ostatniej dobrej odpowiedzi.
        fallback = cache.get(fallback_key)  # Ostatnia dobra odpowiedź pozwala UI nadal działać.
        if fallback is not None:  # Jeśli fallback istnieje, zwracamy go z informacją diagnostyczną.
            fallback['stale'] = True  # Flaga mówi frontendowi, że dane są starsze.
            fallback['source_errors'] = source_errors  # Dołączamy przyczynę użycia fallbacku.
            return Response(fallback)  # Nie zwracamy 502, bo mamy użyteczne dane.
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
        'stale': False,  # Świeża odpowiedź nie jest fallbackiem.
        'cache_ttl_seconds': 900,  # Dane burzowe cacheujemy krócej niż globalną pogodę.
        'counts': {'cyclones': len(cyclones), 'storms': len(storms)},  # Liczniki pomagają UI i debugowaniu.
    }
    cache.set(cache_key, payload, timeout=15 * 60)  # Cache ogranicza liczbę cięższych requestów.
    cache.set(fallback_key, payload, timeout=6 * 60 * 60)  # Ostatnią dobrą odpowiedź trzymamy dłużej jako awaryjną.
    return Response(payload)  # Zwracamy gotową warstwę burzową.
