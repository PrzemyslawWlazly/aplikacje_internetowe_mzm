// Stały klucz zapobiega literówkom przy odczycie i zapisie sesji w localStorage.
const AUTH_STORAGE_KEY = 'mzm-auth-session'

// Funkcja odczytuje poprzednią sesję po odświeżeniu karty przeglądarki.
export function readAuthSession() {
  try {
    // localStorage zwraca tekst albo null, gdy użytkownik jeszcze się nie logował.
    const storedValue = window.localStorage.getItem(AUTH_STORAGE_KEY)
    // Brak wartości oznacza po prostu brak aktywnej sesji.
    if (!storedValue) return null
    // Zamieniamy tekst JSON z powrotem na obiekt JavaScript.
    const session = JSON.parse(storedValue)
    // Do działania sesji wymagamy obu tokenów oraz danych użytkownika.
    if (!session.access || !session.refresh || !session.user) return null
    // Poprawnie zbudowany obiekt może zostać użyty przez komponent aplikacji.
    return session
  } catch {
    // Uszkodzony JSON nie powinien zablokować uruchomienia całej aplikacji.
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    // Zwracamy brak sesji, aby użytkownik mógł zalogować się ponownie.
    return null
  }
}

// Funkcja zapisuje tokeny i profil po udanym logowaniu albo odświeżeniu tokenu.
export function saveAuthSession(session) {
  // JSON.stringify zamienia obiekt na tekst obsługiwany przez localStorage.
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

// Funkcja usuwa wszystkie lokalne informacje sesji podczas wylogowania.
export function clearAuthSession() {
  // Usunięcie jednego klucza nie narusza innych ustawień aplikacji w przeglądarce.
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
}
