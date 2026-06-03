from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class Configuracion(BaseSettings):
    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")

    # JWT
    jwt_secret: str = Field(default="CAMBIAR_A_UN_SECRET_FUERTE", alias="JWT_SECRET")
    jwt_algoritmo: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiracion_minutos: int = Field(default=480, alias="JWT_EXPIRE_MINUTES")  # 8 horas = 1 turno

    # CORS
    allowed_origins: list[str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_ORIGINS.copy(),
        alias="ALLOWED_ORIGINS"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validaciones al arrancar el servidor
        if not self.supabase_url:
            print("ERROR: SUPABASE_URL no cargada")
        if not self.supabase_key:
            print("ERROR: SUPABASE_KEY no cargada")
        if self.jwt_secret == "CAMBIAR_A_UN_SECRET_FUERTE":
            print("ADVERTENCIA: JWT_SECRET usando valor por defecto, cámbialo en producción")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parsear_allowed_origins(cls, value):
        if value is None or value == "":
            return DEFAULT_ALLOWED_ORIGINS.copy()

        if isinstance(value, list):
            limpio = [origin.strip() for origin in value if origin and origin.strip()]
            return limpio or DEFAULT_ALLOWED_ORIGINS.copy()

        if isinstance(value, str):
            valor_raw = value.strip()
            if not valor_raw:
                return DEFAULT_ALLOWED_ORIGINS.copy()

            if valor_raw.startswith("[") and valor_raw.endswith("]"):
                valor_raw = valor_raw[1:-1]

            origenes = [
                origin.strip().strip('"').strip("'")
                for origin in valor_raw.split(",")
                if origin.strip()
            ]
            return origenes or DEFAULT_ALLOWED_ORIGINS.copy()

        raise ValueError("ALLOWED_ORIGINS debe ser una lista o string separado por comas")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instancia global — se importa en todo el proyecto
config = Configuracion()