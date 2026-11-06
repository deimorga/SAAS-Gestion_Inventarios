import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Request
from nicegui import app, ui

from app import api, theme
from app.api import SessionExpiredError

STORAGE_SECRET = os.getenv("STORAGE_SECRET", "dev-secret-change-in-prod")
PORT = int(os.getenv("PORT", "8080"))
API_BASE_URL = api.BASE_URL

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _token() -> str:
    """Return the current access token (may be expired)."""
    return app.storage.user.get("token", "")


def _guard() -> None:
    """Redirect to login if no session data exists at all."""
    if not _token() and not app.storage.user.get("refresh_token", ""):
        ui.navigate.to("/login")


def _copy_js(value: str) -> str:
    """JS compatible con Safari HTTP (execCommand) y navegadores modernos (clipboard API)."""
    safe = value.replace("\\", "\\\\").replace("`", "\\`")
    return f"""
    (function() {{
        const v = `{safe}`;
        if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(v);
        }} else {{
            const el = document.createElement('textarea');
            el.value = v;
            el.style.position = 'fixed';
            el.style.left = '-9999px';
            document.body.appendChild(el);
            el.focus();
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }}
    }})();
    """


def _info_row(label: str, value: str, copyable: bool = False, mono: bool = False) -> None:
    with ui.row().classes("items-center gap-2 w-full no-wrap"):
        ui.label(label).classes("mn-label w-36 shrink-0")
        ui.label(value).classes(f"text-sm break-all flex-1 {'mn-mono' if mono else ''}")
        if copyable:
            ui.button(
                icon="content_copy",
                on_click=lambda v=value: ui.run_javascript(_copy_js(v)),
            ).props('flat round dense size=sm color=grey-7 aria-label="Copiar"').tooltip("Copiar")


def _err_msg(ex: Exception) -> str:
    """Extrae el `detail` del API; en errores de validación, el primer mensaje."""
    if isinstance(ex, httpx.HTTPStatusError):
        try:
            detail = ex.response.json().get("detail")
        except Exception:
            detail = None
        if isinstance(detail, list) and detail:
            first = detail[0]
            detail = first.get("msg") if isinstance(first, dict) else str(first)
        return str(detail) if detail else f"HTTP {ex.response.status_code}"
    return str(ex)


def _row_location(row: dict) -> dict:
    """Lote, bin y proveedor de una fila de saldo, para que el ajuste caiga sobre ESA fila.

    Sin esto el ajuste iba al stock sin lote ni ubicación del producto en la zona,
    aunque se hubiera elegido la fila de un lote o de un estante concreto.
    """
    return {
        "lot_number": row.get("lot_number"),
        "bin_id": row.get("bin_id"),
        "supplier_id": row.get("supplier_id"),
    }


def _row_label(row: dict) -> str:
    """Texto que identifica una fila de saldo en los diálogos: producto · almacén · zona · lote · ubicación."""
    parts = [row.get("product_name", ""), row.get("warehouse_name", ""), row.get("zone_name", "")]
    if row.get("lot_number"):
        parts.append(f"Lote {row['lot_number']}")
    if row.get("bin_code"):
        parts.append(f"Ubicación {row['bin_code']}")
    return " · ".join(part for part in parts if part)


# ─── Login ────────────────────────────────────────────────────────────────────

@ui.page("/login")
def page_login(request: Request, email: str = "") -> None:
    theme.apply_theme()
    # IP del navegador, para que el límite de intentos del API cuente por origen
    # real y no por la IP del portal, que es la misma para todos.
    browser_ip = _browser_ip(request)

    # Centra la tarjeta en la pantalla (el contenedor de página es una columna flex)
    ui.query(".nicegui-content").classes("items-center justify-center").style(
        "min-height:85vh;max-width:none"
    )

    with ui.card().classes("w-96 max-w-full p-8 gap-0"):
        with ui.row().classes("items-center gap-3 no-wrap mb-8"):
            with ui.element("div").classes("mn-logo"):
                ui.icon("cloud").classes("text-[22px]")
            with ui.column().classes("gap-0"):
                ui.label("MicroNuba").classes("mn-brand-name")
                ui.label("Portal de administración").classes("mn-brand-sub")

        ui.label("Iniciar sesión").classes("mn-h2 mb-4")
        email_input = ui.input("Email", value=email, placeholder="admin@micronuba.com").classes("w-full")
        password_input = ui.input(
            "Contraseña", password=True, password_toggle_button=True
        ).classes("w-full mt-4")
        error_label = ui.label("").classes("text-negative text-sm hidden mt-2")

        async def do_login() -> None:
            error_label.classes(remove="hidden")
            error_label.set_text("")
            if not email_input.value or not password_input.value:
                error_label.set_text("Completa todos los campos.")
                return
            try:
                data = await api.admin_login(email_input.value, password_input.value, browser_ip)
                app.storage.user["token"] = data["access_token"]
                app.storage.user["refresh_token"] = data.get("refresh_token", "")
                app.storage.user["user_email"] = data["user"]["email"]
                app.storage.user["role"] = data["user"]["role"]
                app.storage.user["tenant_id"] = data["user"]["tenant_id"]
                
                if data["user"]["role"] == "tenant_admin":
                    ui.navigate.to(f"/tenants/{data['user']['tenant_id']}")
                else:
                    ui.navigate.to("/tenants")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    error_label.set_text("Credenciales incorrectas.")
                elif e.response.status_code == 429:
                    error_label.set_text(e.response.json().get("detail", "Demasiados intentos fallidos."))
                elif e.response.status_code == 422:
                    try:
                        detail = e.response.json().get("detail", "Datos inválidos")
                        if isinstance(detail, list):
                            msg = detail[0].get("msg", "Datos inválidos")
                            error_label.set_text(f"Error de validación: {msg}")
                        else:
                            error_label.set_text(f"Error 422: {detail}")
                    except Exception:
                        error_label.set_text("Error de validación en los datos enviados.")
                else:
                    error_label.set_text(f"Error {e.response.status_code}.")
            except Exception as e:
                error_label.set_text(f"ERROR DE RED: {str(e)}")

        password_input.on("keydown.enter", do_login)
        ui.button("Ingresar", on_click=do_login).classes("w-full mt-4").props(
            'color="primary" unelevated'
        )
        ui.link("¿Olvidaste tu contraseña?", "/forgot-password").classes("text-sm mt-4 self-center")

    ui.label(f"API: {API_BASE_URL}").classes("fixed bottom-2 right-4 text-xs mn-muted")


# ─── Tenants list ─────────────────────────────────────────────────────────────

