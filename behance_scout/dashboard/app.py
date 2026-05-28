"""
FastAPI Dashboard для дизайнера
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))         # dashboard/ — для api_quota
sys.path.insert(0, str(Path(__file__).parent.parent))  # behance_scout/ — для database, config

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import json
import re
import logging
import api_quota
import database as db
from config import PAGE_SIZE, SCREENSHOTS_DIR

app = FastAPI(title="Behance Scout")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/projects")
async def get_projects(bucket: int = -1, page: int = 1):
    bucket_arg = None if bucket == -1 else bucket
    rows, total = db.get_pending_projects(bucket=bucket_arg, page=page, page_size=PAGE_SIZE)

    projects = []
    for r in rows:
        db.mark_shown(r["behance_id"])
        projects.append({
            "id":          r["behance_id"],
            "url":         r["behance_url"],
            "title":       r["title"] or "Untitled",
            "author":      r["author_name"] or "",
            "posted_at":   r["posted_at"] or "",
            "comment":     r["generated_comment"] or "",
            "comment_ru":  r["comment_ru"] or "",
            "screenshot":  f"/screenshots/{Path(r['screenshot_path']).name}" if r["screenshot_path"] else None,
            "bucket":      r["freshness_bucket"],
            "is_done":     r["is_done"],
        })

    _, c0 = db.get_pending_projects(bucket=0, page=1, page_size=1)
    _, c1 = db.get_pending_projects(bucket=1, page=1, page_size=1)
    _, c2 = db.get_pending_projects(bucket=2, page=1, page_size=1)

    return JSONResponse({
        "projects": projects,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "counts": {"0": c0, "1": c1, "2": c2, "all": c0 + c1 + c2},
    })


@app.post("/api/done/{behance_id}")
async def mark_done(behance_id: str):
    db.mark_done(behance_id)
    return {"ok": True}


@app.get("/api/stats/quota")
async def quota_stats():
    """Статистика использования API за сегодня (для индикатора в дашборде)."""
    return JSONResponse(api_quota.get_today_stats())


# ─────────────────────────────────────────────────────────
#  STRIPS PRO GEN — V46 Catalog
# ─────────────────────────────────────────────────────────

_STRIPS_CATALOG = """\
C1 (Design School): pick exactly 1 ID from 1-123.
  1=Post-Swiss Brutalism, 2=Alchemical Brutalism, 3=Tokyo Avant-Garde, 4=Monolithic Architecture,
  5=Kinetic Data Mapping, 6=Clinical Transhumanism, 7=Systemic Constructivism, 8=Haute Viticulture,
  9=Aerospace Brutalism, 10=Optical Supremacy, 11=Structural Brutalism, 12=Tactile Dissonance,
  13=Deep Sea Pressure Metrics, 14=Financial Cybernetics, 15=Thermal Industrial, 16=Cryptographic Grid,
  17=Aerodynamic Stealth, 18=Molecular Olfactory, 19=Clinical Genomics, 20=Carbon Nano-Topography,
  23=Neural Brutalism, 24=Orbital Brutalism, 26=Forensic Minimalism, 27=Algorithmic Atrophy,
  32=Tectonic Deconstruction, 37=Cybernetic Typography, 40=Radiographic Minimalism,
  41=Bauhaus Grid, 42=Dieter Rams Functionalist, 43=Massimo Vignelli, 44=Wim Crouwel,
  45=Muller-Brockmann Objective Grid, 46=Ulm School, 47=Japanese Metabolism,
  48=Tadao Ando Concrete, 50=Carlo Scarpa, 51=Brutalist Cartography, 52=Archival Bureaucracy,
  53=Forensic Typography, 54=Archival Microfilm Grid, 55=Stratigraphic Layout, 56=Lexical Brutalism,
  57=Typographic Seismology, 58=Post-Digital Print, 59=Dictionary Supremacy, 60=Analog Indexing,
  81=Zero-Gravity Brutalism, 82=Aerospace Schematic, 83=Ballistic Geometry, 84=Deep-Space UI,
  85=Sub-Oceanic Topography, 91=Hyper-Rationalism, 92=Algorithmic Swiss, 93=Parametric Brutalism,
  94=Deconstructive Typography, 95=Orthogonal Supremacy, 100=Theoretical Physics UI,
  101=Swiss International, 102=Russian Constructivism, 103=Italian Futurism, 104=Neo-Brutalism,
  105=Deconstructivism, 107=Paula Scher Dynamic Typography, 108=Herb Lubalin Ligatures,
  110=Neville Brody Deconstructive, 111=Emil Ruder Typographic Rhythm, 112=Parametric Design,
  113=Biopunk Organic, 114=Cassette Futurism, 115=Cyber-Noir, 116=Tech-Wear, 118=Controlled Glitch,
  119=Anti-Design, 120=Absolute Void, 121=Tactile Skeuomorph, 122=DOS Terminal, 123=3D Wireframe

