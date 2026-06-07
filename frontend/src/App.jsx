// Importujemy hooki Reacta, bo komponent przechowuje dane z API i reaguje na zmianę warstwy.
import { useCallback, useEffect, useMemo, useState } from 'react'
// Importujemy Axios, żeby frontend wykonywał czytelne requesty HTTP do backendu.
import axios from 'axios'
// Importujemy komponenty React Leaflet, czyli prawdziwą bibliotekę mapową opartą o Leaflet.
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
// Importujemy Leaflet jako obiekt L, żeby tworzyć niestandardowe ikony obrazkowe.
import L from 'leaflet'
// Importujemy style Leafleta, bez których kafelki i kontrolki mapy nie wyglądają poprawnie.
import 'leaflet/dist/leaflet.css'
// Importujemy ikonę dla umiarkowanie ciepłej, słonecznej pogody.
import hotIconUrl from '../pictures/hot.svg'
// Importujemy ikonę dla cieplejszej, słonecznej pogody.
import veryHotIconUrl from '../pictures/very_hot.svg'
// Importujemy ikonę dla bardzo gorącej, słonecznej pogody.
import veryVeryHotIconUrl from '../pictures/very_very_hot.svg'
// Importujemy ikonę do wizualizacji zorganizowanych cyklonów tropikalnych.
import cycloneIconUrl from '../pictures/cyclone.svg'
// Importujemy ikonę do wizualizacji burz i potencjału burzowego.
import stormIconUrl from '../pictures/storm.svg'
// Importujemy lokalne style aplikacji.
import './App.css'
// Importujemy oficjalny przycisk Google Identity Services opakowany w komponent React.
import GoogleSignIn from './auth/GoogleSignIn'
// Importujemy requesty odpowiedzialne za logowanie, profil i odświeżanie lokalnego JWT.
import { exchangeGoogleCredential, fetchCurrentUser, refreshAccessToken } from './auth/api'
// Importujemy funkcje utrwalające sesję między odświeżeniami przeglądarki.
import { clearAuthSession, readAuthSession, saveAuthSession } from './auth/session'
// Importujemy wspólny adres API i publiczny identyfikator klienta Google.
import { API_BASE_URL, GOOGLE_CLIENT_ID } from './config'

// Definiujemy konfigurację mapy pogodowej ustawionej globalnie, bo pokazujemy stolice świata i miasta G20.
const WEATHER_VIEW = { center: [20, 10], zoom: 2 }

// Definiujemy konfigurację mapy sejsmicznej ustawionej na cały świat.
const SEISMIC_VIEW = { center: [20, 10], zoom: 2 }

// Definiujemy konfigurację mapy cyklonów.
const CYCLONE_VIEW = { center: [15, -35], zoom: 2 }

// Definiujemy konfigurację mapy burz/potencjału burzowego.
const STORM_VIEW = { center: [20, 10], zoom: 2 }

// Tworzymy ikonę Leaflet dla zakresu temperatur 15-20 stopni i małego zachmurzenia.
const hotWeatherIcon = L.icon({
  iconUrl: hotIconUrl, // Plik SVG z folderu pictures.
  iconSize: [102, 102], // Ikonę hot powiększamy 3 razy względem poprzedniego rozmiaru 34x34.
  iconAnchor: [51, 51], // Anchor zostaje w środku powiększonej ikony.
  popupAnchor: [0, -53], // Popup otwiera się nad dużą ikoną.
})

// Tworzymy ikonę Leaflet dla zakresu temperatur 20-25 stopni i małego zachmurzenia.
const veryHotWeatherIcon = L.icon({
  iconUrl: veryHotIconUrl, // Plik SVG z folderu pictures.
  iconSize: [114, 114], // Ikonę very_hot powiększamy 3 razy względem poprzedniego rozmiaru 38x38.
  iconAnchor: [57, 57], // Anchor pozostaje w środku większej ikony.
  popupAnchor: [0, -59], // Popup nie przykrywa powiększonego obrazka.
})

// Tworzymy ikonę Leaflet dla temperatur powyżej 25 stopni i małego zachmurzenia.
const veryVeryHotWeatherIcon = L.icon({
  iconUrl: veryVeryHotIconUrl, // Plik SVG z folderu pictures.
  iconSize: [35, 35], // Ikonę very_very_hot zmniejszamy 1.2 razy względem poprzedniego rozmiaru 42x42.
  iconAnchor: [17.5, 17.5], // Anchor zostaje w środku zmniejszonej ikony.
  popupAnchor: [0, -18], // Popup otwiera się nad mniejszą ikoną.
})

// Tworzymy ikonę Leaflet dla cyklonów tropikalnych.
const cycloneIcon = L.icon({
  iconUrl: cycloneIconUrl, // Plik SVG cyclone z folderu pictures.
  iconSize: [54, 54], // Cyklon jest większy, bo reprezentuje zorganizowany system.
  iconAnchor: [27, 27], // Środek ikony wskazuje pozycję zdarzenia.
  popupAnchor: [0, -29], // Popup otwiera się nad ikoną.
})

// Tworzymy ikonę Leaflet dla burz/potencjału burzowego.
const stormIcon = L.icon({
  iconUrl: stormIconUrl, // Plik SVG storm z folderu pictures.
  iconSize: [42, 42], // Burza jest czytelna, ale mniejsza od cyklonu.
  iconAnchor: [21, 21], // Środek ikony trafia w punkt pomiaru.
  popupAnchor: [0, -23], // Popup otwiera się nad ikoną.
})

