"""Tema visual del portal admin — dirección «A · Claro con barra lateral».

Todo lo visual vive aquí: paleta, CSS, barra lateral y las piezas pequeñas que se repiten
(pastillas de estado, avatar, migas de pan). `main.py` solo llama a estas funciones, de modo
que cambiar el aspecto del portal no obliga a tocar la lógica de las páginas.

Uso típico en una página:

    await theme.shell("resumen", tenant_id=tenant_id)   # barra lateral + tema
    theme.sub_header(tenant, tenant_id, "Productos")     # migas de pan + título
"""

from __future__ import annotations

import unicodedata

from nicegui import app, ui

from app import api

# ─── Paleta ───────────────────────────────────────────────────────────────────
# Los colores de estado están oscurecidos a propósito: el texto blanco sobre ellos
# (botones `unelevated`) y el texto sobre las pastillas suaves superan 4.5:1.
PRIMARY = "#1D4ED8"

# Opción 1 (2026-11-04): «Productos» muestra también las existencias de cada producto por
# ubicación y lote, así que «Stock» sale del menú. La página /tenants/{id}/stock sigue
# existiendo intacta: poner True para volver a mostrarla en el menú.
SHOW_STOCK_PAGE = False

_ROLE_LABELS = {
    "super_admin": "Super admin",
    "tenant_admin": "Admin del tenant",
}

_MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Tonos de las baldosas de categoría: fondo suave + tinta oscura, misma luminosidad entre sí
# para que ninguno grite más que otro. Se evitan verde y rojo, que ya significan estado.
_CATEGORY_TINTS = [
    ("#E7EDFC", "#1B44B5"),  # azul
    ("#DDF3F0", "#0F6B5F"),  # verde azulado
    ("#FBEBD0", "#7A4300"),  # ámbar
    ("#EEE8FB", "#5B3BB5"),  # violeta
    ("#E0F0FB", "#0B5A8A"),  # celeste
]
_NO_CATEGORY_TINT = ("#ECEEF2", "#3A4352")

# Ícono por palabra clave del nombre de la categoría (sin tildes, en minúsculas).
# Lo que no encaje usa una etiqueta genérica.
_CATEGORY_ICONS = [
    ("aceite", "water_drop"),
    ("lubric", "water_drop"),
    ("bateri", "battery_charging_full"),
    ("electri", "bolt"),
    ("filtro", "filter_alt"),
    ("freno", "album"),
    ("llanta", "trip_origin"),
    ("neumat", "trip_origin"),
    ("herramient", "handyman"),
    ("repuesto", "settings"),
    ("motor", "settings"),
    ("suspension", "compress"),
    ("luz", "lightbulb"),
    ("luces", "lightbulb"),
    ("accesori", "auto_awesome"),
]
NO_CATEGORY = "Sin Categoría"

# Los campos de los formularios se dibujan con contorno en todo el portal.
for _cls in (ui.input, ui.select, ui.textarea, ui.number):
    _cls.default_props("outlined")

_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --mn-ground: #F4F5F7;
  --mn-surface: #FFFFFF;
  --mn-line: #E3E6EB;
  --mn-line-strong: #D5D9E0;
  --mn-text: #151922;
  --mn-ink-2: #3A4352;
  --mn-muted: #566070;
  --mn-primary: #1D4ED8;
  --mn-primary-soft: #E7EDFC;
  --mn-primary-ink: #1B44B5;
  --mn-ok-bg: #DDF4E7;
  --mn-ok-ink: #11633A;
  --mn-ok-dot: #1E9E5A;
  --mn-off-bg: #ECEEF2;
  --mn-off-ink: #3A4352;
  --mn-off-dot: #7B8494;
}

body, .q-layout, .q-page-container, .q-page {
  font-family: 'Figtree', system-ui, sans-serif;
  color: var(--mn-text);
  background: var(--mn-ground);
}

/* Contenedor de página: ancho cómodo y centrado */
.nicegui-content {
  width: 100%;
  max-width: 1180px;
  margin: 0;
  padding: 32px 40px 56px;
  gap: 24px;
}
@media (max-width: 640px) { .nicegui-content { padding: 20px 16px 40px; } }

/* Tipografía */
.mn-h1 { font-size: 28px; line-height: 1.2; font-weight: 700; letter-spacing: -0.015em; }
.mn-h2 { font-size: 16px; font-weight: 600; }
.mn-muted { color: var(--mn-muted); }
.mn-mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
.mn-label {
  font-size: 12px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: var(--mn-muted);
}

