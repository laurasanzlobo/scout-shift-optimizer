# app.py
import io
import json
import os
import time
import uuid
import atexit
import logging
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template, abort

from optimization import cargar_responsables, plan_limpieza, resolver_con_minizinc, DIAS
from report_generator import generar_excel, generar_pdf

# ─────────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB máximo por CSV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Directorio donde se guardan los JSON temporales de cada sesión de optimización.
# En producción puede apuntar a /tmp o a un volumen compartido entre workers.
TMP_DIR = Path(os.environ.get("SCOUT_TMP_DIR", Path(__file__).parent / "tmp_sessions"))
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Tiempo máximo (en segundos) que se conserva un archivo de sesión (1 hora)
SESSION_TTL = int(os.environ.get("SCOUT_SESSION_TTL", 3600))


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de sesión
# ─────────────────────────────────────────────────────────────────────────────

def _session_path(session_id: str) -> Path:
    """Devuelve la ruta al JSON de la sesión, validando que el ID sea un UUID."""
    try:
        uuid.UUID(session_id)          # Lanza ValueError si no es un UUID válido
    except ValueError:
        abort(404)
    return TMP_DIR / f"{session_id}.json"


def _guardar_sesion(asignaciones: list, limpieza: list) -> str:
    """Serializa las asignaciones de comedor y de limpieza en disco y devuelve el session_id."""
    session_id = str(uuid.uuid4())
    path = _session_path(session_id)
    contenido = {
        "asignaciones": asignaciones,
        "limpieza":     limpieza,
    }
    path.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    logger.info("Sesión creada: %s", session_id)
    return session_id


def _cargar_sesion(session_id: str) -> dict:
    """Carga las asignaciones y la limpieza de una sesión. Aborta con 404 si no existe.

    Mantiene compatibilidad con sesiones antiguas, guardadas como una lista
    plana de asignaciones sin la clave 'limpieza'.
    """
    path = _session_path(session_id)
    if not path.exists():
        abort(404, description="Sesión no encontrada o expirada. Genera el horario de nuevo.")

    datos = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(datos, list):
        # Formato heredado: solo asignaciones, sin datos de limpieza.
        return {"asignaciones": datos, "limpieza": []}

    return {
        "asignaciones": datos.get("asignaciones", []),
        "limpieza":     datos.get("limpieza", []),
    }


def _limpiar_sesiones_expiradas():
    """Elimina archivos de sesión más antiguos que SESSION_TTL segundos."""
    ahora = time.time()
    eliminados = 0
    for archivo in TMP_DIR.glob("*.json"):
        if ahora - archivo.stat().st_mtime > SESSION_TTL:
            archivo.unlink(missing_ok=True)
            eliminados += 1
    if eliminados:
        logger.info("Limpieza de sesiones: %d archivos eliminados", eliminados)


# Limpieza al arrancar (por si quedaron archivos de una ejecución anterior)
_limpiar_sesiones_expiradas()

# Limpieza final al apagar el proceso (funciona con Gunicorn --preload)
atexit.register(_limpiar_sesiones_expiradas)


# ─────────────────────────────────────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Sirve el frontend de la SPA."""
    return render_template("index.html")


