from unittest.mock import patch  # Mock pozwala testować logowanie bez połączenia z serwerami Google.

from django.contrib.auth import get_user_model  # Pobieramy aktywny model użytkownika Django.
from django.test import override_settings  # Dekorator ustawia testowy Google Client ID.
from rest_framework import status  # Nazwane statusy HTTP poprawiają czytelność asercji.
from rest_framework.test import APITestCase  # Klasa udostępnia klienta do testowania endpointów DRF.

from .models import GoogleAccount  # Model pozwala sprawdzić, czy powiązanie zostało zapisane.


@override_settings(GOOGLE_OAUTH_CLIENT_ID='test-client.apps.googleusercontent.com')
class GoogleLoginTests(APITestCase):
    """Sprawdza wymianę tokenu Google na lokalną sesję JWT."""

    def google_payload(self):
        # Zwracamy dane podobne do zweryfikowanego tokenu ID, ale bez prawdziwych danych użytkownika.
        return {
            'sub': 'google-subject-123',  # Stabilny identyfikator konta Google.
            'email': 'student@example.com',  # Testowy zweryfikowany adres e-mail.
            'email_verified': True,  # Backend wymaga potwierdzenia własności adresu.
            'given_name': 'Jan',  # Imię powinno trafić do użytkownika Django.
            'family_name': 'Kowalski',  # Nazwisko powinno trafić do użytkownika Django.
            'picture': 'https://example.com/avatar.jpg',  # URL zdjęcia powinien trafić do GoogleAccount.
        }

    @patch('accounts.views.google_id_token.verify_oauth2_token')
    def test_google_login_creates_account_and_returns_jwt(self, verify_token):
        # Zastępujemy kryptograficzną weryfikację kontrolowanym wynikiem testowym.
        verify_token.return_value = self.google_payload()

        # Wysyłamy dowolny tekst credential, ponieważ funkcja Google jest w tym teście zamockowana.
        response = self.client.post('/api/auth/google/', {'credential': 'test-token'}, format='json')

        # Poprawne logowanie powinno zwrócić odpowiedź 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Odpowiedź powinna zawierać krótko żyjący access token.
        self.assertIn('access', response.data)
        # Odpowiedź powinna zawierać refresh token do odnowienia sesji.
        self.assertIn('refresh', response.data)
        # Frontend powinien od razu otrzymać adres zalogowanego użytkownika.
        self.assertEqual(response.data['user']['email'], 'student@example.com')
        # Baza powinna zawierać dokładnie jednego użytkownika Django.
        self.assertEqual(get_user_model().objects.count(), 1)
        # Baza powinna zawierać dokładnie jedno trwałe powiązanie Google.
        self.assertEqual(GoogleAccount.objects.count(), 1)

    @patch('accounts.views.google_id_token.verify_oauth2_token')
    def test_second_login_reuses_existing_google_account(self, verify_token):
        # Oba logowania zwracają ten sam identyfikator sub.
        verify_token.return_value = self.google_payload()

        # Pierwszy request tworzy użytkownika i powiązanie.
        self.client.post('/api/auth/google/', {'credential': 'first-token'}, format='json')
        # Drugi request powinien zalogować to samo konto.
        self.client.post('/api/auth/google/', {'credential': 'second-token'}, format='json')

        # Ponowne logowanie nie może utworzyć duplikatu użytkownika.
        self.assertEqual(get_user_model().objects.count(), 1)
        # Ponowne logowanie nie może utworzyć duplikatu powiązania.
        self.assertEqual(GoogleAccount.objects.count(), 1)

    @patch('accounts.views.google_id_token.verify_oauth2_token')
    def test_invalid_google_token_is_rejected(self, verify_token):
        # Biblioteka Google zgłasza ValueError dla tokenu ze złym podpisem, aud albo terminem ważności.
        verify_token.side_effect = ValueError('invalid token')

        # Wysyłamy request z tokenem, który zostanie odrzucony przez zamockowaną bibliotekę.
        response = self.client.post('/api/auth/google/', {'credential': 'invalid-token'}, format='json')

        # Endpoint powinien odpowiedzieć kodem 401.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Odrzucone logowanie nie może tworzyć konta w bazie.
        self.assertEqual(get_user_model().objects.count(), 0)

    @patch('accounts.views.google_id_token.verify_oauth2_token')
    def test_google_login_does_not_link_existing_account_by_email_only(self, verify_token):
        # Tworzymy lokalne konto, które nie zostało jeszcze jawnie połączone z Google.
        get_user_model().objects.create_user(
            username='local-student',
            email='student@example.com',
            password='temporary-test-password',
        )
        # Google zwraca ten sam e-mail, ale samo podobieństwo adresu nie wystarcza do połączenia kont.
        verify_token.return_value = self.google_payload()

        # Próbujemy wykonać pierwsze logowanie Google dla zajętego adresu.
        response = self.client.post('/api/auth/google/', {'credential': 'test-token'}, format='json')

        # Backend powinien wymagać osobnego, świadomego procesu łączenia kont.
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        # Nie tworzymy automatycznie rekordu GoogleAccount dla istniejącego konta.
        self.assertEqual(GoogleAccount.objects.count(), 0)

    @patch('accounts.views.google_id_token.verify_oauth2_token')
    def test_access_token_authorizes_current_user_endpoint(self, verify_token):
        # Przygotowujemy poprawny wynik logowania Google.
        verify_token.return_value = self.google_payload()
        # Pobieramy lokalny access token z odpowiedzi endpointu logowania.
        login_response = self.client.post('/api/auth/google/', {'credential': 'test-token'}, format='json')
        # Dodajemy token Bearer do następnego requestu.
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        # Endpoint profilu powinien rozpoznać użytkownika z tokenu JWT.
        response = self.client.get('/api/auth/me/')

        # Poprawny token powinien dać odpowiedź 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Profil powinien należeć do właśnie zalogowanego użytkownika.
        self.assertEqual(response.data['user']['email'], 'student@example.com')
