"""Podstawowe endpointy techniczne aplikacji."""

from django.core.cache import cache  # Cache pozwala sprawdzić połączenie z Redisem.
from django.db import connection  # Połączenie wykonuje lekkie zapytanie kontrolne do bazy.
from drf_spectacular.types import OpenApiTypes  # Ogólny obiekt wystarcza dla technicznej odpowiedzi kontrolnej.
from drf_spectacular.utils import extend_schema  # Dekorator dodaje endpoint do dokumentacji OpenAPI.
from rest_framework import status  # Nazwane kody odpowiedzi poprawiają czytelność.
from rest_framework.decorators import api_view, permission_classes  # Dekoratory tworzą publiczny endpoint DRF.
from rest_framework.permissions import AllowAny  # Healthcheck musi działać przed logowaniem użytkownika.
from rest_framework.response import Response  # Response serializuje wynik kontroli do JSON.


@extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Stan backendu, bazy i cache')
@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """Sprawdza dostępność backendu, relacyjnej bazy i Redisa."""

    checks = {'database': 'ok', 'redis': 'ok'}  # Domyślnie zakładamy poprawny stan obu zależności.
    errors = {}  # Szczegóły błędów pomagają w diagnostyce Docker Compose.

    try:
        with connection.cursor() as cursor:  # Kursor korzysta z aktualnie skonfigurowanej bazy.
            cursor.execute('SELECT 1')  # Najlżejsze zapytanie potwierdza gotowość połączenia.
            cursor.fetchone()  # Odczyt wyniku kończy pełny cykl zapytania.
    except Exception as error:
        checks['database'] = 'error'  # Nieudane zapytanie oznacza niedostępną bazę.
        errors['database'] = str(error)  # Komunikat trafia do odpowiedzi diagnostycznej.

    try:
        cache.set('health:probe', 'ok', timeout=10)  # Zapis sprawdza, czy Redis przyjmuje dane.
        if cache.get('health:probe') != 'ok':  # Odczyt potwierdza pełne działanie cache.
            raise RuntimeError('Redis nie zwrócił wartości kontrolnej.')
    except Exception as error:
        checks['redis'] = 'error'  # Awaria cache jest widoczna osobno od bazy.
        errors['redis'] = str(error)  # Szczegół ułatwia rozpoznanie problemu sieciowego.

    is_healthy = all(value == 'ok' for value in checks.values())  # Backend jest zdrowy tylko przy obu zależnościach.
    payload = {  # Odpowiedź ma stabilny format przy sukcesie i błędzie.
        'status': 'ok' if is_healthy else 'error',  # Główny status jest czytelny dla Dockera.
        **checks,  # Pola database i redis pokazują stan każdej usługi.
        'errors': errors,  # Przy sukcesie obiekt pozostaje pusty.
    }
    response_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE  # 503 zatrzymuje zależne kontenery.
    return Response(payload, status=response_status)  # Zwracamy wynik kontroli.
