import os
from typing import Any

import httpx
from nicegui import app, ui

from app import api
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


def _info_row(label: str, value: str, copyable: bool = False) -> None:
    with ui.row().classes("items-center gap-2 w-full"):
        ui.label(label).classes("text-xs font-semibold text-gray-500 uppercase w-36 shrink-0")
        ui.label(value).classes("text-sm text-gray-800 break-all flex-1")
        if copyable:
            ui.button(
                icon="content_copy",
                on_click=lambda v=value: ui.run_javascript(
                    f"navigator.clipboard.writeText({v!r})"
                ),
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

    ui.label(f"API: {API_BASE_URL}").classes("fixed bottom-2 right-4 text-xs text-gray-400")


# ─── Tenants list ─────────────────────────────────────────────────────────────

@ui.page("/tenants")
async def page_tenants() -> None:
    _guard()
    ui.colors(primary="#1a56db")

    # ── Header ────────────────────────────────────────────────────────────────
    with ui.row().classes("w-full items-center justify-between mb-6"):
        ui.label("Tenants").classes("text-2xl font-bold")
        with ui.row().classes("items-center gap-2"):
            ui.label(app.storage.user.get("user_email", "")).classes("text-sm text-gray-500")
            ui.button(
                "Salir",
                icon="logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat dense color=negative")

    # ── Create dialog ─────────────────────────────────────────────────────────
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
                    data = await api.create_tenant(_token(), payload)
                    created.clear()
                    created.update(data)
                    create_dialog.close()
                    result_content.refresh()
                    result_dialog.open()
                    await refresh_table()
                    # Reset form
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
    with ui.row().classes("w-full justify-between items-center mb-3"):
        ui.label("").classes("text-sm text-gray-500")
        ui.button("+ Nuevo Tenant", on_click=create_dialog.open).props('unelevated color="primary"')

    table_container = ui.column().classes("w-full")

    async def refresh_table() -> None:
        table_container.clear()
        with table_container:
            try:
                data = await api.list_tenants(_token())
                items: list[dict] = data.get("items", [])
                total: int = data.get("total", 0)

                if not items:
                    with ui.card().classes("w-full p-8 text-center"):
                        ui.icon("business", size="4rem").classes("text-gray-300")
                        ui.label("Sin tenants registrados").classes("text-gray-500 mt-2")
                        ui.label("Crea el primero con el botón superior.").classes("text-sm text-gray-400")
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

                tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full shadow-sm")
                tbl.add_slot("body-cell-status", """
                    <q-td :props="props">
                        <q-badge :color="props.row.is_active ? 'positive' : 'grey'" :label="props.value" />
                    </q-td>
                """)
                tbl.add_slot("body-cell-tier", """
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === 'ENTERPRISE' ? 'orange' : props.value === 'PROFESSIONAL' ? 'purple' : 'blue'"
                            :label="props.value" />
                    </q-td>
                """)
                tbl.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn flat dense icon="open_in_new" color="primary" size="sm"
                               @click="$parent.$emit('view', props.row)" class="mr-1" />
                        <q-btn flat dense icon="block" size="sm"
                               :color="props.row.is_active ? 'negative' : 'positive'"
                               @click="$parent.$emit('suspend', props.row)" />
                    </q-td>
                """)

                tbl.on("view", lambda e: ui.navigate.to(f"/tenants/{e.args['id']}"))

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
    ui.colors(primary="#1a56db")

    # ── Header ────────────────────────────────────────────────────────────────
    with ui.row().classes("w-full items-center gap-3 mb-6"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/tenants")).props(
            "flat round"
        )
        ui.label("Detalle del Tenant").classes("text-2xl font-bold")

    try:
        tenant = await api.get_tenant(_token(), tenant_id)
        keys_data = await api.get_tenant_keys(_token(), tenant_id)
    except httpx.HTTPStatusError as e:
        ui.notify(f"Error {e.response.status_code} cargando tenant.", type="negative")
        return
    except Exception as ex:
        ui.notify(f"Error: {ex}", type="negative")
        return

    # ── Tenant info ───────────────────────────────────────────────────────────
    with ui.row().classes("w-full gap-4 items-start"):
        # Info card
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

        # Quick actions card
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
                                _token(), tenant_id, {"is_active": not tenant["is_active"]}
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
            ui.separator().classes("my-2")
            ui.button(
                "📦 Gestionar Productos",
                on_click=lambda: ui.navigate.to(f"/tenants/{tenant_id}/products"),
            ).classes("w-full").props('unelevated color="primary"')
            ui.button(
                "📊 Gestionar Stock",
                on_click=lambda: ui.navigate.to(f"/tenants/{tenant_id}/stock"),
            ).classes("w-full mt-2").props('unelevated color="secondary"')

    # ── API Keys ──────────────────────────────────────────────────────────────
    ui.separator().classes("my-5")

    with ui.row().classes("items-center justify-between mb-3"):
        ui.label("API Keys").classes("text-lg font-bold")

    keys: list[dict] = keys_data.get("items", [])

    if not keys:
        with ui.card().classes("w-full p-6 text-center"):
            ui.icon("vpn_key", size="3rem").classes("text-gray-300")
            ui.label("Sin API Keys").classes("text-gray-500 mt-2")
        return

    key_container = ui.column().classes("w-full gap-3")

    async def build_keys() -> None:
        key_container.clear()
        current_keys = keys_data.get("items", [])
        with key_container:
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
                            _info_row("Scope", k.get("scope", ""))
                            expires = k.get("expires_at")
                            _info_row(
                                "Expira",
                                expires[:10] if expires else "Sin vencimiento",
                            )
                            _info_row("ID (UUID)", str(k.get("id", "")), copyable=True)

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
                                            await api.revoke_key(_token(), tenant_id, kid)
                                            dlg.close()
                                            ui.notify("API Key revocada.", type="positive")
                                            # Reload keys
                                            fresh = await api.get_tenant_keys(_token(), tenant_id)
                                            keys_data["items"] = fresh.get("items", [])
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


# ─── Products page ───────────────────────────────────────────────────────────

@ui.page("/tenants/{tenant_id}/products")
async def page_products(tenant_id: str) -> None:
    _guard()
    ui.colors(primary="#1a56db")

    with ui.row().classes("w-full items-center gap-3 mb-4"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to(f"/tenants/{tenant_id}")).props("flat round")
        ui.label("Productos").classes("text-2xl font-bold")

    search_input = ui.input(placeholder="Buscar por SKU o nombre...").classes("w-full mb-4").props('outlined dense clearable')

    product_container = ui.column().classes("w-full")

    # ── Dialogs ───────────────────────────────────────────────────────────────
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
                    await load_products()
                except Exception as ex:
                    dialog_err.set_text(f"Error: {ex}")

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
                    await load_products()
                except Exception as ex:
                    ui.notify(f"Error: {ex}", type="negative")

            with ui.row().classes("justify-end gap-2"):
                ui.button("Cancelar", on_click=confirm_delete.close).props("flat")
                ui.button("Desactivar", on_click=do_delete).props('unelevated color="negative"')

    # ── Table ─────────────────────────────────────────────────────────────────
    async def load_products(search: str | None = None) -> None:
        product_container.clear()
        with product_container:
            try:
                data = await api.list_products(_token(), tenant_id, search=search or None)
                items = data.get("data", [])
                total = data.get("pagination", {}).get("total_items", 0)

                with ui.row().classes("w-full justify-between items-center mb-2"):
                    ui.label(f"{total} producto(s)").classes("text-sm text-gray-500")
                    ui.button("+ Nuevo Producto", on_click=lambda: (
                        editing.clear(),
                        sku_in.set_value(""),
                        name_in.set_value(""),
                        price_in.set_value(None),
                        uom_in.set_value(""),
                        desc_in.set_value(""),
                        dialog_title.set_text("Nuevo Producto"),
                        dialog_err.set_text(""),
                        sku_in.props(remove="readonly"),
                        product_dialog.open(),
                    )).props('unelevated color="primary"')

                if not items:
                    with ui.card().classes("w-full p-8 text-center"):
                        ui.icon("inventory_2", size="4rem").classes("text-gray-300")
                        ui.label("Sin productos").classes("text-gray-500 mt-2")
                    return

                columns = [
                    {"name": "sku", "label": "SKU", "field": "sku", "align": "left", "sortable": True},
                    {"name": "name", "label": "Nombre", "field": "name", "align": "left", "sortable": True},
                    {"name": "base_uom", "label": "UOM", "field": "base_uom", "align": "center"},
                    {"name": "sale_price", "label": "Precio", "field": "sale_price_str", "align": "right"},
                    {"name": "actions", "label": "", "field": "id", "align": "center"},
                ]
                rows = [
                    {
                        **p,
                        "sale_price_str": f"${float(p['sale_price']):,.0f}" if p.get("sale_price") else "—",
                    }
                    for p in items
                ]

                tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full shadow-sm")
                tbl.add_slot(
                    "body-cell-actions",
                    """
                    <q-td :props="props">
                        <q-btn flat dense icon="edit" color="primary" size="sm"
                               @click="$parent.$emit('edit', props.row)" class="mr-1"/>
                        <q-btn flat dense icon="delete" color="negative" size="sm"
                               @click="$parent.$emit('delete', props.row)" />
                    </q-td>
                    """,
                )

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

                tbl.on("edit", on_edit)
                tbl.on("delete", on_delete)

            except Exception as ex:
                ui.notify(f"Error cargando productos: {ex}", type="negative")

    search_input.on("keydown.enter", lambda: load_products(search_input.value))
    search_input.on("clear", lambda: load_products(None))

    await load_products()


# ─── Stock page ──────────────────────────────────────────────────────────────

@ui.page("/tenants/{tenant_id}/stock")
async def page_stock(tenant_id: str) -> None:
    _guard()
    ui.colors(primary="#1a56db")

    with ui.row().classes("w-full items-center gap-3 mb-4"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to(f"/tenants/{tenant_id}")).props("flat round")
        ui.label("Stock").classes("text-2xl font-bold")

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
                    "items": [{"product_id": r_product.value, "quantity": float(r_qty.value), "unit_cost": float(r_cost.value)}],
                }
                try:
                    await api.stock_receipt(_token(), tenant_id, payload)
                    ui.notify("Entrada registrada.", type="positive")
                    receipt_dialog.close()
                    await load_stock()
                except Exception as ex:
                    r_err.set_text(f"Error: {ex}")

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
                    "items": [{"product_id": a_product.value, "new_qty": float(a_qty.value)}],
                }
                try:
                    await api.stock_adjustment(_token(), tenant_id, payload)
                    ui.notify("Ajuste registrado.", type="positive")
                    adjust_dialog.close()
                    await load_stock()
                except Exception as ex:
                    a_err.set_text(f"Error: {ex}")

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
                        ui.button("+ Entrada de Stock", on_click=receipt_dialog.open).props('unelevated color="primary"')
                        ui.button("⚖ Ajustar Stock", on_click=adjust_dialog.open).props('unelevated color="warning"')

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
                    {"name": "physical", "label": "Físico", "field": "physical_qty", "align": "right"},
                    {"name": "reserved", "label": "Reservado", "field": "reserved_qty", "align": "right"},
                    {"name": "available", "label": "Disponible", "field": "available_qty", "align": "right"},
                    {"name": "actions", "label": "", "field": "id", "align": "center"},
                ]
                rows = [
                    {
                        **s,
                        "product_name": prod_map.get(str(s["product_id"]).lower(), str(s["product_id"])[:8]),
                        "warehouse_name": wh_map.get(str(s["warehouse_id"]).lower(), "—"),
                        "zone_name": all_zones.get(str(s["zone_id"]).lower(), "—"),
                        "physical_qty": float(s["physical_qty"]),
                        "reserved_qty": float(s["reserved_qty"]),
                        "available_qty": float(s["available_qty"]),
                    }
                    for s in items
                ]
                tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full shadow-sm")
                tbl.add_slot("body-cell-available", """
                    <q-td :props="props">
                        <q-badge :color="props.value > 0 ? 'positive' : 'grey'" :label="props.value" />
                    </q-td>
                """)
                tbl.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn flat dense icon="edit" color="primary" size="sm"
                               @click="$parent.$emit('edit_stock', props.row)" class="mr-1" />
                        <q-btn flat dense icon="delete" color="negative" size="sm"
                               @click="$parent.$emit('delete_stock', props.row)" />
                    </q-td>
                """)

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
                                "items": [{"product_id": edit_stock_row["product_id"], "new_qty": float(edit_stock_qty.value)}],
                            }
                            try:
                                await api.stock_adjustment(_token(), tenant_id, payload)
                                edit_stock_dialog.close()
                                ui.notify("Stock actualizado.", type="positive")
                                await load_stock()
                            except Exception as ex:
                                edit_stock_err.set_text(f"Error: {ex}")

                        with ui.row().classes("w-full justify-end mt-4 gap-2"):
                            ui.button("Cancelar", on_click=edit_stock_dialog.close).props("flat")
                            ui.button("Guardar", on_click=do_edit_stock).props('unelevated color="primary"')

                def on_edit_stock(e: Any) -> None:
                    row = e.args
                    edit_stock_row.clear()
                    edit_stock_row.update(row)
                    edit_stock_info.set_text(
                        f"{row['product_name']} · {row['warehouse_name']} · {row['zone_name']}"
                    )
                    edit_stock_qty.set_value(float(row["physical_qty"]))
                    edit_stock_err.set_text("")
                    edit_stock_dialog.open()

                delete_stock_row: dict = {}
                delete_stock_dialog = ui.dialog().props("persistent")
                with delete_stock_dialog:
                    with ui.card().classes("p-5 w-80"):
                        ui.label("¿Poner stock en 0?").classes("font-bold text-red-600 mb-2")
                        ui.label("Se registrará un ajuste a cantidad 0 para este producto.").classes("text-sm text-gray-600 mb-4")

                        async def do_delete_stock() -> None:
                            try:
                                payload = {
                                    "reference_id": "AJUSTE-MANUAL",
                                    "reason_code": "CONTEO_FISICO",
                                    "warehouse_id": delete_stock_row["warehouse_id"],
                                    "zone_id": delete_stock_row["zone_id"],
                                    "items": [{"product_id": delete_stock_row["product_id"], "new_qty": 0}],
                                }
                                await api.stock_adjustment(_token(), tenant_id, payload)
                                delete_stock_dialog.close()
                                ui.notify("Stock ajustado a 0.", type="positive")
                                await load_stock()
                            except Exception as ex:
                                ui.notify(f"Error: {ex}", type="negative")

                        with ui.row().classes("justify-end gap-2"):
                            ui.button("Cancelar", on_click=delete_stock_dialog.close).props("flat")
                            ui.button("Poner en 0", on_click=do_delete_stock).props('unelevated color="negative"')

                def on_delete_stock(e: Any) -> None:
                    delete_stock_row.clear()
                    delete_stock_row.update(e.args)
                    delete_stock_dialog.open()

                tbl.on("edit_stock", on_edit_stock)
                tbl.on("delete_stock", on_delete_stock)
            except Exception as ex:
                ui.notify(f"Error cargando stock: {ex}", type="negative")

    await load_stock()


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
