// Hooki Reacta obsługują formularz, wybór punktu i asynchroniczną historię.
import { useEffect, useMemo, useState } from 'react'
// Recharts wizualizuje temperaturę zapisaną w kolejnych snapshotach bazy danych.
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Funkcja API pobiera historię wybranego punktu przez chroniony endpoint.
import { fetchSavedLocationWeatherHistory } from './api'

// Pusty formularz jest stałą, aby po zapisie przywracać identyczny zestaw pól.
const EMPTY_FORM = {
  name: '', // Nazwa jest wymagana przez backend.
  latitude: '', // Szerokość przyjmujemy w stopniach dziesiętnych.
  longitude: '', // Długość przyjmujemy w stopniach dziesiętnych.
  country: '', // Kraj pozostaje opcjonalny.
  region: '', // Region pozostaje opcjonalny.
  description: '', // Notatka użytkownika pozostaje opcjonalna.
}

// Funkcja wydobywa czytelny komunikat z odpowiedzi DRF albo błędu sieciowego.
function requestErrorMessage(error) {
  // Pole detail jest standardowym komunikatem błędu w API projektu.
  if (error.response?.data?.detail) return error.response.data.detail
  // Błąd współrzędnych pochodzi z walidacji wielopolowej serializera.
  if (error.response?.data?.coordinates) return error.response.data.coordinates
  // Dla błędów pojedynczych pól łączymy pierwsze komunikaty w jeden tekst.
  if (error.response?.data && typeof error.response.data === 'object') {
    // Object.values pobiera komunikaty niezależnie od nazwy błędnego pola.
    const messages = Object.values(error.response.data).flat()
    // Zwracamy komunikaty rozdzielone spacją, jeśli backend je udostępnił.
    if (messages.length) return messages.join(' ')
  }
  // W przypadku błędu sieci pozostaje komunikat Axios.
  return error.message || 'Wystąpił nieznany błąd.'
}

