# Konfiguracja logowania Google

Projekt korzysta z Google Identity Services do potwierdzenia tożsamości użytkownika. Frontend odbiera token ID, backend sprawdza jego podpis i odbiorcę, a następnie wydaje własne tokeny JWT aplikacji.

## 1. Utworzenie projektu Google Cloud

1. Otwórz [tworzenie projektu Google Cloud](https://console.cloud.google.com/projectcreate).
2. Zaloguj się na konto Google.
3. Ustaw nazwę projektu, na przykład `Matka Ziemia Monitor`.
4. Kliknij `Create`.
5. Po utworzeniu projektu wybierz go w górnym selektorze Google Cloud.

## 2. Konfiguracja ekranu zgody

1. Otwórz [Google Auth Platform - Branding](https://console.cloud.google.com/auth/branding).
2. Jeśli pojawi się przycisk `Get started`, uruchom konfigurację.
3. Ustaw nazwę aplikacji `Matka Ziemia Monitor`.
4. Wybierz adres e-mail pomocy technicznej.
5. Podaj własny adres w sekcji danych kontaktowych dewelopera.
6. Na etapie lokalnym logo, domena produkcyjna, polityka prywatności i regulamin mogą pozostać nieuzupełnione, jeśli konsola na to pozwala.

## 3. Ustawienie odbiorców

1. Otwórz [Google Auth Platform - Audience](https://console.cloud.google.com/auth/audience).
2. Dla zwykłych kont Google wybierz typ `External`.
3. Podczas rozwoju pozostaw status `Testing`.
4. Jeżeli konsola pokazuje sekcję `Test users`, dodaj adresy Google osób testujących aplikację.
5. Dla samego Sign in with Google używamy wyłącznie danych profilu, e-maila i OpenID, bez wrażliwych uprawnień do Dysku, Gmaila lub Kalendarza.

## 4. Utworzenie Client ID

1. Otwórz [Google Auth Platform - Clients](https://console.cloud.google.com/auth/clients).
2. Kliknij `Create client`.
3. Jako `Application type` wybierz `Web application`.
4. Nazwij klienta, na przykład `Matka Ziemia Monitor - lokalnie`.
5. W `Authorized JavaScript origins` dodaj:

```text
http://localhost:5174
http://127.0.0.1:5174
```

6. Jeżeli frontend będzie uruchamiany także na standardowym porcie Vite, opcjonalnie dodaj:

```text
http://localhost:5173
http://127.0.0.1:5173
```

7. Pole `Authorized redirect URIs` pozostaw puste. Ta implementacja używa callbacku JavaScript, a nie przekierowania OAuth.
8. Kliknij `Create`.
9. Skopiuj wartość `Client ID` kończącą się na `.apps.googleusercontent.com`.
10. `Client secret` nie jest używany w tym przepływie i nie wolno umieszczać go we frontendzie.

## 5. Zapisanie Client ID w projekcie

Utwórz plik `/home/harry-potter/mzm/.env` i wpisz:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=TU_WKLEJ_CLIENT_ID.apps.googleusercontent.com
```

Utwórz plik `/home/harry-potter/mzm/frontend/.env.local` i wpisz:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api
VITE_GOOGLE_CLIENT_ID=TU_WKLEJ_CLIENT_ID.apps.googleusercontent.com
```

W obu miejscach musi znajdować się dokładnie ten sam Client ID.

## 6. Ponowne uruchomienie aplikacji

Po zmianie plików środowiskowych uruchom ponownie backend i frontend:

```bash
cd /home/harry-potter/mzm/backend
./.venv/bin/python manage.py runserver 0.0.0.0:8000
```

```bash
cd /home/harry-potter/mzm/frontend
npm run dev -- --host 0.0.0.0 --port 5174
```

Następnie otwórz [http://localhost:5174](http://localhost:5174), kliknij `Zaloguj` i wybierz konto Google.

## Dokumentacja Google

- [Konfiguracja Sign in with Google](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
- [Weryfikacja tokenu ID na backendzie](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [Zarządzanie odbiorcami i trybem testowym](https://support.google.com/cloud/answer/15549945)