@ui.page("/tenants")
async def page_tenants() -> None:
    _guard()
    await theme.shell("tenants")

    with ui.row().classes("w-full items-end justify-between gap-4"):
        with ui.column().classes("gap-1"):
            ui.label("Tenants").classes("mn-h1")
            subtitle = ui.label("").classes("mn-muted")
        with ui.row().classes("items-center gap-3"):
            search = ui.input(placeholder="Buscar por nombre o slug").props(
                'dense clearable aria-label="Buscar tenant"'
            ).classes("w-72 max-w-full")
            with search.add_slot("prepend"):
                ui.icon("search")
            ui.button(
                "Nuevo tenant", icon="add", on_click=lambda: create_dialog.open()
            ).props("unelevated color=primary no-caps")

    created: dict[str, Any] = {}

    result_dialog = ui.dialog().props("persistent")
    create_dialog = ui.dialog().props("persistent")

    with result_dialog:
        with ui.card().classes("w-[520px] p-6"):
            ui.label("Tenant creado").classes("text-lg font-bold text-positive mb-4")

            @ui.refreshable
            def result_content() -> None:
                t = created
                if not t:
                    return
                with ui.column().classes("w-full gap-1"):
                    _info_row("Tenant ID", str(t.get("id", "")), copyable=True)
                    _info_row("Nombre", t.get("name", ""))
                    _info_row("Slug", t.get("slug", ""), copyable=True)
                    _info_row("Tier", t.get("subscription_tier", ""))
                    _info_row("Admin Email", t.get("admin_email", ""), copyable=True)
                    _info_row("Admin User ID", str(t.get("admin_user_id", "")), copyable=True)

                ui.separator().classes("my-3")

                with ui.card().classes("bg-blue-50 w-full p-3"):
                    ui.label("Próximos pasos para el cliente").classes(
                        "font-semibold text-blue-800 mb-2"
                    )
                    steps = [
                        "Se envió un email de activación al admin (válido 48 h).",
                        "El admin debe abrir el link del email y establecer su contraseña.",
                        "Tras activar, puede hacer login en /auth/login con su email.",
                        "Desde su cuenta puede crear API Keys para integrar sus sistemas.",
                    ]
                    for i, step in enumerate(steps, 1):
                        ui.label(f"{i}. {step}").classes("text-sm text-blue-700")

            result_content()

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(
                    "Ver detalle",
                    icon="open_in_new",
                    on_click=lambda: (
                        result_dialog.close(),
                        ui.navigate.to(f"/tenants/{created.get('id')}"),
                    ),
                ).props("flat color=primary")
                ui.button("Cerrar", on_click=result_dialog.close).props(
                    'unelevated color="primary"'
                )

    with create_dialog:
        with ui.card().classes("w-[440px] p-6"):
            ui.label("Nuevo Tenant").classes("text-xl font-bold mb-4")

            name_in = ui.input("Nombre del cliente *", placeholder="Talleres García S.A.S").classes(
                "w-full"
            )
            email_in = ui.input("Email del admin *", placeholder="admin@talleres.com").classes(
                "w-full mt-2"
            )
            fullname_in = ui.input("Nombre completo del admin *", placeholder="Carlos García").classes(
                "w-full mt-2"
            )
            tier_in = ui.select(
                {"STARTER": "Starter", "PROFESSIONAL": "Professional", "ENTERPRISE": "Enterprise"},
                value="STARTER",
                label="Tier de suscripción",
            ).classes("w-full mt-2")

            err = ui.label("").classes("text-red-500 text-sm")

            async def do_create() -> None:
                err.set_text("")
                if not name_in.value or not email_in.value or not fullname_in.value:
                    err.set_text("Todos los campos marcados con * son obligatorios.")
                    return
                try:
                    payload = {
                        "name": name_in.value.strip(),
                        "subscription_tier": tier_in.value,
                        "admin_email": email_in.value.strip(),
                        "admin_full_name": fullname_in.value.strip(),
                    }
                    data = await api.create_tenant(_token(), payload)
                    created.clear()
                    created.update(data)
                    create_dialog.close()
                    result_content.refresh()
                    result_dialog.open()
                    await refresh_table()
                    name_in.set_value("")
                    email_in.set_value("")
                    fullname_in.set_value("")
                    tier_in.set_value("STARTER")
                except httpx.HTTPStatusError as e:
                    detail = e.response.json().get("detail", str(e))
                    err.set_text(f"Error {e.response.status_code}: {detail}")
                except Exception as ex:
                    err.set_text(f"Error inesperado: {ex}")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=create_dialog.close).props("flat")
                ui.button("Crear Tenant", on_click=do_create).props('unelevated color="primary"')

    # ── Edit dialog ───────────────────────────────────────────────────────────
    editing_tenant: dict = {}
    edit_dialog = ui.dialog().props("persistent")
    with edit_dialog:
        with ui.card().classes("w-[440px] p-6"):
            ui.label("Editar Tenant").classes("text-xl font-bold mb-4")
            edit_name = ui.input("Nombre *").classes("w-full")
            edit_tier = ui.select(
                {"STARTER": "Starter", "PROFESSIONAL": "Professional", "ENTERPRISE": "Enterprise"},
                label="Tier",
            ).classes("w-full mt-2")
            edit_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def do_edit() -> None:
                edit_err.set_text("")
                if not edit_name.value.strip():
                    edit_err.set_text("El nombre es obligatorio.")
                    return
                try:
                    await api.update_tenant(_token(), editing_tenant["id"], {
                        "name": edit_name.value.strip(),
                        "subscription_tier": edit_tier.value,
                    })
                    edit_dialog.close()
                    ui.notify("Tenant actualizado.", type="positive")
                    await refresh_table()
                except Exception as ex:
                    edit_err.set_text(f"Error: {ex}")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=edit_dialog.close).props("flat")
                ui.button("Guardar", on_click=do_edit).props('unelevated color="primary"')

    # ── Suspend dialog ────────────────────────────────────────────────────────
    suspending_tenant: dict = {}
    suspend_confirm = ui.dialog().props("persistent")
    with suspend_confirm:
        with ui.card().classes("p-5 w-80"):
            suspend_msg = ui.label("").classes("font-bold mb-2")
            suspend_sub = ui.label("").classes("text-sm text-gray-600 mb-4")

            async def do_suspend() -> None:
                try:
                    await api.update_tenant(_token(), suspending_tenant["id"], {
                        "is_active": not suspending_tenant["is_active"]
                    })
                    suspend_confirm.close()
                    ui.notify("Estado actualizado.", type="positive")
                    await refresh_table()
                except Exception as ex:
                    ui.notify(f"Error: {ex}", type="negative")

            with ui.row().classes("justify-end gap-2"):
                ui.button("Cancelar", on_click=suspend_confirm.close).props("flat")
                ui.button("Confirmar", on_click=do_suspend).props('unelevated color="negative"')

    # ── Table ─────────────────────────────────────────────────────────────────
    table_container = ui.column().classes("w-full")

    async def refresh_table() -> None:
        table_container.clear()
        with table_container:
            try:
                data = await api.list_tenants(_token())
                all_items: list[dict] = data.get("items", [])
                # Las sedes no se listan aquí: viven dentro del detalle de su tenant
                # principal (sección Sedes). Aquí solo se cuentan.
                sedes_por_padre: dict[str, int] = {}
                for t in all_items:
                    if t.get("parent_tenant_id"):
                        pid = str(t["parent_tenant_id"])
                        sedes_por_padre[pid] = sedes_por_padre.get(pid, 0) + 1
                items = [t for t in all_items if not t.get("parent_tenant_id")]
                total: int = len(items)

                subtitle.set_text(
                    f"{theme.plural(total, 'tenant')} "
                    f"{'registrado' if total == 1 else 'registrados'}" if items else "Sin tenants"
                )

                if not items:
                    with ui.column().classes("w-full items-center p-12 gap-1"):
                        ui.icon("apartment", size="3rem").classes("text-slate-300")
                        ui.label("Sin tenants registrados").classes("font-semibold mt-2")
                        ui.label("Crea el primero con el botón «Nuevo tenant».").classes("text-sm mn-muted")
                    return

                columns = [
                    # `search_str` junta nombre y slug: es lo que filtra el buscador y ordena la columna.
                    {"name": "name", "label": "Tenant", "field": "search_str", "align": "left", "sortable": True},
                    {"name": "sedes", "label": "Sedes", "field": "sedes_str", "align": "left"},
                    {"name": "tier", "label": "Plan", "field": "subscription_tier", "align": "left", "sortable": True},
                    {"name": "status", "label": "Estado", "field": "status_str", "align": "left"},
                    {"name": "created_at", "label": "Creado", "field": "created_at", "align": "left", "sortable": True},
                    {"name": "actions", "label": "", "field": "id", "align": "right"},
                ]

                rows = [
                    {
                        **t,
                        "search_str": f"{t['name']} {t['slug']}",
                        "status_str": "Activo" if t["is_active"] else "Suspendido",
                        "created_str": theme.fmt_date(t["created_at"]),
                        "sedes_str": str(sedes_por_padre.get(str(t["id"]), 0) or "—"),
                    }
                    for t in items
                ]

                tbl = ui.table(
                    columns=columns, rows=rows, row_key="id", pagination=50
                ).classes("w-full")
                tbl.props('hide-bottom no-data-label="Ningún tenant coincide con la búsqueda"')
                tbl.bind_filter_from(search, "value")
                tbl.add_slot("body-cell-name", """
                    <q-td :props="props">
                        <a :href="'/tenants/' + props.row.id" class="mn-tenant-link">
                            <span class="mn-avatar"
                                  style="width:38px;height:38px;border-radius:10px;font-size:16px">
                                {{ props.row.name.charAt(0).toUpperCase() }}
                            </span>
                            <span class="mn-tenant-text">
                                <span class="mn-tenant-name">{{ props.row.name }}</span>
                                <span class="mn-mono mn-tenant-slug">{{ props.row.slug }}</span>
                            </span>
                        </a>
                    </q-td>
                """)
                tbl.add_slot("body-cell-tier", """
                    <q-td :props="props">
                        <span class="mn-pill"
                              :class="props.value === 'ENTERPRISE' ? 'mn-pill--enterprise'
                                      : props.value === 'PROFESSIONAL' ? 'mn-pill--pro' : ''">
                            {{ props.value }}
                        </span>
                    </q-td>
                """)
                tbl.add_slot("body-cell-status", """
                    <q-td :props="props">
                        <span class="mn-pill" :class="props.row.is_active ? 'mn-pill--ok' : ''">
                            <span class="mn-dot"></span>{{ props.value }}
                        </span>
                    </q-td>
                """)
                tbl.add_slot("body-cell-created_at", """
                    <q-td :props="props" class="mn-muted">{{ props.row.created_str }}</q-td>
                """)
                tbl.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn flat round dense icon="chevron_right" color="grey-7"
                               :href="'/tenants/' + props.row.id"
                               :aria-label="'Abrir ' + props.row.name" />
                        <q-btn flat round dense icon="more_vert" color="grey-7"
                               :aria-label="'Más acciones para ' + props.row.name">
                            <q-menu auto-close>
                                <q-list style="min-width: 180px">
                                    <q-item clickable @click="$parent.$emit('edit', props.row)">
                                        <q-item-section avatar><q-icon name="edit" /></q-item-section>
                                        <q-item-section>Editar</q-item-section>
                                    </q-item>
                                    <q-item clickable @click="$parent.$emit('suspend', props.row)">
                                        <q-item-section avatar>
                                            <q-icon :name="props.row.is_active ? 'pause_circle' : 'play_circle'" />
                                        </q-item-section>
                                        <q-item-section>
                                            {{ props.row.is_active ? 'Suspender' : 'Reactivar' }}
                                        </q-item-section>
                                    </q-item>
                                </q-list>
                            </q-menu>
                        </q-btn>
                    </q-td>
                """)

                def on_edit(e: Any) -> None:
                    editing_tenant.clear()
                    editing_tenant.update(e.args)
                    edit_name.set_value(e.args["name"])
                    edit_tier.set_value(e.args["subscription_tier"])
                    edit_err.set_text("")
                    edit_dialog.open()

                def on_suspend(e: Any) -> None:
                    suspending_tenant.clear()
                    suspending_tenant.update(e.args)
                    is_active = e.args["is_active"]
                    suspend_msg.set_text(f"{'¿Suspender' if is_active else '¿Reactivar'} {e.args['name']}?")
                    suspend_sub.set_text(
                        "Suspender impide el login de sus usuarios." if is_active
                        else "El tenant y sus usuarios podrán volver a operar."
                    )
                    suspend_confirm.open()

                tbl.on("edit", on_edit)
                tbl.on("suspend", on_suspend)

            except SessionExpiredError:
                app.storage.user.clear()
                ui.notify("Tu sesión ha expirado. Inicia sesión de nuevo.", type="warning")
                ui.navigate.to("/login")
            except Exception as ex:
                ui.notify(f"Error cargando tenants: {ex}", type="negative")

    await refresh_table()


# ─── Tenant detail ────────────────────────────────────────────────────────────

@ui.page("/tenants/{tenant_id}")
async def page_tenant_detail(tenant_id: str) -> None:
    _guard()

    try:
        tenant = await api.get_tenant(_token(), tenant_id)
        parent_name = ""
        if tenant.get("parent_tenant_id"):
            try:
                parent_name = (await api.get_tenant(_token(), tenant["parent_tenant_id"]))["name"]
            except Exception:
                parent_name = tenant["parent_tenant_id"]
        all_keys = (await api.get_tenant_keys(_token(), tenant_id)).get("data", [])
        keys_data: dict = {"data": all_keys}
    except httpx.HTTPStatusError as e:
        await theme.shell("tenants")
        ui.notify(f"Error {e.response.status_code} cargando tenant.", type="negative")
        return
    except Exception as ex:
        await theme.shell("tenants")
        ui.notify(f"Error: {ex}", type="negative")
        return

    await theme.shell("resumen", tenant_id=tenant_id, tenant=tenant)

    es_sede = bool(tenant.get("parent_tenant_id"))
    is_active = tenant["is_active"]

    # ── Suspender / reactivar ─────────────────────────────────────────────────────
    suspend_dialog = ui.dialog()
    with suspend_dialog:
        with ui.card().classes("p-5 w-80"):
            action = "reactivar" if not is_active else "suspender"
            ui.label(f"¿{action.capitalize()} este tenant?").classes("font-bold mb-2")
            ui.label(
                "Suspender impide el login de sus usuarios pero no revoca API Keys activas."
                if is_active
                else "El tenant y sus usuarios podrán volver a operar."
            ).classes("text-sm mn-muted mb-4")

            async def do_toggle() -> None:
                try:
                    await api.update_tenant(_token(), tenant_id, {"is_active": not is_active})
                    suspend_dialog.close()
                    ui.navigate.to(f"/tenants/{tenant_id}")
                except Exception as ex:
                    ui.notify(f"Error: {ex}", type="negative")

            with ui.row().classes("justify-end gap-2"):
                ui.button("Cancelar", on_click=suspend_dialog.close).props("flat no-caps")
                ui.button(action.capitalize(), on_click=do_toggle).props(
                    f'unelevated no-caps color="{"warning" if is_active else "positive"}"'
                )

    # ── Cabecera ──────────────────────────────────────────────────────────────────
    if app.storage.user.get("role") == "super_admin":
        theme.breadcrumb(("Tenants", "/tenants"), (tenant["name"], None))

    with ui.row().classes("w-full items-center justify-between gap-4"):
        with ui.row().classes("items-center gap-4 no-wrap"):
            theme.avatar(tenant["name"], 56)
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-3"):
                    ui.label(tenant["name"]).classes("mn-h1")
                    theme.tier_pill(tenant["subscription_tier"])
                    theme.status_pill(is_active)
                ui.label(f"Creado el {theme.fmt_date(tenant['created_at'])}").classes("mn-muted")
        with ui.row().classes("items-center gap-2"):
            ui.button(
                "Gestionar usuarios",
                icon="group",
                on_click=lambda: ui.navigate.to(f"/tenants/{tenant_id}/users"),
            ).props("outline no-caps color=primary")
            ui.button(
                "Suspender tenant" if is_active else "Reactivar tenant",
                icon="pause" if is_active else "play_arrow",
                on_click=suspend_dialog.open,
            ).props(f'outline no-caps color="{"warning" if is_active else "positive"}"')

    # ── Información ───────────────────────────────────────────────────────────────
    with ui.card().classes("mn-card w-full"):
        with ui.element("div").classes("mn-card-head"):
            ui.label("Información").classes("mn-h2")
        with ui.column().classes("mn-card-body gap-3"):
            _info_row("ID", str(tenant["id"]), copyable=True, mono=True)
            _info_row("Nombre", tenant["name"])
            _info_row("Slug", tenant["slug"], copyable=True, mono=True)
            if tenant.get("tax_id"):
                _info_row("NIT", tenant["tax_id"])
            if es_sede:
                with ui.row().classes("items-center gap-2 w-full no-wrap"):
                    ui.label("Sede de").classes("mn-label w-36 shrink-0")
                    ui.link(
                        parent_name, f"/tenants/{tenant['parent_tenant_id']}"
                    ).classes("text-sm text-primary")
            _info_row("Creado", theme.fmt_datetime(tenant["created_at"]))

    # ── Sedes ─────────────────────────────────────────────────────────────────────
    # Cada sede es un tenant APARTE (catálogo y stock propios, aislados por RLS)
    # que apunta a este tenant con parent_tenant_id. Se crea con todo listo:
    # admin, bodega física con sus zonas y la API key para Appits.
    sede_created: dict = {}

    sede_result_dialog = ui.dialog().props("persistent")
    with sede_result_dialog:
        with ui.card().classes("w-[560px] p-6"):
            ui.label("Sede creada").classes("text-lg font-bold text-green-600 mb-1")
            ui.label(
                "Copia la API key ahora — no podrás verla de nuevo. Es la que se pega en Appits para conectar esta sede."
            ).classes("text-sm text-amber-600 mb-4")

            @ui.refreshable
            def sede_result_content() -> None:
                d = sede_created
                if not d:
                    return
                wh = d.get("warehouse", {})
                key = d.get("api_key", {})
                with ui.column().classes("w-full gap-2"):
                    _info_row("Tenant ID", str(d.get("tenant_id", "")), copyable=True)
                    _info_row("Nombre", d.get("name", ""))
                    _info_row("Admin", d.get("admin_email", ""), copyable=True)
                    _info_row("Bodega", f"{wh.get('code', '')} — {wh.get('name', '')}")
                    _info_row("Bodega ID", str(wh.get("id", "")), copyable=True)
                    _info_row("Zonas", ", ".join(z.get("zone_type", "") for z in wh.get("zones", [])))
                    ui.separator().classes("my-2")
                    ui.label("API Key de la sede (copia ahora):").classes(
                        "text-xs font-semibold text-gray-500 uppercase"
                    )
                    with ui.card().classes("bg-gray-100 w-full p-3"):
                        ui.label(key.get("key_secret", "")).classes(
                            "font-mono text-sm break-all text-gray-900"
                        )
                    ui.button(
                        "Copiar Key",
                        icon="content_copy",
                        on_click=lambda v=key.get("key_secret", ""): ui.run_javascript(_copy_js(v)),
                    ).props("unelevated color=primary size=sm")

            sede_result_content()
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(
                    "Ver sede",
                    icon="open_in_new",
                    on_click=lambda: (
                        sede_result_dialog.close(),
                        ui.navigate.to(f"/tenants/{sede_created.get('tenant_id')}"),
                    ),
                ).props("flat color=primary")
                ui.button("Cerrar", on_click=sede_result_dialog.close).props('unelevated color="primary"')

    sede_dialog = ui.dialog().props("persistent")
    with sede_dialog:
        with ui.card().classes("w-[480px] p-6"):
            ui.label(f"Nueva sede de {tenant['name']}").classes("text-xl font-bold mb-1")
            ui.label(
                "La sede nace como tenant aparte: sus productos y su stock no se mezclan con los de "
                f"{tenant['name']}. Se crea con su admin, su bodega y su API key."
            ).classes("text-sm text-gray-600 mb-4")

            sede_name_in = ui.input("Nombre de la sede *", placeholder="Sede Norte").classes("w-full")
            sede_nit_in = ui.input("NIT", placeholder="900123456-7").classes("w-full mt-2")
            sede_email_in = ui.input("Email del admin *", placeholder="sede.norte@taller.com").classes("w-full mt-2")
            ui.label("Debe ser distinto al de cualquier otro tenant.").classes("text-xs text-gray-500")
            sede_admin_in = ui.input("Nombre del admin *", placeholder="Carlos García").classes("w-full mt-2")
            sede_wh_in = ui.input("Nombre de la bodega", placeholder="Bodega Sede Norte").classes("w-full mt-2")
            sede_ext_in = ui.input("ID en Appits (opcional)", placeholder="shop_42").classes("w-full mt-2")
            sede_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def do_create_sede() -> None:
                sede_err.set_text("")
                if not sede_name_in.value or not sede_email_in.value or not sede_admin_in.value:
                    sede_err.set_text("Nombre, email del admin y nombre del admin son obligatorios.")
                    return
                payload: dict = {
                    "name": sede_name_in.value.strip(),
                    "tax_id": (sede_nit_in.value or "").strip() or None,
                    "admin_email": sede_email_in.value.strip(),
                    "admin_full_name": sede_admin_in.value.strip(),
                    "warehouse": {
                        "code": "PRINCIPAL",
                        "name": (sede_wh_in.value or "").strip() or f"Bodega {sede_name_in.value.strip()}",
                    },
                    "api_key_name": f"Appits — {sede_name_in.value.strip()}",
                }
                if (sede_ext_in.value or "").strip():
                    payload["external_id"] = sede_ext_in.value.strip()
                try:
                    data = await api.create_sede(_token(), tenant_id, payload)
                    sede_created.clear()
                    sede_created.update(data)
                    sede_dialog.close()
                    sede_result_content.refresh()
                    sede_result_dialog.open()
                    await load_sedes()
                except Exception as ex:
                    sede_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=sede_dialog.close).props("flat")
                ui.button("Crear Sede", on_click=do_create_sede).props('unelevated color="primary"')

    def open_sede_dialog() -> None:
        for inp in (sede_name_in, sede_nit_in, sede_email_in, sede_admin_in, sede_wh_in, sede_ext_in):
            inp.set_value("")
        sede_err.set_text("")
        sede_dialog.open()

    with ui.card().classes("mn-card w-full"):
        with ui.element("div").classes("mn-card-head"):
            with ui.row().classes("items-center gap-2"):
                ui.label("Sedes").classes("mn-h2")
                sedes_count = ui.label("").classes("mn-count")
                sedes_count.set_visibility(False)
            if not es_sede:
                ui.button("Nueva sede", icon="add", on_click=open_sede_dialog).props(
                    "unelevated color=primary no-caps"
                )
        sedes_container = ui.column().classes("w-full gap-0")

    async def load_sedes() -> None:
        sedes_container.clear()
        with sedes_container:
            if es_sede:
                ui.label(
                    f"Este tenant es una sede de {parent_name}. Las sedes solo se crean desde el tenant principal."
                ).classes("text-sm mn-muted w-full px-6 pb-5")
                return
            try:
                sedes = await api.list_sedes(_token(), tenant_id)
            except Exception as ex:
                ui.notify(f"Error cargando sedes: {_err_msg(ex)}", type="negative")
                return
            sedes_count.set_text(str(len(sedes)))
            sedes_count.set_visibility(True)
            if not sedes:
                with ui.column().classes("w-full items-center p-8 gap-1").style(
                    "border-top:1px solid var(--mn-line)"
                ):
                    ui.icon("store", size="2.5rem").classes("text-slate-300")
                    ui.label("Sin sedes").classes("font-semibold mt-1")
                    ui.label(
                        "Una sede es un tenant aparte con su propio inventario, ligado a este tenant."
                    ).classes("text-sm mn-muted text-center")
                return
            columns = [
                {"name": "name", "label": "Nombre", "field": "name", "align": "left"},
                {"name": "slug", "label": "Slug", "field": "slug", "align": "left"},
                {"name": "external", "label": "Origen", "field": "external_str", "align": "left"},
                {"name": "status", "label": "Estado", "field": "status_str", "align": "left"},
                {"name": "actions", "label": "", "field": "id", "align": "right"},
            ]
            rows = [
                {
                    **s,
                    "status_str": "Activa" if s["is_active"] else "Suspendida",
                    "external_str": (
                        f"Appits · {s['external_id']}" if s.get("external_provider") == "appits"
                        else "Panel"
                    ),
                }
                for s in sedes
            ]
            tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
            tbl.props("hide-bottom")
            tbl.add_slot("body-cell-name", """
                <q-td :props="props"><span class="font-semibold">{{ props.value }}</span></q-td>
            """)
            tbl.add_slot("body-cell-slug", """
                <q-td :props="props"><span class="mn-mono mn-muted" style="font-size:13px">{{ props.value }}</span></q-td>
            """)
            tbl.add_slot("body-cell-external", """
                <q-td :props="props"><span class="mn-pill">{{ props.value }}</span></q-td>
            """)
            tbl.add_slot("body-cell-status", """
                <q-td :props="props">
                    <span class="mn-pill" :class="props.row.is_active ? 'mn-pill--ok' : ''">
                        <span class="mn-dot"></span>{{ props.value }}
                    </span>
                </q-td>
            """)
            tbl.add_slot("body-cell-actions", """
                <q-td :props="props">
                    <q-btn flat round dense icon="open_in_new" color="grey-7"
                           :href="'/tenants/' + props.row.id"
                           :aria-label="'Abrir la sede ' + props.row.name" />
                </q-td>
            """)

    await load_sedes()

    # ── API Keys ──────────────────────────────────────────────────────────────────
    new_key_result: dict = {}

    # Diálogo: mostrar key_secret (solo una vez tras la creación)
    key_reveal_dialog = ui.dialog().props("persistent")
    with key_reveal_dialog:
        with ui.card().classes("w-[500px] p-6"):
            ui.label("API Key creada").classes("text-lg font-bold text-green-600 mb-1")
            ui.label("Copia la key ahora — no podrás verla de nuevo.").classes(
                "text-sm text-amber-600 mb-4"
            )

            @ui.refreshable
            def reveal_content() -> None:
                k = new_key_result
                if not k:
                    return
                with ui.column().classes("w-full gap-2"):
                    _info_row("Nombre", k.get("name", ""))
                    _info_row("Scopes", ", ".join(k.get("scopes", [])))
                    ui.separator().classes("my-2")
                    ui.label("API Key (copia ahora):").classes(
                        "text-xs font-semibold text-gray-500 uppercase"
                    )
                    with ui.card().classes("bg-gray-100 w-full p-3"):
                        ui.label(k.get("key_secret", "")).classes(
                            "font-mono text-sm break-all text-gray-900"
                        )
                    ui.button(
                        "Copiar Key",
                        icon="content_copy",
                        on_click=lambda v=k.get("key_secret", ""): ui.run_javascript(
                            _copy_js(v)
                        ),
                    ).props("unelevated color=primary size=sm")

            reveal_content()
            with ui.row().classes("justify-end mt-4"):
                ui.button("Cerrar", on_click=key_reveal_dialog.close).props("flat")

    # Diálogo: crear API Key
    ALL_SCOPES = [
        "READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG",
        "WRITE_CATALOG", "MANAGE_WAREHOUSES", "MANAGE_RESERVATIONS", "ADMIN",
    ]
    # PLATFORM solo se puede emitir en el tenant interno: aprovisiona sedes desde Appits
    if str(tenant_id) == "00000000-0000-0000-0000-000000000001":
        ALL_SCOPES.append("PLATFORM")
    create_key_dialog = ui.dialog().props("persistent")
    with create_key_dialog:
        with ui.card().classes("w-[440px] p-6"):
            ui.label("Nueva API Key").classes("text-xl font-bold mb-4")
            key_name_in = ui.input("Nombre *", placeholder="Integración Talleres").classes("w-full")
            with ui.column().classes("mt-3 gap-1"):
                ui.label("Scopes *").classes("text-sm font-semibold text-gray-600")
                scope_checks = {s: ui.checkbox(s) for s in ALL_SCOPES}
            key_err = ui.label("").classes("text-red-500 text-sm mt-2")

            async def do_create_key() -> None:
                key_err.set_text("")
                if not key_name_in.value:
                    key_err.set_text("El nombre es obligatorio.")
                    return
                selected = [s for s, cb in scope_checks.items() if cb.value]
                if not selected:
                    key_err.set_text("Selecciona al menos un scope.")
                    return
                try:
                    data = await api.create_tenant_api_key(
                        _token(), tenant_id, {"name": key_name_in.value.strip(), "scopes": selected}
                    )
                    new_key_result.clear()
                    new_key_result.update(data)
                    create_key_dialog.close()
                    reveal_content.refresh()
                    key_reveal_dialog.open()
                    fresh = await api.get_tenant_keys(_token(), tenant_id)
                    keys_data["data"] = fresh.get("data", [])
                    await build_keys()
                    key_name_in.set_value("")
                    for cb in scope_checks.values():
                        cb.set_value(False)
                except httpx.HTTPStatusError as e:
                    detail = e.response.json().get("detail", str(e))
                    key_err.set_text(f"Error {e.response.status_code}: {detail}")
                except Exception as ex:
                    key_err.set_text(f"Error: {ex}")

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=create_key_dialog.close).props("flat")
                ui.button("Crear Key", on_click=do_create_key).props('unelevated color="primary"')

    with ui.card().classes("mn-card w-full"):
        with ui.element("div").classes("mn-card-head"):
            with ui.row().classes("items-center gap-2"):
                ui.label("API Keys").classes("mn-h2")
                keys_count = ui.label("").classes("mn-count")
            ui.button("Nueva API key", icon="add", on_click=create_key_dialog.open).props(
                "unelevated color=primary no-caps"
            )
        key_container = ui.column().classes("w-full gap-0")

    async def build_keys() -> None:
        key_container.clear()
        current_keys = keys_data.get("data", [])
        # Las revocadas no se descartan (son historial), pero van plegadas para que no tapen
        # las que sí están en uso.
        active_keys = [k for k in current_keys if k.get("is_active", False)]
        revoked_keys = [k for k in current_keys if not k.get("is_active", False)]
        keys_count.set_text(f"{len(active_keys)} {'activa' if len(active_keys) == 1 else 'activas'}")
        with key_container:
            if not current_keys:
                with ui.column().classes("w-full items-center p-8 gap-1").style(
                    "border-top:1px solid var(--mn-line)"
                ):
                    ui.icon("vpn_key", size="2.5rem").classes("text-slate-300")
                    ui.label("Sin API Keys").classes("font-semibold mt-1")
                return

            def render_key(k: dict) -> None:
                is_active = k.get("is_active", False)
                with ui.row().classes(f"mn-key w-full no-wrap items-start gap-4 {'' if is_active else 'mn-key--off'}"):
                    with ui.element("div").classes("mn-key-icon"):
                        ui.icon("vpn_key").classes("text-[20px]")

                    with ui.column().classes("gap-3 flex-1 min-w-0"):
                        with ui.row().classes("items-center gap-3"):
                            ui.label(k.get("name", "Sin nombre")).classes("font-semibold text-[15px]")
                            theme.status_pill(is_active, "Activa", "Revocada")

                        with ui.row().classes("items-center gap-1 no-wrap"):
                            ui.label(k.get("key_id", "")).classes("mn-mono text-[13px] break-all")
                            ui.button(
                                icon="content_copy",
                                on_click=lambda v=k.get("key_id", ""): ui.run_javascript(_copy_js(v)),
                            ).props('flat round dense size=sm color=grey-7 aria-label="Copiar prefijo de la key"')

                        with ui.row().classes("gap-2"):
                            for scope in k.get("scopes", []):
                                ui.label(scope).classes("mn-chip")

                        expires = k.get("expires_at")
                        with ui.row().classes("items-center gap-x-5 gap-y-1 text-[13px] mn-muted"):
                            ui.label(f"Expira: {theme.fmt_date(expires) if expires else 'sin vencimiento'}")
                            ui.label(f"Creada: {theme.fmt_date(k.get('created_at'))}")
                            with ui.row().classes("items-center gap-1 no-wrap"):
                                ui.label(f"ID {k.get('id', '')}").classes("mn-mono break-all")
                                ui.button(
                                    icon="content_copy",
                                    on_click=lambda v=str(k.get("id", "")): ui.run_javascript(_copy_js(v)),
                                ).props('flat round dense size=xs color=grey-7 aria-label="Copiar ID de la key"')

                    if is_active:
                        revoke_dialog = ui.dialog()
                        with revoke_dialog:
                            with ui.card().classes("p-5 w-80"):
                                ui.label("¿Revocar esta API Key?").classes(
                                    "font-bold text-negative mb-2"
                                )
                                ui.label(
                                    "Esta acción es permanente. Las integraciones que usen esta key dejarán de funcionar."
                                ).classes("text-sm mn-muted mb-4")

                                async def do_revoke(
                                    kid: str = str(k["id"]),
                                    dlg: ui.dialog = revoke_dialog,
                                ) -> None:
                                    try:
                                        await api.revoke_key(_token(), tenant_id, kid)
                                        dlg.close()
                                        ui.notify("API Key revocada.", type="positive")
                                        fresh = await api.get_tenant_keys(_token(), tenant_id)
                                        keys_data["data"] = fresh.get("data", [])
                                        await build_keys()
                                    except Exception as ex:
                                        ui.notify(f"Error: {ex}", type="negative")

                                with ui.row().classes("justify-end gap-2"):
                                    ui.button("Cancelar", on_click=revoke_dialog.close).props(
                                        "flat no-caps"
                                    )
                                    ui.button("Revocar", on_click=do_revoke).props(
                                        'unelevated no-caps color="negative"'
                                    )

                        ui.button(
                            "Revocar", icon="block", on_click=revoke_dialog.open
                        ).props("outline no-caps color=negative").classes("shrink-0")

            for k in active_keys:
                render_key(k)
            if not active_keys:
                ui.label("No hay API keys activas.").classes(
                    "w-full px-6 pb-5 text-sm mn-muted"
                ).style("border-top:1px solid var(--mn-line);padding-top:20px")
            if revoked_keys:
                with ui.expansion(f"Revocadas ({len(revoked_keys)})", icon="block").classes(
                    "mn-revoked w-full"
                ):
                    for k in revoked_keys:
                        render_key(k)

    await build_keys()


# ─── Productos + existencias (opción 1) ───────────────────────────────────────
# Catálogo y existencias en una sola pantalla: cada producto muestra cuánto hay
# disponible en total y, al abrirlo, en qué zona, ubicación y lote está.
# La página /stock sigue existiendo con sus propios diálogos (theme.SHOW_STOCK_PAGE).

async def _load_locations(tenant_id: str) -> tuple[list[dict], dict[str, list[dict]]]:
    """Almacenes del tenant y sus zonas: para los selectores y para nombrar cada saldo."""
    warehouses: list[dict] = []
    zones_by_wh: dict[str, list[dict]] = {}
    try:
        warehouses = await api.list_warehouses(_token(), tenant_id)
        for wh in warehouses:
            try:
                zones_by_wh[wh["id"]] = await api.list_zones(_token(), tenant_id, wh["id"])
            except Exception:
                zones_by_wh[wh["id"]] = []
    except Exception as ex:
        ui.notify(f"Error cargando almacenes: {_err_msg(ex)}", type="negative")
    return warehouses, zones_by_wh


async def _all_balances(tenant_id: str) -> list[dict]:
    """Todos los saldos del tenant (el endpoint pagina de a 200 como máximo)."""
    items: list[dict] = []
    page = 1
    while True:
        data = await api.list_stock(_token(), tenant_id, page=page, page_size=200)
        items.extend(data.get("data", []))
        if page >= data.get("pagination", {}).get("total_pages", 1):
            return items
        page += 1


def _zone_type_label(zone_type: str | None) -> str:
    """'RECEIVING' → 'Recepción' (la etiqueta de la pantalla de Almacenes, sin la explicación)."""
    if not zone_type:
        return "—"
    return ZONE_TYPES.get(zone_type, zone_type).split(" — ")[0]


def _qty(value: Any) -> str:
    """'96.0000' → '96'; '9.5000' → '9.5'."""
    number = float(value or 0)
    if number == int(number):
        return f"{number:,.0f}"
    return f"{number:,.2f}".rstrip("0")


class _StockDialogs:
    """Entrada de stock, ajuste general y ajuste de una fila de saldo concreta."""

    def __init__(self, tenant_id: str, warehouses: list[dict], zones_by_wh: dict[str, list[dict]], on_done) -> None:
        self.tenant_id = tenant_id
        self.zones_by_wh = zones_by_wh
        self.on_done = on_done
        self.row: dict = {}
        wh_options = {w["id"]: w["name"] for w in warehouses}

        # ── Entrada de stock ──────────────────────────────────────────────────
        self.receipt = ui.dialog().props("persistent")
        with self.receipt, ui.card().classes("w-[480px] p-6"):
            ui.label("Entrada de stock").classes("text-xl font-bold mb-2")
            self.r_wh = ui.select(
                wh_options, label="Almacén *", on_change=lambda e: self._fill_zones(e.value, self.r_zone)
            ).classes("w-full")
            self.r_zone = ui.select({}, label="Zona *").classes("w-full mt-2")
            self.r_product = ui.select({}, label="Producto *", with_input=True).classes("w-full mt-2")
            self.r_qty = ui.number("Cantidad *", min=0.0001, step=1, format="%.0f").classes("w-full mt-2")
            self.r_cost = ui.number("Costo unitario *", min=0, step=100, format="%.2f").classes(
                "w-full mt-2"
            ).props('prefix="$"')
            self.r_lot = ui.input("Lote", placeholder="Obligatorio si el producto maneja lotes").classes("w-full mt-2")
            self.r_ref = ui.input("Referencia", value="CARGA-MANUAL").classes("w-full mt-2")
            self.r_err = ui.label("").classes("text-negative text-sm mt-1")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=self.receipt.close).props("flat no-caps")
                ui.button("Registrar entrada", on_click=self._do_receipt).props("unelevated no-caps color=primary")

        # ── Ajuste general (cantidad real contada) ───────────────────────────
        self.adjust = ui.dialog().props("persistent")
        with self.adjust, ui.card().classes("w-[480px] p-6"):
            ui.label("Ajustar stock").classes("text-xl font-bold mb-1")
            ui.label("Ingresa la cantidad REAL que hay físicamente.").classes("text-sm mn-muted mb-2")
            self.a_wh = ui.select(
                wh_options, label="Almacén *", on_change=lambda e: self._fill_zones(e.value, self.a_zone)
            ).classes("w-full")
            self.a_zone = ui.select({}, label="Zona *").classes("w-full mt-2")
            self.a_product = ui.select({}, label="Producto *", with_input=True).classes("w-full mt-2")
            self.a_qty = ui.number("Cantidad real *", min=0, step=1, format="%.0f").classes("w-full mt-2")
            self.a_lot = ui.input("Lote", placeholder="Obligatorio si el producto maneja lotes").classes("w-full mt-2")
            self.a_ref = ui.input("Referencia", value="AJUSTE-MANUAL").classes("w-full mt-2")
            self.a_err = ui.label("").classes("text-negative text-sm mt-1")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=self.adjust.close).props("flat no-caps")
                ui.button("Registrar ajuste", on_click=self._do_adjust).props("unelevated no-caps color=warning")

        # ── Ajuste de una fila (zona + ubicación + lote concretos) ────────────
        self.row_dialog = ui.dialog().props("persistent")
        with self.row_dialog, ui.card().classes("w-[420px] p-6"):
            ui.label("Ajustar cantidad").classes("text-xl font-bold mb-1")
            self.row_info = ui.label("").classes("text-sm mn-muted mb-4")
            self.row_qty = ui.number("Nueva cantidad real *", min=0, step=1, format="%.0f").classes("w-full")
            self.row_err = ui.label("").classes("text-negative text-sm mt-1")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=self.row_dialog.close).props("flat no-caps")
                ui.button("Guardar", on_click=self._do_row).props("unelevated no-caps color=primary")

    def _fill_zones(self, warehouse_id: str | None, zone_select: ui.select) -> None:
        zone_select.options = {z["id"]: z["name"] for z in self.zones_by_wh.get(warehouse_id or "", [])}
        zone_select.value = None
        zone_select.update()

    def set_products(self, products: list[dict]) -> None:
        options = {p["id"]: f"{p['sku']} — {p['name']}" for p in products}
        for select in (self.r_product, self.a_product):
            select.options = options
            select.update()

    def open_receipt(self) -> None:
        self.r_err.set_text("")
        self.receipt.open()

    def open_adjust(self) -> None:
        self.a_err.set_text("")
        self.adjust.open()

    def open_row(self, row: dict) -> None:
        self.row = dict(row)
        self.row_info.set_text(_row_label(row))
        self.row_qty.set_value(float(row.get("physical_qty") or 0))
        self.row_err.set_text("")
        self.row_dialog.open()

    async def _do_receipt(self) -> None:
        self.r_err.set_text("")
        if not all([self.r_wh.value, self.r_zone.value, self.r_product.value, self.r_qty.value]) or self.r_cost.value is None:
            self.r_err.set_text("Todos los campos marcados con * son obligatorios.")
            return
        payload = {
            "reference_type": "INITIAL_STOCK",
            "reference_id": self.r_ref.value or "CARGA-MANUAL",
            "reason_code": "CARGA_INICIAL",
            "warehouse_id": self.r_wh.value,
            "zone_id": self.r_zone.value,
            "items": [{
                "product_id": self.r_product.value,
                "quantity": float(self.r_qty.value),
                "unit_cost": float(self.r_cost.value),
                "lot_number": (self.r_lot.value or "").strip() or None,
            }],
        }
        try:
            await api.stock_receipt(_token(), self.tenant_id, payload)
            ui.notify("Entrada registrada.", type="positive")
            self.receipt.close()
            await self.on_done()
        except Exception as ex:
            self.r_err.set_text(_err_msg(ex))

    async def _do_adjust(self) -> None:
        self.a_err.set_text("")
        if not all([self.a_wh.value, self.a_zone.value, self.a_product.value]) or self.a_qty.value is None:
            self.a_err.set_text("Todos los campos marcados con * son obligatorios.")
            return
        payload = {
            "reference_id": self.a_ref.value or "AJUSTE-MANUAL",
            "reason_code": "CONTEO_FISICO",
            "warehouse_id": self.a_wh.value,
            "zone_id": self.a_zone.value,
            "items": [{
                "product_id": self.a_product.value,
                "new_qty": float(self.a_qty.value),
                "lot_number": (self.a_lot.value or "").strip() or None,
            }],
        }
        try:
            await api.stock_adjustment(_token(), self.tenant_id, payload)
            ui.notify("Ajuste registrado.", type="positive")
            self.adjust.close()
            await self.on_done()
        except Exception as ex:
            self.a_err.set_text(_err_msg(ex))

    async def _do_row(self) -> None:
        self.row_err.set_text("")
        if self.row_qty.value is None:
            self.row_err.set_text("Ingresa la cantidad.")
            return
        payload = {
            "reference_id": "AJUSTE-MANUAL",
            "reason_code": "CONTEO_FISICO",
            "warehouse_id": self.row["warehouse_id"],
            "zone_id": self.row["zone_id"],
            "items": [{
                "product_id": self.row["product_id"],
                "new_qty": float(self.row_qty.value),
                **_row_location(self.row),
            }],
        }
        try:
            await api.stock_adjustment(_token(), self.tenant_id, payload)
            ui.notify("Stock actualizado.", type="positive")
            self.row_dialog.close()
            await self.on_done()
        except Exception as ex:
            self.row_err.set_text(_err_msg(ex))


_PRODUCT_ROW_SLOT = """
<q-tr :props="props">
    <q-td key="name" :props="props">
        <div class="mn-tenant-text">
            <span class="mn-tenant-name">{{ props.row.name }}</span>
            <span class="mn-mono mn-tenant-slug">{{ props.row.sku }}</span>
        </div>
    </q-td>
    <q-td key="base_uom" :props="props">{{ props.row.base_uom }}</q-td>
    <q-td key="price" :props="props">{{ props.row.price_str }}</q-td>
    <q-td key="available" :props="props">
        <div style="display:flex;flex-direction:column;align-items:flex-start;gap:2px">
            <span class="mn-pill" :class="props.row.available_num > 0 ? 'mn-pill--ok' : ''">{{ props.row.available }}</span>
            <span v-if="props.row.reserved_label" class="text-xs mn-muted">{{ props.row.reserved_label }}</span>
        </div>
    </q-td>
    <q-td key="where" :props="props" class="mn-muted">{{ props.row.where }}</q-td>
    <q-td key="actions" :props="props" class="text-no-wrap">
        <q-btn flat round dense icon="edit" color="primary" :aria-label="'Editar ' + props.row.name"
               @click="$parent.$emit('edit', props.row)" />
        <q-btn flat round dense icon="delete" color="negative" :aria-label="'Desactivar ' + props.row.name"
               @click="$parent.$emit('delete', props.row)" />
        <q-btn flat round dense color="grey-7" :icon="props.expand ? 'expand_less' : 'expand_more'"
               :aria-expanded="props.expand ? 'true' : 'false'"
               :aria-label="'Ver dónde está ' + props.row.name"
               @click="props.expand = !props.expand" />
    </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" class="mn-locs-tr">
    <q-td colspan="100%" class="mn-locs-cell">
        <div class="mn-locs">
            <template v-if="props.row.locations.length">
                <div class="mn-loc mn-loc--head">
                    <span>Almacén</span><span>Zona</span><span>Ubicación</span><span>Lote</span><span>Proveedor</span>
                    <span class="num">Físico</span><span class="num">Reservado</span><span class="num">Disponible</span><span></span>
                </div>
                <div v-for="loc in props.row.locations" :key="loc.id" class="mn-loc">
                    <span>
                        <span>{{ loc.warehouse_name }}</span>
                        <span v-if="loc.warehouse_code" class="sub mn-mono">{{ loc.warehouse_code }}</span>
                    </span>
                    <span>
                        <span>{{ loc.zone_type_label }}</span>
                        <span v-if="loc.zone_detail" class="sub">{{ loc.zone_detail }}</span>
                    </span>
                    <span>
                        <span :class="loc.bin_code ? 'mn-mono' : 'mn-muted'">{{ loc.bin_str }}</span>
                        <span v-if="loc.bin_name" class="sub">{{ loc.bin_name }}</span>
                    </span>
                    <span :class="loc.lot_number ? 'mn-mono' : 'mn-muted'">{{ loc.lot_str }}</span>
                    <span>
                        <span :class="loc.supplier_id ? '' : 'mn-muted'">{{ loc.supplier_name }}</span>
                        <span v-if="loc.supplier_code" class="sub mn-mono">{{ loc.supplier_code }}</span>
                    </span>
                    <span class="num">{{ loc.physical }}</span>
                    <span class="num">{{ loc.reserved }}</span>
                    <span class="avail">{{ loc.available }}</span>
                    <q-btn flat round dense icon="tune" color="warning" :aria-label="'Ajustar ' + loc.where_label"
                           @click="$parent.$emit('adjust_loc', loc)" />
                </div>
            </template>
            <div v-else class="mn-locs-empty">Sin existencias. Usa «Entrada de stock» para registrar la primera.</div>
        </div>
    </q-td>
