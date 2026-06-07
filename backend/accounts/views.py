from django.conf import settings  # Ustawienia udostępniają Client ID do sprawdzenia odbiorcy tokenu.
from django.contrib.auth import get_user_model  # Funkcja zwraca aktywny model użytkownika Django.
from django.db import transaction  # Transakcja chroni tworzenie użytkownika i konta przed częściowym zapisem.
from google.auth import exceptions as google_auth_exceptions  # Importujemy błędy biblioteki Google Auth.
from google.auth.transport import requests as google_requests  # Adapter pobiera klucze publiczne Google przez HTTP.
from google.oauth2 import id_token as google_id_token  # Moduł kryptograficznie sprawdza token ID od Google.
from drf_spectacular.utils import extend_schema  # Dekorator opisuje requesty i odpowiedzi w dokumentacji Swagger.
from rest_framework import status  # Nazwane statusy HTTP są czytelniejsze od surowych liczb.
from rest_framework.permissions import AllowAny, IsAuthenticated  # Uprawnienia rozdzielają logowanie i profil.
from rest_framework.response import Response  # Response serializuje słownik do odpowiedzi JSON.
from rest_framework.views import APIView  # APIView jest bazą dla endpointów Django REST Framework.
from rest_framework_simplejwt.tokens import RefreshToken  # SimpleJWT tworzy token dostępu i odświeżania.

from .models import GoogleAccount  # Model przechowuje stabilne powiązanie z identyfikatorem Google.
from .serializers import (  # Importujemy serializery wejścia i odpowiedzi dla dokumentacji API.
    CurrentUserResponseSerializer,
    GoogleCredentialSerializer,
    GoogleLoginResponseSerializer,
)


def serialize_user(user):
    """Buduje bezpieczny słownik z danymi użytkownika widocznymi dla frontendu."""

    # Relacja może nie istnieć dla kont utworzonych lokalnie przez panel administracyjny.
    google_account = getattr(user, 'google_account', None)
    # Zwracamy tylko dane potrzebne interfejsowi, bez haseł i uprawnień administracyjnych.
    return {
        'id': user.pk,  # Identyfikator przyda się później przy zasobach należących do użytkownika.
        'email': user.email,  # E-mail jest zweryfikowany przez Google przed zapisaniem.
        'first_name': user.first_name,  # Imię wyświetlimy w nagłówku aplikacji.
        'last_name': user.last_name,  # Nazwisko może uzupełnić nazwę profilu.
        'picture_url': google_account.picture_url if google_account else '',  # Zdjęcie jest opcjonalne.
    }


def build_unique_username(subject):
    """Tworzy techniczną, unikalną nazwę użytkownika na podstawie identyfikatora Google."""

    # Pobieramy aktywny model użytkownika, aby nie wiązać kodu na stałe z django.contrib.auth.User.
    user_model = get_user_model()
    # Prefiks wyjaśnia pochodzenie konta, a fragment sub mieści się w standardowym limicie 150 znaków.
    base_username = f'google_{subject}'[:150]
    # Najczęściej pierwsza propozycja jest wolna, więc możemy od razu ją zwrócić.
    if not user_model.objects.filter(username=base_username).exists():
        return base_username
    # Kolizje są mało prawdopodobne, ale licznik gwarantuje poprawne działanie także przy danych testowych.
    suffix = 1
    # Szukamy kolejnej wolnej nazwy bez ograniczania liczby możliwych prób.
    while True:
        # Skracamy bazę tak, aby sufiks i podkreślenie nie przekroczyły limitu pola username.
        candidate = f'{base_username[:145]}_{suffix}'
        # Zwracamy pierwszą nazwę, której nie ma jeszcze w bazie.
        if not user_model.objects.filter(username=candidate).exists():
            return candidate
        # Zwiększamy licznik przed następną próbą.
        suffix += 1


