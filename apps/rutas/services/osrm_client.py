import requests
from django.conf import settings

from core.exceptions import ServicioExternoNoDisponible


def calcular_ruta(coordenadas: list[tuple[float, float]]) -> dict:
    if len(coordenadas) < 2:
        raise ValueError("Se requieren al menos 2 puntos para calcular una ruta.")

    # OSRM espera lon,lat separados por ';'
    puntos = ";".join(f"{lng},{lat}" for lat, lng in coordenadas)
    url = f"{settings.OSRM_URL}/route/v1/driving/{puntos}"
    params = {"overview": "full", "geometries": "polyline"}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ServicioExternoNoDisponible(detail=f"OSRM no respondió: {exc}") from exc

    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ServicioExternoNoDisponible(detail=f"OSRM devolvió: {data.get('code')}")

    ruta = data["routes"][0]
    return {
        "geometria": ruta["geometry"],
        "distancia_km": round(ruta["distance"] / 1000, 2),
        "duracion_min": round(ruta["duration"] / 60, 1),
    }
