from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.utils import validar_fortaleza_password

from .models import PerfilRepartidor, Direccion

Usuario = get_user_model()


def campo_email():
    return serializers.EmailField(
        max_length=150,
        validators=[
            UniqueValidator(
                queryset=Usuario.objects.all(),
                lookup="iexact",
                message="Ya existe un usuario con este correo.",
            )
        ],
    )


class PerfilRepartidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilRepartidor
        fields = [
            "id", "tipo_vehiculo", "placa", "licencia", "disponible",
            "ultima_lat", "ultima_lng", "calificacion_promedio",
        ]
        read_only_fields = ["calificacion_promedio"]


class UsuarioSerializer(serializers.ModelSerializer):
    perfil_repartidor = PerfilRepartidorSerializer(read_only=True)
    nombre_completo = serializers.ReadOnlyField()

    class Meta:
        model = Usuario
        fields = [
            "id", "email", "nombre", "apellido", "nombre_completo",
            "telefono", "rol", "foto_url", "activo", "fecha_creacion",
            "perfil_repartidor",
        ]
        read_only_fields = ["id", "fecha_creacion"]


class RegistroSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True, min_length=8)
    email = campo_email()

    class Meta:
        model = Usuario
        fields = ["id", "email", "password", "nombre", "apellido", "telefono", "rol"]
        extra_kwargs = {
            # No se puede enviar `rol`: todo alta pública es cliente.
            "rol": {"read_only": True},
        }

    def validate_email(self, value):
        # Normaliza lo que se guarda; la unicidad la cubre `campo_email()`.
        return value.strip().lower()

    def validate_password(self, value):
        return validar_fortaleza_password(value)

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Redundante con read_only, pero deja la intención explícita.
        validated_data["rol"] = Usuario.Rol.CLIENTE
        return Usuario.objects.create_user(password=password, **validated_data)


class UsuarioCrearSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True, min_length=8, required=True)
    email = campo_email()

    class Meta:
        model = Usuario
        fields = [
            "id", "email", "password", "nombre", "apellido",
            "telefono", "rol", "foto_url", "activo",
        ]

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        return validar_fortaleza_password(value)

    def create(self, validated_data):
        password = validated_data.pop("password")
        # `create_user` ya hace set_password y normalize_email.
        return Usuario.objects.create_user(password=password, **validated_data)


class UsuarioActualizarSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True, min_length=8, required=False)
    email = campo_email()

    class Meta:
        model = Usuario
        fields = [
            "id", "email", "password", "nombre", "apellido",
            "telefono", "rol", "foto_url", "activo",
        ]

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        return validar_fortaleza_password(value, self.instance)

    def _es_uno_mismo(self) -> bool:
        peticion = self.context.get("request")
        return bool(peticion and self.instance and self.instance.pk == peticion.user.pk)

    def _quedan_otros_administradores(self) -> bool:
        return (
            Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADOR, activo=True)
            .exclude(pk=self.instance.pk)
            .exists()
        )

    def validate_activo(self, value):
        if value is False and self.instance:
            if self._es_uno_mismo():
                raise serializers.ValidationError("No puedes desactivar tu propia cuenta.")
            if self.instance.rol == Usuario.Rol.ADMINISTRADOR and not self._quedan_otros_administradores():
                # Que no quede el sistema sin ningún administrador.
                raise serializers.ValidationError(
                    "No puedes desactivar al último administrador activo."
                )
        return value

    def validate_rol(self, value):
        if not self.instance or value == self.instance.rol:
            return value
        if self.instance.rol == Usuario.Rol.ADMINISTRADOR:
            if self._es_uno_mismo():
                raise serializers.ValidationError(
                    "No puedes cambiar tu propio rol de administrador."
                )
            if not self._quedan_otros_administradores():
                raise serializers.ValidationError(
                    "No puedes degradar al último administrador activo."
                )
        return value

    def update(self, instance, validated_data):
        # Si no viene `password`, no se toca.
        password = validated_data.pop("password", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class SolicitarRecuperacionSerializer(serializers.Serializer):

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class ConfirmarRecuperacionSerializer(serializers.Serializer):

    email = serializers.EmailField()
    codigo = serializers.CharField(
        min_length=6,
        max_length=6,
        validators=[RegexValidator(r"^\d{6}$", "El código son 6 dígitos.")],
    )
    password_nueva = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()


class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direccion
        fields = [
            "id", "usuario", "alias", "calle", "numero", "distrito",
            "ciudad", "referencia", "latitud", "longitud", "es_default",
        ]
        extra_kwargs = {
            # Opcional: la vista lo fija al usuario autenticado por defecto.
            "usuario": {"required": False},
        }


class MiPerfilRepartidorSerializer(serializers.ModelSerializer):

    class Meta:
        model = PerfilRepartidor
        fields = [
            "id", "tipo_vehiculo", "placa", "licencia", "disponible",
            "ultima_lat", "ultima_lng", "calificacion_promedio",
        ]
        read_only_fields = [
            "id", "tipo_vehiculo", "placa", "licencia",
            "ultima_lat", "ultima_lng", "calificacion_promedio",
        ]