// Opisujemy metadane trybów mapy, żeby UI nie miał rozproszonych tekstów.
const mapModes = {
  // Tryb pogodowy pobiera dane z endpointu Open-Meteo przez backend.
  weather: {
    label: 'Pogoda swiat',
    eyebrow: 'Mapa pogodowa',
    title: 'Globalna pogoda',
    subtitle: 'Stolice swiata, 7 najwiekszych miast panstw G20 oraz 20 najwiekszych miast Polski.',
  },
  // Tryb sejsmiczny pobiera dane z USGS przez backend.
  seismic: {
    label: 'Sejsmiczna swiat',
    eyebrow: 'Mapa sejsmiczna',
    title: 'Zdarzenia sejsmiczne',
    subtitle: 'Ostatnie trzesienia ziemi z USGS pokazane jako markery na mapie swiata.',
  },
  // Tryb cyklonów pokazuje zorganizowane systemy z NASA EONET.
  cyclones: {
    label: 'Cyklony',
    eyebrow: 'Cyklony tropikalne',
    title: 'Aktywne cyklony',
    subtitle: 'Zorganizowane systemy burzowe pobierane z NASA EONET.',
  },
  // Tryb burz pokazuje potencjał burzowy liczony z Open-Meteo.
  storms: {
    label: 'Burze',
    eyebrow: 'Potencjal burzowy',
    title: 'Najsilniejsze burze',
    subtitle: 'Punkty z wysokim potencjalem burzowym wedlug porywow wiatru, opadu i kodu pogody.',
  },
}

// Ten komponent zmienia widok mapy po przełączeniu między Polską i światem.
function MapViewController({ mode }) {
  // Pobieramy instancję mapy Leaflet z kontekstu React Leaflet.
  const map = useMap()

  // Po zmianie trybu przesuwamy mapę do odpowiedniego centrum i poziomu zoomu.
  useEffect(() => {
    // Wybieramy konfigurację widoku zależnie od aktywnej warstwy.
    const view = mode === 'weather'
      ? WEATHER_VIEW
      : mode === 'cyclones'
        ? CYCLONE_VIEW
        : mode === 'storms'
          ? STORM_VIEW
          : SEISMIC_VIEW
    // flyTo daje płynne przejście, więc użytkownik widzi zmianę zakresu mapy.
    map.flyTo(view.center, view.zoom, { duration: 0.8 })
  }, [map, mode])

  // Komponent sterujący mapą niczego nie renderuje w DOM.
  return null
}

// Funkcja zamienia temperaturę na kolor markera pogodowego.
function weatherColor(temperature) {
  // Brak temperatury pokazujemy neutralnym fioletem.
  if (temperature == null) return '#c4b5fd'
  // Chłodne punkty oznaczamy kolorem cyjanowym.
  if (temperature < 18) return '#67e8f9'
  // Umiarkowane punkty oznaczamy żółcią.
  if (temperature < 23) return '#facc15'
  // Ciepłe punkty oznaczamy różem.
  return '#fb7185'
}

// Funkcja wybiera ikonę obrazkową na podstawie temperatury i zachmurzenia.
function weatherPictureIcon(point) {
  // Zamieniamy temperaturę na liczbę, żeby porównania były jednoznaczne.
  const temperature = Number(point.temperature)
  // Zamieniamy zachmurzenie na liczbę procentową.
  const cloudCover = Number(point.cloud_cover)
  // Jeśli brakuje którejś wartości, nie używamy ikony obrazkowej.
  if (Number.isNaN(temperature) || Number.isNaN(cloudCover)) return null
  // Obrazki mają pojawiać się tylko przy małym zachmurzeniu.
  if (cloudCover >= 20) return null
  // Zakres [15, 20] oznacza temperaturę od 15 do 20 włącznie.
  if (temperature >= 15 && temperature <= 20) return hotWeatherIcon
  // Zakres [20, 25] interpretujemy jako powyżej 20 do 25 włącznie, żeby 20 nie wpadało w dwa warunki.
  if (temperature > 20 && temperature <= 25) return veryHotWeatherIcon
  // Temperatury powyżej 25 stopni dostają najmocniejszą ikonę.
  if (temperature > 25) return veryVeryHotWeatherIcon
  // Pozostałe przypadki wracają do standardowego markera kołowego.
  return null
}

// Komponent renderuje pojedynczy punkt pogodowy jako ikonę obrazkową albo marker kołowy.
function WeatherMarker({ point, onSelect }) {
  // Dla danego punktu próbujemy dobrać ikonę z folderu pictures.
  const pictureIcon = weatherPictureIcon(point)
  // Współrzędne Leafleta zapisujemy raz, żeby nie powtarzać tablicy.
  const position = [point.latitude, point.longitude]
  // Treść popupu jest wspólna dla markera obrazkowego i kołowego.
  const popup = (
    <Popup>
      <strong>{point.name}{point.country ? `, ${point.country}` : ''}</strong>
      <br />
      {point.temperature ?? '-'} C, wiatr {point.wind_speed ?? '-'} km/h, zachmurzenie {point.cloud_cover ?? '-'}%
    </Popup>
  )

  // Jeśli warunki temperatury i zachmurzenia pasują, renderujemy obrazek.
  if (pictureIcon) {
    return (
      <Marker
        eventHandlers={{ click: () => onSelect(point) }}
        icon={pictureIcon}
        position={position}
      >
        {popup}
      </Marker>
    )
  }

  // Jeśli warunki nie pasują, zostaje standardowy marker kołowy.
  return (
    <CircleMarker
      center={position}
      eventHandlers={{ click: () => onSelect(point) }}
      fillColor={weatherColor(point.temperature)}
      fillOpacity={0.88}
      pathOptions={{ color: '#ffffff', weight: 2 }}
      radius={point.group === 'poland_top_20' ? 8 : 6}
    >
      {popup}
    </CircleMarker>
  )
}