</q-tr>
"""


@ui.page("/tenants/{tenant_id}/products")
async def page_products(tenant_id: str) -> None:
    _guard()
    tenant = await theme.shell("products", tenant_id=tenant_id)
    theme.sub_header(tenant, tenant_id, "Productos")
    subtitle = ui.label("").classes("mn-muted").style("margin-top:-16px")

    warehouses, zones_by_wh = await _load_locations(tenant_id)
    wh_names = {str(w["id"]).lower(): w["name"] for w in warehouses}
    zone_names = {str(z["id"]).lower(): z["name"] for zones in zones_by_wh.values() for z in zones}
    whs_by_id = {str(w["id"]).lower(): w for w in warehouses}
    zones_by_id = {str(z["id"]).lower(): z for zones in zones_by_wh.values() for z in zones}
    try:
        suppliers_by_id = {str(s["id"]).lower(): s for s in await api.list_suppliers(_token(), tenant_id)}
    except Exception:
        suppliers_by_id = {}

    # ── Diálogos de producto (ficha del catálogo) ─────────────────────────────
    editing: dict = {}

    product_dialog = ui.dialog().props("persistent")
    with product_dialog:
        with ui.card().classes("w-[480px] p-6"):
            dialog_title = ui.label("Nuevo Producto").classes("text-xl font-bold mb-4")

            sku_in = ui.input("SKU *", placeholder="FILTRO-001").classes("w-full")
            name_in = ui.input("Nombre *", placeholder="Filtro de aceite").classes("w-full mt-2")
            price_in = ui.number("Precio de venta", min=0, step=100, format="%.2f").classes("w-full mt-2").props('outlined prefix="$"')
            uom_in = ui.input("Unidad de medida *", placeholder="UND").classes("w-full mt-2")
            desc_in = ui.textarea("Descripción", placeholder="Descripción opcional").classes("w-full mt-2").props("rows=2")
            dialog_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def do_save() -> None:
                dialog_err.set_text("")
                if not sku_in.value or not name_in.value or not uom_in.value:
                    dialog_err.set_text("SKU, nombre y unidad de medida son obligatorios.")
                    return
                payload: dict = {
                    "sku": sku_in.value.strip(),
                    "name": name_in.value.strip(),
                    "base_uom": uom_in.value.strip().upper(),
                    "description": desc_in.value.strip() or None,
                    "sale_price": float(price_in.value) if price_in.value else None,
                }
                try:
                    if editing.get("id"):
                        update_payload = {
                            "name": payload["name"],
                            "description": payload["description"],
                            "sale_price": payload["sale_price"],
                        }
                        await api.update_product(_token(), tenant_id, editing["id"], update_payload)
                        ui.notify("Producto actualizado.", type="positive")
                    else:
                        await api.create_product(_token(), tenant_id, payload)
                        ui.notify("Producto creado.", type="positive")
                    product_dialog.close()
                    editing.clear()
                    await load_products(search_input.value)
                except Exception as ex:
                    dialog_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=lambda: (product_dialog.close(), editing.clear())).props("flat")
                ui.button("Guardar", on_click=do_save).props('unelevated color="primary"')

    confirm_delete = ui.dialog().props("persistent")
    deleting: dict = {}
    with confirm_delete:
        with ui.card().classes("p-5 w-80"):
            ui.label("¿Desactivar este producto?").classes("font-bold text-red-600 mb-2")
            ui.label("El producto dejará de aparecer en el catálogo.").classes("text-sm text-gray-600 mb-4")

            async def do_delete() -> None:
                try:
                    await api.delete_product(_token(), tenant_id, deleting["id"])
                    confirm_delete.close()
                    ui.notify("Producto desactivado.", type="positive")
                    await load_products(search_input.value)
                except Exception as ex:
                    ui.notify(_err_msg(ex), type="negative")

            with ui.row().classes("justify-end gap-2"):
                ui.button("Cancelar", on_click=confirm_delete.close).props("flat")
                ui.button("Desactivar", on_click=do_delete).props('unelevated color="negative"')

    def open_new_product() -> None:
        editing.clear()
        sku_in.set_value("")
        name_in.set_value("")
        price_in.set_value(None)
        uom_in.set_value("")
        desc_in.set_value("")
        dialog_title.set_text("Nuevo Producto")
        dialog_err.set_text("")
        sku_in.props(remove="readonly")
        product_dialog.open()

    def on_edit(e: Any) -> None:
        row = e.args
        editing.update({"id": row["id"]})
        sku_in.set_value(row["sku"])
        name_in.set_value(row["name"])
        price_in.set_value(float(row["sale_price"]) if row.get("sale_price") else None)
        uom_in.set_value(row["base_uom"])
        desc_in.set_value(row.get("description") or "")
        dialog_title.set_text("Editar Producto")
        dialog_err.set_text("")
        sku_in.props("readonly")
        product_dialog.open()

    def on_delete(e: Any) -> None:
        deleting.update({"id": e.args["id"]})
        confirm_delete.open()

    # ── Diálogos de stock (entrada, ajuste, ajuste de una fila) ───────────────
    stock = _StockDialogs(tenant_id, warehouses, zones_by_wh, on_done=lambda: load_products(search_input.value))

    # ── Barra de acciones ─────────────────────────────────────────────────────
    with ui.row().classes("w-full items-center gap-3"):
        search_input = ui.input(placeholder="Buscar por SKU o nombre…").props(
            'dense clearable aria-label="Buscar producto"'
        ).classes("flex-1 min-w-[240px]")
        with search_input.add_slot("prepend"):
            ui.icon("search")
        ui.button("Entrada de stock", icon="add", on_click=stock.open_receipt).props("outline no-caps color=primary")
        ui.button("Ajustar stock", icon="tune", on_click=stock.open_adjust).props("outline no-caps color=warning")
        ui.button("Nuevo producto", icon="add", on_click=open_new_product).props("unelevated no-caps color=primary")

    product_container = ui.column().classes("w-full gap-0")

    columns = [
        {"name": "name", "label": "Producto", "field": "name", "align": "left", "sortable": True},
        {"name": "base_uom", "label": "Unidad", "field": "base_uom", "align": "left"},
        {"name": "price", "label": "Precio", "field": "price_str", "align": "left"},
        {"name": "available", "label": "Disponible", "field": "available_num", "align": "left", "sortable": True},
        {"name": "where", "label": "Dónde está", "field": "where", "align": "left"},
        {"name": "actions", "label": "", "field": "id", "align": "right"},
    ]

    def build_rows(products: list[dict], balances: list[dict]) -> list[dict]:
        by_product: dict[str, list[dict]] = {}
        for b in balances:
            # Un saldo en cero (p. ej. tras «poner en 0») no es una ubicación con stock.
            if float(b["physical_qty"]) == 0 and float(b["reserved_qty"]) == 0:
                continue
            by_product.setdefault(str(b["product_id"]).lower(), []).append(b)

        rows = []
        for p in products:
            product_name = f"{p['sku']} — {p['name']}"
            locs = []
            for b in by_product.get(str(p["id"]).lower(), []):
                zone_name = zone_names.get(str(b["zone_id"]).lower(), "—")
                bin_str = b.get("bin_code") or "Sin ubicar"
                zone = zones_by_id.get(str(b["zone_id"]).lower(), {})
                wh = whs_by_id.get(str(b["warehouse_id"]).lower(), {})
                supplier = suppliers_by_id.get(str(b.get("supplier_id") or "").lower())
                if supplier:
                    supplier_name, supplier_code = supplier["name"], supplier.get("code", "")
                elif b.get("supplier_id"):
                    supplier_name, supplier_code = "Proveedor no encontrado", str(b["supplier_id"])[:8]
                else:
                    supplier_name, supplier_code = "—", ""
                locs.append({
                    **b,
                    "warehouse_code": wh.get("code", ""),
                    "zone_type_label": _zone_type_label(zone.get("zone_type")),
                    "zone_detail": " · ".join(x for x in (zone.get("name"), zone.get("code")) if x),
                    "bin_name": b.get("bin_name") or "",
                    "supplier_name": supplier_name,
                    "supplier_code": supplier_code,
                    "product_name": product_name,
                    "warehouse_name": wh_names.get(str(b["warehouse_id"]).lower(), "—"),
                    "zone_name": zone_name,
                    "bin_str": bin_str,
                    "lot_str": b.get("lot_number") or "—",
                    "expiry_str": theme.fmt_date(b.get("expiry_date")) if b.get("expiry_date") else "—",
                    "physical": _qty(b["physical_qty"]),
                    "reserved": _qty(b["reserved_qty"]),
                    "available": _qty(b["available_qty"]),
                    "where_label": f"{zone_name} · {bin_str}",
                    "is_next": False,
                })
            locs.sort(key=lambda loc: (loc["zone_name"], loc.get("bin_code") or "", loc.get("lot_number") or ""))
            # Marca el lote que sale primero (el que vence antes), como hace la reserva FEFO.
            dated = [loc for loc in locs if loc.get("expiry_date")]
            if dated:
                min(dated, key=lambda loc: loc["expiry_date"])["is_next"] = True

            available = sum(float(loc["available_qty"]) for loc in locs)
            reserved = sum(float(loc["reserved_qty"]) for loc in locs)
            lots = {loc["lot_number"] for loc in locs if loc.get("lot_number")}
            if not locs:
                where = "Sin existencias"
            else:
                where = theme.plural(len(locs), "ubicación", "ubicaciones")
                if lots:
                    where += f" · {theme.plural(len(lots), 'lote')}"
            rows.append({
                **p,
                "price_str": f"${float(p['sale_price']):,.0f}" if p.get("sale_price") else "—",
                "available_num": available,
                "available": _qty(available),
                "reserved_label": f"{_qty(reserved)} reservada{'s' if reserved != 1 else ''}" if reserved else "",
                "where": where,
                "locations": locs,
            })
        return rows

    async def load_products(search: str | None = None) -> None:
        product_container.clear()
        try:
            data = await api.list_products(_token(), tenant_id, search=search or None, page_size=200)
            products = data.get("data", [])
            total = data.get("pagination", {}).get("total_items", 0)
            balances = await _all_balances(tenant_id)
        except Exception as ex:
            ui.notify(f"Error cargando productos: {_err_msg(ex)}", type="negative")
            return

        if not search:
            stock.set_products(products)
        subtitle.set_text(
            f"{theme.plural(total, 'producto')} · el disponible suma todas las ubicaciones. "
            "Abre un producto para ver dónde está."
        )

        with product_container:
            if not products:
                with ui.column().classes("w-full items-center p-12 gap-1"):
                    ui.icon("inventory_2", size="3rem").classes("text-slate-300")
                    ui.label("Sin productos").classes("font-semibold mt-2")
                return

            grouped: dict[str, list[dict]] = {}
            for row in build_rows(products, balances):
                cat = row.get("category")
                grouped.setdefault(cat.get("name") if cat else "Sin Categoría", []).append(row)

            sorted_cats = sorted(grouped.keys(), key=lambda x: (x == "Sin Categoría", x))
            for i, cat_name in enumerate(sorted_cats):
                with theme.category_expansion(cat_name, len(grouped[cat_name]), i):
                    tbl = ui.table(columns=columns, rows=grouped[cat_name], row_key="id").classes(
                        "w-full shadow-none border-t"
                    )
                    tbl.props("wrap-cells")
                    tbl.add_slot("body", _PRODUCT_ROW_SLOT)
                    tbl.on("edit", on_edit)
                    tbl.on("delete", on_delete)
                    tbl.on("adjust_loc", lambda e: stock.open_row(e.args))

    search_input.on("keydown.enter", lambda: load_products(search_input.value))
    search_input.on("clear", lambda: load_products(None))

    await load_products()


# ─── Stock page ──────────────────────────────────────────────────────────────

@ui.page("/tenants/{tenant_id}/stock")
async def page_stock(tenant_id: str) -> None:
    _guard()
    tenant = await theme.shell("stock", tenant_id=tenant_id)
    theme.sub_header(tenant, tenant_id, "Stock")

    # Cargar almacenes y productos para los formularios
    warehouses: list[dict] = []
    zones_by_wh: dict[str, list[dict]] = {}
    products_cache: list[dict] = []

    try:
        warehouses = await api.list_warehouses(_token(), tenant_id)
        for wh in warehouses:
            try:
                zones_by_wh[wh["id"]] = await api.list_zones(_token(), tenant_id, wh["id"])
            except Exception as ez:
                print(f"Error loading zones for wh {wh['id']}:", ez)
    except Exception as ew:
        print("Error loading warehouses:", ew)

    try:
        prod_data = await api.list_products(_token(), tenant_id, page_size=200)
        products_cache = prod_data.get("data", [])
    except Exception as ep:
        print("Error loading products:", ep)


    wh_options = {w["id"]: w["name"] for w in warehouses}

    stock_container = ui.column().classes("w-full")

    # ── Dialogs ───────────────────────────────────────────────────────────────

    # Entrada de stock
    receipt_dialog = ui.dialog().props("persistent")
    with receipt_dialog:
        with ui.card().classes("w-[480px] p-6"):
            ui.label("Entrada de Stock").classes("text-xl font-bold mb-4")

            r_wh = ui.select(wh_options, label="Almacén *").classes("w-full")
            r_zone = ui.select({}, label="Zona *").classes("w-full mt-2")
            r_product = ui.select(
                {p["id"]: f"{p['sku']} — {p['name']}" for p in products_cache},
                label="Producto *",
            ).classes("w-full mt-2")
            r_qty = ui.number("Cantidad *", min=0.0001, step=1, format="%.0f").classes("w-full mt-2")
            r_cost = ui.number("Costo unitario *", min=0, step=100, format="%.2f").classes("w-full mt-2").props('prefix="$"')
            r_lot = ui.input("Lote", placeholder="Obligatorio si el producto maneja lotes").classes("w-full mt-2")
            r_ref = ui.input("Referencia", value="CARGA-MANUAL").classes("w-full mt-2")
            r_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def on_wh_change_r(e: Any) -> None:
                zones = zones_by_wh.get(r_wh.value, [])
                r_zone.options = {z["id"]: z["name"] for z in zones}
                r_zone.value = None
                r_zone.update()

            r_wh.on("update:model-value", on_wh_change_r)

            async def do_receipt() -> None:
                r_err.set_text("")
                if not all([r_wh.value, r_zone.value, r_product.value, r_qty.value, r_cost.value]):
                    r_err.set_text("Todos los campos marcados con * son obligatorios.")
                    return
                payload = {
                    "reference_type": "INITIAL_STOCK",
                    "reference_id": r_ref.value or "CARGA-MANUAL",
                    "reason_code": "CARGA_INICIAL",
                    "warehouse_id": r_wh.value,
                    "zone_id": r_zone.value,
                    "items": [{
                        "product_id": r_product.value,
                        "quantity": float(r_qty.value),
                        "unit_cost": float(r_cost.value),
                        "lot_number": (r_lot.value or "").strip() or None,
                    }],
                }
                try:
                    await api.stock_receipt(_token(), tenant_id, payload)
                    ui.notify("Entrada registrada.", type="positive")
                    receipt_dialog.close()
                    await load_stock()
                except Exception as ex:
                    r_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=receipt_dialog.close).props("flat")
                ui.button("Registrar Entrada", on_click=do_receipt).props('unelevated color="primary"')

    # Ajuste de stock
    adjust_dialog = ui.dialog().props("persistent")
    with adjust_dialog:
        with ui.card().classes("w-[480px] p-6"):
            ui.label("Ajuste de Stock").classes("text-xl font-bold mb-4")
            ui.label("Ingresa la cantidad REAL que hay físicamente.").classes("text-sm text-gray-500 mb-2")

            a_wh = ui.select(wh_options, label="Almacén *").classes("w-full")
            a_zone = ui.select({}, label="Zona *").classes("w-full mt-2")
            a_product = ui.select(
                {p["id"]: f"{p['sku']} — {p['name']}" for p in products_cache},
                label="Producto *",
            ).classes("w-full mt-2")
            a_qty = ui.number("Cantidad real *", min=0, step=1, format="%.0f").classes("w-full mt-2")
            a_lot = ui.input("Lote", placeholder="Obligatorio si el producto maneja lotes").classes("w-full mt-2")
            a_ref = ui.input("Referencia", value="AJUSTE-MANUAL").classes("w-full mt-2")
            a_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def on_wh_change_a(e: Any) -> None:
                zones = zones_by_wh.get(a_wh.value, [])
                a_zone.options = {z["id"]: z["name"] for z in zones}
                a_zone.value = None
                a_zone.update()

            a_wh.on("update:model-value", on_wh_change_a)

            async def do_adjust() -> None:
                a_err.set_text("")
                if not all([a_wh.value, a_zone.value, a_product.value, a_qty.value is not None]):
                    a_err.set_text("Todos los campos marcados con * son obligatorios.")
                    return
                payload = {
                    "reference_id": a_ref.value or "AJUSTE-MANUAL",
                    "reason_code": "CONTEO_FISICO",
                    "warehouse_id": a_wh.value,
                    "zone_id": a_zone.value,
                    "items": [{
                        "product_id": a_product.value,
                        "new_qty": float(a_qty.value),
                        "lot_number": (a_lot.value or "").strip() or None,
                    }],
                }
                try:
                    await api.stock_adjustment(_token(), tenant_id, payload)
                    ui.notify("Ajuste registrado.", type="positive")
                    adjust_dialog.close()
                    await load_stock()
                except Exception as ex:
                    a_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=adjust_dialog.close).props("flat")
                ui.button("Registrar Ajuste", on_click=do_adjust).props('unelevated color="warning"')

    # ── Tabla de saldos ───────────────────────────────────────────────────────
    async def load_stock() -> None:
        stock_container.clear()
        with stock_container:
            try:
                data = await api.list_stock(_token(), tenant_id)
                items = data.get("data", [])
                total = data.get("pagination", {}).get("total_items", 0)

                with ui.row().classes("w-full justify-between items-center mb-2"):
                    ui.label(f"{total} saldo(s) de stock").classes("text-sm text-gray-500")
                    with ui.row().classes("gap-2"):
                        ui.button("Entrada de stock", icon="add", on_click=receipt_dialog.open).props('unelevated no-caps color="primary"')
                        ui.button("Ajustar stock", icon="tune", on_click=adjust_dialog.open).props('unelevated no-caps color="warning"')

                if not items:
                    with ui.card().classes("w-full p-8 text-center"):
                        ui.icon("inventory", size="4rem").classes("text-gray-300")
                        ui.label("Sin movimientos de stock registrados").classes("text-gray-500 mt-2")
                    return

                prod_map = {str(p["id"]).lower(): f"{p['sku']} — {p['name']}" for p in products_cache}
                wh_map = {str(w["id"]).lower(): w["name"] for w in warehouses}
                all_zones = {str(z["id"]).lower(): z["name"] for zones in zones_by_wh.values() for z in zones}

                columns = [
                    {"name": "product", "label": "Producto", "field": "product_name", "align": "left"},
                    {"name": "warehouse", "label": "Almacén", "field": "warehouse_name", "align": "left"},
                    {"name": "zone", "label": "Zona", "field": "zone_name", "align": "left"},
                    {"name": "lot", "label": "Lote", "field": "lot_str", "align": "left"},
                    {"name": "bin", "label": "Ubicación", "field": "bin_str", "align": "left"},
                    {"name": "physical", "label": "Físico", "field": "physical_qty", "align": "right"},
                    {"name": "reserved", "label": "Reservado", "field": "reserved_qty", "align": "right"},
                    {"name": "available", "label": "Disponible", "field": "available_qty", "align": "right"},
                    {"name": "actions", "label": "", "field": "id", "align": "center"},
                ]

                # Diálogo simplificado de edición por fila
                edit_stock_row: dict = {}
                edit_stock_dialog = ui.dialog().props("persistent")
                with edit_stock_dialog:
                    with ui.card().classes("w-[400px] p-6"):
                        ui.label("Ajustar Cantidad").classes("text-xl font-bold mb-1")
                        edit_stock_info = ui.label("").classes("text-sm text-gray-500 mb-4")
                        edit_stock_qty = ui.number("Nueva cantidad real *", min=0, step=1, format="%.0f").classes("w-full")
                        edit_stock_err = ui.label("").classes("text-red-500 text-sm mt-1")

                        async def do_edit_stock() -> None:
                            edit_stock_err.set_text("")
                            if edit_stock_qty.value is None:
                                edit_stock_err.set_text("Ingresa la cantidad.")
                                return
                            payload = {
                                "reference_id": "AJUSTE-MANUAL",
                                "reason_code": "CONTEO_FISICO",
                                "warehouse_id": edit_stock_row["warehouse_id"],
                                "zone_id": edit_stock_row["zone_id"],
                                "items": [{
                                    "product_id": edit_stock_row["product_id"],
                                    "new_qty": float(edit_stock_qty.value),
                                    **_row_location(edit_stock_row),
                                }],
                            }
                            try:
                                await api.stock_adjustment(_token(), tenant_id, payload)
                                edit_stock_dialog.close()
                                ui.notify("Stock actualizado.", type="positive")
                                await load_stock()
                            except Exception as ex:
                                edit_stock_err.set_text(_err_msg(ex))

                        with ui.row().classes("w-full justify-end mt-4 gap-2"):
                            ui.button("Cancelar", on_click=edit_stock_dialog.close).props("flat")
                            ui.button("Guardar", on_click=do_edit_stock).props('unelevated color="primary"')

                def on_edit_stock(e: Any) -> None:
                    row = e.args
                    edit_stock_row.clear()
                    edit_stock_row.update(row)
                    edit_stock_info.set_text(_row_label(row))
                    edit_stock_qty.set_value(float(row["physical_qty"]))
                    edit_stock_err.set_text("")
                    edit_stock_dialog.open()

                delete_stock_row: dict = {}
                delete_stock_dialog = ui.dialog().props("persistent")
                with delete_stock_dialog:
                    with ui.card().classes("p-5 w-80"):
                        ui.label("¿Poner stock en 0?").classes("font-bold text-red-600 mb-2")
                        ui.label("Se registrará un ajuste a cantidad 0 para:").classes("text-sm text-gray-600")
                        delete_stock_info = ui.label("").classes("text-sm font-semibold mb-4")

                        async def do_delete_stock() -> None:
                            try:
                                payload = {
                                    "reference_id": "AJUSTE-MANUAL",
                                    "reason_code": "CONTEO_FISICO",
                                    "warehouse_id": delete_stock_row["warehouse_id"],
                                    "zone_id": delete_stock_row["zone_id"],
                                    "items": [{
                                        "product_id": delete_stock_row["product_id"],
                                        "new_qty": 0,
                                        **_row_location(delete_stock_row),
                                    }],
                                }
                                await api.stock_adjustment(_token(), tenant_id, payload)
                                delete_stock_dialog.close()
                                ui.notify("Stock ajustado a 0.", type="positive")
                                await load_stock()
                            except Exception as ex:
                                ui.notify(_err_msg(ex), type="negative")

                        with ui.row().classes("justify-end gap-2"):
                            ui.button("Cancelar", on_click=delete_stock_dialog.close).props("flat")
                            ui.button("Poner en 0", on_click=do_delete_stock).props('unelevated color="negative"')

                def on_delete_stock(e: Any) -> None:
                    delete_stock_row.clear()
                    delete_stock_row.update(e.args)
                    delete_stock_info.set_text(_row_label(e.args))
                    delete_stock_dialog.open()

                # Group by category
                grouped_items = {}
                for s in items:
                    prod_id = str(s["product_id"]).lower()
                    prod_info = next((p for p in products_cache if str(p["id"]).lower() == prod_id), {})
                    cat = prod_info.get("category")
                    cat_name = cat.get("name") if cat else "Sin Categoría"
                    
                    row_dict = {
                        **s,
                        "product_name": prod_map.get(prod_id, prod_id[:8]),
                        "warehouse_name": wh_map.get(str(s["warehouse_id"]).lower(), "—"),
                        "zone_name": all_zones.get(str(s["zone_id"]).lower(), "—"),
                        "lot_str": s.get("lot_number") or "—",
                        "bin_str": s.get("bin_code") or "Sin ubicar",
                        "physical_qty": float(s["physical_qty"]),
                        "reserved_qty": float(s["reserved_qty"]),
                        "available_qty": float(s["available_qty"]),
                    }
                    grouped_items.setdefault(cat_name, []).append(row_dict)

                sorted_cats = sorted(grouped_items.keys(), key=lambda x: (x == "Sin Categoría", x))

                for i, cat_name in enumerate(sorted_cats):
                    rows = grouped_items[cat_name]
                    with theme.category_expansion(cat_name, len(rows), i):
                        tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full shadow-none border-t")
                        # Nombres de producto y zona largos: que partan línea en vez de
                        # empujar las columnas de cantidades fuera de la vista.
                        tbl.props("wrap-cells")
                        tbl.add_slot("body-cell-available", """
                            <q-td :props="props">
                                <span class="mn-pill" :class="props.value > 0 ? 'mn-pill--ok' : ''">
                                    {{ props.value }}
                                </span>
                            </q-td>
                        """)
                        tbl.add_slot("body-cell-actions", """
                            <q-td :props="props" class="text-no-wrap">
                                <q-btn flat dense icon="edit" color="primary" size="sm"
                                       @click="$parent.$emit('edit_stock', props.row)" class="mr-1" />
                                <q-btn flat dense icon="delete" color="negative" size="sm"
                                       @click="$parent.$emit('delete_stock', props.row)" />
                            </q-td>
                        """)
                        tbl.on("edit_stock", on_edit_stock)
                        tbl.on("delete_stock", on_delete_stock)
            except Exception as ex:
                ui.notify(f"Error cargando stock: {ex}", type="negative")

    await load_stock()


# ─── Warehouses page ─────────────────────────────────────────────────────────

ZONE_TYPES = {
    "STORAGE": "Almacenamiento — stock disponible",
    "PICKING": "Alistamiento — separación de pedidos",
    "RECEIVING": "Recepción — mercancía que llega",
    "DISPATCH": "Despacho — listo para salir",
    "QUARANTINE": "Cuarentena — pendiente de inspección",
    "TRANSIT": "Tránsito — entre almacenes",
}

_CODE_RE = re.compile(r"^[A-Za-z0-9\-_]+$")


@ui.page("/tenants/{tenant_id}/warehouses")
async def page_warehouses(tenant_id: str) -> None:
    _guard()
    tenant = await theme.shell("warehouses", tenant_id=tenant_id)
    theme.sub_header(tenant, tenant_id, "Almacenes")

    wh_container = ui.column().classes("w-full")

    # ── Diálogo: nuevo almacén ────────────────────────────────────────────────
    wh_dialog = ui.dialog().props("persistent")
    with wh_dialog:
        with ui.card().classes("w-[480px] p-6"):
            ui.label("Nuevo Almacén").classes("text-xl font-bold mb-1")
            ui.label(
                "Un almacén físico nace con sus zonas de recepción, despacho y cuarentena "
                "ya creadas: queda listo para registrar stock."
            ).classes("text-sm text-gray-600 mb-4")

            wh_code_in = ui.input("Código *", placeholder="BOG-01").classes("w-full")
            ui.label("Solo letras, números, guion y guion bajo. No se puede cambiar después.").classes(
                "text-xs text-gray-500"
            )
            wh_name_in = ui.input("Nombre *", placeholder="Bodega Principal Bogotá").classes("w-full mt-2")
            wh_addr_in = ui.input("Dirección", placeholder="Calle 80 # 45-23, Bogotá").classes("w-full mt-2")
            wh_virtual_in = ui.checkbox("Almacén virtual (lógico, sin ubicación física)").classes("mt-2")
            ui.label("Los virtuales no reciben mercancía ni generan zonas automáticas.").classes(
                "text-xs text-gray-500"
            )
            wh_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def do_create_wh() -> None:
                wh_err.set_text("")
                code = (wh_code_in.value or "").strip()
                name = (wh_name_in.value or "").strip()
                if not code or not name:
                    wh_err.set_text("Código y nombre son obligatorios.")
                    return
                if not _CODE_RE.match(code):
                    wh_err.set_text("El código solo admite letras, números, guion y guion bajo.")
                    return
                payload = {
                    "code": code,
                    "name": name,
                    "location_address": (wh_addr_in.value or "").strip() or None,
                    "is_virtual": bool(wh_virtual_in.value),
                }
                try:
                    await api.create_warehouse(_token(), tenant_id, payload)
                    wh_dialog.close()
                    ui.notify("Almacén creado.", type="positive")
                    await load_warehouses()
                except Exception as ex:
                    wh_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=wh_dialog.close).props("flat")
                ui.button("Crear", on_click=do_create_wh).props('unelevated color="primary"')

    # ── Diálogo: nueva zona ───────────────────────────────────────────────────
    zone_target: dict = {}
    zone_dialog = ui.dialog().props("persistent")
    with zone_dialog:
        with ui.card().classes("w-[480px] p-6"):
            ui.label("Nueva Zona").classes("text-xl font-bold mb-1")
            zone_wh_label = ui.label("").classes("text-sm text-gray-600 mb-4")

            zone_code_in = ui.input("Código *", placeholder="ZONA-A").classes("w-full")
            zone_name_in = ui.input("Nombre *", placeholder="Zona de Almacenamiento General").classes("w-full mt-2")
            zone_type_in = ui.select(ZONE_TYPES, label="Tipo *", value="STORAGE").classes("w-full mt-2")
            zone_err = ui.label("").classes("text-red-500 text-sm mt-1")

            async def do_create_zone() -> None:
                zone_err.set_text("")
                code = (zone_code_in.value or "").strip()
                name = (zone_name_in.value or "").strip()
                if not code or not name or not zone_type_in.value:
                    zone_err.set_text("Código, nombre y tipo son obligatorios.")
                    return
                payload = {"code": code, "name": name, "zone_type": zone_type_in.value}
                try:
                    await api.create_zone(_token(), tenant_id, zone_target["id"], payload)
                    zone_dialog.close()
                    ui.notify("Zona creada.", type="positive")
                    await load_warehouses()
                except Exception as ex:
                    zone_err.set_text(_err_msg(ex))

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button("Cancelar", on_click=zone_dialog.close).props("flat")
                ui.button("Crear", on_click=do_create_zone).props('unelevated color="primary"')

    def open_wh_dialog() -> None:
        wh_code_in.set_value("")
        wh_name_in.set_value("")
        wh_addr_in.set_value("")
        wh_virtual_in.set_value(False)
        wh_err.set_text("")
        wh_dialog.open()

    def open_zone_dialog(wh: dict) -> None:
        zone_target.clear()
        zone_target.update({"id": wh["id"]})
        zone_wh_label.set_text(f"En el almacén: {wh['name']}")
        zone_code_in.set_value("")
        zone_name_in.set_value("")
        zone_type_in.set_value("STORAGE")
        zone_err.set_text("")
        zone_dialog.open()

    # ── Listado ───────────────────────────────────────────────────────────────
    async def load_warehouses() -> None:
        wh_container.clear()
        with wh_container:
            try:
                warehouses = await api.list_warehouses(_token(), tenant_id)
            except Exception as ex:
                ui.notify(f"Error cargando almacenes: {_err_msg(ex)}", type="negative")
                return

            with ui.row().classes("w-full justify-between items-center mb-2"):
                ui.label(f"{len(warehouses)} almacén(es)").classes("text-sm text-gray-500")
                ui.button("Nuevo almacén", icon="add", on_click=open_wh_dialog).props('unelevated no-caps color="primary"')

            if not warehouses:
                with ui.card().classes("w-full p-8 text-center"):
                    ui.icon("warehouse", size="4rem").classes("text-gray-300")
                    ui.label("Sin almacenes").classes("text-gray-500 mt-2")
                    ui.label(
                        "Sin al menos un almacén no se puede registrar stock: los productos "
                        "quedan creados pero sin existencias."
                    ).classes("text-sm text-gray-400 mt-1")
                return

            zone_columns = [
                {"name": "code", "label": "Código", "field": "code", "align": "left"},
                {"name": "name", "label": "Nombre", "field": "name", "align": "left"},
                {"name": "zone_type", "label": "Tipo", "field": "zone_type", "align": "center"},
            ]

            for wh in warehouses:
                try:
                    zones = await api.list_zones(_token(), tenant_id, wh["id"])
                except Exception:
                    zones = []

                kind = "Virtual" if wh.get("is_virtual") else "Físico"
                title = f"{wh['code']} — {wh['name']}  ·  {kind}  ·  {len(zones)} zona(s)"
                with ui.expansion(title, icon="warehouse").classes(
                    "w-full bg-white shadow-sm mb-2"
                ).props("default-opened"):
                    with ui.column().classes("w-full p-2 gap-2"):
                        if wh.get("location_address"):
                            ui.label(wh["location_address"]).classes("text-sm text-gray-500")
                        with ui.row().classes("w-full justify-end"):
                            ui.button(
                                "Nueva zona",
                                icon="add",
                                on_click=lambda w=wh: open_zone_dialog(w),
                            ).props('flat dense no-caps color="primary"')
                        if zones:
                            ui.table(columns=zone_columns, rows=zones, row_key="id").classes(
                                "w-full shadow-none border-t"
                            )
                        else:
                            ui.label("Este almacén no tiene zonas — no puede recibir stock todavía.").classes(
                                "text-sm text-amber-600"
                            )

    await load_warehouses()


# ─── Páginas públicas: activar cuenta y recuperar contraseña ─────────────────
# No exigen sesión: el enlace del email es la credencial. Por eso no llaman a `_guard()`.

# Misma política que el API (RN-052-4). El portal la valida antes de enviar; el API manda.
PASSWORD_MIN_LENGTH = 12
_LINK_EXPIRED = "El enlace no es válido o caducó."


def _browser_ip(request: Request) -> str:
    """IP del navegador, para que los límites del API cuenten por origen real y no por el portal."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() or (request.client.host if request.client else "")


