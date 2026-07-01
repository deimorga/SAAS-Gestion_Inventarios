import os
from typing import Any

import httpx
from nicegui import app, ui

from app import api

STORAGE_SECRET = os.getenv("STORAGE_SECRET", "dev-secret-change-in-prod")
PORT = int(os.getenv("PORT", "8080"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _token() -> str:
    return app.storage.user.get("token", "")


def _guard() -> None:
    if not _token():
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


def _info_row(label: str, value: str, copyable: bool = False) -> None:
    with ui.row().classes("items-center gap-2 w-full"):
        ui.label(label).classes("text-xs font-semibold text-gray-500 uppercase w-36 shrink-0")
        ui.label(value).classes("text-sm text-gray-800 break-all flex-1")
        if copyable:
            ui.button(
                icon="content_copy",
                on_click=lambda v=value: ui.run_javascript(_copy_js(v)),
            ).props("flat dense size=xs").tooltip("Copiar")


def _tier_badge(tier: str) -> None:
    colors = {"STARTER": "blue", "PROFESSIONAL": "purple", "ENTERPRISE": "orange"}
    color = colors.get(tier, "grey")
    ui.badge(tier, color=color)


# ─── Login ────────────────────────────────────────────────────────────────────

@ui.page("/login")
def page_login() -> None:
    ui.colors(primary="#1a56db")

    with ui.card().classes("absolute-center w-96 shadow-2xl p-8"):
        ui.label("MicroNuba").classes("text-3xl font-bold text-primary text-center")
        ui.label("Portal de Administración").classes("text-sm text-gray-500 text-center mb-6")

        email_input = ui.input("Email", placeholder="admin@micronuba.com").classes("w-full")
        password_input = ui.input(
            "Contraseña", password=True, password_toggle_button=True
        ).classes("w-full mt-2")
        error_label = ui.label("").classes("text-red-500 text-sm hidden")

        async def do_login() -> None:
            error_label.classes(remove="hidden")
            error_label.set_text("")
            if not email_input.value or not password_input.value:
                error_label.set_text("Completa todos los campos.")
                return
            try:
                data = await api.admin_login(email_input.value, password_input.value)
                app.storage.user["token"] = data["access_token"]
                app.storage.user["user_email"] = data["user"]["email"]
                ui.navigate.to("/tenants")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    error_label.set_text("Credenciales incorrectas.")
                else:
                    error_label.set_text(f"Error {e.response.status_code}.")
            except Exception:
                error_label.set_text("No se pudo conectar con la API.")

        password_input.on("keydown.enter", do_login)
        ui.button("Ingresar", on_click=do_login).classes("w-full mt-4").props(
            'color="primary" unelevated'
        )

    ui.label(f"API: {API_BASE_URL}").classes("fixed bottom-2 right-4 text-xs text-gray-400")


# ─── Tenants list ─────────────────────────────────────────────────────────────

@ui.page("/tenants")
async def page_tenants() -> None:
    _guard()
    token = _token()
    ui.colors(primary="#1a56db")

    with ui.row().classes("w-full items-center justify-between mb-6"):
        ui.label("Tenants").classes("text-2xl font-bold")
        with ui.row().classes("items-center gap-2"):
            ui.label(app.storage.user.get("user_email", "")).classes("text-sm text-gray-500")
            ui.button(
                "Salir",
                icon="logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat dense color=negative")

    created: dict[str, Any] = {}

    result_dialog = ui.dialog().props("persistent")
    create_dialog = ui.dialog().props("persistent")

    with result_dialog:
        with ui.card().classes("w-[520px] p-6"):
            ui.label("✅ Tenant creado exitosamente").classes(
                "text-lg font-bold text-green-600 mb-4"
            )

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
                    data = await api.create_tenant(token, payload)
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

    with ui.row().classes("w-full justify-between items-center mb-3"):
        ui.label("").classes("text-sm text-gray-500")
        ui.button("+ Nuevo Tenant", on_click=create_dialog.open).props('unelevated color="primary"')

    table_container = ui.column().classes("w-full")

    async def refresh_table() -> None:
        table_container.clear()
        with table_container:
            try:
                data = await api.list_tenants(token)
                items: list[dict] = data.get("items", [])
                total: int = data.get("total", 0)

                if not items:
                    with ui.card().classes("w-full p-8 text-center"):
                        ui.icon("business", size="4rem").classes("text-gray-300")
                        ui.label("Sin tenants registrados").classes("text-gray-500 mt-2")
                        ui.label("Crea el primero con el botón superior.").classes(
                            "text-sm text-gray-400"
                        )
                    return

                ui.label(f"{total} tenant(s) registrado(s)").classes("text-sm text-gray-500 mb-2")

                columns = [
                    {"name": "name", "label": "Nombre", "field": "name", "align": "left", "sortable": True},
                    {"name": "slug", "label": "Slug", "field": "slug", "align": "left"},
                    {"name": "tier", "label": "Tier", "field": "subscription_tier", "align": "center", "sortable": True},
                    {"name": "status", "label": "Estado", "field": "status_str", "align": "center"},
                    {"name": "created_at", "label": "Creado", "field": "created_str", "align": "center", "sortable": True},
                    {"name": "actions", "label": "", "field": "id", "align": "center"},
                ]

                rows = [
                    {
                        **t,
                        "status_str": "Activo" if t["is_active"] else "Suspendido",
                        "created_str": t["created_at"][:10],
                    }
                    for t in items
                ]

                tbl = ui.table(columns=columns, rows=rows, row_key="id").classes(
                    "w-full shadow-sm"
                )
                tbl.add_slot(
                    "body-cell-status",
                    """
                    <q-td :props="props">
                        <q-badge :color="props.row.is_active ? 'positive' : 'grey'" :label="props.value" />
                    </q-td>
                    """,
                )
                tbl.add_slot(
                    "body-cell-tier",
                    """
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'ENTERPRISE' ? 'orange' : props.value === 'PROFESSIONAL' ? 'purple' : 'blue'"
                            :label="props.value" />
                    </q-td>
                    """,
                )
                tbl.add_slot(
                    "body-cell-actions",
                    """
                    <q-td :props="props">
                        <q-btn flat dense icon="open_in_new" color="primary" size="sm"
                               @click="$parent.$emit('view', props.row)" />
                    </q-td>
                    """,
                )
                tbl.on("view", lambda e: ui.navigate.to(f"/tenants/{e.args['id']}"))

            except Exception as ex:
                ui.notify(f"Error cargando tenants: {ex}", type="negative")

    await refresh_table()


# ─── Tenant detail ────────────────────────────────────────────────────────────

@ui.page("/tenants/{tenant_id}")
async def page_tenant_detail(tenant_id: str) -> None:
    _guard()
    token = _token()
    ui.colors(primary="#1a56db")

    with ui.row().classes("w-full items-center gap-3 mb-6"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/tenants")).props(
            "flat round"
        )
        ui.label("Detalle del Tenant").classes("text-2xl font-bold")

    try:
        tenant = await api.get_tenant(token, tenant_id)
        keys_data = await api.get_tenant_keys(token, tenant_id)
    except httpx.HTTPStatusError as e:
        ui.notify(f"Error {e.response.status_code} cargando tenant.", type="negative")
        return
    except Exception as ex:
        ui.notify(f"Error: {ex}", type="negative")
        return

    with ui.row().classes("w-full gap-4 items-start"):
        with ui.card().classes("flex-1 p-5"):
            with ui.row().classes("items-center justify-between mb-4"):
                ui.label("Información").classes("text-lg font-bold")
                with ui.row().classes("gap-2 items-center"):
                    _tier_badge(tenant["subscription_tier"])
                    status_color = "positive" if tenant["is_active"] else "grey"
                    status_label = "Activo" if tenant["is_active"] else "Suspendido"
                    ui.badge(status_label, color=status_color)

            with ui.column().classes("w-full gap-2"):
                _info_row("ID", str(tenant["id"]), copyable=True)
                _info_row("Nombre", tenant["name"])
                _info_row("Slug", tenant["slug"], copyable=True)
                _info_row("Creado", tenant["created_at"][:19].replace("T", " "))

        with ui.card().classes("w-64 p-5"):
            ui.label("Acciones").classes("text-lg font-bold mb-3")

            suspend_dialog = ui.dialog()
            with suspend_dialog:
                with ui.card().classes("p-5 w-80"):
                    action = "reactivar" if not tenant["is_active"] else "suspender"
                    ui.label(f"¿{action.capitalize()} este tenant?").classes("font-bold mb-2")
                    ui.label(
                        "Suspender impide el login de sus usuarios pero no revoca API Keys activas."
                        if tenant["is_active"]
                        else "El tenant y sus usuarios podrán volver a operar."
                    ).classes("text-sm text-gray-600 mb-4")

                    async def do_toggle() -> None:
                        try:
                            await api.update_tenant(
                                token, tenant_id, {"is_active": not tenant["is_active"]}
                            )
                            suspend_dialog.close()
                            ui.navigate.to(f"/tenants/{tenant_id}")
                        except Exception as ex:
                            ui.notify(f"Error: {ex}", type="negative")

                    with ui.row().classes("justify-end gap-2"):
                        ui.button("Cancelar", on_click=suspend_dialog.close).props("flat")
                        ui.button(
                            action.capitalize(),
                            on_click=do_toggle,
                        ).props(
                            f'unelevated color="{"warning" if tenant["is_active"] else "positive"}"'
                        )

            btn_label = "⏸ Suspender tenant" if tenant["is_active"] else "▶ Reactivar tenant"
            btn_color = "warning" if tenant["is_active"] else "positive"
            ui.button(btn_label, on_click=suspend_dialog.open).classes("w-full").props(
                f'flat color="{btn_color}"'
            )

    # ── API Keys ──────────────────────────────────────────────────────────────────
    ui.separator().classes("my-5")

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
                        token, tenant_id, {"name": key_name_in.value.strip(), "scopes": selected}
                    )
                    new_key_result.clear()
                    new_key_result.update(data)
                    create_key_dialog.close()
                    reveal_content.refresh()
                    key_reveal_dialog.open()
                    fresh = await api.get_tenant_keys(token, tenant_id)
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

    with ui.row().classes("items-center justify-between mb-3"):
        ui.label("API Keys").classes("text-lg font-bold")
        ui.button("+ Nueva API Key", on_click=create_key_dialog.open).props('unelevated color="primary"')

    key_container = ui.column().classes("w-full gap-3")

    async def build_keys() -> None:
        key_container.clear()
        current_keys = keys_data.get("data", [])
        with key_container:
            if not current_keys:
                with ui.card().classes("w-full p-6 text-center"):
                    ui.icon("vpn_key", size="3rem").classes("text-gray-300")
                    ui.label("Sin API Keys").classes("text-gray-500 mt-2")
                return
            for k in current_keys:
                is_active = k.get("is_active", False)
                with ui.card().classes(
                    f"w-full p-4 {'border-l-4 border-green-500' if is_active else 'opacity-60'}"
                ):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.column().classes("gap-1 flex-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(k.get("name", "Sin nombre")).classes("font-semibold")
                                if is_active:
                                    ui.badge("Activa", color="positive")
                                else:
                                    ui.badge("Revocada", color="grey")

                            _info_row("Key prefix", k.get("key_id", ""), copyable=True)
                            _info_row("Scopes", ", ".join(k.get("scopes", [])))
                            expires = k.get("expires_at")
                            _info_row(
                                "Expira",
                                expires[:10] if expires else "Sin vencimiento",
                            )
                            _info_row("ID (UUID)", str(k.get("id", "")), copyable=True)
                            _info_row("Creada", k.get("created_at", "")[:10])

                        if is_active:
                            revoke_dialog = ui.dialog()
                            with revoke_dialog:
                                with ui.card().classes("p-5 w-80"):
                                    ui.label("¿Revocar esta API Key?").classes(
                                        "font-bold text-red-600 mb-2"
                                    )
                                    ui.label(
                                        "Esta acción es permanente. Las integraciones que usen esta key dejarán de funcionar."
                                    ).classes("text-sm text-gray-600 mb-4")

                                    async def do_revoke(
                                        kid: str = str(k["id"]),
                                        dlg: ui.dialog = revoke_dialog,
                                    ) -> None:
                                        try:
                                            await api.revoke_key(token, tenant_id, kid)
                                            dlg.close()
                                            ui.notify("API Key revocada.", type="positive")
                                            fresh = await api.get_tenant_keys(token, tenant_id)
                                            keys_data["data"] = fresh.get("data", [])
                                            await build_keys()
                                        except Exception as ex:
                                            ui.notify(f"Error: {ex}", type="negative")

                                    with ui.row().classes("justify-end gap-2"):
                                        ui.button("Cancelar", on_click=revoke_dialog.close).props(
                                            "flat"
                                        )
                                        ui.button("Revocar", on_click=do_revoke).props(
                                            'unelevated color="negative"'
                                        )

                            ui.button(
                                "Revocar", icon="block", on_click=revoke_dialog.open
                            ).props("flat color=negative dense")

    await build_keys()


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
