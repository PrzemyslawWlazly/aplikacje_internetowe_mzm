# ADR 008: Smithsonian GVP jako źródło katalogu wulkanów i VEI

## Status

Zaakceptowano.

## Data

2026-06-13

## Decyzja

Warstwa wulkaniczna korzysta z oficjalnego `Web Feature Service` programu Smithsonian Global Volcanism Program. Aplikacja pobiera dwie warstwy:

- katalog wszystkich wulkanów holoceńskich,
- historię erupcji zawierającą między innymi `Volcanic Explosivity Index`.

Rekordy są łączone przez stabilne pole `Volcano_Number`. Model zapisuje `VEI` ostatniej znanej erupcji oraz najwyższe znane `VEI` w historii danego wulkanu.

## Kontekst

NASA EONET dobrze opisuje wybrane bieżące zdarzenia naturalne, ale nie jest pełnym naukowym katalogiem wulkanów i nie udostępnia systematycznie VEI. Użytkownik aplikacji powinien móc zobaczyć możliwie wiele prawdziwych wulkanów, również wtedy, gdy obecnie nie trwa przy nich raportowane zdarzenie.

VEI nie jest stałym parametrem wulkanu. Jest indeksem przypisanym konkretnej erupcji. Pokazanie jednej wartości bez wyjaśnienia mogłoby sugerować, że każdy wulkan ma niezmienną „siłę”.

## Rozważane alternatywy

- pozostawienie bieżących zdarzeń NASA EONET,
- ręczna lista najbardziej znanych wulkanów,
- nieoficjalny serwis komercyjny lub scraping stron HTML,
- przechowywanie każdej erupcji w osobnej lokalnej tabeli.

## Uzasadnienie

Smithsonian GVP jest źródłem pierwotnym i udostępnia dane przestrzenne w standardzie `WFS`. Warstwa wulkanów zawiera nazwę, numer, współrzędne, kraj, typ, wysokość i opis geologiczny. Warstwa erupcji pozwala policzyć ostatnie i maksymalne VEI bez zgadywania wartości.

Pełna lokalna kopia uproszczonego katalogu w PostgreSQL pozwala szybko narysować mapę bez wykonywania dużego requestu do Smithsonian przy każdym wejściu użytkownika. Dzienne zadanie Celery aktualizuje dane w tle.

## Trade-offy

- Synchronizacja pobiera większą paczkę niż wcześniejszy endpoint EONET.
- Część erupcji nie ma określonego VEI, dlatego interfejs musi pokazywać „brak danych”.
- Około 1200 ikon Leaflet jest cięższe niż kilkanaście aktywnych zdarzeń.
- Model przechowuje podsumowanie erupcji, a nie pełną relacyjną historię każdej erupcji.
- Smithsonian może zmienić schemat lub nazwę warstwy WFS, dlatego import posiada walidację kompletności odpowiedzi.

## Konsekwencje

Po poprawnej synchronizacji dawne rekordy demonstracyjne i rekordy wulkaniczne EONET są usuwane. Publiczny endpoint zwraca cały katalog i opcjonalnie filtruje go po kraju, regionie oraz minimalnym najwyższym VEI.

Źródło: [Smithsonian GVP Webservices](https://volcano.si.edu/database/webservices.cfm).
