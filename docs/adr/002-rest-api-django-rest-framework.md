# ADR 002: REST API z Django REST Framework

## Status

Zaakceptowano.

## Data

2026-06-12

## Decyzja

Backend udostępnia zasoby aplikacji przez REST API zbudowane przy użyciu Django REST Framework. Publiczne dane środowiskowe oraz prywatne zasoby użytkownika otrzymują osobne endpointy HTTP, a kontrakt jest dokumentowany w OpenAPI przez drf-spectacular.

## Kontekst

Frontend React działa jako osobna aplikacja SPA i potrzebuje stabilnego kontraktu do pobierania map, obsługi logowania, zarządzania lokalizacjami oraz historii pogody. Projekt musi także pokazać co najmniej trzy zasoby powiązane relacjami i ochronę wybranych endpointów.

REST dobrze odwzorowuje operacje projektu:

- `GET/POST /api/locations/`,
- `DELETE /api/locations/{id}/`,
- `GET /api/locations/{id}/weather/`,
- `GET /api/locations/{id}/weather/history/`,
- publiczne endpointy pogody, sejsmiki i burz.

## Rozważane alternatywy

- GraphQL z jednym elastycznym endpointem,
- tRPC ze współdzielonym typowaniem TypeScript,
- klasyczne widoki i formularze Django bez osobnego API,
- ręczne widoki JSON bez Django REST Framework.

## Uzasadnienie

REST jest wystarczający, ponieważ zasoby i operacje są przewidywalne, a frontend nie potrzebuje wielu radykalnie różnych kształtów tych samych danych. Django REST Framework zapewnia serializery, walidację, statusy HTTP, klasy uprawnień i integrację z JWT. OpenAPI tworzy czytelną dokumentację przydatną podczas prezentacji projektu.

tRPC wymagałoby backendu TypeScript albo dodatkowej warstwy integracyjnej. GraphQL zwiększyłby koszt schematu, resolverów i ochrony przed zapytaniami N+1 bez wyraźnej korzyści dla obecnej skali aplikacji.

## Trade-offy

- Frontend i backend nie współdzielą typów automatycznie.
- Niektóre widoki wymagają kilku requestów, na przykład pobrania listy lokalizacji i historii wybranego punktu.
- Trzeba utrzymywać serializery odpowiedzi i dokumentację endpointów.
- REST może prowadzić do dedykowanych endpointów takich jak `weather/history`, ale ich znaczenie pozostaje jasne i łatwe do testowania.

## Konsekwencje

Każdy prywatny endpoint musi filtrować queryset po `request.user`. Walidacja danych wejściowych znajduje się w serializerach, a niestandardowe odpowiedzi pogodowe są opisane osobnymi serializerami OpenAPI.