def _password_problem(password: str | None, repeated: str | None) -> str | None:
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
    if password != repeated:
        return "Las contraseñas no coinciden."
    return None


def _public_card(title: str, subtitle: str = "") -> ui.card:
    """Tarjeta centrada con la marca, igual que el login. Devuelve la tarjeta para seguir añadiendo."""
    theme.apply_theme()
    ui.query(".nicegui-content").classes("items-center justify-center").style(
        "min-height:85vh;max-width:none"
    )
    card = ui.card().classes("w-96 max-w-full p-8 gap-0")
    with card:
        with ui.row().classes("items-center gap-3 no-wrap mb-8"):
            with ui.element("div").classes("mn-logo"):
                ui.icon("cloud").classes("text-[22px]")
            with ui.column().classes("gap-0"):
                ui.label("MicroNuba").classes("mn-brand-name")
                ui.label("Portal de administración").classes("mn-brand-sub")
        ui.label(title).classes("mn-h2 mb-1")
        if subtitle:
            ui.label(subtitle).classes("text-sm mn-muted mb-4")
    return card


def _password_fields() -> tuple[ui.input, ui.input]:
    first = ui.input("Nueva contraseña", password=True, password_toggle_button=True).classes("w-full")
    second = ui.input("Repetir contraseña", password=True, password_toggle_button=True).classes("w-full mt-4")
    ui.label(f"Mínimo {PASSWORD_MIN_LENGTH} caracteres.").classes("text-xs mn-muted mt-1")
    return first, second


