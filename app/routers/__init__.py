"""Registro de rutas auxiliares de NetDoc.

La aplicación importa este paquete al montar sus routers principales. Se aprovecha
ese punto único para registrar el módulo LLDP sin acoplarlo al router de racks o al
constructor de modelos.
"""

from app.main import app as _app
from app.routers.lldp_discovery import router as _lldp_discovery_router


if not getattr(_app.state, "lldp_discovery_router_registered", False):
    _app.include_router(_lldp_discovery_router)
    _app.state.lldp_discovery_router_registered = True
