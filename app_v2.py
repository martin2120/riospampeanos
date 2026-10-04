# -*- coding: utf-8 -*-
"""
Servidor Flask - Bot Hídrico La Pampa
Consulta datos hidrológicos desde COIRCO e INA/SNIH mediante módulo lapampa.py en Gist
"""

import os
import sys
import importlib.util
import requests
from datetime import datetime
from flask import Flask, jsonify

# URL del Gist crudo apuntando a lapampa.py
GIST_RAW_URL = os.getenv(
    "GIST_RAW_URL",
    "https://gist.githubusercontent.com/martin2120/c108b944ca3206b9e79542eaa8137ea5/raw/lapampa.py"
)

app = Flask(__name__)
lapampa_module = None


def cargar_modulo_desde_gist():
    """Descarga y carga dinámicamente el módulo lapampa.py desde el Gist."""
    global lapampa_module
    try:
        print("[INFO] Cargando módulo desde Gist...")
        resp = requests.get(GIST_RAW_URL, timeout=12)
        resp.raise_for_status()
        
        # Crear especificación y módulo virtual
        spec = importlib.util.spec_from_loader("lapampa", loader=None)
        modulo_temp = importlib.util.module_from_spec(spec)
        
        # Ejecutar el código del Gist dentro del espacio de nombres del módulo
        exec(resp.text, modulo_temp.__dict__)
        
        lapampa_module = modulo_temp
        print("[✓] Módulo lapampa cargado correctamente desde Gist")
        return True
    except Exception as e:
        print(f"[✗] Error al cargar módulo desde Gist: {e}")
        return False


# Intentar cargar el módulo al iniciar la API
if not cargar_modulo_desde_gist():
    print("[ADVERTENCIA] No se pudo cargar el módulo del Gist al iniciar")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route("/", methods=["GET"])
def index():
    """Endpoint raíz - información del servicio."""
    return jsonify({
        "servicio": "Bot Hídrico La Pampa",
        "version": "2.0",
        "estado": "activo" if lapampa_module is not None else "degradado",
        "descripcion": "Sistema de monitoreo hidrológico en tiempo real",
        "fuentes": ["COIRCO (Río Colorado)", "SNIH/INA (Cuenca del Plata)"],
        "endpoints": {
            "GET /": "Esta información",
            "GET /api/datos": "Todos los datos hídricos",
            "GET /api/estaciones": "Listado de estaciones",
            "GET /api/estacion/<st_id>": "Datos de una estación específica",
            "GET /api/estado": "Estado de las fuentes de datos",
            "POST /api/reload": "Recargar módulo desde Gist"
        }
    }), 200


@app.route("/api/datos", methods=["GET"])
def api_datos():
    """Retorna todos los datos hídricos en tiempo real."""
    if lapampa_module is None:
        return jsonify({
            "exito": False,
            "error": "Módulo no cargado. Ejecuta POST /api/reload o verifica la URL del Gist."
        }), 500
    
    try:
        datos = lapampa_module.obtener_datos_hidricos()
        return jsonify({
            "exito": True,
            "cantidad": len(datos),
            "timestamp": datetime.now().isoformat(),
            "datos": datos
        }), 200
    except Exception as e:
        return jsonify({
            "exito": False,
            "error": str(e)
        }), 500


@app.route("/api/estaciones", methods=["GET"])
def api_estaciones():
    """Lista todas las estaciones disponibles con metadatos."""
    if lapampa_module is None:
        return jsonify({
            "exito": False,
            "error": "Módulo no cargado"
        }), 500
    
    try:
        datos = lapampa_module.listar_estaciones()
        estaciones = [
            {
                "id": est["id"],
                "nombre": est["nombre"],
                "rio": est["rio"],
                "provincia": est["provincia"],
                "tipo": est["tipo"],
                "fuente": est.get("fuente", "N/A"),
                "ultima_actualizacion": est.get("fecha_txt", "")
            }
            for est in datos
        ]
        
        return jsonify({
            "exito": True,
            "cantidad": len(estaciones),
            "timestamp": datetime.now().isoformat(),
            "estaciones": estaciones
        }), 200
    except Exception as e:
        return jsonify({
            "exito": False,
            "error": str(e)
        }), 500


@app.route("/api/estacion/<st_id>", methods=["GET"])
def api_estacion(st_id):
    """Retorna datos completos de una estación específica."""
    if lapampa_module is None:
        return jsonify({
            "exito": False,
            "error": "Módulo no cargado"
        }), 500
    
    try:
        estacion = lapampa_module.obtener_estacion(st_id)
        
        if estacion is None:
            return jsonify({
                "exito": False,
                "error": f"Estación '{st_id}' no encontrada",
                "estaciones_disponibles": [
                    est["id"] for est in lapampa_module.listar_estaciones()
                ]
            }), 404
        
        return jsonify({
            "exito": True,
            "timestamp": datetime.now().isoformat(),
            "estacion": estacion
        }), 200
    except Exception as e:
        return jsonify({
            "exito": False,
            "error": str(e)
        }), 500


@app.route("/api/estado", methods=["GET"])
def api_estado():
    """Retorna el estado de las fuentes de datos (COIRCO, SNIH)."""
    if lapampa_module is None:
        return jsonify({
            "exito": False,
            "error": "Módulo no cargado"
        }), 500
    
    try:
        if hasattr(lapampa_module, 'obtener_estado_sistema'):
            estado = lapampa_module.obtener_estado_sistema()
            return jsonify({
                "exito": True,
                "estado": estado
            }), 200
        else:
            return jsonify({
                "exito": False,
                "error": "Función obtener_estado_sistema no disponible en el Gist"
            }), 500
    except Exception as e:
        return jsonify({
            "exito": False,
            "error": str(e)
        }), 500


@app.route("/api/reload", methods=["POST"])
def api_reload():
    """Recarga el módulo desde el Gist (útil tras actualizar el Gist)."""
    if cargar_modulo_desde_gist():
        return jsonify({
            "exito": True,
            "mensaje": "Módulo lapampa.py recargado correctamente desde Gist",
            "timestamp": datetime.now().isoformat()
        }), 200
    else:
        return jsonify({
            "exito": False,
            "error": "Error al recargar el módulo desde el Gist"
        }), 500


# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "exito": False,
        "error": "Endpoint no encontrado",
        "hint": "Ver GET / para listar endpoints disponibles"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "exito": False,
        "error": "Error interno del servidor",
        "timestamp": datetime.now().isoformat()
    }), 500


# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    app.run(host="0.0.0.0", port=port, debug=debug)