def _done_view(message: str, detail: str, login_email: str = "") -> None:
    ui.icon("check_circle").classes("text-positive text-5xl self-center")
    ui.label(message).classes("mn-h2 text-center mt-2")
    ui.label(detail).classes("text-sm mn-muted text-center mb-4")
    target = f"/login?email={quote(login_email)}" if login_email else "/login"
    ui.button("Iniciar sesión", on_click=lambda: ui.navigate.to(target)).classes("w-full").props(
        'color="primary" unelevated no-caps'
    )


@ui.page("/activate")
def page_activate(token: str = "") -> None:
    card = _public_card("Activa tu cuenta", "Elige una contraseña para empezar a usar la plataforma.")
    with card:
        if not token:
            ui.label(f"{_LINK_EXPIRED} Pide a tu administrador que te reenvíe la activación.").classes(
                "text-negative text-sm"
            )
            ui.link("Ir a iniciar sesión", "/login").classes("text-sm mt-4")
            return

        form = ui.column().classes("w-full gap-0")
        with form:
            password, repeated = _password_fields()
            error = ui.label("").classes("text-negative text-sm mt-2")

            async def submit() -> None:
                problem = _password_problem(password.value, repeated.value)
                if problem:
                    error.set_text(problem)
                    return
                error.set_text("")
                try:
                    data = await api.activate_account(token, password.value)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 410:
                        error.set_text(
                            f"{_LINK_EXPIRED} Pide a tu administrador que te reenvíe la activación."
                        )
                    else:
                        error.set_text(_err_msg(e))
                    return
                except Exception as ex:
                    error.set_text(f"No se pudo conectar: {ex}")
                    return
                form.clear()
                with form:
                    _done_view(
                        "Cuenta activada",
                        "Ya puedes iniciar sesión con tu nueva contraseña.",
                        data.get("email") or "",
                    )

            repeated.on("keydown.enter", submit)
            ui.button("Activar cuenta", on_click=submit).classes("w-full mt-4").props(
                'color="primary" unelevated no-caps'
            )


