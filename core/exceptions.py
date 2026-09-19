from rest_framework.exceptions import APIException
from rest_framework import status


class TransicionEstadoInvalida(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "La transición de estado solicitada no es válida."
    default_code = "transicion_invalida"


class ServicioExternoNoDisponible(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "El servicio externo (OSRM) no está disponible en este momento."
    default_code = "servicio_no_disponible"


class CodigoRecuperacionInvalido(APIException):

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "El código es inválido o ha expirado. Solicita uno nuevo."
    default_code = "codigo_invalido"
