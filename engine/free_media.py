"""Free media fetcher — downloads copyright-free images and videos.

Provider priority (images):
  1. Local cache  — instant
  2. Wikimedia Commons — scientific diagrams, no API key needed, CC-licensed
  3. Pixabay — photos + videos, free tier 100 req/hr (5000/hr with free key)
  4. Pexels  — high-quality photos + videos, free key required
  5. Unsplash — nature / science photos, free key required

Provider priority (videos):
  1. Local cache
  2. Pixabay Videos
  3. Pexels Videos
  4. Mixkit  — no API key, curated free clips

API keys (all free):
  PIXABAY_API_KEY  — pixabay.com/api/docs/
  PEXELS_API_KEY   — pexels.com/api/
  UNSPLASH_API_KEY — unsplash.com/developers
"""

import os
import re
import json
import hashlib
import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subject → search query map  (covers school → degree → competitive exams)
# ---------------------------------------------------------------------------
SUBJECT_HINTS = {
    # ── Biology ─────────────────────────────────────────────────────────────
    "biology": {
        "cell":                 "animal cell diagram biology microscope",
        "plant_cell":           "plant cell structure biology diagram",
        "dna":                  "DNA double helix strand genetics",
        "photosynthesis":       "photosynthesis plant leaf chloroplast sunlight",
        "food_chain":           "food chain predator prey ecosystem",
        "mitosis":              "cell division mitosis biology phases",
        "meiosis":              "meiosis cell division biology",
        "human_body":           "human anatomy body organs diagram",
        "heart":                "human heart anatomy chambers diagram",
        "brain":                "human brain anatomy diagram",
        "neuron":               "neuron nerve cell structure axon dendrite",
        "eye":                  "human eye anatomy cross section diagram",
        "ear":                  "human ear anatomy diagram",
        "kidney":               "kidney nephron anatomy diagram",
        "lung":                 "lung alveoli anatomy diagram",
        "blood_cells":          "blood cells red white platelet microscope",
        "digestive_system":     "human digestive system diagram",
        "respiration":          "aerobic respiration equation ATP",
        "osmosis":              "osmosis diffusion cell membrane biology",
        "genetics":             "genetics chromosome DNA gene heredity",
        "punnett_square":       "Punnett square genetics dominant recessive",
        "evolution":            "evolution natural selection Darwin species",
        "ecosystem":            "ecosystem biome food web nature",
        "water_cycle":          "water cycle evaporation condensation rain diagram",
        "nitrogen_cycle":       "nitrogen cycle bacteria soil diagram",
        "virus":                "virus structure biology icosahedral",
        "bacteria":             "bacteria cell structure flagella biology",
        "plant_parts":          "plant parts root stem leaf flower diagram",
        "pollination":          "pollination flower bee cross pollination",
        "skeleton":             "human skeleton bones anatomy diagram",
        "muscle":               "muscle tissue fiber anatomy",
        "hormone":              "endocrine system hormone gland diagram",
        "immune_system":        "immune system antibody white blood cell",
        "biochemistry":         "biochemistry protein enzyme structure",
        "ecology":              "ecology environment biodiversity nature",
        "default":              "biology science laboratory microscope",
    },

    # ── Physics ──────────────────────────────────────────────────────────────
    "physics": {
        "pendulum":             "simple pendulum physics oscillation experiment",
        "circuit":              "electric circuit components resistor diagram",
        "optics":               "light refraction prism convex lens spectrum",
        "concave_mirror":       "concave mirror reflection focal point diagram",
        "convex_mirror":        "convex mirror reflection diverging diagram",
        "gravity":              "gravity free fall acceleration physics",
        "magnetism":            "magnet magnetic field iron filings bar magnet",
        "solenoid":             "solenoid electromagnet coil magnetic field",
        "waves":                "sound wave frequency oscillation physics",
        "force":                "force diagram vector physics free body",
        "projectile":           "projectile motion parabola trajectory physics",
        "inclined_plane":       "inclined plane ramp angle force physics",
        "thermodynamics":       "thermodynamics heat engine carnot cycle",
        "nuclear":              "nuclear fission atom uranium neutron chain reaction",
        "motion":               "Newton law motion velocity acceleration graph",
        "circular_motion":      "circular motion centripetal force diagram",
        "transformer":          "step up down transformer coil iron core",
        "capacitor":            "parallel plate capacitor electric field",
        "nuclear_fusion":       "nuclear fusion hydrogen helium energy sun",
        "photoelectric":        "photoelectric effect photon electron metal",
        "pressure":             "fluid pressure Pascal law column diagram",
        "pulley":               "pulley system mechanical advantage rope",
        "semiconductor":        "semiconductor diode transistor circuit",
        "laser":                "laser light stimulated emission coherent",
        "relativity":           "special relativity Einstein spacetime",
        "quantum":              "quantum mechanics wave particle duality",
        "default":              "physics science experiment laboratory",
    },

    # ── Chemistry ────────────────────────────────────────────────────────────
    "chemistry": {
        "lab":                  "chemistry laboratory beaker flask experiment",
        "molecule":             "molecule model 3d chemical structure bond",
        "periodic_table":       "periodic table elements chemistry",
        "periodic_element":     "element card periodic table symbol atomic number",
        "reaction":             "chemical reaction equation arrow product reactant",
        "acid_base":            "acid base pH indicator litmus paper",
        "ph_scale":             "pH scale acid neutral alkaline indicator",
        "organic":              "organic chemistry carbon compound functional group",
        "electrolysis":         "electrolysis cell electrode anode cathode",
        "galvanic_cell":        "galvanic cell zinc copper salt bridge electrochemistry",
        "titration":            "titration burette flask equivalence point",
        "crystallization":      "crystal formation crystallization chemistry",
        "distillation":         "distillation flask condenser laboratory",
        "benzene":              "benzene ring aromatic compound Kekule",
        "bond_ionic":           "ionic bond sodium chloride Na Cl crystal",
        "bond_covalent":        "covalent bond electron sharing molecule diagram",
        "hybridization":        "sp3 sp2 hybridization carbon orbitals",
        "activation_energy":    "activation energy reaction progress diagram Ea",
        "enthalpy":             "enthalpy diagram exothermic endothermic",
        "chromatography":       "paper chromatography separation spots",
        "polymer":              "polymer chain monomer plastic nylon",
        "nuclear_chemistry":    "radioactive decay alpha beta gamma",
        "test_tube":            "test tube reaction chemistry colour change",
        "bunsen_burner":        "Bunsen burner flame chemistry laboratory",
        "default":              "chemistry laboratory science flask",
    },

    # ── Mathematics ──────────────────────────────────────────────────────────
    "math": {
        "geometry":             "geometry shapes triangle circle polygon",
        "graph":                "mathematics graph function coordinate",
        "algebra":              "algebra equation variable expression",
        "statistics":           "statistics data graph bar chart pie",
        "trigonometry":         "trigonometry sine cosine unit circle",
        "calculus":             "calculus derivative integral graph",
        "number_theory":        "number theory prime factor divisibility",
        "probability":          "probability Venn diagram sample space",
        "sets":                 "set theory Venn diagram union intersection",
        "matrices":             "matrix determinant linear algebra",
        "vectors":              "vector addition physics mathematics arrow",
        "coordinate":           "coordinate geometry axes Cartesian plane",
        "default":              "mathematics education numbers formula",
    },

    # ── History ──────────────────────────────────────────────────────────────
    "history": {
        "ancient_india":        "ancient India Indus Valley civilization ruins",
        "medieval":             "medieval India Mughal fort palace architecture",
        "freedom_struggle":     "India independence freedom movement Gandhi",
        "world_war":            "World War map battlefield historical",
        "civilizations":        "ancient civilization Egypt Rome Greece ruins",
        "monuments":            "historical monument architecture India",
        "maps_historical":      "historical map ancient trade route",
        "constitution":         "Indian constitution assembly historic",
        "default":              "history ancient civilization artifacts",
    },

    # ── Geography ────────────────────────────────────────────────────────────
    "geography": {
        "india_map":            "India map states physical outline",
        "world_map":            "world map continents ocean countries",
        "landforms":            "landforms mountain valley plain glacier",
        "rivers":               "river delta meander oxbow lake",
        "climate":              "climate zones tropical temperate polar map",
        "soil":                 "soil types erosion agriculture India",
        "minerals":             "minerals mining ore geology rocks",
        "agriculture":          "agriculture crop farming field India",
        "population":           "population density map India",
        "natural_disaster":     "natural disaster earthquake volcano flood",
        "atmosphere":           "atmosphere layers stratosphere troposphere",
        "ocean":                "ocean current wave Pacific Atlantic",
        "default":              "geography map world nature",
    },

    # ── Civics / Political Science ────────────────────────────────────────────
    "polity": {
        "parliament":           "Indian Parliament Lok Sabha Rajya Sabha building",
        "constitution":         "Indian constitution preamble fundamental rights",
        "government":           "government structure legislative executive judiciary",
        "election":             "election voting ballot India democracy",
        "supreme_court":        "Supreme Court of India judiciary law",
        "president":            "President of India Rashtrapati Bhavan",
        "default":              "Indian government democracy parliament",
    },

    # ── Economics ────────────────────────────────────────────────────────────
    "economics": {
        "gdp":                  "GDP growth chart economy India",
        "supply_demand":        "supply demand curve economics graph",
        "inflation":            "inflation price rise cost of living",
        "budget":               "Union budget India government spending",
        "banking":              "banking RBI Reserve Bank India currency",
        "stock_market":         "stock market graph trading economy",
        "poverty":              "poverty development rural India",
        "trade":                "international trade export import",
        "default":              "economics business finance chart",
    },

    # ── Computer Science ─────────────────────────────────────────────────────
    "computer_science": {
        "programming":          "programming code computer software",
        "data_structures":      "data structure algorithm flowchart",
        "networking":           "computer network topology internet",
        "database":             "database SQL table rows columns",
        "operating_system":     "operating system process memory CPU",
        "artificial_intelligence": "artificial intelligence machine learning neural network",
        "circuit_digital":      "digital circuit logic gate binary",
        "default":              "computer science programming technology",
    },

    # ── Engineering (Degree) ──────────────────────────────────────────────────
    "engineering": {
        "thermodynamics":       "thermodynamics engine heat transfer",
        "fluid_mechanics":      "fluid mechanics pipe flow Bernoulli",
        "strength_materials":   "stress strain beam bending diagram",
        "circuit_theory":       "electrical circuit AC DC analysis",
        "digital_electronics":  "digital logic gate circuit VLSI",
        "machine_learning":     "machine learning neural network training",
        "default":              "engineering technology manufacturing",
    },

    # ── Medical (Degree) ─────────────────────────────────────────────────────
    "medical": {
        "anatomy":              "human anatomy body system diagram",
        "physiology":           "physiology organ function process",
        "pharmacology":         "drug medicine pharmacology molecular",
        "pathology":            "pathology disease tissue microscope",
        "microbiology":         "microbiology bacteria virus culture",
        "biochemistry":         "biochemistry enzyme protein structure",
        "default":              "medical science healthcare biology",
    },

    # ── Commerce / Accountancy ────────────────────────────────────────────────
    "commerce": {
        "accounting":           "accounting balance sheet ledger journal",
        "taxation":             "income tax GST India business",
        "business":             "business management strategy organization",
        "finance":              "finance investment return portfolio",
        "default":              "business commerce accounting finance",
    },

    # ── Reasoning (SSC/Banking) ───────────────────────────────────────────────
    "reasoning": {
        "analogy":              "analogy pattern relationship visual",
        "series":               "number letter series pattern sequence",
        "direction":            "compass direction north south east west",
        "blood_relation":       "family tree relationship diagram",
        "seating":              "seating arrangement circular linear",
        "coding":               "coding decoding cipher pattern",
        "syllogism":            "Venn diagram syllogism logic",
        "default":              "reasoning logic puzzle brain",
    },

    # ── English / Language ────────────────────────────────────────────────────
    "english": {
        "grammar":              "grammar parts of speech sentence structure",
        "vocabulary":           "vocabulary words dictionary English",
        "reading":              "reading comprehension passage book",
        "default":              "English language grammar learning",
    },

    # ── Environment / Ecology ─────────────────────────────────────────────────
    "environment": {
        "pollution":            "air water pollution environment",
        "climate_change":       "climate change global warming CO2",
        "biodiversity":         "biodiversity wildlife species conservation",
        "renewable_energy":     "solar wind renewable energy green",
        "deforestation":        "deforestation forest loss environment",
        "default":              "environment nature ecology conservation",
    },

    "default": {
        "default": "education science learning knowledge",
    },
}

# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def _key(name):
    return os.environ.get(name, "")


# ---------------------------------------------------------------------------
# Provider: Wikimedia Commons  (NO API KEY — CC-licensed scientific images)
# ---------------------------------------------------------------------------

def _wikimedia_image(query: str, cache_dir: str) -> str:
    """Search Wikimedia Commons for a CC-licensed image."""
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"wm:{query}", ".jpg")
    if os.path.exists(cached):
        return cached

    q   = urllib.parse.quote_plus(_safe_query(query))
    url = (
        "https://commons.wikimedia.org/w/api.php"
        f"?action=query&list=search&srsearch={q}&srnamespace=6"
        "&srlimit=5&format=json&origin=*"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        results = data.get("query", {}).get("search", [])
        if not results:
            return ""
        # Get image info for first result
        title = results[0]["title"]
        info_url = (
            "https://commons.wikimedia.org/w/api.php"
            f"?action=query&titles={urllib.parse.quote(title)}"
            "&prop=imageinfo&iiprop=url&format=json&origin=*"
        )
        with urllib.request.urlopen(info_url, timeout=8) as r:
            info = json.loads(r.read())
        pages = info.get("query", {}).get("pages", {})
        img_url = ""
        for page in pages.values():
            ii = page.get("imageinfo", [{}])
            img_url = ii[0].get("url", "") if ii else ""
            if img_url:
                break
        if not img_url:
            return ""
        # Only download image files (skip svg for simplicity, handle jpg/png/gif)
        ext = os.path.splitext(img_url)[-1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            return ""
        cached_real = _cache_path(cache_dir, f"wm:{query}", ext)
        with urllib.request.urlopen(img_url, timeout=20) as r:
            raw = r.read()
        with open(cached_real, "wb") as f:
            f.write(raw)
        log.info("free_media[wikimedia]: cached '%s' → %s", query, cached_real)
        return cached_real
    except Exception as e:
        log.debug("free_media[wikimedia]: failed '%s': %s", query, e)
        return ""


# ---------------------------------------------------------------------------
# Provider: Pixabay
# ---------------------------------------------------------------------------

def _pixabay_image(query: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"pxb_img:{query}", ".jpg")
    if os.path.exists(cached):
        return cached
    key = _key("PIXABAY_API_KEY")
    q   = urllib.parse.quote_plus(_safe_query(query))
    url = (
        f"https://pixabay.com/api/?key={key}&q={q}"
        "&image_type=photo&orientation=horizontal"
        "&safesearch=true&per_page=5&min_width=640"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        hits = data.get("hits", [])
        if not hits:
            return ""
        best    = max(hits, key=lambda h: h.get("imageWidth", 0))
        img_url = best.get("webformatURL") or best.get("largeImageURL", "")
        if not img_url:
            return ""
        with urllib.request.urlopen(img_url, timeout=15) as r:
            raw = r.read()
        with open(cached, "wb") as f:
            f.write(raw)
        log.info("free_media[pixabay]: cached img '%s'", query)
        return cached
    except Exception as e:
        log.debug("free_media[pixabay]: img failed '%s': %s", query, e)
        return ""


def _pixabay_video(query: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"pxb_vid:{query}", ".mp4")
    if os.path.exists(cached):
        return cached
    key = _key("PIXABAY_API_KEY")
    q   = urllib.parse.quote_plus(_safe_query(query))
    url = (
        f"https://pixabay.com/api/videos/?key={key}&q={q}"
        "&safesearch=true&per_page=5"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        hits = data.get("hits", [])
        if not hits:
            return ""
        hit    = hits[0]
        videos = hit.get("videos", {})
        vurl   = ""
        for qual in ("medium", "small", "large", "tiny"):
            vurl = videos.get(qual, {}).get("url", "")
            if vurl:
                break
        if not vurl:
            return ""
        with urllib.request.urlopen(vurl, timeout=60) as r:
            raw = r.read()
        with open(cached, "wb") as f:
            f.write(raw)
        log.info("free_media[pixabay]: cached vid '%s'", query)
        return cached
    except Exception as e:
        log.debug("free_media[pixabay]: vid failed '%s': %s", query, e)
        return ""


# ---------------------------------------------------------------------------
# Provider: Pexels  (free API key — pexels.com/api/)
# ---------------------------------------------------------------------------

def _pexels_image(query: str, cache_dir: str) -> str:
    api_key = _key("PEXELS_API_KEY")
    if not api_key:
        return ""
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"pex_img:{query}", ".jpg")
    if os.path.exists(cached):
        return cached
    q   = urllib.parse.quote_plus(_safe_query(query))
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/search?query={q}&per_page=5",
        headers={"Authorization": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        photos = data.get("photos", [])
        if not photos:
            return ""
        img_url = photos[0].get("src", {}).get("large", "")
        if not img_url:
            return ""
        with urllib.request.urlopen(img_url, timeout=15) as r:
            raw = r.read()
        with open(cached, "wb") as f:
            f.write(raw)
        log.info("free_media[pexels]: cached img '%s'", query)
        return cached
    except Exception as e:
        log.debug("free_media[pexels]: img failed '%s': %s", query, e)
        return ""


def _pexels_video(query: str, cache_dir: str) -> str:
    api_key = _key("PEXELS_API_KEY")
    if not api_key:
        return ""
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"pex_vid:{query}", ".mp4")
    if os.path.exists(cached):
        return cached
    q   = urllib.parse.quote_plus(_safe_query(query))
    req = urllib.request.Request(
        f"https://api.pexels.com/videos/search?query={q}&per_page=3",
        headers={"Authorization": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        videos = data.get("videos", [])
        if not videos:
            return ""
        # Pick smallest file for speed
        files  = videos[0].get("video_files", [])
        files  = sorted(files, key=lambda f: f.get("width", 9999))
        vurl   = files[0].get("link", "") if files else ""
        if not vurl:
            return ""
        with urllib.request.urlopen(vurl, timeout=60) as r:
            raw = r.read()
        with open(cached, "wb") as f:
            f.write(raw)
        log.info("free_media[pexels]: cached vid '%s'", query)
        return cached
    except Exception as e:
        log.debug("free_media[pexels]: vid failed '%s': %s", query, e)
        return ""


# ---------------------------------------------------------------------------
# Provider: Unsplash  (free API key — unsplash.com/developers)
# ---------------------------------------------------------------------------

def _unsplash_image(query: str, cache_dir: str) -> str:
    api_key = _key("UNSPLASH_API_KEY")
    if not api_key:
        return ""
    os.makedirs(cache_dir, exist_ok=True)
    cached = _cache_path(cache_dir, f"uns_img:{query}", ".jpg")
    if os.path.exists(cached):
        return cached
    q   = urllib.parse.quote_plus(_safe_query(query))
    req = urllib.request.Request(
        f"https://api.unsplash.com/search/photos?query={q}&per_page=5",
        headers={"Authorization": f"Client-ID {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        if not results:
            return ""
        img_url = results[0].get("urls", {}).get("regular", "")
        if not img_url:
            return ""
        with urllib.request.urlopen(img_url, timeout=15) as r:
            raw = r.read()
        with open(cached, "wb") as f:
            f.write(raw)
        log.info("free_media[unsplash]: cached '%s'", query)
        return cached
    except Exception as e:
        log.debug("free_media[unsplash]: failed '%s': %s", query, e)
        return ""


# ---------------------------------------------------------------------------
# Provider: Mixkit  (free video clips — no API key)
# ---------------------------------------------------------------------------

def _mixkit_video(query: str, cache_dir: str) -> str:
    """Mixkit doesn't have a public API — kept as placeholder for manual downloads.
    Returns "" always; user should manually download Mixkit clips and place in
    storage/assets/videos/ with descriptive filenames.
    """
    return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str, key: str, ext: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()[:16]
    return os.path.join(cache_dir, f"{h}{ext}")


def _safe_query(query: str) -> str:
    query = re.sub(r"[^a-zA-Z0-9 \-]", "", query)
    return query.strip()[:100]


def _default_cache(media_type: str) -> str:
    root = Path(__file__).parent.parent / "storage" / "assets"
    sub  = "videos" if media_type == "video" else "images"
    return str(root / sub)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_media(
    query: str,
    media_type: str = "image",     # "image" | "video"
    subject: str = "",
    topic_hint: str = "",
    cache_dir: str = "",
) -> str:
    """Resolve a free media file for the given query.

    Tries providers in priority order; returns first successful local path.
    All results are cached — each query downloads at most once.

    Args:
        query:      Search phrase (e.g. "animal cell biology microscope")
        media_type: "image" or "video"
        subject:    Subject key for hint expansion (e.g. "biology")
        topic_hint: Sub-topic key within subject hints (e.g. "cell")
        cache_dir:  Override local cache directory

    Returns:
        Absolute path to cached file, or "" if all providers fail.
    """
    if not cache_dir:
        cache_dir = _default_cache(media_type)

    # Expand short/generic queries via subject hint map
    if len(query.split()) <= 2:
        hints  = SUBJECT_HINTS.get(subject.lower(), SUBJECT_HINTS["default"])
        hint_q = hints.get(topic_hint, hints.get("default", query))
        if hint_q and hint_q != query:
            query = hint_q

    if media_type == "video":
        # Video provider chain: Pixabay → Pexels → (Mixkit manual)
        for fn in (_pixabay_video, _pexels_video):
            path = fn(query, cache_dir)
            if path:
                return path
        return ""

    # Image provider chain: Wikimedia → Pixabay → Pexels → Unsplash
    for fn in (_wikimedia_image, _pixabay_image, _pexels_image, _unsplash_image):
        path = fn(query, cache_dir)
        if path:
            return path
    return ""


def batch_prefetch(subject: str, cache_dir: str = "", media_type: str = "image") -> dict:
    """Pre-fetch all topic media for a subject. Returns {topic: path}."""
    results = {}
    hints   = SUBJECT_HINTS.get(subject.lower(), {})
    for topic, query in hints.items():
        if topic == "default":
            continue
        path = resolve_media(query, media_type, subject, topic, cache_dir)
        results[topic] = path
    return results