@ui.page("/forgot-password")
def page_forgot_password(request: Request) -> None:
    browser_ip = _browser_ip(request)
    card = _public_card(
        "¿Olvidaste tu contraseña?", "Escribe tu email y te enviaremos un enlace para restablecerla."
    )
    with card:
        form = ui.column().classes("w-full gap-0")
        with form:
            email = ui.input("Email").classes("w-full")
            error = ui.label("").classes("text-negative text-sm mt-2")

            async def submit() -> None:
                address = (email.value or "").strip()
                if "@" not in address:
                    error.set_text("Escribe un email válido.")
                    return
                error.set_text("")
                try:
                    data = await api.forgot_password(address, browser_ip)
                except httpx.HTTPStatusError as e:
                    # 429 es el único caso que no responde lo mismo para todos: es un límite de uso
                    error.set_text(_err_msg(e) if e.response.status_code == 429 else "No se pudo enviar. Inténtalo de nuevo.")
                    return
                except Exception as ex:
                    error.set_text(f"No se pudo conectar: {ex}")
                    return
                form.clear()
                with form:
                    ui.icon("mark_email_read").classes("text-primary text-5xl self-center")
                    # Siempre el mensaje del API, idéntico exista o no el email (RN-050-1)
                    ui.label(data.get("message", "")).classes("text-sm text-center mt-2 mb-4")
                    ui.link("Volver a iniciar sesión", "/login").classes("text-sm self-center")

            email.on("keydown.enter", submit)
            ui.button("Enviar enlace", on_click=submit).classes("w-full mt-4").props(
                'color="primary" unelevated no-caps'
            )
            ui.link("Volver a iniciar sesión", "/login").classes("text-sm mt-4 self-center")


