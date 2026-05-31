// Importujemy createRoot, żeby uruchomić aplikację React w elemencie #root.
import { createRoot } from 'react-dom/client'
// Importujemy globalne style całej aplikacji.
import './index.css'
// Importujemy główny komponent aplikacji.
import App from './App.jsx'

// Montujemy aplikację w elemencie #root z pliku index.html.
createRoot(document.getElementById('root')).render(
  // Nie używamy StrictMode w dev, bo podwaja useEffect i potrafi podbić limity zewnętrznych API.
  <App />,
)