C2 (Aesthetic DNA mix): pick 2-4 IDs from 1-120.
  1=Fine Horology, 2=Data Logistics, 3=Surgical Steel, 4=Biohacking Cybernetics, 5=Michelin Gastronomy,
  7=Grand Cru Wine, 9=Orbital Aerospace, 10=Stealth Luxury, 11=Concrete Architecture, 12=Haute Couture,
  13=Quantum Laboratory, 14=Old Money Wealth, 15=F1 Carbon Telemetry, 16=Niche Perfume Packaging,
  17=Abyssal Submersibles, 18=Cryptographic Security, 19=Heavy Smelting, 20=Art Gallery Curation,
  22=DNA Sequencing Biotech, 23=Precision Optics, 27=Analog Vinyl, 28=Neural Networks,
  29=Cockpit Avionics, 31=Server Racks, 34=Molecular Gastronomy, 39=Absolute Zero Cryogenics,
  40=Skeleton Watchmaking, 56=Deep-Sea Data Cables, 62=Vintage Printing Press, 65=Architectural Models,
  71=Bespoke Tailoring, 75=Fine Fragrance Distillation, 79=Haute Horlogerie Assembly,
  81=Forensic Toxicology Lab, 82=Carbon Dating Lab, 87=Cryonic Preservation, 88=Biometric Iris Scanners,
  91=Wind Tunnel Testing, 92=Lunar Module Avionics, 93=Stealth Bomber Hull, 96=Nuclear Reactor Core,
  100=Hypersonic Wind Blades, 101=Particle Accelerator, 104=Quantum Processor Core,
  111=Archival Microfiche, 117=Geological Strata Core, 119=Submarine Sonar Array, 120=Bank Vault Schematics

C3 (3-Color Palette): pick exactly 1 ID from 1-60.
  1=Vantablack+White+SafetyOrange, 2=Graphite+Bone+Cyan, 3=Navy+Silver+NeonYellow,
  4=Charcoal+Ash+Crimson, 5=Concrete+White+Ultramarine, 6=PitchBlack+Chrome+Mint,
  7=Olive+Sand+HazardYellow, 8=Midnight+Gold+White, 9=Tungsten+White+OpticGreen,
  10=Umber+Ivory+DigitalCyan, 14=Lead+White+ToxicGreen, 15=Black+PaleGold+Burgundy,
  17=Obsidian+Chrome+Violet, 20=Vantablack+OffWhite+AcidNeon, 23=MatteBlack+Brass+White,
  25=Asphalt+SafetyOrange+White, 26=Blueprint+White+Red, 43=SurgicalGreen+IodineAmber+Titanium,
  49=AbyssalBlue+BiolumGreen+Basalt, 55=KevlarYellow+Gunmetal+Aviation Orange,
  56=MilitaryOlive+CarbonFiber+CrimsonTracer, 58=ThermalBlue+HeatmapRed+VoidBlack,
  59=SiliconWaferGreen+TechGold+MatteBlack

C4 (Color Rotation): pick exactly 1 ID from 1-20.
  1=80/15/5 rotation, 2=70/20/10 rotation, 3=60/30/10 shift,
  4=FirstBase dominant+flashes, 5=Dark Rhythm gradient, 6=Third Base ascension,
  7=Twins+Antipodes, 10=Isolation vs Triad explosion, 14=FirstBase fade-out, 16=85/10/5 rotation,
  20=Total Asymmetry