@ui.page("/reset-password")
def page_reset_password(request: Request, token: str = "") -> None:
    browser_ip = _browser_ip(request)
    card = _public_card("Restablece tu contraseña", "Elige una contraseña nueva para tu cuenta.")
    with card:
        if not token:
            ui.label(_LINK_EXPIRED).classes("text-negative text-sm")
            ui.link("Solicitar un enlace nuevo", "/forgot-password").classes("text-sm mt-4")
            return

        form = ui.column().classes("w-full gap-0")
        with form:
            password, repeated = _password_fields()
            error = ui.label("").classes("text-negative text-sm mt-2")
            retry_link = ui.link("Solicitar un enlace nuevo", "/forgot-password").classes("text-sm mt-2")
            retry_link.set_visibility(False)

            async def submit() -> None:
                problem = _password_problem(password.value, repeated.value)
                if problem:
                    error.set_text(problem)
                    return
                error.set_text("")
                try:
                    await api.reset_password(token, password.value, browser_ip)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400:
                        error.set_text(_LINK_EXPIRED)
                        retry_link.set_visibility(True)
                    else:
                        error.set_text(_err_msg(e))
                    return
                except Exception as ex:
                    error.set_text(f"No se pudo conectar: {ex}")
                    return
                form.clear()
                with form:
                    _done_view(
                        "Contraseña actualizada",
                        "Cerramos tus sesiones abiertas. Inicia sesión con tu contraseña nueva.",
                    )

            repeated.on("keydown.enter", submit)
            ui.button("Cambiar contraseña", on_click=submit).classes("w-full mt-4").props(
                'color="primary" unelevated no-caps'
            )


# ─── Usuarios (RF-047, RF-048) y super admins (RF-049) ────────────────────────
# Una sola tabla y los mismos diálogos para las dos pantallas. El super_admin gestiona los
# usuarios de cualquier tenant por /admin; el tenant_admin, los de su propio tenant por /v1.

_ROLE_NAMES = {
    "super_admin": "Super admin",
    "tenant_admin": "Administrador",
    "inventory_manager": "Gestor de inventario",
    "viewer": "Solo lectura",
}
_STATUS_NAMES = {"active": "Activo", "pending": "Pendiente", "disabled": "Desactivado"}
_STATUS_FILTER = {"": "Todos", "active": "Activos", "pending": "Pendientes", "disabled": "Desactivados"}
_USERS_PAGE_SIZE = 20

# Lo que cada rol puede asignar (RN-047-1, RN-048-1). El API lo vuelve a comprobar.
_ASSIGNABLE = {
    "super_admin": ["tenant_admin", "inventory_manager", "viewer"],
    "tenant_admin": ["inventory_manager", "viewer"],
}

_USER_COLUMNS = [
    {"name": "name", "label": "Usuario", "field": "full_name", "align": "left"},
    {"name": "role", "label": "Rol", "field": "role_name", "align": "left"},
    {"name": "status", "label": "Estado", "field": "status_name", "align": "left"},
    {"name": "last_login", "label": "Último acceso", "field": "last_login_str", "align": "left"},
    {"name": "created", "label": "Alta", "field": "created_str", "align": "left"},
    {"name": "actions", "label": "", "field": "id", "align": "right"},
]

_USER_CELL_NAME = """
    <q-td :props="props">
        <div class="mn-tenant-link" style="cursor: default">
            <span class="mn-avatar" style="width:38px;height:38px;border-radius:10px;font-size:16px">
                {{ props.row.full_name.charAt(0).toUpperCase() }}
            </span>
            <span class="mn-tenant-text">
                <span class="mn-tenant-name">{{ props.row.full_name }}</span>
                <span class="mn-mono mn-tenant-slug">{{ props.row.email }}</span>
            </span>
        </div>
    </q-td>
"""

_USER_CELL_STATUS = """
    <q-td :props="props">
        <span class="mn-pill"
              :class="props.row.status === 'active' ? 'mn-pill--ok'
                      : props.row.status === 'pending' ? 'mn-pill--warn' : ''">
            <span class="mn-dot"></span>{{ props.row.status_name }}
        </span>
        <span v-if="props.row.is_protected" class="mn-pill mn-pill--root" style="margin-left:6px">Raíz</span>
        <span v-if="props.row.is_me" class="mn-pill mn-pill--root" style="margin-left:6px">Tú</span>
    </q-td>
"""

_USER_CELL_MUTED = """<q-td :props="props" class="mn-muted">{{ props.value }}</q-td>"""

# La cuenta raíz no tiene acciones (L-1). Tampoco las ve un tenant_admin sobre otro tenant_admin
# (RN-048-2). Es una ayuda visual: el API es quien lo impone.
_USER_CELL_ACTIONS = """
    <q-td :props="props" auto-width>
        <span v-if="!props.row.can_manage" class="mn-muted" style="font-size:12px">Sin acciones</span>
        <q-btn v-else flat round dense icon="more_vert" color="grey-7"
               :aria-label="'Acciones de ' + props.row.full_name">
            <q-menu auto-close>
                <q-list style="min-width: 240px">
                    <q-item clickable @click="$parent.$emit('edit', props.row)">
                        <q-item-section avatar><q-icon name="edit" /></q-item-section>
                        <q-item-section>Editar</q-item-section>
                    </q-item>
                    <q-item v-if="props.row.status === 'pending' && props.row.can_resend" clickable
                            @click="$parent.$emit('resend', props.row)">
                        <q-item-section avatar><q-icon name="forward_to_inbox" /></q-item-section>
                        <q-item-section>Reenviar activación</q-item-section>
                    </q-item>
                    <q-item v-if="props.row.status === 'active'" clickable
                            @click="$parent.$emit('reset', props.row)">
                        <q-item-section avatar><q-icon name="lock_reset" /></q-item-section>
                        <q-item-section>Forzar reseteo de contraseña</q-item-section>
                    </q-item>
                    <q-item v-if="props.row.status === 'active' && !props.row.is_me" clickable
                            @click="$parent.$emit('deactivate', props.row)">
                        <q-item-section avatar><q-icon name="person_off" /></q-item-section>
                        <q-item-section>Desactivar</q-item-section>
                    </q-item>
                    <q-item v-if="props.row.status === 'disabled'" clickable
                            @click="$parent.$emit('reactivate', props.row)">
                        <q-item-section avatar><q-icon name="person_check" /></q-item-section>
                        <q-item-section>Reactivar</q-item-section>
                    </q-item>
                </q-list>
            </q-menu>
        </q-btn>
    </q-td>
"""


def _user_rows(items: list[dict], actor_role: str, *, can_resend: bool = True) -> list[dict]:
    me = app.storage.user.get("user_email", "").lower()
    rows = []
    for u in items:
        is_me = u["email"].lower() == me
        rows.append({
            **u,
            "is_me": is_me,
            "role_name": _ROLE_NAMES.get(u["role"], u["role"]),
            "status_name": _STATUS_NAMES.get(u["status"], u["status"]),
            "last_login_str": theme.fmt_datetime(u["last_login_at"]) if u.get("last_login_at") else "Nunca",
            "created_str": theme.fmt_date(u["created_at"]),
            # Los super admins pendientes se reactivan con «olvidé mi contraseña», que reenvía la activación
            "can_resend": can_resend,
            "can_manage": not u.get("is_protected")
            and not (actor_role == "tenant_admin" and u["role"] == "tenant_admin" and not is_me),
        })
    return rows


def _user_table(rows: list[dict]) -> ui.table:
    tbl = ui.table(columns=_USER_COLUMNS, rows=rows, row_key="id", pagination=0).classes("w-full")
    tbl.props('hide-bottom no-data-label="Ningún usuario coincide"')
    tbl.add_slot("body-cell-name", _USER_CELL_NAME)
    tbl.add_slot("body-cell-status", _USER_CELL_STATUS)
    tbl.add_slot("body-cell-last_login", _USER_CELL_MUTED)
    tbl.add_slot("body-cell-created", _USER_CELL_MUTED)
    tbl.add_slot("body-cell-actions", _USER_CELL_ACTIONS)
    return tbl