@app.route("/generar_horario", methods=["POST"])
def generar_horario():
    if "file" not in request.files:
        return jsonify({"status": "error", "mensaje": "Falta el archivo CSV en la petición."}), 400

    archivo_csv = request.files["file"]

    if not archivo_csv.filename.lower().endswith(".csv"):
        return jsonify({"status": "error", "mensaje": "El archivo debe tener extensión .csv."}), 400

    try:
        df = cargar_responsables(archivo_csv)
        limpieza_dict = plan_limpieza()
        resultado, df_original = resolver_con_minizinc(df, limpieza_dict)

        if not resultado.solution:
            return jsonify({
                "status": "error",
                "mensaje": "Imposible generar turnos con las restricciones actuales. "
                           "Comprueba disponibilidades y vuelve a intentarlo."
            }), 422

        turnos_nombres = ["Desayuno", "Comida", "Cena"]
        matriz_comedor = resultado.solution.comedor
        total_dias_campamento = len(DIAS)

        asignaciones_finales = []
        plazas_cubiertas = 0
        for d_idx, d in enumerate(DIAS):
            for t_idx, t_name in enumerate(turnos_nombres):
                for p_idx, (_, row) in enumerate(df_original.iterrows()):
                    if matriz_comedor[d_idx][t_idx][p_idx]:
                        plazas_cubiertas += 1
                        asignaciones_finales.append({
                            "Dia":    d,
                            "Turno":  t_name,
                            "Nombre": row["Nombre"],
                            "Grupo":  row["Grupo"],
                        })

        plazas_totales = plazas_cubiertas

        # Yo calculo la media solo con los responsables que asisten todos los días.
        asistentes_campamento_completo = [
            row for _, row in df_original.iterrows()
            if len(row["DiasDisponibles"]) == total_dias_campamento
        ]
        turnos_por_persona_completa = {}
        for fila in asignaciones_finales:
            turnos_por_persona_completa[fila["Nombre"]] = turnos_por_persona_completa.get(fila["Nombre"], 0) + 1

        if asistentes_campamento_completo:
            suma_turnos = sum(turnos_por_persona_completa.get(row["Nombre"], 0) for row in asistentes_campamento_completo)
            carga_media = suma_turnos / len(asistentes_campamento_completo)
        else:
            carga_media = 0.0

        metricas_dashboard = {
            "kraal_activo": len(df_original),
            "plazas_cubiertas": plazas_cubiertas,
            "plazas_totales": plazas_totales,
            "plazas_porcentaje": 100 if plazas_totales else 0,
            "carga_media": round(carga_media, 1),
        }

        # Traducir limpieza_dict {(dia, turno): grupo} a una lista serializable en JSON,
        # ya que las claves de tupla no son válidas en JSON.
        limpieza_final = [
            {"Dia": d, "Turno": t_name, "GrupoLimpieza": grupo}
            for (d, t_name), grupo in limpieza_dict.items()
        ]

        # Limpiar sesiones antiguas de forma oportunista (sin overhead de hilo)
        _limpiar_sesiones_expiradas()

        # Persistir y obtener el identificador único de esta sesión
        session_id = _guardar_sesion(asignaciones_finales, limpieza_final)

        return jsonify({
            "status":       "exito",
            "session_id":   session_id,
            "asignaciones": asignaciones_finales,
            "limpieza":     limpieza_final,
            "metricas":     metricas_dashboard,
        })

    except Exception as exc:
        logger.exception("Error al generar horario: %s", exc)
        return jsonify({"status": "error", "mensaje": str(exc)}), 500


@app.route("/descargar/excel/<session_id>", methods=["GET"])
def descargar_excel(session_id: str):
    sesion = _cargar_sesion(session_id)
    try:
        excel_bytes = generar_excel(sesion["asignaciones"], sesion["limpieza"])
        return send_file(
            io.BytesIO(excel_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="turnos_campamento_2026.xlsx",
        )
    except Exception as exc:
        logger.exception("Error al generar Excel: %s", exc)
        return jsonify({"status": "error", "mensaje": str(exc)}), 500


@app.route("/descargar/pdf/<session_id>", methods=["GET"])
def descargar_pdf(session_id: str):
    sesion = _cargar_sesion(session_id)
    try:
        pdf_bytes = generar_pdf(sesion["asignaciones"], sesion["limpieza"])
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="turnos_campamento_2026.pdf",
        )
    except Exception as exc:
        logger.exception("Error al generar PDF: %s", exc)
        return jsonify({"status": "error", "mensaje": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Manejadores de error globales
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(exc):
    return jsonify({"status": "error", "mensaje": str(exc)}), 404


@app.errorhandler(413)
def request_too_large(_):
    return jsonify({"status": "error", "mensaje": "El archivo CSV supera el límite de 2 MB."}), 413


# ─────────────────────────────────────────────────────────────────────────────
# Arranque en desarrollo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
