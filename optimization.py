# motor_optimizacion.py
import minizinc
import pandas as pd
from typing import Dict, List, Set, Tuple
from datetime import timedelta
from pathlib import Path

# ─────────────────── Parámetros globales ──────────────────────────────────────
DIAS: List[int] = [d for d in range(15, 31) if d not in {17, 18, 19}]
TURNOS: List[str] = ["Desayuno", "Comida", "Cena"]
GRUPOS: List[str] = ["Castores", "Lobatos", "Ranger", "Pioneros", "Rutas"]

NO_DESAYUNO_DAYS = {20}
NO_COMIDA_DAYS_COMEDOR: Set[int] = {20, 25, 30}
NO_CENA_DAYS: Set[int] = {30}

def _split_days(text: str) -> Set[int]:
    if not text or pd.isna(text):
        return set()
    tokens = [t.strip() for t in str(text).replace(",", ";").split(";") if t.strip()]
    return {int(t.split()[0]) for t in tokens if t.split()[0].isdigit()}

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


    df["DiasTeatroComida"] = df.get("TeatroComida", "").apply(_split_days)
    df["DiasTeatroCena"] = df.get("TeatroCena", "").apply(_split_days)
    disp = df.get("Disponible", "").apply(_split_days)
    df["DiasDisponibles"] = [s if s else set(DIAS) for s in disp]

    return df[["Nombre", "Grupo", "DiasDisponibles", "DiasTeatroComida", "DiasTeatroCena"]]

def plan_limpieza() -> Dict[Tuple[int, str], str]:
    mapping: Dict[Tuple[int, str], str] = {}
    for i, d in enumerate(DIAS):
        if d not in NO_DESAYUNO_DAYS:
            mapping[(d, "Desayuno")] = GRUPOS[i % 5]
        if d not in NO_COMIDA_DAYS_COMEDOR:
            mapping[(d, "Comida")] = GRUPOS[(i + 1) % 5]
        if d not in NO_CENA_DAYS:
            mapping[(d, "Cena")] = GRUPOS[(i + 2) % 5]
    return mapping

def resolver_con_minizinc(df: pd.DataFrame, limpieza_dict: Dict[Tuple[int, str], str]):
    n_personas = len(df)
    mapa_grupos = {grupo: idx + 1 for idx, grupo in enumerate(GRUPOS)}
    grupo_persona = [mapa_grupos.get(g, 1) for g in df["Grupo"]]

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

    limite_turnos = []
    for _, row in df.iterrows():
        dias_disp = len(row["DiasDisponibles"])
        
        # Ahora la cuota teórica es justa y proporcional a la disponibilidad real
        cuota_teorica = round(total_plazas_necesarias * dias_disp / total_dias_disponibles_kraal)
        
        # Añado un margen de +3 para que el solver respire y no haga timeout
        limite_turnos.append(cuota_teorica + 3)

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

    resultado = instancia.solve(timeout=timedelta(seconds=15))

    return resultado, df

