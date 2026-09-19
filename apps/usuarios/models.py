from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("rol", Usuario.Rol.CLIENTE)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", Usuario.Rol.ADMINISTRADOR)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractUser):

    class Rol(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        REPARTIDOR = "repartidor", "Repartidor"
        ADMINISTRADOR = "administrador", "Administrador"

    username = None  # usamos email como identificador
    email = models.EmailField("correo electrónico", max_length=150, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)
    foto_url = models.URLField(max_length=255, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "apellido"]

    objects = UsuarioManager()

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        self.is_active = self.activo
        campos = kwargs.get("update_fields")
        if campos is not None and "activo" in campos and "is_active" not in campos:
            kwargs["update_fields"] = list(campos) + ["is_active"]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rol})"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"


class PerfilRepartidor(models.Model):
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="perfil_repartidor"
    )
    tipo_vehiculo = models.CharField(max_length=50, blank=True, null=True)
    placa = models.CharField(max_length=20, blank=True, null=True)
    licencia = models.CharField(max_length=50, blank=True, null=True)
    disponible = models.BooleanField(default=True)
    ultima_lat = models.FloatField(blank=True, null=True)
    ultima_lng = models.FloatField(blank=True, null=True)
    calificacion_promedio = models.DecimalField(
        max_digits=3, decimal_places=2, default=0
    )

    class Meta:
        db_table = "perfiles_repartidor"
        verbose_name = "perfil de repartidor"
        verbose_name_plural = "perfiles de repartidor"

    def __str__(self):
        return f"Perfil repartidor: {self.usuario.nombre_completo}"


class Direccion(models.Model):
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="direcciones"
    )
    alias = models.CharField(max_length=50, blank=True, null=True)
    calle = models.CharField(max_length=150)
    numero = models.CharField(max_length=20, blank=True, null=True)
    distrito = models.CharField(max_length=100, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    referencia = models.CharField(max_length=255, blank=True, null=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    es_default = models.BooleanField(default=False)

    class Meta:
        db_table = "direcciones"
        verbose_name = "dirección"
        verbose_name_plural = "direcciones"

    def __str__(self):
        return f"{self.alias or self.calle} - {self.ciudad or ''}"


class CodigoRecuperacion(models.Model):

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacion",
    )
    # Guardamos el HMAC, nunca el código en claro.
    codigo_hash = models.CharField(max_length=64)
    expira_en = models.DateTimeField()
    # Fecha en vez de booleano, para saber cuándo se consumió.
    usado_en = models.DateTimeField(null=True, blank=True)
    # En la fila y no en caché, para que sobreviva a un reinicio.
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    ip_solicitante = models.GenericIPAddressField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "codigos_recuperacion"
        ordering = ["-fecha_creacion"]
        verbose_name = "código de recuperación"
        verbose_name_plural = "códigos de recuperación"
        indexes = [
            # La consulta caliente es "el último código de este usuario".
            models.Index(fields=["usuario", "-fecha_creacion"], name="idx_codrec_usuario_fecha"),
            models.Index(fields=["expira_en"], name="idx_codrec_expira"),
        ]

    def __str__(self):
        estado = "usado" if self.usado_en else "pendiente"
        return f"Código de {self.usuario.email} ({estado})"

    @property
    def esta_vigente(self) -> bool:
        from django.conf import settings as ajustes

        return (
            self.usado_en is None
            and self.expira_en > timezone.now()
            and self.intentos_fallidos < ajustes.PASSWORD_RESET_MAX_INTENTOS
        )
