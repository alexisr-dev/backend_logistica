import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.pedidos.models import EstadoPedido, Pedido
from apps.usuarios.models import Direccion, PerfilRepartidor

Usuario = get_user_model()

USUARIOS = "/api/v1/usuarios/"
CLAVE = "Trufa#Naranja7"


def api(usuario=None):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(user=usuario)
    return cliente


@pytest.fixture
def actores(db):
    return {
        "admin": Usuario.objects.create_user(
            email="admin@x.com", password="x", nombre="Ada", apellido="Admin",
            rol="administrador",
        ),
        "repartidor": Usuario.objects.create_user(
            email="rep@x.com", password="x", nombre="Raúl", apellido="Reparte",
            rol="repartidor",
        ),
        "cliente": Usuario.objects.create_user(
            email="cli@x.com", password="x", nombre="Carla", apellido="Pérez",
            rol="cliente",
        ),
    }


# --- Permisos ---------------------------------------------------------------

@pytest.mark.django_db
def test_cliente_no_puede_listar_usuarios(actores):
    assert api(actores["cliente"]).get(USUARIOS).status_code == 403


@pytest.mark.django_db
def test_repartidor_no_puede_crear_usuarios(actores):
    # `create` exige EsAdministrador, no solo IsAuthenticated.
    respuesta = api(actores["repartidor"]).post(
        USUARIOS,
        {"email": "intruso@x.com", "password": CLAVE, "nombre": "I", "apellido": "N"},
        format="json",
    )
    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_anonimo_no_puede_crear_usuarios(actores):
    respuesta = api().post(
        USUARIOS,
        {"email": "intruso@x.com", "password": CLAVE, "nombre": "I", "apellido": "N"},
        format="json",
    )
    assert respuesta.status_code == 401


@pytest.mark.django_db
def test_cliente_ve_su_ficha_pero_no_la_de_otro(actores):
    cliente = api(actores["cliente"])

    propia = cliente.get(f"{USUARIOS}{actores['cliente'].pk}/")
    ajena = cliente.get(f"{USUARIOS}{actores['repartidor'].pk}/")

    assert propia.status_code == 200
    assert ajena.status_code == 403


@pytest.mark.django_db
def test_yo_sigue_abierto_a_cualquier_autenticado(actores):
    for rol in ["cliente", "repartidor"]:
        respuesta = api(actores[rol]).get(f"{USUARIOS}yo/")
        assert respuesta.status_code == 200
        assert respuesta.data["email"] == actores[rol].email


# --- Alta y edición ---------------------------------------------------------