// Funkcja zamienia magnitudę na kolor markera sejsmicznego.
function seismicColor(magnitude) {
  // Brak magnitudy pokazujemy neutralnym fioletem.
  if (magnitude == null) return '#c4b5fd'
  // Słabsze zdarzenia są cyjanowe.
  if (magnitude < 4) return '#67e8f9'
  // Średnie zdarzenia są żółte.
  if (magnitude < 5) return '#facc15'
  // Silniejsze zdarzenia są różowe.
  return '#fb7185'
}

// Funkcja przelicza magnitudę na promień markera, żeby silniejsze zdarzenia były większe.
function seismicRadius(magnitude) {
  // Minimalny promień chroni małe zdarzenia przed zniknięciem.
  return Math.max(7, Math.min(22, Number(magnitude || 0) * 3.2))
}

// Główny komponent aplikacji renderuje panel, statystyki i mapę.
function App() {
  // Sesję inicjalizujemy danymi z localStorage, aby profil nie znikał podczas odświeżenia strony.
  const [authSession, setAuthSession] = useState(() => readAuthSession())
  // Ten stan steruje widocznością okna logowania.
  const [authDialogOpen, setAuthDialogOpen] = useState(false)
  // Flaga blokuje ponowne kliknięcie przycisku podczas wymiany tokenu z backendem.
  const [authLoading, setAuthLoading] = useState(false)
  // Osobny komunikat błędu nie miesza problemów logowania z błędami danych pogodowych.
  const [authError, setAuthError] = useState('')
  // Aktywny tryb decyduje, czy pokazujemy pogodę w Polsce, czy sejsmikę świata.
  const [activeMode, setActiveMode] = useState('weather')
  // Stan z danymi pogodowymi pochodzi z endpointu /api/weather/current/.
  const [weatherPoints, setWeatherPoints] = useState([])
  // Stan ze zdarzeniami sejsmicznymi pochodzi z endpointu /api/earthquakes/.
  const [earthquakes, setEarthquakes] = useState([])
  // Stan z cyklonami pochodzi z endpointu /api/storms/active/.
  const [cyclones, setCyclones] = useState([])
  // Stan z burzami/potencjałem burzowym także pochodzi z endpointu /api/storms/active/.
  const [storms, setStorms] = useState([])
  // Ten stan mówi, czy warstwa burz/cyklonów została już pobrana chociaż raz.
  const [stormLayersLoaded, setStormLayersLoaded] = useState(false)
  // Ten stan mówi, czy aktualnie trwa pobieranie warstwy burz/cyklonów.
  const [stormLayersLoading, setStormLayersLoading] = useState(false)
  // Ten stan trzyma błąd tylko dla warstw burz/cyklonów.
  const [stormLayersError, setStormLayersError] = useState('')
  // Osobny stan przechowuje wybrany punkt pogodowy.
  const [selectedWeather, setSelectedWeather] = useState(null)
  // Osobny stan przechowuje wybrane trzęsienie ziemi.
  const [selectedEarthquake, setSelectedEarthquake] = useState(null)
  // Osobny stan przechowuje wybrany cyklon.
  const [selectedCyclone, setSelectedCyclone] = useState(null)
  // Osobny stan przechowuje wybraną burzę.
  const [selectedStorm, setSelectedStorm] = useState(null)
  // Loading mówi użytkownikowi, że frontend czeka na backend.
  const [loading, setLoading] = useState(true)
  // Error przechowuje komunikat, gdy backend albo API zewnętrzne nie odpowie.
  const [error, setError] = useState('')

  // Efekt sprawdza zapisaną sesję i w razie potrzeby odnawia wygasły access token.
  useEffect(() => {
    // Bez zapisanej sesji nie wykonujemy żadnego requestu autoryzacyjnego.
    if (!authSession) return undefined
    // Flaga chroni przed aktualizacją stanu po odmontowaniu komponentu.
    let active = true

    // Funkcja próbuje potwierdzić profil aktualnym access tokenem.
    async function restoreSession() {
      try {
        // Poprawny token zwraca aktualne dane użytkownika z backendu.
        const user = await fetchCurrentUser(authSession.access)
        // Aktualizujemy profil tylko wtedy, gdy komponent nadal istnieje.
        if (active) {
          const verifiedSession = { ...authSession, user }
          setAuthSession(verifiedSession)
          saveAuthSession(verifiedSession)
        }
      } catch (profileError) {
        // Odświeżanie ma sens wyłącznie dla błędu 401 i dostępnego refresh tokenu.
        if (profileError.response?.status === 401 && authSession.refresh) {
          try {
            // Backend wymienia refresh token na nowy access token.
            const access = await refreshAccessToken(authSession.refresh)
            // Nowy access token powinien ponownie umożliwić pobranie profilu.
            const user = await fetchCurrentUser(access)
            // Zapisujemy odnowioną sesję w stanie i localStorage.
            if (active) {
              const refreshedSession = { ...authSession, access, user }
              setAuthSession(refreshedSession)
              saveAuthSession(refreshedSession)
            }
            // Po udanym odświeżeniu kończymy obsługę błędu.
            return
          } catch {
            // Nieudany refresh oznacza, że użytkownik powinien zalogować się ponownie.
          }
        }
        // Błąd profilu albo refreshu unieważnia lokalną kopię sesji.
        if (active) {
          clearAuthSession()
          setAuthSession(null)
        }
      }
    }

    // Uruchamiamy sprawdzenie sesji po pierwszym renderze.
    restoreSession()

    // Cleanup wyłącza późne aktualizacje stanu.
    return () => {
      active = false
    }
    // Efekt celowo działa tylko dla sesji wczytanej przy starcie, a nie po każdym odnowieniu tokenu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Callback wymienia token ID Google na lokalną sesję JWT.
  const handleGoogleCredential = useCallback(async (credential) => {
    // Czyścimy poprzedni błąd przed nową próbą logowania.
    setAuthError('')
    // Blokujemy przycisk do zakończenia requestu.
    setAuthLoading(true)

    try {
      // Backend weryfikuje token Google i zwraca własne tokeny oraz profil.
      const session = await exchangeGoogleCredential(credential)
      // Zapisujemy sesję, aby przetrwała odświeżenie strony.
      saveAuthSession(session)
      // Aktualizujemy nagłówek aplikacji danymi zalogowanego użytkownika.
      setAuthSession(session)
      // Zamykamy modal dopiero po pełnym sukcesie requestu.
      setAuthDialogOpen(false)
    } catch (loginError) {
      // Preferujemy komunikat backendu, a przy błędzie sieci pokazujemy komunikat Axios.
      const detail = loginError.response?.data?.detail ?? loginError.message
      // Błąd pozostaje w modalu, aby użytkownik mógł spróbować ponownie.
      setAuthError(`Nie udało się zalogować: ${detail}`)
    } finally {
      // Odblokowujemy kontrolkę niezależnie od wyniku requestu.
      setAuthLoading(false)
    }
  }, [])

  // Callback otrzymuje błędy skryptu Google z komponentu przycisku.
  const handleGoogleError = useCallback((message) => {
    // Zachowujemy jeden czytelny komunikat w oknie logowania.
    setAuthError(message)
  }, [])

  // Funkcja usuwa lokalne tokeny i wyłącza automatyczny wybór konta Google.
  function logout() {
    // Czyścimy trwałą kopię sesji w przeglądarce.
    clearAuthSession()
    // Czyścimy stan Reacta, aby natychmiast pokazać przycisk logowania.
    setAuthSession(null)
    // Google nie powinno automatycznie wybierać poprzedniego konta po świadomym wylogowaniu.
    window.google?.accounts?.id?.disableAutoSelect()
  }

  // Efekt startowy pobiera prawdziwe dane z backendu po pierwszym renderze.
  useEffect(() => {
    // Flaga mounted chroni przed ustawianiem stanu po odmontowaniu komponentu.
    let mounted = true

    // Funkcja async porządkuje pobieranie kilku endpointów naraz.
    async function loadEnvironmentalData() {
      // Czyścimy poprzedni błąd przed nową próbą pobrania danych.
      setError('')
      // Ustawiamy loading, żeby UI pokazał aktualny stan requestu.
      setLoading(true)

      try {
        // Pobieramy tylko podstawowe warstwy startowe, żeby nie przekroczyć limitów API na wejściu.
        const [weatherResponse, earthquakeResponse] = await Promise.allSettled([
          axios.get(`${API_BASE_URL}/weather/current/`),
          axios.get(`${API_BASE_URL}/earthquakes/`, {
            params: { hours: 24, min_magnitude: 2.5 },
          }),
        ])

        // Jeśli komponent nadal istnieje, zapisujemy dane pogodowe do stanu.
        if (mounted) {
          // Backend zwraca listę pogodową w polu results, jeśli request się udał.
          const nextWeather = weatherResponse.status === 'fulfilled' ? weatherResponse.value.data.results ?? [] : []
          // Backend zwraca trzęsienia ziemi w polu results, jeśli request się udał.
          const nextEarthquakes = earthquakeResponse.status === 'fulfilled' ? earthquakeResponse.value.data.results ?? [] : []
          // Zbieramy błędy poszczególnych warstw zamiast przerywać cały ekran.
          const layerErrors = [
            weatherResponse.status === 'rejected' ? `Pogoda: ${weatherResponse.reason.response?.data?.detail ?? weatherResponse.reason.message}` : '',
            earthquakeResponse.status === 'rejected' ? `Sejsmika: ${earthquakeResponse.reason.response?.data?.detail ?? earthquakeResponse.reason.message}` : '',
          ].filter(Boolean)
          // Aktualizujemy punkty pogodowe.
          setWeatherPoints(nextWeather)
          // Aktualizujemy zdarzenia sejsmiczne.
          setEarthquakes(nextEarthquakes)
          // Domyślnie zaznaczamy Warszawę, a gdy jej nie ma, pierwszy punkt z listy.
          setSelectedWeather(nextWeather.find((point) => point.name === 'Warszawa') ?? nextWeather[0] ?? null)
          // Domyślnie zaznaczamy najnowsze zdarzenie z USGS.
          setSelectedEarthquake(nextEarthquakes[0] ?? null)
          // Jeśli część warstw padła, pokazujemy krótką informację, ale zostawiamy dane z warstw działających.
          setError(layerErrors.join(' | '))
        }
      } catch (requestError) {
        // Jeśli request się nie uda, zapisujemy czytelny komunikat dla użytkownika.
        if (mounted) {
          // Axios może mieć odpowiedź backendu albo tylko komunikat błędu sieciowego.
          const detail = requestError.response?.data?.detail ?? requestError.message
          // Komunikat pojawia się w panelu statusu i nie wywraca całego UI.
          setError(`Nie udalo sie pobrac danych: ${detail}`)
        }
      } finally {
        // Po sukcesie albo błędzie kończymy stan ładowania.
        if (mounted) setLoading(false)
      }
    }

    // Uruchamiamy pobieranie danych.
    loadEnvironmentalData()

    // Cleanup ustawia flagę, gdy komponent znika.
    return () => {
      // Dzięki temu unikamy ostrzeżeń Reacta przy wolnym requestcie.
      mounted = false
    }
  }, [])

  // Wybrany rekord zależy od aktywnej warstwy.
  const selected = activeMode === 'weather'
    ? selectedWeather
    : activeMode === 'cyclones'
      ? selectedCyclone
      : activeMode === 'storms'
        ? selectedStorm
        : selectedEarthquake

  // Dane listy zależą od aktywnej warstwy.
  const items = activeMode === 'weather'
    ? weatherPoints
    : activeMode === 'cyclones'
      ? cyclones
      : activeMode === 'storms'
        ? storms
        : earthquakes

  // Metadane tekstowe aktywnego trybu pobieramy z konfiguracji.
  const mode = mapModes[activeMode]

  // Statystyki liczymy na podstawie prawdziwych danych pobranych z API.
  const stats = useMemo(() => {
    // Dla pogody pokazujemy średnią temperaturę, liczbę punktów i odświeżanie cache.
    if (activeMode === 'weather') {
      // Filtrujemy wartości null, żeby średnia nie była przekłamana.
      const temperatures = weatherPoints.map((point) => point.temperature).filter((value) => value != null)
      // Liczymy średnią tylko wtedy, gdy mamy przynajmniej jeden pomiar.
      const avgTemp = temperatures.length
        ? Math.round(temperatures.reduce((sum, value) => sum + value, 0) / temperatures.length)
        : null
      // Zwracamy karty statystyk dla widoku pogodowego.
      return [
        { label: 'Srednia temp.', value: avgTemp == null ? '-' : `${avgTemp} C` },
        { label: 'Punkty mapy', value: weatherPoints.length },
        { label: 'Cache backendu', value: '15 min' },
      ]
    }

    // Dla cyklonów pokazujemy liczbę aktywnych zdarzeń z EONET.
    if (activeMode === 'cyclones') {
      return [
        { label: 'Aktywne cyklony', value: cyclones.length },
        { label: 'Zrodlo', value: 'EONET' },
        { label: 'Status', value: 'open' },
      ]
    }

    // Dla burz pokazujemy liczbę punktów i najwyższy wynik burzowy.
    if (activeMode === 'storms') {
      const scores = storms.map((storm) => storm.storm_score).filter((value) => value != null)
      const maxScore = scores.length ? Math.max(...scores) : null
      return [
        { label: 'Punkty burzowe', value: storms.length },
        { label: 'Najwyzszy score', value: maxScore == null ? '-' : maxScore.toFixed(1) },
        { label: 'Zrodlo', value: 'Open-Meteo' },
      ]
    }

    // Dla sejsmiki wyliczamy największą magnitudę z aktualnej listy.
    const magnitudes = earthquakes.map((event) => event.magnitude).filter((value) => value != null)
    // Gdy lista jest pusta, pokazujemy kreskę zamiast błędnej liczby.
    const maxMagnitude = magnitudes.length ? Math.max(...magnitudes) : null
    // Zwracamy karty statystyk dla widoku sejsmicznego.
    return [
      { label: 'Zdarzenia', value: earthquakes.length },
      { label: 'Najwieksza M', value: maxMagnitude == null ? '-' : maxMagnitude.toFixed(1) },
      { label: 'Zakres', value: '24 h' },
    ]
  }, [activeMode, cyclones, earthquakes, storms, weatherPoints])

  // Funkcja pobiera warstwy cyklonów i burz dopiero wtedy, gdy użytkownik ich potrzebuje.
  async function loadStormLayers() {
    // Ustawiamy flagę ładowania tylko dla warstw burzowych.
    setStormLayersLoading(true)
    // Czyścimy poprzedni błąd burzowy przed nowym requestem.
    setStormLayersError('')

    try {
      // Pobieramy jeden endpoint, który zwraca dwie listy: cyclones i storms.
      const stormsResponse = await axios.get(`${API_BASE_URL}/storms/active/`)
      // Z odpowiedzi wyciągamy cyklony z NASA EONET.
      const nextCyclones = stormsResponse.data.cyclones ?? []
      // Z odpowiedzi wyciągamy punkty burzowe z Open-Meteo.
      const nextStorms = stormsResponse.data.storms ?? []
      // Zapisujemy cyklony do stanu mapy.
      setCyclones(nextCyclones)
      // Zapisujemy burze do stanu mapy.
      setStorms(nextStorms)
      // Zapamiętujemy, że ta warstwa była już pobrana.
      setStormLayersLoaded(true)
      // Ustawiamy domyślnie pierwszy cyklon, jeśli istnieje.
      setSelectedCyclone(nextCyclones[0] ?? null)
      // Ustawiamy domyślnie najsilniejszy punkt burzowy, jeśli istnieje.
      setSelectedStorm(nextStorms[0] ?? null)
      // Jeśli backend zwrócił ostrzeżenia źródeł, pokazujemy je bez kasowania danych.
      setStormLayersError((stormsResponse.data.source_errors ?? []).join(' | '))
    } catch (requestError) {
      // Wyciągamy czytelny komunikat z odpowiedzi backendu albo z błędu sieciowego.
      const detail = requestError.response?.data?.detail ?? requestError.message
      // Zapisujemy błąd tylko dla warstw burzowych.
      setStormLayersError(`Burze/cyklony: ${detail}`)
    } finally {
      // Kończymy stan ładowania niezależnie od wyniku.
      setStormLayersLoading(false)
    }
  }

  // Funkcja zmienia warstwę i zostawia wybór w odpowiednim stanie domenowym.
  function changeMode(nextMode) {
    // Ustawiamy aktywny tryb mapy.
    setActiveMode(nextMode)
    // Przy przejściu na pogodę wybieramy istniejący punkt albo pierwszy wynik.
    if (nextMode === 'weather' && !selectedWeather) setSelectedWeather(weatherPoints[0] ?? null)
    // Przy przejściu na sejsmikę wybieramy istniejące zdarzenie albo pierwszy wynik.
    if (nextMode === 'seismic' && !selectedEarthquake) setSelectedEarthquake(earthquakes[0] ?? null)
    // Warstwy burzowe pobieramy dopiero po kliknięciu, żeby nie obciążać Open-Meteo na starcie.
    if ((nextMode === 'cyclones' || nextMode === 'storms') && !stormLayersLoaded && !stormLayersLoading) {
      loadStormLayers()
    }
    // Przy przejściu na cyklony wybieramy pierwszy aktywny system.
    if (nextMode === 'cyclones' && !selectedCyclone) setSelectedCyclone(cyclones[0] ?? null)
    // Przy przejściu na burze wybieramy najsilniejszy punkt burzowy.
    if (nextMode === 'storms' && !selectedStorm) setSelectedStorm(storms[0] ?? null)
  }

  // Renderujemy kompletny ekran aplikacji.
  return (
    <main className="app-shell">
      {/* Panel boczny trzyma nawigację i wybór warstwy mapy. */}
      <aside className="sidebar" aria-label="Panel nawigacji">
        {/* Brand mówi użytkownikowi, w jakiej aplikacji się znajduje. */}
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">MZ</span>
          <div>
            <strong>Matka Ziemia</strong>
            <span>Monitor</span>
          </div>
        </div>

        {/* Nawigacja jest szkicem przyszłych widoków aplikacji. */}
        <nav className="nav-list" aria-label="Glowne widoki">
          <button className="nav-item active" type="button">Mapa</button>
          <button className="nav-item" type="button">Dashboard</button>
          <button className="nav-item" type="button">Lokalizacje</button>
          <button className="nav-item" type="button">Synchronizacja</button>
        </nav>

        {/* Panel warstw pozwala przełączać mapę pogodową i sejsmiczną. */}
        <section className="layer-panel" aria-labelledby="layer-title">
          <h2 id="layer-title">Warstwa</h2>
          <div className="segmented-control">
            {Object.entries(mapModes).map(([key, item]) => (
              <button
                className={activeMode === key ? 'selected' : ''}
                key={key}
                onClick={() => changeMode(key)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>

        {/* Status pokazuje, czy frontend ma dane z backendu. */}
        <section className="sync-card" aria-label="Status danych">
          <span>Status danych</span>
          <strong>{loading || stormLayersLoading ? 'Pobieranie...' : error || stormLayersError ? 'Czesciowy blad' : 'Dane z API'}</strong>
          <small>{stormLayersError || error || `Backend: ${API_BASE_URL}`}</small>
        </section>
      </aside>

      {/* Główna przestrzeń robocza zawiera opis, statystyki, mapę i panel szczegółów. */}
      <section className="workspace">
        {/* Nagłówek zmienia się zależnie od aktywnej warstwy. */}
        <header className="topbar">
          <div>
            <span className="eyebrow">{mode.eyebrow}</span>
            <h1>{mode.title}</h1>
            <p>{mode.subtitle}</p>
          </div>
          {/* Prawa część nagłówka pokazuje logowanie albo profil aktywnego użytkownika. */}
          <div className="profile-actions">
            {authSession ? (
              <>
                {/* Profil używa zdjęcia Google, a przy jego braku pokazuje inicjał. */}
                <div className="profile-summary" title={authSession.user.email}>
                  {authSession.user.picture_url ? (
                    <img alt="" src={authSession.user.picture_url} />
                  ) : (
                    <span aria-hidden="true">{(authSession.user.first_name || authSession.user.email)[0]?.toUpperCase()}</span>
                  )}
                  <strong>{authSession.user.first_name || authSession.user.email}</strong>
                </div>
                {/* Wylogowanie usuwa tokeny tylko z tej aplikacji, bez wylogowywania całego konta Google. */}
                <button className="logout-button" onClick={logout} type="button">Wyloguj</button>
              </>
            ) : (
              /* Niezalogowany użytkownik może otworzyć modal z oficjalnym przyciskiem Google. */
              <button
                className="profile-button"
                onClick={() => {
                  setAuthError('')
                  setAuthDialogOpen(true)
                }}
                type="button"
              >
                Zaloguj
              </button>
            )}
          </div>
        </header>

        {/* Karty pokazują szybkie podsumowanie aktualnej warstwy. */}
        <section className="stats-grid" aria-label="Podsumowanie">
          {stats.map((stat) => (
            <article className="stat-card" key={stat.label}>
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
            </article>
          ))}
        </section>

        {/* Layout mapy trzyma prawdziwą mapę oraz panel szczegółów. */}
        <section className="map-layout">
          {/* Kontener mapy ma stałą wysokość, żeby Leaflet mógł poprawnie policzyć rozmiar. */}
          <div className="map-surface">
            <MapContainer
              center={activeMode === 'weather' ? WEATHER_VIEW.center : SEISMIC_VIEW.center}
              className="leaflet-map"
              scrollWheelZoom
              zoom={activeMode === 'weather' ? WEATHER_VIEW.zoom : SEISMIC_VIEW.zoom}
            >
              {/* Kontroler przesuwa mapę po zmianie trybu. */}
              <MapViewController mode={activeMode} />

              {/* TileLayer pobiera prawdziwe kafelki mapy z OpenStreetMap. */}
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* Markery pogodowe pokazują punkty z Open-Meteo i czasem używają ikon z folderu pictures. */}
              {activeMode === 'weather' && weatherPoints.map((point) => (
                <WeatherMarker
                  key={`${point.group}-${point.country}-${point.name}-${point.latitude}-${point.longitude}`}
                  onSelect={setSelectedWeather}
                  point={point}
                />
              ))}

              {/* Markery sejsmiczne pokazują zdarzenia z USGS na mapie świata. */}
              {activeMode === 'seismic' && earthquakes.map((event) => (
                <CircleMarker
                  center={[event.latitude, event.longitude]}
                  eventHandlers={{ click: () => setSelectedEarthquake(event) }}
                  fillColor={seismicColor(event.magnitude)}
                  fillOpacity={0.84}
                  key={event.external_id}
                  pathOptions={{ color: '#ffffff', weight: 2 }}
                  radius={seismicRadius(event.magnitude)}
                >
                  <Popup>
                    <strong>{event.place}</strong>
                    <br />
                    Magnituda {event.magnitude ?? '-'}, glebokosc {event.depth_km ?? '-'} km
                  </Popup>
                </CircleMarker>
              ))}

              {/* Markery cyklonów używają ikony cyclone z folderu pictures. */}
              {activeMode === 'cyclones' && cyclones.map((event) => (
                <Marker
                  eventHandlers={{ click: () => setSelectedCyclone(event) }}
                  icon={cycloneIcon}
                  key={event.external_id}
                  position={[event.latitude, event.longitude]}
                >
                  <Popup>
                    <strong>{event.name}</strong>
                    <br />
                    Zrodlo: {event.source}
                  </Popup>
                </Marker>
              ))}

              {/* Markery burz używają ikony storm z folderu pictures. */}
              {activeMode === 'storms' && storms.map((event) => (
                <Marker
                  eventHandlers={{ click: () => setSelectedStorm(event) }}
                  icon={stormIcon}
                  key={event.external_id}
                  position={[event.latitude, event.longitude]}
                >
                  <Popup>
                    <strong>{event.name}{event.country ? `, ${event.country}` : ''}</strong>
                    <br />
                    Score {event.storm_score}, porywy {event.wind_gusts ?? '-'} km/h
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>

          {/* Panel szczegółów pokazuje wybrany punkt z aktywnej warstwy. */}
          <aside className="details-panel" aria-label="Szczegoly zaznaczenia">
            <span className="eyebrow">Zaznaczone</span>

            {/* Gdy trwa ładowanie, panel nie udaje, że ma gotowe dane. */}
            {loading && <p className="panel-note">Pobieranie danych z backendu...</p>}

            {/* Gdy użytkownik pierwszy raz wybierze burze lub cyklony, pobieramy tę warstwę osobno. */}
            {stormLayersLoading && (activeMode === 'cyclones' || activeMode === 'storms') && (
              <p className="panel-note">Pobieranie warstwy burzowej...</p>
            )}

            {/* Gdy wystąpi błąd, pokazujemy go w miejscu szczegółów. */}
            {!loading && error && <p className="panel-note error">{error}</p>}

            {/* Błędy warstw burzowych pokazujemy tylko przy tych warstwach. */}
            {!stormLayersLoading && stormLayersError && (activeMode === 'cyclones' || activeMode === 'storms') && (
              <p className="panel-note error">{stormLayersError}</p>
            )}

            {/* Widok szczegółów pogody. */}
            {!loading && activeMode === 'weather' && selected && (
              <>
                <h2>{selected.name}</h2>
                <dl>
                  <div>
                    <dt>Kraj</dt>
                    <dd>{selected.country || '-'}</dd>
                  </div>
                  <div>
                    <dt>Temperatura</dt>
                    <dd>{selected.temperature ?? '-'} C</dd>
                  </div>
                  <div>
                    <dt>Wiatr</dt>
                    <dd>{selected.wind_speed ?? '-'} km/h</dd>
                  </div>
                  <div>
                    <dt>Wilgotnosc</dt>
                    <dd>{selected.humidity ?? '-'}%</dd>
                  </div>
                  <div>
                    <dt>Zachmurzenie</dt>
                    <dd>{selected.cloud_cover ?? '-'}%</dd>
                  </div>
                  <div>
                    <dt>Zrodlo</dt>
                    <dd>{selected.source}</dd>
                  </div>
                  <div>
                    <dt>Grupa</dt>
                    <dd>{selected.group}</dd>
                  </div>
                </dl>
              </>
            )}

            {/* Widok szczegółów zdarzenia sejsmicznego. */}
            {!loading && activeMode === 'seismic' && selected && (
              <>
                <h2>{selected.place}</h2>
                <dl>
                  <div>
                    <dt>Magnituda</dt>
                    <dd>{selected.magnitude ?? '-'}</dd>
                  </div>
                  <div>
                    <dt>Glebokosc</dt>
                    <dd>{selected.depth_km ?? '-'} km</dd>
                  </div>
                  <div>
                    <dt>Czas</dt>
                    <dd>{selected.event_time ? new Date(selected.event_time).toLocaleString('pl-PL') : '-'}</dd>
                  </div>
                  <div>
                    <dt>Zrodlo</dt>
                    <dd>{selected.source}</dd>
                  </div>
                </dl>
              </>
            )}

            {/* Widok szczegółów cyklonu tropikalnego. */}
            {!loading && activeMode === 'cyclones' && selected && (
              <>
                <h2>{selected.name}</h2>
                <dl>
                  <div>
                    <dt>Czas</dt>
                    <dd>{selected.event_time ? new Date(selected.event_time).toLocaleString('pl-PL') : '-'}</dd>
                  </div>
                  <div>
                    <dt>Typ</dt>
                    <dd>cyklon</dd>
                  </div>
                  <div>
                    <dt>Zrodlo</dt>
                    <dd>{selected.source}</dd>
                  </div>
                </dl>
              </>
            )}

            {/* Widok szczegółów burzy albo punktu wysokiego potencjału burzowego. */}
            {!loading && activeMode === 'storms' && selected && (
              <>
                <h2>{selected.name}</h2>
                <dl>
                  <div>
                    <dt>Kraj</dt>
                    <dd>{selected.country || '-'}</dd>
                  </div>
                  <div>
                    <dt>Score burzowy</dt>
                    <dd>{selected.storm_score ?? '-'}</dd>
                  </div>
                  <div>
                    <dt>Porywy</dt>
                    <dd>{selected.wind_gusts ?? '-'} km/h</dd>
                  </div>
                  <div>
                    <dt>Opad</dt>
                    <dd>{selected.precipitation ?? '-'} mm</dd>
                  </div>
                  <div>
                    <dt>Kod pogody</dt>
                    <dd>{selected.weather_code ?? '-'}</dd>
                  </div>
                  <div>
                    <dt>Zrodlo</dt>
                    <dd>{selected.source}</dd>
                  </div>
                </dl>
              </>
            )}

            {/* Lista umożliwia szybkie przełączenie zaznaczonego punktu. */}
            <div className="event-list">
              {items.slice(0, 8).map((item) => (
                <button
                  key={activeMode === 'weather' ? `${item.group}-${item.country}-${item.name}` : item.external_id}
                  onClick={() => (
                    activeMode === 'weather'
                      ? setSelectedWeather(item)
                      : activeMode === 'cyclones'
                        ? setSelectedCyclone(item)
                        : activeMode === 'storms'
                          ? setSelectedStorm(item)
                          : setSelectedEarthquake(item)
                  )}
                  type="button"
                >
                  <span>{activeMode === 'weather' || activeMode === 'storms' || activeMode === 'cyclones' ? item.name : item.place}</span>
                  <strong>
                    {activeMode === 'weather'
                      ? `${item.temperature ?? '-'} C`
                      : activeMode === 'storms'
                        ? `${item.storm_score ?? '-'}`
                        : activeMode === 'cyclones'
                          ? 'EONET'
                          : `M ${item.magnitude ?? '-'}`}
                  </strong>
                </button>
              ))}
            </div>
          </aside>
        </section>
      </section>

      {/* Modal izoluje proces logowania od mapy i pozostawia aplikację czytelną na małym ekranie. */}
      {authDialogOpen && (
        <div
          aria-labelledby="auth-dialog-title"
          aria-modal="true"
          className="auth-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !authLoading) setAuthDialogOpen(false)
          }}
          role="dialog"
        >
          {/* Panel zawiera tylko niezbędne informacje oraz oficjalny przycisk Google. */}
          <section className="auth-dialog">
            <div className="auth-dialog-header">
              <div>
                <span className="eyebrow">Konto użytkownika</span>
                <h2 id="auth-dialog-title">Zaloguj się</h2>
              </div>
              {/* Przycisk zamknięcia jest blokowany podczas trwającego requestu. */}
              <button
                className="auth-close-button"
                disabled={authLoading}
                onClick={() => setAuthDialogOpen(false)}
                type="button"
              >
                Zamknij
              </button>
            </div>

            {/* Krótki opis wyjaśnia, że Google potwierdza tożsamość dla konta aplikacji. */}
            <p>Użyj konta Google, aby utworzyć lub otworzyć profil w Matka Ziemia Monitor.</p>

            {/* Oficjalny komponent Google zwróci token ID do callbacku po wybraniu konta. */}
            <GoogleSignIn
              clientId={GOOGLE_CLIENT_ID}
              disabled={authLoading}
              onCredential={handleGoogleCredential}
              onError={handleGoogleError}
            />

            {/* Stan requestu i błędy są ogłaszane technologiom asystującym. */}
            <div aria-live="polite" className={authError ? 'auth-status error' : 'auth-status'}>
              {authLoading ? 'Trwa bezpieczne logowanie...' : authError}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}

// Eksportujemy komponent główny, żeby main.jsx mógł go wyrenderować.
export default App
