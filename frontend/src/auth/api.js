// Axios upraszcza requesty JSON i udostępnia status odpowiedzi w przypadku błędu.
import axios from 'axios'

// Wspólna konfiguracja zapewnia jeden adres backendu dla wszystkich requestów autoryzacyjnych.
import { API_BASE_URL } from '../config'

// Funkcja przesyła token ID uzyskany z Google do naszego backendu.
export async function exchangeGoogleCredential(credential) {
  // Backend sprawdza podpis tokenu i zwraca własne tokeny JWT aplikacji.
  const response = await axios.post(`${API_BASE_URL}/auth/google/`, { credential })
  // Zwracamy sam obiekt danych, aby komponent nie zależał od szczegółów Axios.
  return response.data
}

// Funkcja sprawdza access token przez pobranie aktualnego profilu użytkownika.
export async function fetchCurrentUser(accessToken) {
  // Nagłówek Bearer jest standardowym sposobem przesłania JWT do Django REST Framework.
  const response = await axios.get(`${API_BASE_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  // Endpoint opakowuje dane profilu w pole user.
  return response.data.user
}

// Funkcja wymienia dłużej żyjący refresh token na nowy access token.
export async function refreshAccessToken(refreshToken) {
  // Refresh token wysyłamy wyłącznie do dedykowanego endpointu odświeżania.
  const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
    refresh: refreshToken,
  })
  // SimpleJWT zwraca nowy token dostępu w polu access.
  return response.data.access
}