@pytest.mark.django_db
def test_admin_crea_usuario_con_contrasena_y_este_inicia_sesion(actores):
    respuesta = api(actores["admin"]).post(
        USUARIOS,
        {
            "email": "nuevo@x.com", "password": CLAVE,
            "nombre": "Nuevo", "apellido": "Usuario", "rol": "cliente",
        },
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.data
    assert "password" not in respuesta.data
    assert respuesta.data["nombre_completo"] == "Nuevo Usuario"

    login = api().post(
        "/api/v1/auth/login/", {"email": "nuevo@x.com", "password": CLAVE}, format="json"
    )
    assert login.status_code == 200, login.data


@pytest.mark.django_db
def test_admin_resetea_la_contrasena_al_editar(actores):
    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{actores['cliente'].pk}/", {"password": CLAVE}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.data
    actores["cliente"].refresh_from_db()
    assert actores["cliente"].check_password(CLAVE)


@pytest.mark.django_db
def test_actualizar_sin_password_no_toca_la_contrasena(actores):
    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{actores['cliente'].pk}/", {"telefono": "999"}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.data
    actores["cliente"].refresh_from_db()
    assert actores["cliente"].telefono == "999"
    assert actores["cliente"].check_password("x")


@pytest.mark.django_db
def test_cambiar_rol_a_repartidor_crea_el_perfil(actores):
    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{actores['cliente'].pk}/", {"rol": "repartidor"}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.data
    assert PerfilRepartidor.objects.filter(usuario=actores["cliente"]).exists()


@pytest.mark.django_db
def test_cambiar_rol_a_cliente_elimina_el_perfil(actores):
    assert PerfilRepartidor.objects.filter(usuario=actores["repartidor"]).exists()

    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{actores['repartidor'].pk}/", {"rol": "cliente"}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.data
    assert not PerfilRepartidor.objects.filter(usuario=actores["repartidor"]).exists()


# --- Baja -------------------------------------------------------------------

@pytest.mark.django_db
def test_borrar_usuario_sin_historial_lo_elimina(actores):
    pk = actores["cliente"].pk

    respuesta = api(actores["admin"]).delete(f"{USUARIOS}{pk}/")

    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["resultado"] == "eliminado"
    assert not Usuario.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_borrar_usuario_con_pedidos_lo_desactiva_sin_romper(actores, estados_pedido):
    cliente = actores["cliente"]
    origen = Direccion.objects.create(usuario=cliente, calle="O", latitud=0, longitud=0)
    destino = Direccion.objects.create(usuario=cliente, calle="D", latitud=1, longitud=1)
    Pedido.objects.create(
        cliente=cliente,
        direccion_origen=origen,
        direccion_destino=destino,
        estado=EstadoPedido.objects.get(codigo="pendiente"),
    )

    respuesta = api(actores["admin"]).delete(f"{USUARIOS}{cliente.pk}/")

    # Lo importante: `Pedido.cliente` es PROTECT y antes esto era un 500 opaco.
    assert respuesta.status_code != 500
    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["resultado"] == "desactivado"
    assert respuesta.data["referencias"]["pedidos"] == 1

    cliente.refresh_from_db()
    assert cliente.activo is False


@pytest.mark.django_db
def test_admin_no_puede_borrarse_a_si_mismo(actores):
    respuesta = api(actores["admin"]).delete(f"{USUARIOS}{actores['admin'].pk}/")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "autoeliminacion"
    assert Usuario.objects.filter(pk=actores["admin"].pk).exists()


@pytest.mark.django_db
def test_admin_no_puede_desactivarse_a_si_mismo(actores):
    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{actores['admin'].pk}/", {"activo": False}, format="json"
    )

    assert respuesta.status_code == 400
    assert "activo" in respuesta.data
    actores["admin"].refresh_from_db()
    assert actores["admin"].activo is True


@pytest.mark.django_db
def test_no_se_puede_desactivar_al_ultimo_administrador(actores):
    otro_admin = Usuario.objects.create_user(
        email="admin2@x.com", password="x", nombre="Otro", apellido="Admin",
        rol="administrador",
    )

    respuesta = api(actores["admin"]).patch(
        f"{USUARIOS}{otro_admin.pk}/", {"activo": False}, format="json"
    )
    # Quedaría el admin de `actores`, así que este sí se puede desactivar.
    assert respuesta.status_code == 200, respuesta.data

    # Y ahora `actores["admin"]` es el último activo: nadie puede tumbarlo.
    respuesta = api(otro_admin).patch(
        f"{USUARIOS}{actores['admin'].pk}/", {"activo": False}, format="json"
    )
    assert respuesta.status_code in (400, 403)


# --- Listado ----------------------------------------------------------------

@pytest.mark.django_db
def test_busqueda_por_texto_y_filtros_del_padron(actores):
    admin = api(actores["admin"])

    por_texto = admin.get(USUARIOS, {"search": "Pérez"})
    por_rol = admin.get(USUARIOS, {"rol": "repartidor"})
    por_estado = admin.get(USUARIOS, {"activo": "false"})

    assert por_texto.data["count"] == 1
    assert por_texto.data["results"][0]["email"] == "cli@x.com"
    assert por_rol.data["count"] == 1
    assert por_estado.data["count"] == 0


@pytest.mark.django_db
def test_el_listado_llega_paginado_y_ordenado(actores):
    respuesta = api(actores["admin"]).get(USUARIOS, {"ordering": "nombre"})

    assert respuesta.status_code == 200
    assert {"count", "next", "previous", "results"} <= set(respuesta.data)
    nombres = [u["nombre"] for u in respuesta.data["results"]]
    assert nombres == sorted(nombres)