/* Tarjetas */
.q-card { border-radius: 14px; box-shadow: none !important; border: 1px solid var(--mn-line); }
.q-dialog .q-card {
  border: 0;
  box-shadow: 0 24px 60px rgba(15, 23, 42, .22) !important;
  max-width: calc(100vw - 32px);
}
.mn-card { padding: 0 !important; gap: 0 !important; overflow: hidden; }
.mn-card-head {
  width: 100%; display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: 12px; padding: 16px 24px;
}
.mn-card-body { width: 100%; padding: 20px 24px 24px; border-top: 1px solid var(--mn-line); }
.mn-count {
  font-size: 12px; font-weight: 600; background: var(--mn-off-bg);
  color: var(--mn-off-ink); border-radius: 999px; padding: 2px 8px;
}

/* Pastillas (plan, estado, origen) */
.mn-pill {
  display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 10px;
  border-radius: 999px; font-size: 12px; font-weight: 600; letter-spacing: .02em;
  background: var(--mn-off-bg); color: var(--mn-off-ink); white-space: nowrap;
}
.mn-pill--ok { background: var(--mn-ok-bg); color: var(--mn-ok-ink); }
.mn-pill--pro { background: var(--mn-primary-soft); color: var(--mn-primary-ink); }
.mn-pill--enterprise { background: #FBEBD0; color: #7A4300; }
.mn-dot { width: 6px; height: 6px; border-radius: 999px; background: var(--mn-off-dot); }
.mn-pill--ok .mn-dot { background: var(--mn-ok-dot); }
.mn-chip {
  display: inline-flex; align-items: center; height: 24px; padding: 0 8px; border-radius: 6px;
  background: #fff; border: 1px solid var(--mn-line-strong); color: var(--mn-ink-2);
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11.5px;
}
.mn-avatar {
  display: flex; align-items: center; justify-content: center; flex: none;
  background: var(--mn-primary-soft); color: var(--mn-primary-ink); font-weight: 700;
}

/* Barra lateral */
.mn-drawer { background: #fff !important; }
.mn-brand { display: flex; align-items: center; gap: 12px; padding: 0 8px; text-decoration: none !important; color: var(--mn-text) !important; }
.mn-logo {
  width: 36px; height: 36px; border-radius: 10px; background: var(--mn-primary); color: #fff;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.mn-brand-name { font-weight: 700; font-size: 17px; letter-spacing: -0.01em; line-height: 1.25; }
.mn-brand-sub { font-size: 12px; color: var(--mn-muted); line-height: 1.25; }
.mn-nav {
  display: flex; align-items: center; gap: 12px; width: 100%; min-height: 44px; padding: 0 12px;
  border-radius: 10px; color: var(--mn-ink-2) !important; font-weight: 500;
  text-decoration: none !important; cursor: pointer;
}
.mn-nav:hover { background: #F0F2F6; }
.mn-nav--active { background: var(--mn-primary-soft) !important; color: var(--mn-primary-ink) !important; font-weight: 600; }
.mn-nav--active:hover { background: #DCE5FB !important; }
.mn-nav--muted { color: var(--mn-muted) !important; }
/* «Salir» es un <button> nativo con el aspecto de un ítem de menú */
button.mn-nav { border: 0; background: transparent; font: inherit; font-weight: 500; text-align: left; }
.mn-tenant-chip {
  display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--mn-line);
  border-radius: 12px; background: #FAFBFC;
}
.mn-topbar {
  background: #fff !important; color: var(--mn-text) !important;
  border-bottom: 1px solid var(--mn-line); box-shadow: none !important;
}

/* Migas de pan */
.mn-crumb { color: var(--mn-muted) !important; text-decoration: none !important; }
.mn-crumb:hover { color: var(--mn-text) !important; }

/* Botones: sin mayúsculas forzadas y con área táctil cómoda */
.q-btn { border-radius: 10px; text-transform: none; font-weight: 600; letter-spacing: 0; }
.q-btn.q-btn--round { border-radius: 50%; }
.q-btn:not(.q-btn--round):not(.q-btn--dense) { min-height: 44px; padding: 0 18px; }
a:focus-visible, .q-btn:focus-visible { outline: 2px solid var(--mn-primary); outline-offset: 2px; }

/* Campos */
.q-field--outlined .q-field__control { border-radius: 10px; }

/* Tablas */
.q-table__container {
  border: 1px solid var(--mn-line); border-radius: 14px; box-shadow: none !important; background: #fff;
}
.q-table thead tr { background: #FAFBFC; }
.q-table thead th {
  font-size: 12px !important; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: var(--mn-muted);
}
.q-table tbody td { font-size: 14px; height: 60px; }
.q-table tbody tr:hover td { background: #F8F9FB; }
.mn-card .q-table__container,
.q-expansion-item .q-table__container { border: 0; border-top: 1px solid var(--mn-line); border-radius: 0; }
.mn-tenant-link { display: flex; align-items: center; gap: 12px; text-decoration: none; color: var(--mn-text); }
.mn-tenant-text { display: flex; flex-direction: column; line-height: 1.35; }
.mn-tenant-name { font-weight: 600; }
.mn-tenant-slug { font-size: 12.5px; color: var(--mn-muted); }

/* Productos: desglose de existencias por ubicación y lote (fila expandible) */
.q-table tbody tr.mn-locs-tr:hover td { background: #fff; }
.q-table tbody td.mn-locs-cell { height: auto; padding: 0 20px 16px; background: #fff; white-space: normal; }
.mn-locs { border: 1px solid var(--mn-line); border-radius: 12px; background: #FAFBFC; overflow-x: auto; }
.mn-loc {
  display: grid; align-items: center; gap: 12px; padding: 4px 16px;
  grid-template-columns: minmax(0,1.1fr) minmax(0,1.5fr) minmax(0,1.1fr) minmax(0,1fr) minmax(0,1.1fr) minmax(0,.65fr) minmax(0,.8fr) minmax(0,.85fr) 48px;
  border-top: 1px solid var(--mn-line); background: #fff; font-size: 14px; min-height: 52px; min-width: 780px;
}
.mn-loc--head {
  border-top: 0; background: #FAFBFC; min-height: 0; padding: 10px 16px;
  font-size: 11.5px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--mn-ink-2);
}
.mn-loc .num { text-align: right; }
.mn-loc .sub { display: block; font-size: 12px; line-height: 1.3; color: var(--mn-muted); overflow-wrap: anywhere; }
/* Los códigos (lote, estante, almacén) no se parten a mitad de línea */
.mn-loc .mn-mono { white-space: nowrap; }
.mn-loc .avail { text-align: right; font-weight: 600; color: var(--mn-ok-ink); }
.mn-locs-empty { padding: 16px; color: var(--mn-muted); }

/* Secciones colapsables (productos agrupados por categoría) */
.q-expansion-item {
  background: #fff; border: 1px solid var(--mn-line); border-radius: 14px;
  overflow: hidden; box-shadow: none !important;
}
.q-expansion-item .q-item { min-height: 56px; font-weight: 600; }
.q-expansion-item .q-item:has(.mn-cat-head) { min-height: 68px; padding: 12px 20px; }
.mn-cat-icon {
  width: 42px; height: 42px; border-radius: 12px; flex: none;
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 0 1px rgba(21, 25, 34, .05);
}
.mn-cat-name { font-size: 15px; font-weight: 600; color: var(--mn-text); }
/* Sin margen interno: las tablas de dentro llegan al borde de la tarjeta y ganan ancho */
.q-expansion-item .nicegui-expansion-content { padding: 0; }
/* «Revocadas» vive dentro de la tarjeta de API Keys: sin caja propia, solo un filo superior */
.q-expansion-item.mn-revoked { border: 0; border-top: 1px solid var(--mn-line); border-radius: 0; }
.q-expansion-item.mn-revoked > div > .q-item { color: var(--mn-muted); }

/* Lista de API keys */
.mn-key { padding: 18px 24px; border-top: 1px solid var(--mn-line); }
.mn-key--off { opacity: .65; }
.mn-key-icon {
  width: 40px; height: 40px; border-radius: 10px; background: var(--mn-primary-soft);
  color: var(--mn-primary-ink); display: flex; align-items: center; justify-content: center; flex: none;
}
</style>
"""


# ─── Formato ──────────────────────────────────────────────────────────────────

def fmt_date(iso: str | None) -> str:
    """'2026-05-11T16:29:39' → '11 may 2026'."""
    if not iso:
        return "—"
    try:
        return f"{int(iso[8:10])} {_MONTHS[int(iso[5:7]) - 1]} {int(iso[0:4])}"
    except (ValueError, IndexError):
        return iso[:10]


def fmt_datetime(iso: str | None) -> str:
    """'2026-05-11T16:29:39' → '11 may 2026, 16:29'."""
    if not iso:
        return "—"
    return f"{fmt_date(iso)}, {iso[11:16]}" if len(iso) >= 16 else fmt_date(iso)


def plural(n: int, singular: str, plural_: str | None = None) -> str:
    """plural(3, 'tenant') → '3 tenants'; plural(1, 'tenant') → '1 tenant'."""
    return f"{n} {singular if n == 1 else (plural_ or singular + 's')}"


# ─── Piezas reutilizables ─────────────────────────────────────────────────────

def apply_theme() -> None:
    """Colores de Quasar + fuentes + CSS. Idempotente por página."""
    ui.colors(
        primary=PRIMARY,
        secondary="#475569",
        accent=PRIMARY,
        positive="#16803F",
        negative="#B42318",
        info="#2563EB",
        warning="#9A5200",
    )
    ui.add_head_html(_HEAD)


def tier_pill(tier: str) -> None:
    cls = {"ENTERPRISE": "mn-pill--enterprise", "PROFESSIONAL": "mn-pill--pro"}.get(tier, "")
    ui.label(tier).classes(f"mn-pill {cls}")


def status_pill(active: bool, on: str = "Activo", off: str = "Suspendido") -> None:
    with ui.element("div").classes(f"mn-pill {'mn-pill--ok' if active else ''}"):
        ui.element("span").classes("mn-dot")
        ui.label(on if active else off)


def avatar(name: str, size: int = 38) -> None:
    letter = (name.strip()[:1] or "?").upper()
    ui.label(letter).classes("mn-avatar").style(
        f"width:{size}px;height:{size}px;border-radius:{round(size * 0.28)}px;"
        f"font-size:{round(size * 0.42)}px"
    )


def _fold(text: str) -> str:
    """'Baterías' → 'baterias' (minúsculas y sin tildes) para comparar palabras clave."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )


def category_expansion(name: str, count: int, index: int) -> ui.expansion:
    """Panel plegable de una categoría con cabecera propia: baldosa de color + nombre + conteo.

    El tono rota por posición (`index` en la lista ordenada de categorías), así dos
    categorías seguidas nunca comparten color. Como Productos y Stock ordenan igual,
    una categoría conserva su tono entre ambas páginas.
    """
    if name == NO_CATEGORY:
        bg, ink = _NO_CATEGORY_TINT
        icon = "inventory_2"
    else:
        bg, ink = _CATEGORY_TINTS[index % len(_CATEGORY_TINTS)]
        folded = _fold(name)
        icon = next((ic for key, ic in _CATEGORY_ICONS if key in folded), "sell")

    exp = ui.expansion().classes("w-full mb-2").props("default-opened")
    with exp.add_slot("header"):
        with ui.row().classes("mn-cat-head items-center gap-4 no-wrap w-full"):
            with ui.element("div").classes("mn-cat-icon").style(f"background:{bg};color:{ink}"):
                ui.icon(icon).classes("text-[22px]")
            ui.label(name).classes("mn-cat-name")
            ui.label(str(count)).classes("mn-count")
    return exp


def breadcrumb(*parts: tuple[str, str | None]) -> None:
    """breadcrumb(('Tenants', '/tenants'), ('demo', None)) — el último no es enlace."""
    with ui.row().classes("items-center gap-2 text-[13px] mn-muted"):
        for i, (label, href) in enumerate(parts):
            if i:
                ui.label("/")
            if href:
                ui.link(label, href).classes("mn-crumb")
            else:
                ui.label(label).classes("font-semibold").style("color:var(--mn-text)")


def sub_header(tenant: dict | None, tenant_id: str, title: str) -> None:
    """Migas de pan + título para las páginas de un tenant (productos, stock, almacenes)."""
    name = tenant["name"] if tenant else "Tenant"
    if app.storage.user.get("role") == "super_admin":
        breadcrumb(("Tenants", "/tenants"), (name, f"/tenants/{tenant_id}"), (title, None))
    else:
        breadcrumb((name, f"/tenants/{tenant_id}"), (title, None))
    ui.label(title).classes("mn-h1")


def _nav_item(label: str, icon: str, href: str, *, active: bool = False, muted: bool = False) -> None:
    cls = "mn-nav"
    if active:
        cls += " mn-nav--active"
    if muted:
        cls += " mn-nav--muted"
    link = ui.link(target=href).classes(cls)
    if active:
        link.props('aria-current="page"')
    with link:
        ui.icon(icon).classes("text-[20px]")
        ui.label(label)


def _logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/login")


async def shell(
    active: str,
    *,
    tenant_id: str | None = None,
    tenant: dict | None = None,
) -> dict | None:
    """Aplica el tema y dibuja la barra lateral.

    `active` marca el ítem resaltado: "tenants", "resumen", "products", "stock" o "warehouses".
    Con `tenant_id` la barra pasa a ser la del tenant (Resumen / Productos / Stock / Almacenes).
    Si no se pasa `tenant` se pide al API para mostrar su nombre; devuelve el tenant (o None).
    """
    apply_theme()

    user = app.storage.user
    role = user.get("role", "")
    is_super = role == "super_admin"

    if tenant_id and tenant is None:
        try:
            tenant = await api.get_tenant(user.get("token", ""), tenant_id)
        except Exception:
            tenant = None  # la barra sigue funcionando sin el nombre

    home = "/tenants" if is_super else (f"/tenants/{tenant_id}" if tenant_id else "/login")

    with ui.left_drawer(bordered=True).props("width=248 breakpoint=1024").classes("mn-drawer") as drawer:
        with ui.column().classes("w-full h-full no-wrap gap-6 p-4"):
            with ui.link(target=home).classes("mn-brand").props('aria-label="MicroNuba Inventarios, inicio"'):
                with ui.element("div").classes("mn-logo"):
                    ui.icon("cloud").classes("text-[22px]")
                with ui.column().classes("gap-0"):
                    ui.label("MicroNuba").classes("mn-brand-name")
                    ui.label("Inventarios · Admin").classes("mn-brand-sub")

            if tenant_id:
                if is_super:
                    _nav_item("Todos los tenants", "arrow_back", "/tenants", muted=True)
                with ui.element("div").classes("mn-tenant-chip w-full"):
                    avatar(tenant["name"] if tenant else "?", 38)
                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                        # Nombre completo: si es largo, pasa a la línea siguiente (nunca se corta).
                        ui.label(tenant["name"] if tenant else "Tenant").classes("font-semibold").style(
                            "overflow-wrap:anywhere;line-height:1.3"
                        )
                        ui.label(
                            "Sede" if tenant and tenant.get("parent_tenant_id") else "Tenant principal"
                        ).classes("text-xs mn-muted")
                with ui.column().classes("w-full gap-1").props('role="navigation" aria-label="Gestión del tenant"'):
                    _nav_item("Resumen", "dashboard", f"/tenants/{tenant_id}", active=active == "resumen")
                    _nav_item("Productos", "inventory_2", f"/tenants/{tenant_id}/products", active=active == "products")
                    if SHOW_STOCK_PAGE:
                        _nav_item("Stock", "bar_chart", f"/tenants/{tenant_id}/stock", active=active == "stock")
                    _nav_item("Almacenes", "warehouse", f"/tenants/{tenant_id}/warehouses", active=active == "warehouses")
            elif is_super:
                with ui.column().classes("w-full gap-1").props('role="navigation" aria-label="Principal"'):
                    _nav_item("Tenants", "apartment", "/tenants", active=active == "tenants")

            ui.space()

            with ui.column().classes("w-full gap-1").style("border-top:1px solid var(--mn-line);padding-top:16px"):
                with ui.column().classes("gap-0 px-3 py-1 w-full"):
                    ui.label(user.get("user_email", "")).classes("text-[13px] font-semibold truncate w-full")
                    ui.label(_ROLE_LABELS.get(role, role)).classes("text-xs mn-muted")
                with ui.element("button").props("type=button").classes("mn-nav mn-nav--muted").on(
                    "click", _logout
                ):
                    ui.icon("logout").classes("text-[20px]")
                    ui.label("Salir")

    # Barra superior solo en pantallas estrechas: aloja el botón que abre la barra lateral.
    with ui.header().classes("mn-topbar lt-md items-center gap-3 px-4 py-2"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense").props('aria-label="Abrir menú"')
        ui.label("MicroNuba").classes("mn-brand-name")

    return tenant
