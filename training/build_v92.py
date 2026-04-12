#!/usr/bin/env python3
"""build_v92.py — SFT v92 for build-v89/90/91 adapter.

Loads v91 (50 examples), adds 4 new examples = 54 total.
New patterns:
  - Multi-page React Router app (react-router-dom)
  - Public API fetch with no key (Open-Meteo weather)
  - React Context + useReducer (shopping cart)
  - Responsive grid layout with CSS Grid/Flexbox (movie browser)
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.build_v69 import SYSTEM_TEXT, TOOLS

V91 = Path("workspace/training_data/e4b_toolcall_train_v91.jsonl")
OUT = Path("workspace/training_data/e4b_toolcall_train_v92.jsonl")


def tc(tool_name, **kw):
    return {"role": "tool_call", "content": json.dumps({"name": tool_name, "parameters": kw})}


def tr(content):
    return {"role": "tool_result", "content": content}


# ── rr01: Multi-page Recipe App (React Router) ────────────────────────────────
def rr01_recipe_book():
    return [
        {"role": "user", "content": "Build a recipe book app with multiple pages — a home page listing recipes, a detail page for each recipe, and a favorites page."},
        tc("project_init", name="recipe-book", dependencies=["react-router-dom"]),
        tr("Project 'recipe-book' ready (scaffold: react-app) at workspace/deliverables/recipe-book\nExtra deps: react-router-dom\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/main.tsx", content="""import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import App from "./App"

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
"""),
        tr("File written: workspace/deliverables/recipe-book/src/main.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/data/recipes.ts", content="""export interface Recipe {
  id: string
  title: string
  description: string
  time: string
  servings: number
  tags: string[]
  ingredients: string[]
  steps: string[]
  image: string
}

export const RECIPES: Recipe[] = [
  {
    id: "pasta-carbonara",
    title: "Pasta Carbonara",
    description: "Classic Roman pasta with eggs, cheese, and pancetta.",
    time: "25 min", servings: 2,
    tags: ["Italian", "Quick"],
    ingredients: ["200g spaghetti", "100g pancetta", "2 eggs", "50g Pecorino Romano", "Black pepper"],
    steps: [
      "Cook spaghetti until al dente.",
      "Fry pancetta until crispy.",
      "Whisk eggs with grated cheese and pepper.",
      "Off heat, combine pasta with pancetta and egg mixture.",
      "Toss quickly — the residual heat cooks the eggs.",
    ],
    image: "https://images.unsplash.com/photo-1588013273468-31508745a03f?w=400"
  },
  {
    id: "chicken-tikka",
    title: "Chicken Tikka Masala",
    description: "Creamy tomato curry with marinated chicken.",
    time: "45 min", servings: 4,
    tags: ["Indian", "Dinner"],
    ingredients: ["600g chicken", "200ml yogurt", "400ml tomato sauce", "200ml cream", "2 tbsp tikka paste", "Garam masala"],
    steps: [
      "Marinate chicken in yogurt and tikka paste for 30 min.",
      "Grill or pan-fry chicken until charred.",
      "Simmer tomato sauce with spices for 10 min.",
      "Add cream and chicken, cook 10 more min.",
    ],
    image: "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=400"
  },
  {
    id: "avocado-toast",
    title: "Avocado Toast",
    description: "The classic: creamy avocado on sourdough with a twist.",
    time: "10 min", servings: 1,
    tags: ["Breakfast", "Quick", "Vegetarian"],
    ingredients: ["2 slices sourdough", "1 avocado", "Lemon juice", "Red pepper flakes", "Salt"],
    steps: [
      "Toast bread until golden.",
      "Mash avocado with lemon juice and salt.",
      "Spread on toast, top with red pepper flakes.",
    ],
    image: "https://images.unsplash.com/photo-1541519227354-08fa5d50c820?w=400"
  },
  {
    id: "chocolate-mousse",
    title: "Chocolate Mousse",
    description: "Light, airy dark chocolate mousse — restaurant-quality at home.",
    time: "20 min (+2h chill)", servings: 4,
    tags: ["Dessert", "French"],
    ingredients: ["200g dark chocolate", "4 eggs (separated)", "2 tbsp sugar", "200ml heavy cream"],
    steps: [
      "Melt chocolate, let cool slightly.",
      "Whisk yolks with sugar, fold into chocolate.",
      "Whip cream to soft peaks, fold in.",
      "Beat egg whites to stiff peaks, fold gently.",
      "Chill 2 hours before serving.",
    ],
    image: "https://images.unsplash.com/photo-1611329695518-1765b4d3e4c6?w=400"
  },
]
"""),
        tr("File written: workspace/deliverables/recipe-book/src/data/recipes.ts"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/App.tsx", content="""import { Routes, Route } from "react-router-dom"