class GoogleLoginView(APIView):
    """Wymienia token ID Google na tokeny JWT należące do naszej aplikacji."""

    permission_classes = (AllowAny,)  # Niezalogowany użytkownik musi mieć dostęp do endpointu logowania.
    authentication_classes = ()  # Nie próbujemy odczytywać lokalnego JWT podczas pierwszego logowania.

    @extend_schema(
        request=GoogleCredentialSerializer,  # Swagger pokaże wymagane pole credential.
        responses={200: GoogleLoginResponseSerializer},  # Dokumentujemy tokeny i profil zwracane po sukcesie.
        summary='Logowanie kontem Google',  # Krótki tytuł pojawi się na liście endpointów.
    )
    def post(self, request):
        # Serializer sprawdza, czy request zawiera niepustą wartość credential.
        serializer = GoogleCredentialSerializer(data=request.data)
        # Przy błędnym formacie DRF automatycznie zwraca odpowiedź 400 z opisem pola.
        serializer.is_valid(raise_exception=True)

        # Bez Client ID backend nie potrafi sprawdzić, czy token został wystawiony dla naszej aplikacji.
        if not settings.GOOGLE_OAUTH_CLIENT_ID:
            return Response(
                {'detail': 'Logowanie Google nie jest skonfigurowane na backendzie.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            # Biblioteka sprawdza podpis, termin ważności, wystawcę oraz pole aud równe naszemu Client ID.
            token_data = google_id_token.verify_oauth2_token(
                serializer.validated_data['credential'],
                google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except (ValueError, google_auth_exceptions.GoogleAuthError):
            # Nie ujawniamy szczegółów kryptograficznych, bo frontend potrzebuje tylko informacji o odrzuceniu.
            return Response(
                {'detail': 'Token Google jest nieprawidłowy albo wygasł.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Google oznacza zweryfikowany adres osobnym polem, którego wymagamy przed utworzeniem konta.
        email_verified = token_data.get('email_verified') in {True, 'true'}
        # Pole sub jest stabilnym identyfikatorem konta i nie zmienia się razem z adresem czy nazwą.
        subject = str(token_data.get('sub') or '').strip()
        # Normalizujemy e-mail do małych liter, aby nie tworzyć duplikatów różniących się wielkością znaków.
        email = str(token_data.get('email') or '').strip().lower()

        # Brak któregoś z wymaganych pól oznacza, że odpowiedź Google nie wystarcza do bezpiecznego logowania.
        if not subject or not email or not email_verified:
            return Response(
                {'detail': 'Konto Google nie udostępniło zweryfikowanego adresu e-mail.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Pobieramy aktywny model użytkownika przed rozpoczęciem operacji bazodanowych.
        user_model = get_user_model()

        # Jedna transakcja gwarantuje, że użytkownik i jego powiązanie Google powstaną razem.
        with transaction.atomic():
            # Najpierw szukamy stabilnego identyfikatora sub, bo e-mail może zostać kiedyś zmieniony.
            google_account = GoogleAccount.objects.select_related('user').filter(subject=subject).first()

            if google_account:
                # Istniejące powiązanie jednoznacznie wskazuje użytkownika aplikacji.
                user = google_account.user
            else:
                # Sam zgodny e-mail nie wystarcza do bezpiecznego automatycznego połączenia lokalnego konta.
                if user_model.objects.filter(email__iexact=email).exists():
                    return Response(
                        {
                            'detail': (
                                'Konto z tym adresem już istnieje. '
                                'Najpierw połącz je z Google z poziomu ustawień konta.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                # Pierwsze logowanie tworzy nowego użytkownika rozpoznawanego później wyłącznie przez Google sub.
                user = user_model(
                    username=build_unique_username(subject),
                    email=email,
                )
                # Nowy użytkownik loguje się wyłącznie przez Google, więc nie otrzymuje sztucznego hasła.
                user.set_unusable_password()
                # Zapisujemy użytkownika przed utworzeniem relacji OneToOne.
                user.save()
                # Tworzymy trwałe powiązanie z Google po zapisaniu użytkownika.
                google_account = GoogleAccount.objects.create(
                    user=user,
                    subject=subject,
                    email=email,
                    picture_url=str(token_data.get('picture') or ''),
                )

            # Aktualizujemy dane prezentacyjne, ponieważ użytkownik mógł zmienić je w profilu Google.
            user.email = email
            # Standardowy model Django ogranicza imię do 150 znaków.
            user.first_name = str(token_data.get('given_name') or '')[:150]
            # Standardowy model Django ogranicza nazwisko do 150 znaków.
            user.last_name = str(token_data.get('family_name') or '')[:150]
            # Istniejące powiązanie może wskazywać konto zablokowane już po wcześniejszym logowaniu.
            if not user.is_active:
                return Response(
                    {'detail': 'To konto użytkownika jest nieaktywne.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Zapisujemy aktualne dane profilu użytkownika.
            user.save(update_fields=('email', 'first_name', 'last_name'))
            # Aktualizujemy kopię e-maila i zdjęcia w rekordzie integracji.
            google_account.email = email
            # URL zdjęcia może być pusty, dlatego zamieniamy brak wartości na pusty tekst.
            google_account.picture_url = str(token_data.get('picture') or '')
            # Zapisujemy tylko pola, które mogły zmienić się podczas logowania.
            google_account.save(update_fields=('email', 'picture_url', 'updated_at'))

        # Token odświeżania pozwala uzyskać nowy access token bez ponownego otwierania okna Google.
        refresh = RefreshToken.for_user(user)
        # Frontend otrzymuje lokalne tokeny i podstawowe dane profilu w jednej odpowiedzi.
        return Response(
            {
                'access': str(refresh.access_token),  # Krótko żyjący token do autoryzowania requestów API.
                'refresh': str(refresh),  # Dłużej żyjący token służący wyłącznie do odświeżania sesji.
                'user': serialize_user(user),  # Dane pozwalają od razu odświeżyć nagłówek aplikacji.
            },
            status=status.HTTP_200_OK,
        )


class CurrentUserView(APIView):
    """Zwraca profil użytkownika wynikający z lokalnego tokenu JWT."""

    permission_classes = (IsAuthenticated,)  # Endpoint działa tylko z poprawnym access tokenem.

    @extend_schema(
        responses={200: CurrentUserResponseSerializer},  # Swagger pokaże strukturę profilu użytkownika.
        summary='Profil zalogowanego użytkownika',  # Tytuł wyjaśnia przeznaczenie chronionej trasy.
    )
    def get(self, request):
        # request.user został wcześniej odtworzony przez JWTAuthentication z ustawień DRF.
        return Response({'user': serialize_user(request.user)})