C5 (Layout Structure): pick exactly 1 ID from 1-60.
  1=Aggressive Typography Overlap, 2=Hyper-Dense Tetris Grid, 3=Fractured Central Axis,
  4=Edge-to-Edge Text Monolith, 5=Extreme Marginalia, 7=Financial Newspaper Layout,
  8=Radial Typography Explosion, 10=45deg Diagonal Grid, 11=Golden Ratio, 15=Macro-Micro Collision,
  19=Industrial Index Board, 21=Bauhaus 12-column, 25=Technical Manual Layout,
  37=Architectural Blueprint Grid, 44=Periodic Table Matrix, 45=Telemetry Dashboard,
  55=Dual-Axis Split Screen, 58=Overlapping Floating Panels, 60=Raw Wireframe Mesh

C6 (Graphics & Marking): pick 2-4 IDs from 1-60.
  1=EAN-13 Barcodes, 2=Military Radar Sweep, 3=Vector Field Arrows, 5=Thermal Heatmaps,
  7=X-Ray Vector Scans, 8=Pharmaceutical Labels, 9=Topographical Contour Lines,
  11=Voronoi Lattice, 12=Server IP Routing, 13=Moire Interference, 14=Financial Ticker Tape,
  15=Circuit Board Traces, 17=Sonogram Waveforms, 19=Algorithmic Particle Swarms,
  20=F1 Telemetry UI, 22=Serialized Numbers, 25=Orbital Trajectories, 27=Exploded Views,
  28=Aerospace Warning Decals, 34=HAZMAT Placards, 39=Magnetic Field Lines,
  43=Anatomical Cross-Sections, 46=Seismograph Readouts, 48=Sonar Bathymetry,
  54=Satellite Trajectory Vectors, 59=Bio-metric Security Scans, 60=Void Sealing Markings

C7 (Super-Graphics text): pick exactly 1 ID from 1-30.
  1=SL2024/Logistics, 2=SOMA/Biohacking, 3=MOLECULA/Alchemy, 4=VELVET/Wine,
  5=NEURAL ARCHIVE/Networks, 6=AURA/Architecture, 7=OBSIDIAN VAULT/Finance,
  8=KINETIC/Robotics, 9=CHRONOS/Aerospace, 10=LUMINA/Photonics, 11=TECTONIC/Engineering,
  13=ABYSSAL/Ocean, 14=PRAXIS/Trading, 15=HELIOS/Energy, 16=AEGIS/Cyber,
  17=VANGUARD/Motorsport, 18=METRIC NOIR/Perfume, 19=APEX/Biotech, 20=QUANTUM/Nanotech,
  21=BAUHAUS/1919, 24=OPTICS/Aperture, 28=HOROLOGY/Watchmaking, 29=CLINIC/Surgery

C8 (Material & Print technique): pick exactly 1 ID from 1-20.
  1=Blind Emboss 800gsm Cotton, 2=Spot UV+Matte Black Cardboard, 3=Metallic Pantone+Parchment,
  4=Hot Enamel+Basalt Paper, 5=Laser Micro-Perforation+Tyvek, 6=Laser Ablation+Charcoal Paper,
  7=Iridescent Holographic Foil, 8=Raised Silkscreen+Cold Press, 9=Heavy Letterpress,
  11=24k Gold Leaf Gilding, 12=Inside-Glass Laser Engraving, 14=Phosphorescent Glow Pigment,
  17=Black Diamond Dust Inlay, 18=Optically Clear Resin Domes, 20=CNC Wax Seal Stamps

C9 (Camera & Optics — LENS TYPE ONLY, not lighting): pick exactly 1 ID from 1-20.
  1=Macro 100mm f/2.8, 2=Tilt-Shift 24mm architectural, 3=Ultra-Wide 14mm,
  4=Drone Top-Down Orthographic, 5=50mm Prime, 6=85mm Portrait, 7=Telephoto 200mm,
  8=Fisheye 8mm extreme distortion, 9=Large Format 8x10 vintage,
  10=Scanning Electron Microscope SEM, 11=FLIR Thermal Imaging Camera,
  12=Medical X-Ray Scanner, 13=Satellite Topography Camera, 14=Micro-Endoscope fiber optic,
  15=Deep-Sea Submersible Pressure Camera, 16=Pinhole lo-fi, 17=CCTV Security grainy,
  18=Dashboard Dashcam wide-angle, 19=Phantom High-Speed motion capture,
  20=LiDAR 3D point-cloud scanner