import { useState } from "react"
import { HomePage } from "./pages/HomePage"
import { RecipePage } from "./pages/RecipePage"
import { FavoritesPage } from "./pages/FavoritesPage"
import { Navbar } from "./components/Navbar"

export default function App() {
  const [favorites, setFavorites] = useState<Set<string>>(new Set())

  function toggleFavorite(id: string) {
    setFavorites(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div style={{ minHeight:"100vh", background:"#fafaf8", fontFamily:"system-ui" }}>
      <Navbar favoriteCount={favorites.size} />
      <Routes>
        <Route path="/" element={<HomePage favorites={favorites} toggleFavorite={toggleFavorite} />} />
        <Route path="/recipe/:id" element={<RecipePage favorites={favorites} toggleFavorite={toggleFavorite} />} />
        <Route path="/favorites" element={<FavoritesPage favorites={favorites} toggleFavorite={toggleFavorite} />} />
      </Routes>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/App.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/components/Navbar.tsx", content="""import { Link, useLocation } from "react-router-dom"

export function Navbar({ favoriteCount }: { favoriteCount: number }) {
  const { pathname } = useLocation()
  const linkStyle = (path: string): React.CSSProperties => ({
    textDecoration: "none",
    color: pathname === path ? "#e07a3d" : "#555",
    fontWeight: pathname === path ? 700 : 400,
    fontSize: 15,
  })

  return (
    <nav style={{ background:"white", borderBottom:"1px solid #e8e8e0", padding:"0 24px", display:"flex", alignItems:"center", height:56, gap:24, position:"sticky", top:0, zIndex:100 }}>
      <Link to="/" style={{ textDecoration:"none", fontWeight:700, fontSize:18, color:"#e07a3d" }}>🍳 RecipeBook</Link>
      <div style={{ marginLeft:"auto", display:"flex", gap:20, alignItems:"center" }}>
        <Link to="/" style={linkStyle("/")}>Recipes</Link>
        <Link to="/favorites" style={linkStyle("/favorites")}>
          Favorites {favoriteCount > 0 && <span style={{ background:"#e07a3d", color:"white", borderRadius:10, padding:"1px 6px", fontSize:12 }}>{favoriteCount}</span>}
        </Link>
      </div>
    </nav>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/components/Navbar.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/components/RecipeCard.tsx", content="""import { Link } from "react-router-dom"
import type { Recipe } from "../data/recipes"

interface Props { recipe: Recipe; isFavorite: boolean; onToggle: () => void }

export function RecipeCard({ recipe, isFavorite, onToggle }: Props) {
  return (
    <div style={{ background:"white", borderRadius:12, overflow:"hidden", boxShadow:"0 1px 4px rgba(0,0,0,0.08)", transition:"transform 0.15s", cursor:"pointer" }}
         onMouseEnter={e => (e.currentTarget.style.transform = "translateY(-2px)")}
         onMouseLeave={e => (e.currentTarget.style.transform = "none")}>
      <Link to={`/recipe/${recipe.id}`} style={{ textDecoration:"none", color:"inherit" }}>
        <img src={recipe.image} alt={recipe.title} style={{ width:"100%", height:180, objectFit:"cover" }} />
        <div style={{ padding:16 }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:8 }}>
            <h3 style={{ fontSize:16, fontWeight:700, color:"#1a1a1a", margin:0 }}>{recipe.title}</h3>
          </div>
          <p style={{ fontSize:13, color:"#777", margin:"6px 0 10px", lineHeight:1.4 }}>{recipe.description}</p>
          <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
            <span style={{ fontSize:12, color:"#555", background:"#f5f5f0", padding:"2px 8px", borderRadius:20 }}>⏱ {recipe.time}</span>
            <span style={{ fontSize:12, color:"#555", background:"#f5f5f0", padding:"2px 8px", borderRadius:20 }}>👥 {recipe.servings}</span>
            {recipe.tags.slice(0,2).map(t => <span key={t} style={{ fontSize:12, color:"#e07a3d", background:"#fef3ec", padding:"2px 8px", borderRadius:20 }}>{t}</span>)}
          </div>
        </div>
      </Link>
      <button onClick={e => { e.preventDefault(); onToggle() }}
        style={{ position:"absolute", top:12, right:12, background:"white", border:"none", borderRadius:"50%",
                 width:32, height:32, cursor:"pointer", fontSize:16, display:"flex", alignItems:"center", justifyContent:"center",
                 boxShadow:"0 1px 3px rgba(0,0,0,0.2)" }}>
        {isFavorite ? "❤️" : "🤍"}
      </button>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/components/RecipeCard.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/pages/HomePage.tsx", content="""import { useState } from "react"
import { RECIPES } from "../data/recipes"
import { RecipeCard } from "../components/RecipeCard"

interface Props { favorites: Set<string>; toggleFavorite: (id: string) => void }

export function HomePage({ favorites, toggleFavorite }: Props) {
  const [search, setSearch] = useState("")
  const filtered = RECIPES.filter(r =>
    r.title.toLowerCase().includes(search.toLowerCase()) ||
    r.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  )

  return (
    <div style={{ maxWidth:960, margin:"0 auto", padding:32 }}>
      <h1 style={{ fontSize:28, fontWeight:700, marginBottom:8 }}>Recipes</h1>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by name or tag…"
        style={{ width:"100%", maxWidth:400, padding:"10px 16px", border:"1px solid #ddd", borderRadius:24, fontSize:14, marginBottom:24, outline:"none" }}
      />
      {filtered.length === 0 ? (
        <p style={{ color:"#888" }}>No recipes found for "{search}"</p>
      ) : (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(220px, 1fr))", gap:20, position:"relative" }}>
          {filtered.map(r => (
            <RecipeCard key={r.id} recipe={r} isFavorite={favorites.has(r.id)} onToggle={() => toggleFavorite(r.id)} />
          ))}
        </div>
      )}
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/pages/HomePage.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/pages/RecipePage.tsx", content="""import { useParams, useNavigate } from "react-router-dom"
import { RECIPES } from "../data/recipes"

interface Props { favorites: Set<string>; toggleFavorite: (id: string) => void }

export function RecipePage({ favorites, toggleFavorite }: Props) {
  const { id } = useParams()
  const navigate = useNavigate()
  const recipe = RECIPES.find(r => r.id === id)

  if (!recipe) return <div style={{ padding:32 }}>Recipe not found. <button onClick={() => navigate("/")}>Go back</button></div>

  return (
    <div style={{ maxWidth:700, margin:"0 auto", padding:32 }}>
      <button onClick={() => navigate(-1)} style={{ border:"none", background:"none", cursor:"pointer", color:"#666", fontSize:14, marginBottom:16, padding:0 }}>← Back</button>
      <img src={recipe.image} alt={recipe.title} style={{ width:"100%", height:300, objectFit:"cover", borderRadius:12, marginBottom:24 }} />
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div>
          <h1 style={{ fontSize:28, fontWeight:700, margin:"0 0 8px" }}>{recipe.title}</h1>
          <p style={{ color:"#666", fontSize:15, margin:0 }}>{recipe.description}</p>
        </div>
        <button onClick={() => toggleFavorite(recipe.id)}
          style={{ fontSize:24, background:"none", border:"none", cursor:"pointer", padding:"4px 8px" }}>
          {favorites.has(recipe.id) ? "❤️" : "🤍"}
        </button>
      </div>
      <div style={{ display:"flex", gap:16, margin:"16px 0 24px", flexWrap:"wrap" }}>
        <span style={{ color:"#555" }}>⏱ {recipe.time}</span>
        <span style={{ color:"#555" }}>👥 {recipe.servings} servings</span>
        {recipe.tags.map(t => <span key={t} style={{ color:"#e07a3d" }}>#{t}</span>)}
      </div>
      <h2 style={{ fontSize:18, fontWeight:700, marginBottom:12 }}>Ingredients</h2>
      <ul style={{ paddingLeft:20, marginBottom:24 }}>
        {recipe.ingredients.map((ing, i) => <li key={i} style={{ marginBottom:6, color:"#333" }}>{ing}</li>)}
      </ul>
      <h2 style={{ fontSize:18, fontWeight:700, marginBottom:12 }}>Steps</h2>
      <ol style={{ paddingLeft:20 }}>
        {recipe.steps.map((step, i) => <li key={i} style={{ marginBottom:10, color:"#333", lineHeight:1.6 }}>{step}</li>)}
      </ol>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/pages/RecipePage.tsx"),
        tc("file_write", path="workspace/deliverables/recipe-book/src/pages/FavoritesPage.tsx", content="""import { RECIPES } from "../data/recipes"
import { RecipeCard } from "../components/RecipeCard"
import { Link } from "react-router-dom"

interface Props { favorites: Set<string>; toggleFavorite: (id: string) => void }

export function FavoritesPage({ favorites, toggleFavorite }: Props) {
  const favRecipes = RECIPES.filter(r => favorites.has(r.id))

  return (
    <div style={{ maxWidth:960, margin:"0 auto", padding:32 }}>
      <h1 style={{ fontSize:28, fontWeight:700, marginBottom:24 }}>Favorites</h1>
      {favRecipes.length === 0 ? (
        <div style={{ textAlign:"center", marginTop:80, color:"#888" }}>
          <p style={{ fontSize:18 }}>No favorites yet.</p>
          <Link to="/" style={{ color:"#e07a3d" }}>Browse recipes →</Link>
        </div>
      ) : (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(220px, 1fr))", gap:20, position:"relative" }}>
          {favRecipes.map(r => (
            <RecipeCard key={r.id} recipe={r} isFavorite={true} onToggle={() => toggleFavorite(r.id)} />
          ))}
        </div>
      )}
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/recipe-book/src/pages/FavoritesPage.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/recipe-book && npm run build 2>&1 | tail -5"),
        tr("✓ built in 2.1s — 5 chunks transformed"),
        tc("undertow"),
        tr("Screenshot: recipe book app — Home page shows 4 recipe cards in a 2-column grid with images, tags, and heart buttons. Navbar at top with 'RecipeBook' logo and Favorites link showing count badge."),
        tc("message_result", text="**Recipe Book** is live — 3 pages:\n\n- `/` — Browse all recipes, search by name or tag, favorite heart buttons\n- `/recipe/:id` — Full recipe detail with ingredients, steps, back navigation\n- `/favorites` — Your saved recipes\n\nTo add more recipes: edit `src/data/recipes.ts` and add entries to the `RECIPES` array.", done=True),
        tr("Message sent"),
    ]


# ── rr02: Weather App (public API, no key) ─────────────────────────────────────
def rr02_weather_app():
    return [
        {"role": "user", "content": "Build a weather app. Show current conditions and a 7-day forecast."},
        tc("project_init", name="weather-app"),
        tr("Project 'weather-app' ready (scaffold: react-app) at workspace/deliverables/weather-app\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/weather-app/src/App.tsx", content="""import { useState, useEffect } from "react"

interface WeatherDay {
  date: string
  maxTemp: number
  minTemp: number
  weatherCode: number
  precipitation: number
}

interface CurrentWeather {
  temp: number
  weatherCode: number
  windSpeed: number
  humidity: number
}

const WMO_DESCRIPTIONS: Record<number, { label: string; icon: string }> = {
  0:  { label: "Clear sky",          icon: "☀️" },
  1:  { label: "Mainly clear",       icon: "🌤" },
  2:  { label: "Partly cloudy",      icon: "⛅" },
  3:  { label: "Overcast",           icon: "☁️" },
  45: { label: "Foggy",              icon: "🌫" },
  61: { label: "Light rain",         icon: "🌦" },
  63: { label: "Rain",               icon: "🌧" },
  71: { label: "Light snow",         icon: "🌨" },
  73: { label: "Snow",               icon: "❄️" },
  80: { label: "Rain showers",       icon: "🌦" },
  95: { label: "Thunderstorm",       icon: "⛈" },
}

function getWeather(code: number) {
  return WMO_DESCRIPTIONS[code] ?? { label: "Unknown", icon: "🌡" }
}

function formatDay(dateStr: string) {
  const d = new Date(dateStr)
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
}

// Open-Meteo: free, no API key required
async function fetchWeather(lat: number, lon: number) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m` +
    `&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum` +
    `&temperature_unit=celsius&wind_speed_unit=kmh&timezone=auto&forecast_days=7`
  const res = await fetch(url)
  const data = await res.json()
  return {
    current: {
      temp: Math.round(data.current.temperature_2m),
      weatherCode: data.current.weather_code,
      windSpeed: Math.round(data.current.wind_speed_10m),
      humidity: data.current.relative_humidity_2m,
    } as CurrentWeather,
    forecast: data.daily.time.map((date: string, i: number) => ({
      date,
      maxTemp: Math.round(data.daily.temperature_2m_max[i]),
      minTemp: Math.round(data.daily.temperature_2m_min[i]),
      weatherCode: data.daily.weather_code[i],
      precipitation: data.daily.precipitation_sum[i],
    })) as WeatherDay[],
    timezone: data.timezone,
  }
}

const CITIES = [
  { name: "New York",    lat: 40.71, lon: -74.01 },
  { name: "London",      lat: 51.51, lon: -0.13  },
  { name: "Tokyo",       lat: 35.68, lon: 139.69 },
  { name: "Sydney",      lat: -33.87, lon: 151.21 },
  { name: "Paris",       lat: 48.85, lon: 2.35   },
]

export default function App() {
  const [city, setCity] = useState(CITIES[0])
  const [current, setCurrent] = useState<CurrentWeather | null>(null)
  const [forecast, setForecast] = useState<WeatherDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    setLoading(true)
    setError("")
    fetchWeather(city.lat, city.lon)
      .then(data => {
        setCurrent(data.current)
        setForecast(data.forecast)
      })
      .catch(e => setError("Failed to fetch weather: " + e.message))
      .finally(() => setLoading(false))
  }, [city])

  const weather = current ? getWeather(current.weatherCode) : null

  return (
    <div style={{ minHeight:"100vh", background:"linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%)", color:"white", fontFamily:"system-ui", padding:32 }}>
      <div style={{ maxWidth:600, margin:"0 auto" }}>
        {/* City selector */}
        <div style={{ display:"flex", gap:8, marginBottom:32, flexWrap:"wrap" }}>
          {CITIES.map(c => (
            <button key={c.name} onClick={() => setCity(c)}
              style={{ padding:"6px 16px", borderRadius:20, border:"1px solid rgba(255,255,255,0.5)",
                       background: city.name === c.name ? "rgba(255,255,255,0.3)" : "transparent",
                       color:"white", cursor:"pointer", fontSize:13, fontWeight: city.name === c.name ? 700 : 400 }}>
              {c.name}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign:"center", fontSize:18, opacity:0.7 }}>Loading…</div>
        ) : error ? (
          <div style={{ textAlign:"center", color:"#ffcdd2" }}>{error}</div>
        ) : current && weather ? (
          <>
            {/* Current conditions */}
            <div style={{ textAlign:"center", marginBottom:32 }}>
              <div style={{ fontSize:80, lineHeight:1 }}>{weather.icon}</div>
              <div style={{ fontSize:72, fontWeight:300, lineHeight:1.1 }}>{current.temp}°</div>
              <div style={{ fontSize:20, opacity:0.9, marginTop:4 }}>{weather.label}</div>
              <div style={{ fontSize:14, opacity:0.7, marginTop:8 }}>{city.name}</div>
              <div style={{ display:"flex", gap:24, justifyContent:"center", marginTop:16, fontSize:14, opacity:0.85 }}>
                <span>💨 {current.windSpeed} km/h</span>
                <span>💧 {current.humidity}%</span>
              </div>
            </div>

            {/* 7-day forecast */}
            <div style={{ background:"rgba(255,255,255,0.12)", borderRadius:16, padding:16 }}>
              <div style={{ fontSize:12, opacity:0.7, marginBottom:12, textTransform:"uppercase", letterSpacing:1 }}>7-Day Forecast</div>
              {forecast.map(day => {
                const dw = getWeather(day.weatherCode)
                return (
                  <div key={day.date} style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 0",
                                               borderBottom:"1px solid rgba(255,255,255,0.1)" }}>
                    <span style={{ width:110, fontSize:13 }}>{formatDay(day.date)}</span>
                    <span style={{ fontSize:20 }}>{dw.icon}</span>
                    <span style={{ flex:1, fontSize:13, opacity:0.8 }}>{dw.label}</span>
                    {day.precipitation > 0 && <span style={{ fontSize:12, opacity:0.6 }}>💧{day.precipitation}mm</span>}
                    <span style={{ fontSize:14, fontWeight:600, width:35, textAlign:"right" }}>{day.maxTemp}°</span>
                    <span style={{ fontSize:13, opacity:0.6, width:30, textAlign:"right" }}>{day.minTemp}°</span>
                  </div>
                )
              })}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/weather-app/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/weather-app && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.1s"),
        tc("undertow"),
        tr("Screenshot: dark blue gradient weather app — current conditions for New York show ⛅ icon, 18°, 'Partly cloudy', wind 22 km/h, humidity 65%. City buttons across top. 7-day forecast list below with icons and hi/lo temps."),
        tc("message_result", text="**Weather App** is live.\n\nShows current conditions + 7-day forecast for 5 cities. Uses [Open-Meteo](https://open-meteo.com/) — completely free, no API key required.\n\nTo add more cities: edit the `CITIES` array in `App.tsx` with latitude/longitude coordinates.", done=True),
        tr("Message sent"),
    ]


# ── rr03: Shopping Cart (React Context + useReducer) ──────────────────────────
def rr03_shopping_cart():
    return [
        {"role": "user", "content": "Build a shopping cart app. Users can add products, change quantities, and see the total."},
        tc("project_init", name="shopping-cart"),
        tr("Project 'shopping-cart' ready (scaffold: react-app) at workspace/deliverables/shopping-cart\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/shopping-cart/src/App.tsx", content="""import { createContext, useContext, useReducer, useMemo } from "react"

// ── Types ──────────────────────────────────────────────────────────────────
interface Product { id: string; name: string; price: number; image: string; category: string }
interface CartItem { product: Product; qty: number }
type CartAction =
  | { type: "ADD"; product: Product }
  | { type: "REMOVE"; id: string }
  | { type: "SET_QTY"; id: string; qty: number }
  | { type: "CLEAR" }

// ── Catalog ────────────────────────────────────────────────────────────────
const PRODUCTS: Product[] = [
  { id: "p1", name: "Mechanical Keyboard",    price: 129.99, category: "Electronics", image: "⌨️" },
  { id: "p2", name: "Wireless Mouse",         price: 59.99,  category: "Electronics", image: "🖱" },
  { id: "p3", name: "USB-C Hub",              price: 39.99,  category: "Electronics", image: "🔌" },
  { id: "p4", name: "Monitor Stand",          price: 49.99,  category: "Desk",        image: "🖥" },
  { id: "p5", name: "Desk Lamp",              price: 34.99,  category: "Desk",        image: "💡" },
  { id: "p6", name: "Coffee Mug",             price: 14.99,  category: "Kitchen",     image: "☕" },
  { id: "p7", name: "Notebook (A5)",          price: 9.99,   category: "Stationery",  image: "📓" },
  { id: "p8", name: "Wireless Charger",       price: 24.99,  category: "Electronics", image: "🔋" },
]

// ── Cart reducer ───────────────────────────────────────────────────────────
function cartReducer(state: CartItem[], action: CartAction): CartItem[] {
  switch (action.type) {
    case "ADD": {
      const exists = state.find(item => item.product.id === action.product.id)
      if (exists) return state.map(item =>
        item.product.id === action.product.id ? { ...item, qty: item.qty + 1 } : item
      )
      return [...state, { product: action.product, qty: 1 }]
    }
    case "REMOVE":
      return state.filter(item => item.product.id !== action.id)
    case "SET_QTY":
      return action.qty < 1
        ? state.filter(item => item.product.id !== action.id)
        : state.map(item =>
            item.product.id === action.id ? { ...item, qty: action.qty } : item
          )
    case "CLEAR":
      return []
    default:
      return state
  }
}

// ── Context ────────────────────────────────────────────────────────────────
const CartContext = createContext<{
  items: CartItem[]
  dispatch: React.Dispatch<CartAction>
  total: number
  count: number
}>(null!)

function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, dispatch] = useReducer(cartReducer, [])
  const total = useMemo(() => items.reduce((s, i) => s + i.product.price * i.qty, 0), [items])
  const count = useMemo(() => items.reduce((s, i) => s + i.qty, 0), [items])
  return <CartContext.Provider value={{ items, dispatch, total, count }}>{children}</CartContext.Provider>
}

function useCart() { return useContext(CartContext) }

// ── Components ─────────────────────────────────────────────────────────────
function ProductGrid() {
  const { dispatch } = useCart()
  const categories = [...new Set(PRODUCTS.map(p => p.category))]

  return (
    <div>
      {categories.map(cat => (
        <div key={cat} style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize:16, fontWeight:700, color:"#374151", marginBottom:12, textTransform:"uppercase", letterSpacing:0.5 }}>{cat}</h2>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(160px, 1fr))", gap:12 }}>
            {PRODUCTS.filter(p => p.category === cat).map(product => (
              <div key={product.id} style={{ background:"white", borderRadius:10, padding:16, textAlign:"center",
                                            boxShadow:"0 1px 3px rgba(0,0,0,0.08)" }}>
                <div style={{ fontSize:40, marginBottom:8 }}>{product.image}</div>
                <div style={{ fontSize:14, fontWeight:600, marginBottom:4 }}>{product.name}</div>
                <div style={{ fontSize:15, fontWeight:700, color:"#059669", marginBottom:12 }}>${product.price.toFixed(2)}</div>
                <button onClick={() => dispatch({ type:"ADD", product })}
                  style={{ width:"100%", padding:"7px 0", background:"#2563eb", color:"white",
                           border:"none", borderRadius:7, cursor:"pointer", fontSize:13, fontWeight:600 }}>
                  Add to Cart
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function CartPanel() {
  const { items, dispatch, total, count } = useCart()

  return (
    <div style={{ background:"white", borderRadius:12, padding:24, boxShadow:"0 2px 8px rgba(0,0,0,0.1)", position:"sticky", top:24 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <h2 style={{ fontSize:18, fontWeight:700, margin:0 }}>Cart {count > 0 && <span style={{ background:"#2563eb", color:"white", borderRadius:10, padding:"1px 7px", fontSize:13 }}>{count}</span>}</h2>
        {items.length > 0 && <button onClick={() => dispatch({ type:"CLEAR" })}
          style={{ fontSize:13, color:"#dc2626", background:"none", border:"none", cursor:"pointer" }}>Clear</button>}
      </div>

      {items.length === 0 ? (
        <p style={{ color:"#9ca3af", textAlign:"center", margin:"40px 0", fontSize:14 }}>Your cart is empty</p>
      ) : (
        <>
          <div style={{ display:"flex", flexDirection:"column", gap:12, marginBottom:16 }}>
            {items.map(({ product, qty }) => (
              <div key={product.id} style={{ display:"flex", alignItems:"center", gap:10, fontSize:14 }}>
                <span style={{ fontSize:22 }}>{product.image}</span>
                <div style={{ flex:1 }}>
                  <div style={{ fontWeight:600 }}>{product.name}</div>
                  <div style={{ color:"#6b7280", fontSize:13 }}>${product.price.toFixed(2)} each</div>
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:4 }}>
                  <button onClick={() => dispatch({ type:"SET_QTY", id:product.id, qty: qty-1 })}
                    style={{ width:26, height:26, borderRadius:"50%", border:"1px solid #ddd", background:"white", cursor:"pointer", fontSize:14 }}>−</button>
                  <span style={{ width:24, textAlign:"center" }}>{qty}</span>
                  <button onClick={() => dispatch({ type:"SET_QTY", id:product.id, qty: qty+1 })}
                    style={{ width:26, height:26, borderRadius:"50%", border:"1px solid #ddd", background:"white", cursor:"pointer", fontSize:14 }}>+</button>
                </div>
                <button onClick={() => dispatch({ type:"REMOVE", id:product.id })}
                  style={{ background:"none", border:"none", cursor:"pointer", color:"#9ca3af", fontSize:16, padding:"0 4px" }}>✕</button>
              </div>
            ))}
          </div>
          <div style={{ borderTop:"1px solid #f3f4f6", paddingTop:16 }}>
            <div style={{ display:"flex", justifyContent:"space-between", fontSize:18, fontWeight:700, marginBottom:16 }}>
              <span>Total</span>
              <span>${total.toFixed(2)}</span>
            </div>
            <button style={{ width:"100%", padding:"12px 0", background:"#059669", color:"white", border:"none",
                            borderRadius:8, cursor:"pointer", fontSize:15, fontWeight:700 }}>
              Checkout
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <CartProvider>
      <div style={{ minHeight:"100vh", background:"#f9fafb", fontFamily:"system-ui" }}>
        <nav style={{ background:"white", borderBottom:"1px solid #e5e7eb", padding:"0 32px", height:56,
                      display:"flex", alignItems:"center" }}>
          <span style={{ fontWeight:700, fontSize:18 }}>🛒 ShopApp</span>
        </nav>
        <div style={{ maxWidth:1100, margin:"0 auto", padding:"32px 24px", display:"grid",
                      gridTemplateColumns:"1fr 320px", gap:32, alignItems:"start" }}>
          <ProductGrid />
          <CartPanel />
        </div>
      </div>
    </CartProvider>
  )
}
"""),
        tr("File written: workspace/deliverables/shopping-cart/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/shopping-cart && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.3s"),
        tc("undertow"),
        tr("Screenshot: shopping cart app — left side shows product grid organized by category (Electronics, Desk, etc.) with emoji icons, prices, and Add to Cart buttons. Right side shows sticky cart panel with items, quantity +/− controls, total, and Checkout button."),
        tc("message_result", text="**Shopping Cart** is live.\n\nFeatures:\n- Products organized by category with Add to Cart\n- Cart panel: quantity controls (+/−), remove items, clear all\n- Real-time total calculation\n- React Context + `useReducer` for state — no prop drilling\n\nTo add products: extend the `PRODUCTS` array in `App.tsx`.", done=True),
        tr("Message sent"),
    ]


# ── rr04: Movie Browser (async search + movie API pattern) ────────────────────
def rr04_movie_browser():
    return [
        {"role": "user", "content": "Build a movie browser app using The Movie Database API. Show trending movies, and let users search by title."},
        tc("search_web", query="TMDB API free tier access — do I need an API key?"),
        tr("""Results for "TMDB API free tier access":
1. TMDB Developer Docs — Yes, the TMDB API is free for non-commercial use. Sign up at themoviedb.org/signup, then go to Settings > API. You'll get an API Read Access Token (Bearer token). The `/trending/movie/week` and `/search/movie` endpoints are free and have generous rate limits (40 req/10s). No credit card required.
2. Stack Overflow answer — You can use TMDB with just a Bearer token in headers: `Authorization: Bearer <your_read_access_token>`. Store in VITE_TMDB_KEY."""),
        tc("project_init", name="movie-browser"),
        tr("Project 'movie-browser' ready (scaffold: react-app) at workspace/deliverables/movie-browser\nDev server: http://localhost:5173"),
        tc("file_write", path="workspace/deliverables/movie-browser/src/App.tsx", content="""import { useState, useEffect, useCallback } from "react"

interface Movie {
  id: number
  title: string
  overview: string
  release_date: string
  vote_average: number
  poster_path: string | null
}

const API_KEY = import.meta.env.VITE_TMDB_KEY || ""
const BASE_URL = "https://api.themoviedb.org/3"
const IMG_BASE = "https://image.tmdb.org/t/p/w342"

async function fetchMovies(query: string): Promise<Movie[]> {
  const endpoint = query
    ? `${BASE_URL}/search/movie?query=${encodeURIComponent(query)}&include_adult=false`
    : `${BASE_URL}/trending/movie/week`
  const res = await fetch(endpoint, {
    headers: { Authorization: `Bearer ${API_KEY}`, "Content-Type": "application/json" },
  })
  const data = await res.json()
  return data.results || []
}

function MovieCard({ movie }: { movie: Movie }) {
  const year = movie.release_date?.slice(0, 4) || "?"
  const rating = movie.vote_average.toFixed(1)
  return (
    <div style={{ background:"#1e1e2e", borderRadius:10, overflow:"hidden", transition:"transform 0.15s" }}
         onMouseEnter={e => (e.currentTarget.style.transform = "translateY(-3px)")}
         onMouseLeave={e => (e.currentTarget.style.transform = "none")}>
      {movie.poster_path ? (
        <img src={IMG_BASE + movie.poster_path} alt={movie.title}
          style={{ width:"100%", aspectRatio:"2/3", objectFit:"cover", display:"block" }} />
      ) : (
        <div style={{ width:"100%", aspectRatio:"2/3", background:"#2a2a3e", display:"flex", alignItems:"center",
                      justifyContent:"center", fontSize:40 }}>🎬</div>
      )}
      <div style={{ padding:12 }}>
        <div style={{ fontWeight:700, fontSize:14, color:"white", lineHeight:1.3, marginBottom:4 }}>{movie.title}</div>
        <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, color:"#a0a0b0" }}>
          <span>{year}</span>
          <span>⭐ {rating}</span>
        </div>
        <p style={{ fontSize:12, color:"#888", marginTop:6, lineHeight:1.4, display:"-webkit-box",
                    WebkitLineClamp:3, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
          {movie.overview || "No description available."}
        </p>
      </div>
    </div>
  )
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

export default function App() {
  const [query, setQuery] = useState("")
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const debouncedQuery = useDebounce(query, 400)

  useEffect(() => {
    if (!API_KEY) {
      setError("Set VITE_TMDB_KEY in .env — get a free key at themoviedb.org/settings/api")
      setLoading(false)
      return
    }
    setLoading(true)
    setError("")
    fetchMovies(debouncedQuery)
      .then(setMovies)
      .catch(e => setError("Error: " + e.message))
      .finally(() => setLoading(false))
  }, [debouncedQuery])

  return (
    <div style={{ minHeight:"100vh", background:"#0d0d1a", color:"white", fontFamily:"system-ui" }}>
      <div style={{ maxWidth:1200, margin:"0 auto", padding:"32px 24px" }}>
        <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom:32 }}>
          <h1 style={{ fontSize:24, fontWeight:700, margin:0 }}>🎬 MovieBrowser</h1>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search movies…"
            style={{ flex:1, maxWidth:400, padding:"10px 16px", borderRadius:24,
                     background:"#1e1e2e", border:"1px solid #333", color:"white", fontSize:14, outline:"none" }}
          />
          <span style={{ fontSize:14, color:"#666" }}>
            {debouncedQuery ? "Search results" : "Trending this week"}
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign:"center", opacity:0.5, marginTop:80 }}>Loading…</div>
        ) : error ? (
          <div style={{ background:"#2a1a1a", border:"1px solid #5a2a2a", borderRadius:8, padding:20, color:"#ffcdd2" }}>{error}</div>
        ) : (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(180px, 1fr))", gap:16 }}>
            {movies.slice(0, 20).map(movie => <MovieCard key={movie.id} movie={movie} />)}
          </div>
        )}
      </div>
    </div>
  )
}
"""),
        tr("File written: workspace/deliverables/movie-browser/src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/movie-browser && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.0s"),
        tc("undertow"),
        tr("Screenshot: dark movie browser — grid of movie posters with titles, year, and star rating. Search input at top. Shows 'Trending this week' label. Without an API key, shows an error message explaining how to get one."),
        tc("message_result", text="**Movie Browser** is live.\n\nTo activate:\n1. Get a free API key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)\n2. Add to `.env`: `VITE_TMDB_KEY=your_bearer_token_here`\n\nFeatures: trending movies, debounced search (400ms delay), poster grid, rating + year. Handles missing posters gracefully.", done=True),
        tr("Message sent"),
    ]


def build_example(source_fn, messages):
    text = f"<start_of_turn>system\n{SYSTEM_TEXT}<end_of_turn>\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            text += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role in ("assistant", "tool_call", "tool_result"):
            text += f"<start_of_turn>model\n{content}<end_of_turn>\n"
    return {"text": text, "source": source_fn}


def main():
    # Load v91 examples
    v91_examples = []
    if V91.exists():
        with open(V91) as f:
            v91_examples = [json.loads(l) for l in f if l.strip()]
        print(f"Loaded {len(v91_examples)} from v91")
    else:
        print("Warning: v91 not found, starting from scratch")

    new_examples = [
        ("rr01_recipe_book", rr01_recipe_book()),
        ("rr02_weather_app", rr02_weather_app()),
        ("rr03_shopping_cart", rr03_shopping_cart()),
        ("rr04_movie_browser", rr04_movie_browser()),
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for ex in v91_examples:
            f.write(json.dumps(ex) + "\n")
        for source, msgs in new_examples:
            obj = build_example(source, msgs)
            f.write(json.dumps(obj) + "\n")
            print(f"  {source}: {len(msgs)} msgs -> {len(obj['text'])} chars")

    total = len(v91_examples) + len(new_examples)
    print(f"\nTotal: {total} ({len(v91_examples)} v91 + {len(new_examples)} new)")
    print(f"Wrote to {OUT}")


if __name__ == "__main__":
    main()
