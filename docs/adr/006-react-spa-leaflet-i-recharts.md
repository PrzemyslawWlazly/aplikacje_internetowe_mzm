# ADR 006: React SPA, Leaflet i Recharts

## Status

Zaakceptowano.

## Data

2026-06-12

## Decyzja

Interfejs jest aplikacją SPA zbudowaną w React i Vite. Dane geograficzne prezentuje React Leaflet, a historię pomiarów Recharts. Cięższy moduł lokalizacji i wykresów jest ładowany dynamicznie dopiero po wejściu w ten widok.

## Kontekst

Aplikacja łączy kilka interaktywnych warstw mapy, wybór markerów, prywatną listę lokalizacji, formularze oraz wykres historii. Zmiana warstwy lub wybranego punktu nie powinna przeładowywać całej strony.

Mapa jest głównym narzędziem eksploracji danych, a wykres ma pokazać trwałą historię pochodzącą z relacji w bazie danych.

## Rozważane alternatywy

- szablony Django i pełne przeładowania stron,
- Vue lub Svelte,
- Mapbox GL lub Google Maps,
- ręcznie rysowany wykres SVG,
- jedna duża paczka JavaScript bez dynamicznego importu.

## Uzasadnienie

React dobrze obsługuje stan wielu niezależnych źródeł danych oraz warunkowe widoki użytkownika. Leaflet jest wystarczający dla markerów punktowych, działa z otwartymi kafelkami OpenStreetMap i nie wymaga płatnego klucza mapowego. Recharts pasuje do prostego wykresu temperatury i jest już częścią stosu frontendu.

Dynamiczny import `LocationsView` pozostawia początkową paczkę mapy mniejszą i nie pobiera kodu wykresów użytkownikowi, który ogląda wyłącznie publiczne dane.

## Trade-offy

- SPA wymaga obsługi stanów loading, error i odnowienia tokenu po stronie klienta.
- Leaflet nie oferuje zaawansowanego renderowania wektorowego i analiz GIS.
- Recharts zwiększa rozmiar paczki modułu lokalizacji.
- Stan aplikacji jest obecnie zarządzany hookami Reacta bez osobnej biblioteki globalnego stanu.
- Otwarta mapa zależy od dostępności serwerów kafelków OpenStreetMap.

## Konsekwencje

Publiczna mapa i prywatny panel lokalizacji współdzielą listę zapisanych punktów. Markery użytkownika pojawiają się na warstwie pogodowej, a komenda „Mapa” przybliża widok do wskazanych współrzędnych.
