# ADR 004: Google Identity Services i lokalne JWT

## Status

Zaakceptowano.

## Data

2026-06-12

## Decyzja

Google Identity Services potwierdza tożsamość użytkownika, natomiast backend wydaje własny access token i refresh token JWT przez SimpleJWT. Konto Google jest wiązane z użytkownikiem Django przez stabilne pole `sub`.

## Kontekst

Aplikacja potrzebuje rozróżnienia użytkownika anonimowego, zalogowanego i administratora. Publiczna mapa powinna działać bez konta, ale lokalizacje i historia pogody muszą być prywatne. Frontend i backend działają na osobnych originach, więc token Bearer jest wygodnym kontraktem dla SPA.

## Rozważane alternatywy

- lokalna rejestracja e-mail i hasło,
- sesje Django z cookie,
- przesyłanie tokenu Google przy każdym requeście,
- zewnętrzna platforma uwierzytelniania przechowująca całą sesję.

## Uzasadnienie

Google ogranicza potrzebę przechowywania i resetowania haseł w projekcie studenckim. Backend nadal kontroluje czas życia sesji, uprawnienia i relacje w lokalnej bazie. Krótko żyjący access token ogranicza skutki jego przejęcia, a refresh token pozwala zachować wygodną sesję.

Pole `sub` jest używane jako identyfikator konta Google, ponieważ adres e-mail może się zmienić. Backend weryfikuje podpis, wystawcę, ważność, odbiorcę `aud` oraz `email_verified`.

## Trade-offy

- Pierwsze logowanie zależy od dostępności Google.
- Konfiguracja wymaga poprawnego Client ID i autoryzowanych originów.
- Tokeny są obecnie przechowywane w `localStorage`, co upraszcza SPA, ale zwiększa znaczenie ochrony przed XSS.
- Wylogowanie z aplikacji nie wylogowuje użytkownika z całego konta Google.
- Automatyczne połączenie istniejącego lokalnego konta tylko po e-mailu jest celowo zablokowane.

## Konsekwencje

Endpointy prywatne używają `IsAuthenticated`, a frontend automatycznie odnawia access token po odpowiedzi 401. W produkcji należy wymusić HTTPS, ograniczyć Content Security Policy i rozważyć refresh token w bezpiecznym cookie `HttpOnly`.