// Funkcja formatuje czas pomiaru w polskiej strefie prezentacyjnej przeglądarki.
function formatMeasurementTime(value) {
  // Brak daty pokazujemy jako neutralną kreskę.
  if (!value) return '-'
  // Intl używa ustawień języka polskiego i lokalnej strefy urządzenia.
  return new Date(value).toLocaleString('pl-PL', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

// Komponent renderuje kompletny prywatny widok lokalizacji użytkownika.
function LocationsView({
  authSession,
  locations,
  locationsError,
  locationsLoading,
  onCreate,
  onDelete,
  onOpenLogin,
  onRefreshWeather,
  onShowOnMap,
  requestWithAuth,
  weatherPoints,
}) {
  // Formularz przechowuje tekst, aby użytkownik mógł swobodnie wpisywać liczby dziesiętne.
  const [form, setForm] = useState(EMPTY_FORM)
  // Id wybranej lokalizacji steruje panelem szczegółów i historią.
  const [selectedLocationId, setSelectedLocationId] = useState(null)
  // Historia pochodzi z relacji WeatherSnapshot dla wybranej lokalizacji.
  const [history, setHistory] = useState([])
  // Flaga informuje o pobieraniu historii bez blokowania całej listy.
  const [historyLoading, setHistoryLoading] = useState(false)
  // Osobny błąd historii nie przesłania formularza ani listy.
  const [historyError, setHistoryError] = useState('')
  // Action identyfikuje aktualnie wykonywaną operację i blokuje jej powtórzenie.
  const [action, setAction] = useState('')
  // Błąd formularza i akcji jest pokazywany w pobliżu kontrolek.
  const [actionError, setActionError] = useState('')
  // Tekst wyboru z mapy jest oddzielony od formularza, aby ręczna edycja nadal była możliwa.
  const [weatherPointChoice, setWeatherPointChoice] = useState('')

  // Punkty pogodowe sortujemy alfabetycznie i budujemy dla nich jednoznaczne etykiety podpowiedzi.
  const weatherPointOptions = useMemo(
    () => [...weatherPoints]
      .sort((first, second) => (
        `${first.name} ${first.country}`.localeCompare(`${second.name} ${second.country}`, 'pl')
      ))
      .map((point) => ({
        point, // Oryginalny obiekt zawiera współrzędne potrzebne formularzowi.
        value: `${point.name} — ${point.country || 'bez kraju'} (${Number(point.latitude).toFixed(4)}, ${Number(point.longitude).toFixed(4)})`,
      })),
    [weatherPoints],
  )

  // Jeśli użytkownik nie wybrał punktu albo usunął wybór, pokazujemy pierwszy dostępny rekord.
  const selectedLocation = useMemo(
    () => locations.find((location) => location.id === selectedLocationId) ?? locations[0] ?? null,
    [locations, selectedLocationId],
  )

  // Dane wykresu są odwrócone, aby czas płynął od lewej do prawej.
  const chartData = useMemo(
    () => [...history]
      .reverse()
      .map((snapshot) => ({
        time: new Date(snapshot.measured_at).toLocaleString('pl-PL', {
          day: '2-digit',
          month: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        }), // Skrócona etykieta mieści się na osi wykresu.
        temperature: Number(snapshot.temperature), // Recharts wymaga wartości liczbowej zamiast tekstu DecimalField.
      })),
    [history],
  )

  // Efekt pobiera historię zawsze po zmianie wybranej lokalizacji.
  useEffect(() => {
    // Bez zalogowania lub punktu nie wykonujemy prywatnego requestu.
    if (!authSession || !selectedLocation) {
      return undefined
    }
    // Flaga chroni stan po szybkim przełączeniu lokalizacji.
    let active = true

    // Funkcja asynchroniczna porządkuje loading, sukces i błąd historii.
    async function loadHistory() {
      // Czyścimy poprzedni błąd przed requestem.
      setHistoryError('')
      // Pokazujemy lokalny stan ładowania.
      setHistoryLoading(true)

      try {
        // requestWithAuth automatycznie odnawia access token po odpowiedzi 401.
        const data = await requestWithAuth(
          (accessToken) => fetchSavedLocationWeatherHistory(accessToken, selectedLocation.id),
        )
        // Aktualizujemy historię tylko dla nadal aktywnego efektu.
        if (active) setHistory(data.results ?? [])
      } catch (error) {
        // Czytelny błąd pozostaje w panelu historii.
        if (active) setHistoryError(requestErrorMessage(error))
      } finally {
        // Kończymy loading tylko dla aktywnego komponentu.
        if (active) setHistoryLoading(false)
      }
    }

    // Uruchamiamy request po ustaleniu wybranego punktu.
    loadHistory()

    // Cleanup wyłącza późne aktualizacje stanu.
    return () => {
      active = false
    }
  }, [authSession, requestWithAuth, selectedLocation])

  // Funkcja aktualizuje pojedyncze pole formularza po zmianie inputu.
  function updateField(event) {
    // name inputu odpowiada kluczowi obiektu formularza.
    const { name, value } = event.target
    // Zachowujemy pozostałe wartości i podmieniamy tylko edytowane pole.
    setForm((currentForm) => ({ ...currentForm, [name]: value }))
  }

  // Funkcja obsługuje wybór istniejącego punktu albo zwykłe wpisywanie tekstu w polu podpowiedzi.
  function chooseWeatherPoint(event) {
    // Aktualny tekst pozostaje widoczny również wtedy, gdy użytkownik nie wybrał gotowej opcji.
    const value = event.target.value
    // Zapisujemy tekst kontrolki datalist.
    setWeatherPointChoice(value)
    // Dokładne dopasowanie oznacza wybór jednej z lokalizacji mapy pogodowej.
    const selectedOption = weatherPointOptions.find((option) => option.value === value)
    // Niepełny wpis nie powinien nadpisywać ręcznie przygotowanego formularza.
    if (!selectedOption) return
    // Wyciągamy punkt po znalezieniu jednoznacznej etykiety.
    const { point } = selectedOption
    // Automatycznie uzupełniamy pola, które użytkownik nadal może później zmienić.
    setForm((currentForm) => ({
      ...currentForm, // Zachowujemy opis wpisany wcześniej przez użytkownika.
      name: point.name, // Nazwa odpowiada markerowi z mapy.
      latitude: Number(point.latitude).toFixed(6), // Dokładność pasuje do DecimalField backendu.
      longitude: Number(point.longitude).toFixed(6), // Długość otrzymuje ten sam format.
      country: point.country || '', // Brak kraju pozostaje pustym tekstem.
      region: '', // Globalne źródło nie udostępnia jednolitej informacji o regionie.
    }))
  }

  // Funkcja zapisuje lokalizację, a następnie pobiera dla niej pierwszy snapshot pogody.
  async function submitLocation(event) {
    // Blokujemy standardowe przeładowanie strony przez formularz HTML.
    event.preventDefault()
    // Czyścimy poprzedni błąd akcji.
    setActionError('')
    // Stan action blokuje wielokrotne wysłanie.
    setAction('create')

    try {
      // Rodzic wykonuje chroniony POST i aktualizuje wspólną listę markerów.
      const createdLocation = await onCreate(form)
      // Nowo utworzony punkt zostaje aktywnym wyborem.
      setSelectedLocationId(createdLocation.id)
      // Czyścimy formularz dopiero po poprawnym zapisie.
      setForm(EMPTY_FORM)
      // Czyścimy również nazwę wybranego punktu z mapy.
      setWeatherPointChoice('')
      // Pierwszy pomiar tworzy WeatherSnapshot i uzupełnia kartę lokalizacji.
      await onRefreshWeather(createdLocation.id)
    } catch (error) {
      // Komunikat backendu informuje między innymi o duplikacie współrzędnych.
      setActionError(requestErrorMessage(error))
    } finally {
      // Formularz zostaje odblokowany niezależnie od wyniku.
      setAction('')
    }
  }

  // Funkcja ręcznie odświeża pogodę i ponownie pobiera historię.
  async function refreshWeather(locationId) {
    // Czyścimy poprzedni błąd przed rozpoczęciem.
    setActionError('')
    // Id w stanie pozwala zablokować wyłącznie przycisk danego punktu.
    setAction(`weather-${locationId}`)

    try {
      // Rodzic pobiera pogodę i aktualizuje latest_weather na wspólnej liście.
      await onRefreshWeather(locationId)
      // Po sukcesie pobieramy historię ponownie, aby wykres uwzględniał ewentualny nowy snapshot.
      const data = await requestWithAuth(
        (accessToken) => fetchSavedLocationWeatherHistory(accessToken, locationId),
      )
      // Aktualizujemy wykres tylko dla aktualnie wybranej lokalizacji.
      if (selectedLocation?.id === locationId) setHistory(data.results ?? [])
    } catch (error) {
      // Awaria Open-Meteo albo Redisa jest pokazywana bez usuwania poprzednich danych.
      setActionError(requestErrorMessage(error))
    } finally {
      // Kończymy stan operacji.
      setAction('')
    }
  }

  // Funkcja usuwa punkt po potwierdzeniu użytkownika.
  async function removeLocation(location) {
    // Proste potwierdzenie chroni przed przypadkowym usunięciem historii kaskadowej.
    const confirmed = window.confirm(`Usunąć lokalizację „${location.name}” wraz z historią pogody?`)
    // Anulowanie nie wykonuje żadnego requestu.
    if (!confirmed) return
    // Czyścimy poprzedni błąd.
    setActionError('')
    // Stan zawiera id usuwanego punktu.
    setAction(`delete-${location.id}`)

    try {
      // Rodzic wykonuje DELETE i usuwa punkt ze wspólnej listy markerów.
      await onDelete(location.id)
      // Jeśli usunięto aktywny punkt, wybór wraca do pierwszego pozostałego elementu.
      if (selectedLocationId === location.id) setSelectedLocationId(null)
    } catch (error) {
      // Błąd uprawnień lub sieci pozostaje widoczny nad listą.
      setActionError(requestErrorMessage(error))
    } finally {
      // Odblokowujemy przyciski po zakończeniu requestu.
      setAction('')
    }
  }

  // Użytkownik anonimowy widzi jasną granicę między publiczną mapą i prywatnymi danymi.
  if (!authSession) {
    return (
      <section className="locations-auth-state">
        <span className="eyebrow">Prywatne lokalizacje</span>
        <h2>Zaloguj się, aby zapisywać obserwowane miejsca</h2>
        <p>Po zalogowaniu lokalizacje, pogoda i historia pomiarów będą przypisane wyłącznie do Twojego konta.</p>
        <button className="primary-action" onClick={onOpenLogin} type="button">Zaloguj przez Google</button>
      </section>
    )
  }

  // Zalogowany użytkownik otrzymuje formularz, listę oraz szczegóły relacyjnych danych.
  return (
    <section className="locations-workspace">
      {/* Formularz tworzy zasób SavedLocation przez chroniony endpoint POST. */}
      <form className="location-form" onSubmit={submitLocation}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Nowy punkt obserwacji</span>
            <h2>Dodaj lokalizację</h2>
          </div>
          <button className="primary-action" disabled={action === 'create'} type="submit">
            {action === 'create' ? 'Zapisywanie...' : 'Dodaj'}
          </button>
        </div>

        {/* Pola wymagane przez model znajdują się na początku formularza. */}
        <div className="location-form-grid">
          <label className="weather-point-picker">
            <span>Wybierz z punktów „Pogoda świat”</span>
            <input
              autoComplete="off"
              list="weather-point-options"
              onChange={chooseWeatherPoint}
              placeholder={weatherPointOptions.length ? 'Wpisz nazwę miasta lub wybierz podpowiedź' : 'Punkty pogodowe są jeszcze pobierane'}
              value={weatherPointChoice}
            />
            <datalist id="weather-point-options">
              {weatherPointOptions.map((option) => (
                <option key={option.value} value={option.value} />
              ))}
            </datalist>
          </label>
          <label>
            <span>Nazwa</span>
            <input
              maxLength="120"
              name="name"
              onChange={updateField}
              placeholder="Np. Kraków"
              required
              value={form.name}
            />
          </label>
          <label>
            <span>Szerokość geograficzna</span>
            <input
              max="90"
              min="-90"
              name="latitude"
              onChange={updateField}
              placeholder="50.0647"
              required
              step="0.000001"
              type="number"
              value={form.latitude}
            />
          </label>
          <label>
            <span>Długość geograficzna</span>
            <input
              max="180"
              min="-180"
              name="longitude"
              onChange={updateField}
              placeholder="19.9450"
              required
              step="0.000001"
              type="number"
              value={form.longitude}
            />
          </label>
          <label>
            <span>Kraj</span>
            <input
              maxLength="100"
              name="country"
              onChange={updateField}
              placeholder="Polska"
              value={form.country}
            />
          </label>
          <label>
            <span>Region</span>
            <input
              maxLength="120"
              name="region"
              onChange={updateField}
              placeholder="Małopolskie"
              value={form.region}
            />
          </label>
          <label className="location-description-field">
            <span>Opis</span>
            <input
              name="description"
              onChange={updateField}
              placeholder="Opcjonalna notatka"
              value={form.description}
            />
          </label>
        </div>
      </form>

      {/* Błędy listy i akcji są ogłaszane technologiom asystującym. */}
      <div aria-live="polite" className={actionError || locationsError ? 'locations-message error' : 'locations-message'}>
        {actionError || locationsError}
      </div>

      {/* Dolny układ rozdziela skanowalną listę i szczegóły wybranego punktu. */}
      <div className="locations-layout">
        <section className="saved-locations-list" aria-labelledby="saved-locations-title">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Twoje dane</span>
              <h2 id="saved-locations-title">Zapisane lokalizacje</h2>
            </div>
            <strong>{locations.length}</strong>
          </div>

          {/* Stan ładowania nie ukrywa formularza. */}
          {locationsLoading && <p className="locations-empty">Pobieranie lokalizacji...</p>}
          {/* Pusta lista zachęca do użycia formularza bez tekstu instruktażowego o interfejsie. */}
          {!locationsLoading && locations.length === 0 && (
            <p className="locations-empty">Nie masz jeszcze zapisanych lokalizacji.</p>
          )}

          {/* Każdy wiersz pokazuje nazwę, ostatnią pogodę oraz komendy. */}
          <div className="location-rows">
            {locations.map((location) => (
              <article
                className={selectedLocation?.id === location.id ? 'location-row selected' : 'location-row'}
                key={location.id}
              >
                <button
                  className="location-select-button"
                  onClick={() => setSelectedLocationId(location.id)}
                  type="button"
                >
                  <span>
                    <strong>{location.name}</strong>
                    <small>{[location.region, location.country].filter(Boolean).join(', ') || 'Bez regionu'}</small>
                  </span>
                  <span className="location-temperature">
                    {location.latest_weather ? `${location.latest_weather.temperature} °C` : 'Brak pomiaru'}
                  </span>
                </button>
                <div className="location-row-actions">
                  <button onClick={() => onShowOnMap(location)} type="button">Mapa</button>
                  <button
                    disabled={action === `weather-${location.id}`}
                    onClick={() => refreshWeather(location.id)}
                    type="button"
                  >
                    {action === `weather-${location.id}` ? 'Pobieranie...' : 'Pobierz pogodę'}
                  </button>
                  <button
                    className="danger-action"
                    disabled={action === `delete-${location.id}`}
                    onClick={() => removeLocation(location)}
                    type="button"
                  >
                    Usuń
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Panel szczegółów wykorzystuje ostatni snapshot z odpowiedzi listy. */}
        <section className="location-details" aria-labelledby="location-details-title">
          {!selectedLocation && <p className="locations-empty">Wybierz lub dodaj lokalizację.</p>}

          {selectedLocation && (
            <>
              <div className="section-heading">
                <div>
                  <span className="eyebrow">Szczegóły punktu</span>
                  <h2 id="location-details-title">{selectedLocation.name}</h2>
                </div>
                <span className="coordinates">
                  {Number(selectedLocation.latitude).toFixed(4)}, {Number(selectedLocation.longitude).toFixed(4)}
                </span>
              </div>

              {/* Metryki pogodowe pojawiają się po pierwszym poprawnym pobraniu. */}
              {selectedLocation.latest_weather ? (
                <div className="location-weather-grid">
                  <div>
                    <span>Temperatura</span>
                    <strong>{selectedLocation.latest_weather.temperature} °C</strong>
                  </div>
                  <div>
                    <span>Wilgotność</span>
                    <strong>{selectedLocation.latest_weather.humidity}%</strong>
                  </div>
                  <div>
                    <span>Wiatr</span>
                    <strong>{selectedLocation.latest_weather.wind_speed} km/h</strong>
                  </div>
                  <div>
                    <span>Zachmurzenie</span>
                    <strong>{selectedLocation.latest_weather.cloud_cover ?? '-'}%</strong>
                  </div>
                  <div>
                    <span>Ciśnienie</span>
                    <strong>{selectedLocation.latest_weather.pressure} hPa</strong>
                  </div>
                  <div>
                    <span>Warunki</span>
                    <strong>{selectedLocation.latest_weather.description}</strong>
                  </div>
                </div>
              ) : (
                <p className="locations-empty">Brak zapisanego pomiaru pogody.</p>
              )}

              {/* Historia pokazuje trwałe dane z PostgreSQL, a nie tylko bieżącą wartość z cache. */}
              <div className="history-heading">
                <div>
                  <span className="eyebrow">Historia pomiarów</span>
                  <strong>{history.length}</strong>
                </div>
                {selectedLocation.latest_weather && (
                  <small>Ostatni pomiar: {formatMeasurementTime(selectedLocation.latest_weather.measured_at)}</small>
                )}
              </div>

              {/* Wykres pojawia się dopiero, gdy istnieje co najmniej jeden snapshot. */}
              {historyLoading && <p className="locations-empty">Pobieranie historii...</p>}
              {!historyLoading && historyError && <p className="locations-message error">{historyError}</p>}
              {!historyLoading && !historyError && chartData.length > 0 && (
                <div className="weather-history-chart">
                  <ResponsiveContainer height="100%" width="100%">
                    <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 8, left: -12 }}>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                      <XAxis dataKey="time" minTickGap={28} stroke="#b9a6d3" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#b9a6d3" tick={{ fontSize: 11 }} unit="°" />
                      <Tooltip
                        contentStyle={{
                          background: '#1b0e2e',
                          border: '1px solid rgba(255,255,255,0.16)',
                          borderRadius: 8,
                        }}
                        formatter={(value) => [`${value} °C`, 'Temperatura']}
                      />
                      <Line
                        dataKey="temperature"
                        dot={{ fill: '#5eead4', r: 3 }}
                        isAnimationActive={false}
                        stroke="#5eead4"
                        strokeWidth={2}
                        type="monotone"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {!historyLoading && !historyError && chartData.length === 0 && (
                <p className="locations-empty">Historia pojawi się po pierwszym pobraniu pogody.</p>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}

// Eksport domyślny upraszcza osadzenie widoku w głównym komponencie aplikacji.
export default LocationsView
