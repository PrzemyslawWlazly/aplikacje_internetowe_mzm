// Hooki Reacta obsługują formularz filtrów, request i wybrane dane tabeli.
import { useEffect, useState } from 'react'

// Funkcja API wykonuje filtrowane zapytanie do trwałych rekordów USGS.
import { fetchEarthquakeEvents } from './api'

// Funkcja formatuje czas zdarzenia w ustawieniach języka polskiego.
function formatDateTime(value) {
  // Brak czasu pokazujemy jako neutralną kreskę.
  if (!value) return '-'
  // Data i godzina są wystarczające dla tabeli analitycznej.
  return new Date(value).toLocaleString('pl-PL', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

// Funkcja wydobywa komunikat DRF albo błąd połączenia.
function requestErrorMessage(error) {
  // Pole detail jest standardowym komunikatem błędu backendu.
  return error.response?.data?.detail ?? error.message ?? 'Nie udało się pobrać zdarzeń.'
}

// Komponent przedstawia pełną tabelę i filtry opisane w specyfikacji projektu.
function SeismicEventsView({ defaultRangeHours, onShowOnMap }) {
  // Formularz startuje z preferencji użytkownika albo publicznego zakresu jednej doby.
  const [filters, setFilters] = useState({
    hours: defaultRangeHours ?? 24, // Zakres czasu jest wybierany z listy.
    minMagnitude: 2.5, // Domyślny próg ogranicza bardzo słabe zdarzenia.
    maxDepth: 1000, // Wartość 1000 oznacza praktycznie brak filtra głębokości.
    region: '', // Pusty tekst pokazuje cały świat.
  })
  // Wyniki pochodzą wyłącznie z endpointu PostgreSQL / USGS.
  const [events, setEvents] = useState([])
  // Loading blokuje wielokrotne wysłanie tego samego formularza.
  const [loading, setLoading] = useState(true)
  // Błąd pozostaje obok tabeli i nie zmienia pozostałych widoków.
  const [error, setError] = useState('')
  // Metadane pokazują faktyczny zakres zastosowany przez backend.
  const [metadata, setMetadata] = useState(null)

  // Funkcja pobiera wyniki dla bieżącego zestawu filtrów.
  async function loadEvents(nextFilters = filters) {
    // Czyścimy poprzedni błąd przed nową próbą.
    setError('')
    // Formularz i stan pusty informują o trwającym requeście.
    setLoading(true)

    try {
      // Backend wykonuje filtrowanie po indeksowanych polach w PostgreSQL.
      const data = await fetchEarthquakeEvents(nextFilters)
      // Zapisujemy maksymalnie dwieście wyników zwróconych przez endpoint.
      setEvents(data.results ?? [])
      // Metadane pomagają potwierdzić zastosowane parametry.
      setMetadata(data)
    } catch (requestError) {
      // Czytelny komunikat pozostaje nad tabelą.
      setError(requestErrorMessage(requestError))
    } finally {
      // Kończymy loading niezależnie od wyniku.
      setLoading(false)
    }
  }

  // Pierwsze wejście pobiera dane według zapisanej preferencji.
  useEffect(() => {
    // Budujemy początkowy obiekt jawnie, aby efekt nie zależał od późniejszych zmian formularza.
    const initialFilters = {
      hours: defaultRangeHours ?? 24,
      minMagnitude: 2.5,
      maxDepth: 1000,
      region: '',
    }
    // Zerowy timer przenosi aktualizacje stanu poza synchroniczną fazę efektu Reacta.
    const timerId = window.setTimeout(() => loadEvents(initialFilters), 0)
    // Cleanup usuwa zaplanowany start, jeśli użytkownik natychmiast opuści widok.
    return () => window.clearTimeout(timerId)
    // Zmiana preferencji użytkownika powinna przeładować domyślną tabelę.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultRangeHours])

  // Funkcja aktualizuje pojedyncze pole formularza.
  function updateFilter(event) {
    // Nazwa kontrolki odpowiada kluczowi stanu filtrów.
    const { name, value } = event.target
    // Pola liczbowe zamieniamy na Number, a region pozostawiamy tekstem.
    setFilters((currentFilters) => ({
      ...currentFilters,
      [name]: name === 'region' ? value : Number(value),
    }))
  }

  // Wysłanie formularza pobiera nowy zestaw danych.
  function submitFilters(event) {
    // Zatrzymujemy standardowe przeładowanie dokumentu HTML.
    event.preventDefault()
    // Request korzysta z aktualnego stanu kontrolek.
    loadEvents(filters)
  }

  // Renderujemy filtry, podsumowanie i semantyczną tabelę.
  return (
    <div className="seismic-workspace">
      {/* Formularz używa kontrolek odpowiednich dla ograniczonych zestawów wartości. */}
      <form className="seismic-filters" onSubmit={submitFilters}>
        <label>
          <span>Zakres czasu</span>
          <select name="hours" onChange={updateFilter} value={filters.hours}>
            <option value={1}>Ostatnia godzina</option>
            <option value={24}>24 godziny</option>
            <option value={168}>7 dni</option>
            <option value={720}>30 dni</option>
          </select>
        </label>
        <label>
          <span>Minimalna magnituda</span>
          <select name="minMagnitude" onChange={updateFilter} value={filters.minMagnitude}>
            <option value={0}>Wszystkie</option>
            <option value={2.5}>M 2.5+</option>
            <option value={4.5}>M 4.5+</option>
            <option value={6}>M 6.0+</option>
          </select>
        </label>
        <label>
          <span>Maksymalna głębokość</span>
          <select name="maxDepth" onChange={updateFilter} value={filters.maxDepth}>
            <option value={70}>Płytkie, do 70 km</option>
            <option value={300}>Do 300 km</option>
            <option value={1000}>Wszystkie</option>
          </select>
        </label>
        <label>
          <span>Region lub miejsce</span>
          <input
            name="region"
            onChange={updateFilter}
            placeholder="Np. Japan"
            type="search"
            value={filters.region}
          />
        </label>
        <button disabled={loading} type="submit">
          {loading ? 'Filtrowanie...' : 'Zastosuj filtry'}
        </button>
      </form>

      {/* Pasek podsumowania pokazuje wynik zapytania bez dodatkowej karty. */}
      <section className="seismic-summary" aria-label="Podsumowanie filtrów">
        <strong>{metadata?.count ?? events.length} zdarzeń</strong>
        <span>{metadata?.source ?? 'PostgreSQL / USGS'}</span>
        <span>Zakres: {metadata?.hours ?? filters.hours} h</span>
      </section>

      {/* Błąd nie usuwa ostatniej poprawnie pobranej tabeli. */}
      {error && <p className="dashboard-inline-error">{error}</p>}

      {/* Kontener umożliwia poziome przewijanie tabeli na telefonie. */}
      <div className="seismic-table-wrap">
        <table className="seismic-table">
          <thead>
            <tr>
              <th scope="col">Czas</th>
              <th scope="col">Miejsce</th>
              <th scope="col">Magnituda</th>
              <th scope="col">Głębokość</th>
              <th scope="col">Źródło</th>
              <th scope="col">Akcja</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{formatDateTime(event.event_time)}</td>
                <td title={event.place || event.title}>{event.place || event.title}</td>
                <td><strong>M {Number(event.magnitude).toFixed(1)}</strong></td>
                <td>{event.depth_km == null ? '-' : `${event.depth_km} km`}</td>
                <td>{event.source}</td>
                <td>
                  <button onClick={() => onShowOnMap(event, events)} type="button">Mapa</button>
                </td>
              </tr>
            ))}
            {!loading && !events.length && (
              <tr>
                <td className="seismic-empty-cell" colSpan={6}>Brak zdarzeń spełniających filtry.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Eksport domyślny pozwala leniwie załadować tabelę dopiero po wejściu w zakładkę.
export default SeismicEventsView
