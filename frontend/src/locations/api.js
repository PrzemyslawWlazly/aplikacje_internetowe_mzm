// Axios wykonuje requesty JSON do chronionych endpointów lokalizacji.
import axios from 'axios'

// Wspólny adres API zapewnia zgodność z mapą i modułem autoryzacji.
import { API_BASE_URL } from '../config'

// Helper buduje nagłówek Bearer wymagany przez JWTAuthentication w Django.
function authorizationConfig(accessToken) {
  // Token trafia wyłącznie do nagłówka Authorization, a nie do adresu URL.
  return {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  }
}

// Funkcja pobiera wszystkie lokalizacje należące do zalogowanego użytkownika.
export async function listSavedLocations(accessToken) {
  // Backend sam filtruje rekordy po użytkowniku zapisanym w tokenie.
  const response = await axios.get(
    `${API_BASE_URL}/locations/`,
    authorizationConfig(accessToken),
  )
  // Endpoint bez paginacji zwraca bezpośrednio tablicę lokalizacji.
  return response.data
}

// Funkcja tworzy nową lokalizację z danych formularza.
export async function createSavedLocation(accessToken, payload) {
  // Nagłówek JWT jest przekazywany jako trzeci argument requestu POST.
  const response = await axios.post(
    `${API_BASE_URL}/locations/`,
    payload,
    authorizationConfig(accessToken),
  )
  // Zwracamy rekord zapisany przez bazę wraz z jego identyfikatorem.
  return response.data
}

// Funkcja usuwa pojedynczą lokalizację użytkownika.
export async function deleteSavedLocation(accessToken, locationId) {
  // Backend zwróci 404, jeśli podany rekord należy do innego użytkownika.
  await axios.delete(
    `${API_BASE_URL}/locations/${locationId}/`,
    authorizationConfig(accessToken),
  )
}

// Funkcja pobiera aktualną pogodę z Redisa albo Open-Meteo.
export async function fetchSavedLocationWeather(accessToken, locationId) {
  // Odpowiedź zawiera snapshot, flagę cached oraz czas TTL.
  const response = await axios.get(
    `${API_BASE_URL}/locations/${locationId}/weather/`,
    authorizationConfig(accessToken),
  )
  // Komponent wykorzystuje zarówno pogodę, jak i informacje diagnostyczne cache.
  return response.data
}

// Funkcja pobiera maksymalnie sto najnowszych snapshotów lokalizacji.
export async function fetchSavedLocationWeatherHistory(accessToken, locationId) {
  // Historia jest chroniona tym samym JWT co pozostałe dane użytkownika.
  const response = await axios.get(
    `${API_BASE_URL}/locations/${locationId}/weather/history/`,
    authorizationConfig(accessToken),
  )
  // Zwracamy obiekt zawierający results, count i metadane lokalizacji.
  return response.data
}