C10 (Trigger Focus — disrupts ONE element): pick exactly 1 ID from 1-60.
  1=Colossal Geometric Block, 2=Harsh Vector Slice, 3=Vibrant Marker Redaction Slash,
  4=Void-Like Perfect Black Circle, 9=Geometric Chevron Hazard Banner,
  11=Circular Certification Stamp, 12=Heavy Blackout Redaction Bar,
  15=Blown-Out Halftone Dot, 16=Barcode Stretched to Infinity, 17=Massive Unreadable Letterform,
  19=Sniper Reticle Target, 21=Red Wax Seal, 25=Masking Tape Covering Data,
  29=QC Rubber Stamp, 30=Deep Metal Scratch, 31=Harsh Physical Crease, 32=Dog-Eared Corner,
  33=Archival Binding Thread, 34=Deeply Embossed Notary Seal, 37=Torn Inventory Sticker,
  38=Typewriter Strike-Through Redaction, 42=Intrusive Crop Marks,
  43=Over-Inked Bleeding Letterpress, 48=Die-Cut Geometric Void, 50=Rough Deckled Paper Edge,
  51=Shard of Glass Refracting, 54=Precise Laser Scorch Circle, 55=Faraday Copper Mesh Tear,
  58=Scalpel Surgical Slit, 60=Silicone Industrial Plug

C11 (Light & Atmosphere — SEPARATE FROM C9, lighting setup only): pick exactly 1 ID from 1-20.
  1=Slit-Scan Laser, 2=Gobo Shadow Projections, 3=Ring Flash Pop-Art Shadows,
  4=Sterile Shadowless Softbox, 5=Cinematic Edge-Lit Rim Lighting,
  6=HMI Projector with Optical Snoot, 7=Low-Key Chiaroscuro Renaissance,
  8=Warm Tungsten Studio Spotlights, 9=UV Blacklight Fluorescent,
  10=Harsh Golden Hour Sunlight, 11=Ophthalmic Slit-Lamp Bio-Microscope,
  12=Direct Paparazzi Flash blown-out, 13=Extreme Raking Slanted Light,
  14=Sub-Aquatic Caustics through rippling water, 15=Practical Neon Tube harsh colors,
  16=Diffused White Light Tent e-commerce, 17=Sterile Medical Lightbox backlight,
  18=Heavy Overcast Flat Daylight, 19=Volumetric God Rays atmospheric,
  20=Emergency Rotating Red Strobe Lights
