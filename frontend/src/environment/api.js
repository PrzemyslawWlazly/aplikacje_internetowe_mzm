// Axios wykonuje publiczne requesty list zdarzeń środowiskowych.
import axios from 'axios'

// Wspólny adres API zapobiega rozbieżnościom między mapą i tabelami.
import { API_BASE_URL } from '../config'

// Funkcja pobiera trzęsienia ziemi według filtrów obsługiwanych przez Django ORM.
export async function fetchEarthquakeEvents(filters) {
  // Parametry są kodowane przez Axios, więc tekst regionu nie wymaga ręcznego escapowania.
  const response = await axios.get(`${API_BASE_URL}/earthquakes/`, {
    params: {
      hours: filters.hours, // Zakres czasu wynosi od jednej godziny do trzydziestu dni.
      min_magnitude: filters.minMagnitude, // Minimalna magnituda ogranicza słabe zdarzenia.
      max_depth: filters.maxDepth, // Maksymalna głębokość pozwala wybrać zdarzenia płytkie.
      region: filters.region, // Fragment miejsca jest wyszukiwany bez rozróżniania wielkości liter.
    },
  })
  // Zwracamy pełną odpowiedź z wynikami oraz zastosowanymi filtrami.
  return response.data
}

// Funkcja pobiera pełny katalog wulkanów Smithsonian zapisany w PostgreSQL.
export async function fetchVolcanicEvents(filters = {}) {
  // Endpoint domyślnie zwraca wszystkie wulkany, a filtry pozostają opcjonalne.
  const response = await axios.get(`${API_BASE_URL}/volcanoes/events/`, {
    params: {
      region: filters.region ?? '', // Pusty region nie dodaje warunku do zapytania.
      country: filters.country ?? '', // Pusty kraj pozostawia katalog globalny.
      has_vei: filters.hasVei ?? false, // Prawda zwraca wszystkie wulkany z co najmniej jednym znanym VEI.
      min_vei: filters.minVei ?? 0, // Zero zachowuje również wulkany bez znanego VEI.
    },
  })
  // Frontend wykorzystuje listę, licznik i metadane źródła.
  return response.data
}
