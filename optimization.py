# motor_optimizacion.py
import minizinc
import pandas as pd
from typing import Dict, List, Set, Tuple
from datetime import timedelta
from pathlib import Path

# ─────────────────── Parámetros globales ──────────────────────────────────────
DIAS: List[int] = [d for d in range(15, 31) if d not in {17, 18, 19}]
TURNOS: List[str] = ["Desayuno", "Comida", "Cena"]

# Internamente Castores y Rutas se tratan como un único grupo para la
# optimización, pero se siguen mostrando por separado en la salida.
GRUPO_CASTORES_RUTAS = "CastoresRutas"
GRUPOS: List[str] = [GRUPO_CASTORES_RUTAS, "Lobatos", "Ranger", "Pioneros"]
GRUPO_INTERNO_POR_VISIBLE = {
    "Castores": GRUPO_CASTORES_RUTAS,
    "Rutas": GRUPO_CASTORES_RUTAS,
    "Lobatos": "Lobatos",
    "Ranger": "Ranger",
    "Pioneros": "Pioneros",
}

NO_DESAYUNO_DAYS = {20}
NO_COMIDA_DAYS_COMEDOR: Set[int] = {20, 25, 30}
NO_CENA_DAYS: Set[int] = {30}

def _split_days(text: str) -> Set[int]:
    """Parseo mis días separados por ';' o ',' y me quedo solo con los que
    de verdad existen en el campamento. Antes estaba metiendo en el set
    cualquier número que escribiera (p. ej. 17, 18, 19, que ni siquiera son
    días de campamento), y eso me estaba inflando artificialmente la cuota
    teórica de quien tuviera un despiste en el CSV, además de hacer que
    `disponible_siempre` diera falsos negativos/positivos."""
    if not text or pd.isna(text):
        return set()
    tokens = [t.strip() for t in str(text).replace(",", ";").split(";") if t.strip()]
    dias_validos = {int(t.split()[0]) for t in tokens if t.split()[0].isdigit()}
    return dias_validos & set(DIAS)

def cargar_responsables(file_stream) -> pd.DataFrame:
    df = pd.read_csv(file_stream, dtype=str).fillna("")
    df.columns = df.columns.str.strip()

    if not {"Nombre", "Grupo"}.issubset(df.columns):
        # Fallback por si no hay cabecera en el CSV
        file_stream.seek(0)
        df = pd.read_csv(file_stream, dtype=str, header=None).fillna("")
        base = ["Nombre", "Grupo", "TeatroComida", "TeatroCena", "Disponible"][: df.shape[1]]
        base += [f"X{i}" for i in range(df.shape[1] - len(base))]
        df.columns = base
    df["Grupo"] = df["Grupo"].astype(str).str.strip()
    df["GrupoInterno"] = df["Grupo"].map(lambda g: GRUPO_INTERNO_POR_VISIBLE.get(g, g))
    df["DiasTeatroComida"] = df.get("TeatroComida", "").apply(_split_days)
    df["DiasTeatroCena"] = df.get("TeatroCena", "").apply(_split_days)
    disp = df.get("Disponible", "").apply(_split_days)
    df["DiasDisponibles"] = [s if s else set(DIAS) for s in disp]

    return df[["Nombre", "Grupo", "GrupoInterno", "DiasDisponibles", "DiasTeatroComida", "DiasTeatroCena"]]

def calcular_presencia_grupo(df: pd.DataFrame) -> List[List[int]]:
    """Calculo, para cada día y cada rama, cuántos responsables de esa rama
    están físicamente presentes en el campamento (según su DiasDisponibles).

    Esto es lo que me permite saber, p.ej., que Lobatos solo tiene 3
    efectivos reales antes de que llegue Akela el día 24, en vez de asumir
    siempre los 4 que hay en plantilla.
    """
    matriz: List[List[int]] = []
    for d in DIAS:
        fila = []
        for grupo in GRUPOS:  # mismo orden que uso para mapa_grupos
            presentes = sum(
                1 for _, row in df.iterrows()
                if row["GrupoInterno"] == grupo and d in row["DiasDisponibles"]
            )
            fila.append(presentes)
        matriz.append(fila)
    return matriz