"""


@app.get("/strips", response_class=HTMLResponse)
async def strips_page():
    html_path = Path(__file__).parent / "templates" / "strips.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────
#  STRIPS DB EDITOR — API и страница редактора базы кнопок
# ─────────────────────────────────────────────────────────

_CATS_DB   = Path(__file__).parent / "data" / "categories_db.json"
_STRIPS_HTML = Path(__file__).parent / "templates" / "strips.html"
_CAT_START = "// [[CATEGORIES_START]]"
_CAT_END   = "// [[CATEGORIES_END]]"


@app.get("/strips-db/editor", response_class=HTMLResponse)
async def strips_db_editor():
    """Страница редактора базы кнопок."""
    html_path = Path(__file__).parent / "templates" / "strips_admin.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/strips-db/categories")
async def categories_get():
    """Возвращает текущую базу категорий из JSON-файла на сервере."""
    if not _CATS_DB.exists():
        return JSONResponse({"error": "categories_db.json not found"}, status_code=404)
    return JSONResponse(json.loads(_CATS_DB.read_text(encoding="utf-8")))


@app.post("/strips-db/update")
async def categories_update(request: Request):
    """
    Сохраняет отредактированную базу категорий на диск.
    Тело запроса: полный JSON объект CATEGORIES.
    """
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    # Базовая валидация структуры
    if not isinstance(data, dict):
        return JSONResponse({"error": "Root must be an object"}, status_code=400)
    for key, cat in data.items():
        if not isinstance(cat, dict) or "items" not in cat:
            return JSONResponse(
                {"error": f"Category '{key}' must have 'items' array"}, status_code=400
            )
        if not isinstance(cat["items"], list):
            return JSONResponse(
                {"error": f"Category '{key}'.items must be an array"}, status_code=400
            )

    # Atomic write: сначала во temp, потом rename
    _CATS_DB.parent.mkdir(exist_ok=True)
    tmp = _CATS_DB.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_CATS_DB)

    total = sum(len(c.get("items", [])) for c in data.values())
    logging.info(f"[DB Editor] Saved categories_db.json: {len(data)} cats, {total} items")
    return JSONResponse({"status": "ok", "categories": len(data), "total_items": total})


@app.post("/strips-db/bake")
async def categories_bake():
    """
    Запекает текущую categories_db.json обратно в strips.html.
    Заменяет блок между маркерами [[CATEGORIES_START]] и [[CATEGORIES_END]].
    Создаёт бэкап strips.html.bak перед записью.
    """
    if not _CATS_DB.exists():
        return JSONResponse({"error": "categories_db.json not found"}, status_code=404)

    cats = json.loads(_CATS_DB.read_text(encoding="utf-8"))
    html = _STRIPS_HTML.read_text(encoding="utf-8")

    # Проверяем маркеры
    if _CAT_START not in html or _CAT_END not in html:
        return JSONResponse(
            {"error": "Markers [[CATEGORIES_START]] / [[CATEGORIES_END]] not found in strips.html"},
            status_code=500
        )

    # Генерируем JS-блок из Python dict
    js_lines = ["const CATEGORIES = {"]
    cat_keys = list(cats.keys())
    for i, cid in enumerate(cat_keys):
        cat = cats[cid]
        comma = "," if i < len(cat_keys) - 1 else ""
        title = json.dumps(cat.get("title", ""), ensure_ascii=False)
        items_js = _items_to_js(cat.get("items", []))
        js_lines.append(f"  {cid}: {{")
        js_lines.append(f"    title: {title},")
        js_lines.append(f"    items: [{items_js}]")
        js_lines.append(f"  }}{comma}")
    js_lines.append("};")
    js_block = "\n".join(js_lines)

    # Бэкап
    bak = _STRIPS_HTML.with_suffix(".html.bak")
    bak.write_text(html, encoding="utf-8")

    # Замена блока между маркерами
    s_idx = html.index(_CAT_START)
    e_idx = html.index(_CAT_END) + len(_CAT_END)
    new_html = html[:s_idx] + _CAT_START + "\n" + js_block + "\n" + _CAT_END + html[e_idx:]

    # Atomic write
    tmp = _STRIPS_HTML.with_suffix(".html.tmp")
    tmp.write_text(new_html, encoding="utf-8")
    tmp.replace(_STRIPS_HTML)

    logging.info(f"[DB Editor] Baked categories_db.json into strips.html")
    return JSONResponse({"status": "ok", "backup": str(bak.name)})


def _items_to_js(items: list) -> str:
    """Конвертирует список items Python -> JS-строку для вставки в strips.html."""
    parts = []
    for item in items:
        fields = []
        for k, v in item.items():
            if isinstance(v, str):
                # Экранируем одиночные кавычки для JS
                escaped = v.replace("\\", "\\\\").replace("'", "\\'")
                fields.append(f"      {k}: '{escaped}'")
            elif isinstance(v, (int, float, bool)):
                fields.append(f"      {k}: {json.dumps(v)}")
            elif isinstance(v, list):
                inner = ", ".join(json.dumps(x, ensure_ascii=False) for x in v)
                fields.append(f"      {k}: [{inner}]")
            elif isinstance(v, dict):
                inner_parts = []
                for dk, dv in v.items():
                    if isinstance(dv, str):
                        escaped = dv.replace("\\", "\\\\").replace("'", "\\'")
                        inner_parts.append(f"        {dk}: '{escaped}'")
                    else:
                        inner_parts.append(f"        {dk}: {json.dumps(dv, ensure_ascii=False)}")
                fields.append(f"      {k}: {{\n" + ",\n".join(inner_parts) + "\n      }")
        parts.append("    {\n" + ",\n".join(fields) + "\n    }")
    return "\n" + ",\n".join(parts) + "\n  "


@app.post("/api/strips/ai")
async def strips_ai(request: Request):
    """
    AI-генерация параметров Strips Pro Gen V45.
    Каскад: OpenRouter free models → DNA router fallback.
    """
    from config import CRITIC_API_KEY, LLM_API_BASE, LLM_API_KEY, OPENROUTER_API_BASE, OPENROUTER_API_KEY

    OR_KEY = OPENROUTER_API_KEY or CRITIC_API_KEY  # Используем первый доступный ключ
    PROVIDERS = [
        # Новые бесплатные модели 2025-2026 (приоритет)
        (OPENROUTER_API_BASE, OR_KEY, "openai/gpt-oss-20b:free"),
        (OPENROUTER_API_BASE, OR_KEY, "z-ai/glm-4.5-air:free"),
        (OPENROUTER_API_BASE, OR_KEY, "qwen/qwen3-coder-480b-a35b:free"),
        # Старые free-модели как fallback
        (OPENROUTER_API_BASE, OR_KEY, "google/gemma-3-27b-it:free"),
        (OPENROUTER_API_BASE, OR_KEY, "meta-llama/llama-3.1-8b-instruct:free"),
        (OPENROUTER_API_BASE, OR_KEY, "mistralai/mistral-7b-instruct:free"),
        # DNA-роутер как последний резерв
        (LLM_API_BASE, LLM_API_KEY, "deepseek-ai/DeepSeek-V3.2"),
        (LLM_API_BASE, LLM_API_KEY, "Qwen/Qwen2.5-72B-Instruct"),
    ]

    try:
        body = await request.json()
        concept = body.get("concept", "").strip()
        if not concept:
            return JSONResponse({"error": "No concept provided"}, status_code=400)

        system_prompt = (
            "You are an elite art director AI for a design studio. "
            "Select design parameters based on the user's concept description.\n\n"
            f"CATALOG (pick item IDs per category):\n{_STRIPS_CATALOG}\n\n"
            "OUTPUT FORMAT: Respond with ONLY a single valid JSON object. "
            'Keys = category IDs as strings "1" through "11" (11 categories total). '
            "Values = arrays of integer item IDs. No explanation, no markdown, JSON only.\n"
            'Example: {"1":[3],"2":[5,12],"3":[7],"4":[2],"5":[14],"6":[8,22],"7":[4],"8":[11],"9":[6],"10":[17],"11":[3]}'
        )
        user_msg = f"Design concept: {concept}\n\nReturn JSON only."

        last_error = None
        for api_base, api_key, model in PROVIDERS:
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    resp = await client.post(
                        f"{api_base}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user",   "content": user_msg},
                            ],
                            "max_tokens": 350,
                            "temperature": 0.7,
                        }
                    )
                    resp.raise_for_status()
            except Exception as e:
                last_error = e
                logging.warning(f"[Strips AI] {model} request failed: {repr(e)}")
                continue

            try:
                data = resp.json()
            except Exception:
                raw = resp.text[:300] or "[empty body]"
                last_error = ValueError(f"Non-JSON body from {model}: {raw}")
                logging.warning(f"[Strips AI] {model} non-JSON: {raw}")
                api_quota.log_call("strips_ai", model, success=False)
                continue

            text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not text:
                last_error = ValueError(f"{model} empty content. data={data}")
                logging.warning(f"[Strips AI] {model} empty content")
                api_quota.log_call("strips_ai", model, success=False)
                continue

            clean = re.sub(r"```[a-z]*\n?", "", text).strip()
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                result = json.loads(match.group())
                logging.info(f"[Strips AI] OK via {model}")
                api_quota.log_call("strips_ai", model, success=True)
                return JSONResponse(result)

            last_error = ValueError(f"No JSON in {model} response: {text[:150]}")
            logging.warning(f"[Strips AI] {model} no JSON: {text[:200]}")

        return JSONResponse(
            {"error": f"All models failed. Last: {repr(last_error)}"},
            status_code=500
        )

    except Exception as e:
        logging.exception("[Strips AI] Unexpected error")
        return JSONResponse({"error": repr(e)}, status_code=500)