class _Confirm:
    """Un solo diálogo de confirmación reutilizable: título, texto, aviso opcional y acción."""

    def __init__(self) -> None:
        self._action: Any = None
        self.dialog = ui.dialog()
        with self.dialog, ui.card().classes("p-5 w-[420px]"):
            self.title = ui.label("").classes("font-bold text-base mb-1")
            self.message = ui.label("").classes("text-sm mn-muted")
            self.warning = ui.label("").classes("text-sm text-negative mt-2")
            with ui.row().classes("justify-end gap-2 mt-4 w-full"):
                ui.button("Cancelar", on_click=self.dialog.close).props("flat no-caps")
                self.confirm_btn = ui.button("Confirmar", on_click=self._run).props("unelevated no-caps")

    def ask(
        self, title: str, message: str, action: Any, *, warning: str = "", label: str = "Confirmar", color: str = "primary"
    ) -> None:
        self._action = action
        self.title.set_text(title)
        self.message.set_text(message)
        self.warning.set_text(warning)
        self.warning.set_visibility(bool(warning))
        self.confirm_btn.set_text(label)
        self.confirm_btn.props(f'color="{color}"')
        self.dialog.open()

    async def _run(self) -> None:
        self.dialog.close()
        if self._action:
            await self._action()


def _user_form_dialog(title: str, *, with_role: bool, roles: list[str]) -> dict:
    """Diálogo de alta/edición. Devuelve sus campos para que la página los rellene y lea."""
    f: dict[str, Any] = {}
    f["dialog"] = ui.dialog().props("persistent")
    with f["dialog"], ui.card().classes("w-[460px] p-6"):
        f["title"] = ui.label(title).classes("text-xl font-bold mb-3")
        f["email"] = ui.input("Email *", placeholder="persona@empresa.com").classes("w-full")
        f["name"] = ui.input("Nombre completo *").classes("w-full mt-2")
        f["role"] = ui.select(
            {r: _ROLE_NAMES[r] for r in roles}, label="Rol *", value=roles[0] if roles else None
        ).classes("w-full mt-2")
        f["role"].set_visibility(with_role)
        f["hint"] = ui.label("").classes("text-xs mn-muted mt-1")
        f["error"] = ui.label("").classes("text-negative text-sm mt-1")
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button("Cancelar", on_click=f["dialog"].close).props("flat no-caps")
            f["save"] = ui.button("Guardar").props('unelevated no-caps color="primary"')
    return f


@ui.page("/tenants/{tenant_id}/users")
async def page_users(tenant_id: str) -> None:
    if not _token():
        ui.navigate.to("/login")
        return
    role = app.storage.user.get("role", "")
    own_tenant = app.storage.user.get("tenant_id", "")
    if role == "tenant_admin" and tenant_id != own_tenant:
        ui.navigate.to(f"/tenants/{own_tenant}/users")  # un tenant_admin solo ve su tenant
        return
    if role not in ("super_admin", "tenant_admin"):
        ui.navigate.to("/login")
        return

    tenant = await theme.shell("users", tenant_id=tenant_id)
    theme.sub_header(tenant, tenant_id, "Usuarios")
    roles = _ASSIGNABLE[role]
    state: dict[str, Any] = {"page": 1, "status": "", "q": ""}
    confirm = _Confirm()

    create = _user_form_dialog("Nuevo usuario", with_role=True, roles=roles)
    create["hint"].set_text("Recibirá un email para activar su cuenta y elegir su contraseña.")
    edit = _user_form_dialog("Editar usuario", with_role=True, roles=roles)
    edit["email"].props("readonly")  # el email no se edita (RN-047-4)
    edit["hint"].set_text("El email no se puede cambiar: para usar otro, crea un usuario nuevo.")
    editing: dict[str, Any] = {}

    async def refresh() -> None:
        await load()

    async def call(action: Any, ok_message: str) -> None:
        try:
            await action
            ui.notify(ok_message, type="positive")
            await refresh()
        except SessionExpiredError:
            return
        except Exception as ex:
            ui.notify(_err_msg(ex), type="negative")

    async def do_create() -> None:
        create["error"].set_text("")
        email = (create["email"].value or "").strip()
        name = (create["name"].value or "").strip()
        if "@" not in email or len(name) < 2:
            create["error"].set_text("Email válido y nombre (mínimo 2 caracteres) son obligatorios.")
            return
        try:
            await api.create_user(
                _token(), role, tenant_id, {"email": email, "full_name": name, "role": create["role"].value}
            )
        except Exception as ex:
            create["error"].set_text(_err_msg(ex))
            return
        create["dialog"].close()
        ui.notify("Usuario creado. Se envió el email de activación.", type="positive")
        await refresh()

    async def do_edit() -> None:
        edit["error"].set_text("")
        name = (edit["name"].value or "").strip()
        if len(name) < 2:
            edit["error"].set_text("El nombre debe tener al menos 2 caracteres.")
            return
        payload: dict[str, Any] = {}
        if name != editing["full_name"]:
            payload["full_name"] = name
        if edit["role"].visible and edit["role"].value != editing["role"]:
            payload["role"] = edit["role"].value
        if not payload:
            edit["dialog"].close()
            return
        try:
            await api.update_user(_token(), role, tenant_id, editing["id"], payload)
        except Exception as ex:
            edit["error"].set_text(_err_msg(ex))
            return
        edit["dialog"].close()
        ui.notify("Usuario actualizado.", type="positive")
        await refresh()

    create["save"].on_click(do_create)
    edit["save"].on_click(do_edit)

    def open_create() -> None:
        create["email"].set_value("")
        create["name"].set_value("")
        create["role"].set_value("viewer")
        create["error"].set_text("")
        create["dialog"].open()

    async def on_edit(e: Any) -> None:
        u = e.args
        editing.clear()
        editing.update(u)
        edit["email"].set_value(u["email"])
        edit["name"].set_value(u["full_name"])
        # Nadie cambia su propio rol: el tenant podría quedarse sin administrador
        edit["role"].set_visibility(not u["is_me"] and u["role"] in roles)
        if u["role"] in roles:
            edit["role"].set_value(u["role"])
        edit["error"].set_text("")
        edit["dialog"].open()

    async def is_last_active_admin(u: dict) -> bool:
        """RN-047-3: aviso al desactivar al último tenant_admin activo. Solo si el conteo es seguro."""
        if u["role"] != "tenant_admin":
            return False
        try:
            data = await api.list_users(_token(), role, tenant_id, status="active", size=100)
        except Exception:
            return False
        admins = [x for x in data["items"] if x["role"] == "tenant_admin"]
        return data["total"] <= 100 and len(admins) == 1

    async def on_deactivate(e: Any) -> None:
        u = e.args
        warning = (
            "El tenant se quedará sin administrador activo: nadie podrá gestionar a su equipo "
            "hasta que un super admin cree otro."
            if await is_last_active_admin(u)
            else ""
        )
        confirm.ask(
            f"¿Desactivar a {u['full_name']}?",
            "No podrá iniciar sesión y se cerrarán sus sesiones abiertas ahora mismo.",
            lambda: call(
                api.update_user(_token(), role, tenant_id, u["id"], {"is_active": False}), "Usuario desactivado."
            ),
            warning=warning,
            label="Desactivar",
            color="negative",
        )

    async def on_reactivate(e: Any) -> None:
        u = e.args
        await call(api.update_user(_token(), role, tenant_id, u["id"], {"is_active": True}), "Usuario reactivado.")

    async def on_resend(e: Any) -> None:
        u = e.args
        await call(api.resend_user_activation(_token(), role, tenant_id, u["id"]), f"Activación reenviada a {u['email']}.")

    async def on_reset(e: Any) -> None:
        u = e.args
        confirm.ask(
            f"¿Forzar el reseteo de {u['full_name']}?",
            "Le enviamos un email para elegir una contraseña nueva y cerramos sus sesiones abiertas. "
            "Tú nunca ves ni fijas su contraseña.",
            lambda: call(
                api.force_user_reset(_token(), role, tenant_id, u["id"]), "Email de reseteo enviado."
            ),
            label="Enviar reseteo",
            color="warning",
        )

    # ── Barra de herramientas y listado ───────────────────────────────────────
    with ui.row().classes("w-full items-center gap-3"):
        search = ui.input(placeholder="Buscar por email o nombre").props(
            'dense outlined clearable debounce=400 aria-label="Buscar usuario"'
        ).classes("w-72")
        status_select = ui.select(_STATUS_FILTER, value="", label="Estado").props("dense outlined").classes("w-44")
        ui.space()
        ui.button("Nuevo usuario", icon="add", on_click=open_create).props("unelevated no-caps color=primary")

    container = ui.column().classes("w-full gap-3")

    async def load() -> None:
        container.clear()
        with container:
            try:
                data = await api.list_users(
                    _token(), role, tenant_id,
                    page=state["page"], size=_USERS_PAGE_SIZE, status=state["status"] or None, q=state["q"] or None,
                )
            except SessionExpiredError:
                return
            except Exception as ex:
                ui.notify(f"Error cargando usuarios: {_err_msg(ex)}", type="negative")
                return

            total = data["total"]
            ui.label(theme.plural(total, "usuario")).classes("text-sm mn-muted")
            tbl = _user_table(_user_rows(data["items"], role))
            tbl.on("edit", on_edit)
            tbl.on("resend", on_resend)
            tbl.on("reset", on_reset)
            tbl.on("deactivate", on_deactivate)
            tbl.on("reactivate", on_reactivate)

            pages = max(1, -(-total // _USERS_PAGE_SIZE))
            if pages > 1:
                async def go(e: Any) -> None:
                    state["page"] = e.value
                    await load()

                ui.pagination(1, pages, value=state["page"], on_change=go, direction_links=True).props("flat")

    async def on_filters(_: Any = None) -> None:
        state["q"] = (search.value or "").strip()
        state["status"] = status_select.value or ""
        state["page"] = 1
        await load()

    search.on_value_change(on_filters)
    status_select.on_value_change(on_filters)
    await load()


@ui.page("/super-admins")
async def page_super_admins() -> None:
    if not _token():
        ui.navigate.to("/login")
        return
    if app.storage.user.get("role") != "super_admin":
        ui.navigate.to("/login")
        return

    await theme.shell("super_admins")
    theme.breadcrumb(("Super admins", None))
    ui.label("Super admins").classes("mn-h1")
    ui.label(
        "Administran toda la plataforma. La cuenta raíz del ambiente no se puede desactivar, editar "
        "ni resetear: solo su dueño cambia su contraseña."
    ).classes("mn-muted").style("margin-top:-16px")

    confirm = _Confirm()
    create = _user_form_dialog("Nuevo super admin", with_role=False, roles=[])
    create["hint"].set_text("Recibirá un email para activar su cuenta. No será cuenta raíz.")
    edit = _user_form_dialog("Editar super admin", with_role=False, roles=[])
    edit["email"].props("readonly")
    edit["hint"].set_text("Solo se puede cambiar el nombre.")
    editing: dict[str, Any] = {}

    async def call(action: Any, ok_message: str) -> None:
        try:
            await action
            ui.notify(ok_message, type="positive")
            await load()
        except SessionExpiredError:
            return
        except Exception as ex:
            ui.notify(_err_msg(ex), type="negative")

    async def do_create() -> None:
        create["error"].set_text("")
        email = (create["email"].value or "").strip()
        name = (create["name"].value or "").strip()
        if "@" not in email or len(name) < 2:
            create["error"].set_text("Email válido y nombre (mínimo 2 caracteres) son obligatorios.")
            return
        try:
            await api.create_super_admin(_token(), {"email": email, "full_name": name})
        except Exception as ex:
            create["error"].set_text(_err_msg(ex))
            return
        create["dialog"].close()
        ui.notify("Super admin creado. Se envió el email de activación.", type="positive")
        await load()

    async def do_edit() -> None:
        edit["error"].set_text("")
        name = (edit["name"].value or "").strip()
        if len(name) < 2:
            edit["error"].set_text("El nombre debe tener al menos 2 caracteres.")
            return
        if name != editing["full_name"]:
            try:
                await api.update_super_admin(_token(), editing["id"], {"full_name": name})
            except Exception as ex:
                edit["error"].set_text(_err_msg(ex))
                return
            ui.notify("Super admin actualizado.", type="positive")
        edit["dialog"].close()
        await load()

    create["save"].on_click(do_create)
    edit["save"].on_click(do_edit)

    def open_create() -> None:
        create["email"].set_value("")
        create["name"].set_value("")
        create["error"].set_text("")
        create["dialog"].open()

    async def on_edit(e: Any) -> None:
        editing.clear()
        editing.update(e.args)
        edit["email"].set_value(e.args["email"])
        edit["name"].set_value(e.args["full_name"])
        edit["error"].set_text("")
        edit["dialog"].open()

    async def on_deactivate(e: Any) -> None:
        u = e.args
        confirm.ask(
            f"¿Desactivar a {u['full_name']}?",
            "No podrá iniciar sesión y se cerrarán sus sesiones abiertas ahora mismo. "
            "Siempre debe quedar al menos un super admin activo.",
            lambda: call(api.update_super_admin(_token(), u["id"], {"is_active": False}), "Super admin desactivado."),
            label="Desactivar",
            color="negative",
        )

    async def on_reactivate(e: Any) -> None:
        await call(api.update_super_admin(_token(), e.args["id"], {"is_active": True}), "Super admin reactivado.")

    async def on_reset(e: Any) -> None:
        u = e.args
        confirm.ask(
            f"¿Forzar el reseteo de {u['full_name']}?",
            "Le enviamos un email para elegir una contraseña nueva y cerramos sus sesiones abiertas.",
            lambda: call(api.force_super_admin_reset(_token(), u["id"]), "Email de reseteo enviado."),
            label="Enviar reseteo",
            color="warning",
        )

    with ui.row().classes("w-full items-center"):
        ui.space()
        ui.button("Nuevo super admin", icon="add", on_click=open_create).props("unelevated no-caps color=primary")

    container = ui.column().classes("w-full gap-3")

    async def load() -> None:
        container.clear()
        with container:
            try:
                items = await api.list_super_admins(_token())
            except SessionExpiredError:
                return
            except Exception as ex:
                ui.notify(f"Error cargando super admins: {_err_msg(ex)}", type="negative")
                return
            ui.label(theme.plural(len(items), "super admin")).classes("text-sm mn-muted")
            tbl = _user_table(_user_rows(items, "super_admin", can_resend=False))
            tbl.on("edit", on_edit)
            tbl.on("reset", on_reset)
            tbl.on("deactivate", on_deactivate)
            tbl.on("reactivate", on_reactivate)
            # Los super admins pendientes se activan con su enlace; "olvidé mi contraseña" lo reenvía

    await load()


# ─── Root redirect ────────────────────────────────────────────────────────────

@ui.page("/")
def page_root() -> None:
    if _token():
        ui.navigate.to("/tenants")
    else:
        ui.navigate.to("/login")


# ─── Run ──────────────────────────────────────────────────────────────────────

ui.run(
    host="0.0.0.0",
    port=PORT,
    storage_secret=STORAGE_SECRET,
    title="MicroNuba Admin",
    favicon="🏢",
    dark=False,
    reload=False,
)