def plan_limpieza() -> Dict[Tuple[int, str], str]:
    mapping: Dict[Tuple[int, str], str] = {}
    for i, d in enumerate(DIAS):
        if d not in NO_DESAYUNO_DAYS:
            mapping[(d, "Desayuno")] = GRUPOS[i % 4]
        if d not in NO_COMIDA_DAYS_COMEDOR:
            mapping[(d, "Comida")] = GRUPOS[(i + 1) % 4]
        if d not in NO_CENA_DAYS:
            mapping[(d, "Cena")] = GRUPOS[(i + 2) % 4]
    return mapping

def resolver_con_minizinc(df: pd.DataFrame, limpieza_dict: Dict[Tuple[int, str], str],
                           margen_equidad: int = 0):
    """Añado margen_equidad como parámetro configurable: es la desviación
    máxima que le permito a cada responsable de campamento completo respecto
    a su propia cuota ideal. Lo subo o bajo desde aquí sin tocar el .mzn."""
    n_personas = len(df)
    mapa_grupos = {grupo: idx + 1 for idx, grupo in enumerate(GRUPOS)}
    grupo_persona = [mapa_grupos.get(g, 1) for g in df["GrupoInterno"]]

    disponible = []
    teatro_comida = []
    teatro_cena = []

    for _, row in df.iterrows():
        disponible.append([d in row["DiasDisponibles"] for d in DIAS])
        teatro_comida.append([d in row["DiasTeatroComida"] for d in DIAS])
        teatro_cena.append([d in row["DiasTeatroCena"] for d in DIAS])

    turno_activo = []
    grupo_limpia = []
    total_plazas_necesarias = 0

    for d in DIAS:
        dia_activos = []
        dia_limpieza = []

        for t_name in TURNOS:
            activo = True
            if t_name == "Desayuno" and d in NO_DESAYUNO_DAYS: activo = False
            if t_name == "Comida" and d in NO_COMIDA_DAYS_COMEDOR: activo = False
            if t_name == "Cena" and d in NO_CENA_DAYS: activo = False

            dia_activos.append(activo)

            if activo:
                total_plazas_necesarias += 6

            g_limpia_str = limpieza_dict.get((d, t_name))
            dia_limpieza.append(mapa_grupos.get(g_limpia_str, 0) if g_limpia_str else 0)

        turno_activo.append(dia_activos)
        grupo_limpia.append(dia_limpieza)

    total_dias_disponibles_kraal = sum(len(row["DiasDisponibles"]) for _, row in df.iterrows())
    presencia_grupo = calcular_presencia_grupo(df)
    total_dias_campamento = len(DIAS)

    limite_turnos = []
    cuota_ideal = []
    disponible_siempre = []
    for _, row in df.iterrows():
        dias_disp = len(row["DiasDisponibles"])
        cuota_teorica = round(total_plazas_necesarias * dias_disp / total_dias_disponibles_kraal)
        limite_turnos.append(cuota_teorica + 5)
        cuota_ideal.append(cuota_teorica)
        disponible_siempre.append(dias_disp == total_dias_campamento)

    modelo = minizinc.Model(Path(__file__).with_name("shift_scheduler.mzn"))
    solver = minizinc.Solver.lookup("gecode")
    instancia = minizinc.Instance(solver, modelo)

    instancia["n_personas"] = n_personas
    instancia["grupo_persona"] = grupo_persona
    instancia["disponible"] = disponible
    instancia["teatro_comida"] = teatro_comida
    instancia["teatro_cena"] = teatro_cena
    instancia["limite_turnos"] = limite_turnos
    instancia["turno_activo"] = turno_activo
    instancia["grupo_limpia"] = grupo_limpia
    instancia["presencia_grupo"] = presencia_grupo
    instancia["cuota_ideal"] = cuota_ideal
    instancia["disponible_siempre"] = disponible_siempre
    instancia["margen_equidad"] = margen_equidad

    resultado = instancia.solve(timeout=timedelta(seconds=30))

    return resultado, df