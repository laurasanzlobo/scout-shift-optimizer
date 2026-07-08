# generador_informes.py
import io
from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

from jinja2 import Template
import weasyprint

# ─────────────────────────────────────────────────────────────────────────────
# Paleta de colores por rama scout
# ─────────────────────────────────────────────────────────────────────────────
COLORES_GRUPOS = {
    "Castores":  {"hex": "FF9800", "texto": "FFFFFF", "bg_ligero": "FFF3E0"},  
    "Lobatos":   {"hex": "FBC02D", "texto": "333333", "bg_ligero": "FFF9C4"},  
    "Ranger":    {"hex": "1E88E5", "texto": "FFFFFF", "bg_ligero": "E3F2FD"},  
    "Pioneros":  {"hex": "D32F2F", "texto": "FFFFFF", "bg_ligero": "FFEBEE"},  
    "Rutas":     {"hex": "43A047", "texto": "FFFFFF", "bg_ligero": "E8F5E9"},  
}

COLORES_TURNOS = {
    "Desayuno": "FFF9C4",
    "Comida":   "C8E6C9",
    "Cena":     "BBDEFB",
}

DIAS = [d for d in range(15, 31) if d not in {17, 18, 19}]
TURNOS = ["Desayuno", "Comida", "Cena"]


def _thin_border():
    thin = Side(style="thin", color="CCCCCC")
    return Border(left=thin, right=thin, top=thin, bottom=thin)

def _mapa_limpieza(limpieza: Optional[List[Dict]]) -> Dict:
    if not limpieza:
        return {}
    return {
        (item["Dia"], item["Turno"]): item["GrupoLimpieza"]
        for item in limpieza
    }

# ─────────────────────────────────────────────────────────────────────────────
# EXCEL (Se mantiene idéntico)
# ─────────────────────────────────────────────────────────────────────────────
def generar_excel(asignaciones: List[Dict], limpieza: Optional[List[Dict]] = None) -> bytes:
    df = pd.DataFrame(asignaciones)
    limpieza_dict = _mapa_limpieza(limpieza)
    wb = Workbook()

    _hoja_por_dia(wb, df, limpieza_dict)
    _hoja_por_persona(wb, df)
    _hoja_datos(wb, df)

    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def _estilo_cabecera(cell, color_hex: str, texto_hex: str = "FFFFFF"):
    cell.font = Font(bold=True, color=texto_hex, name="Arial", size=10)
    cell.fill = PatternFill("solid", start_color=color_hex)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = _thin_border()

def _hoja_por_dia(wb: Workbook, df: pd.DataFrame, limpieza_dict: Dict):
    ws = wb.create_sheet("Por Día")
    ws.merge_cells("A1:E1")
    ws["A1"] = f"Turnos de Comedor — Campamento Verano 2026"
    ws["A1"].font = Font(bold=True, size=13, name="Arial")
    ws["A1"].alignment = Alignment(horizontal="center")

    cabeceras = ["Día", "Turno", "Responsables", "Grupos", "Limpieza"]
    for col, txt in enumerate(cabeceras, start=1):
        cell = ws.cell(row=3, column=col, value=txt)
        _estilo_cabecera(cell, "37474F")

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 45
    ws.column_dimensions["D"].width = 35
    ws.column_dimensions["E"].width = 18

    fila = 4
    for dia in DIAS:
        for turno in TURNOS:
            subset = df[(df["Dia"] == dia) & (df["Turno"] == turno)]
            if subset.empty:
                continue

            nombres = ", ".join(subset["Nombre"].tolist())
            grupos = ", ".join(subset["Grupo"].tolist())
            grupo_limpieza = limpieza_dict.get((dia, turno), "—")
            color_fondo = COLORES_TURNOS.get(turno, "FFFFFF")
            colores_limpieza = COLORES_GRUPOS.get(grupo_limpieza, {"hex": "ECEFF1", "texto": "333333"})

            valores = [dia, turno, nombres, grupos]
            for col, valor in enumerate(valores, start=1):
                cell = ws.cell(row=fila, column=col, value=valor)
                cell.fill = PatternFill("solid", start_color=color_fondo)
                cell.border = _thin_border()
                cell.font = Font(name="Arial", size=9)
                cell.alignment = Alignment(vertical="center", wrap_text=True)

            celda_limpieza = ws.cell(row=fila, column=5, value=grupo_limpieza)
            celda_limpieza.fill = PatternFill("solid", start_color=colores_limpieza["hex"])
            celda_limpieza.font = Font(name="Arial", size=9, bold=True, color=colores_limpieza["texto"])
            celda_limpieza.border = _thin_border()
            celda_limpieza.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            ws.row_dimensions[fila].height = 30
            fila += 1

    ws.freeze_panes = "A4"

def _hoja_por_persona(wb: Workbook, df: pd.DataFrame):
    ws = wb.create_sheet("Por Persona")
    ws.merge_cells("A1:F1")
    ws["A1"] = "Carga de Turnos por Responsable"
    ws["A1"].font = Font(bold=True, size=13, name="Arial")
    ws["A1"].alignment = Alignment(horizontal="center")

    cabeceras = ["Nombre", "Grupo", "Nº Turnos", "Desayunos", "Comidas", "Cenas"]
    for col, txt in enumerate(cabeceras, start=1):
        cell = ws.cell(row=3, column=col, value=txt)
        _estilo_cabecera(cell, "37474F")

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 14
    for col_letra in ["C", "D", "E", "F"]:
        ws.column_dimensions[col_letra].width = 12

    resumen = (df.groupby(["Nombre", "Grupo", "Turno"]).size().unstack(fill_value=0).reset_index())
    for t in TURNOS:
        if t not in resumen.columns:
            resumen[t] = 0
    resumen["Total"] = resumen[TURNOS].sum(axis=1)
    resumen = resumen.sort_values(["Grupo", "Nombre"])

    fila = 4
    for _, row in resumen.iterrows():
        grupo = row["Grupo"]
        colores = COLORES_GRUPOS.get(grupo, {"hex": "ECEFF1", "texto": "333333"})

        valores = [row["Nombre"], grupo, row["Total"], row.get("Desayuno", 0), row.get("Comida", 0), row.get("Cena", 0)]
        for col, valor in enumerate(valores, start=1):
            cell = ws.cell(row=fila, column=col, value=valor)
            cell.fill = PatternFill("solid", start_color=colores["hex"])
            cell.font = Font(name="Arial", size=9, color=colores["texto"])
            cell.border = _thin_border()
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if col == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")

        fila += 1

    total_row = fila
    ws.cell(row=total_row, column=1, value="TOTAL TURNOS").font = Font(bold=True, name="Arial")
    ws.cell(row=total_row, column=3, value=f"=SUM(C4:C{total_row-1})").font = Font(bold=True, name="Arial")
    for col in [4, 5, 6]:
        letra = get_column_letter(col)
        ws.cell(row=total_row, column=col, value=f"=SUM({letra}4:{letra}{total_row-1})").font = Font(bold=True, name="Arial")

    ws.freeze_panes = "A4"

def _hoja_datos(wb: Workbook, df: pd.DataFrame):
    ws = wb.create_sheet("Datos")
    ws["A1"] = "Volcado de datos — generado automáticamente"
    ws["A1"].font = Font(italic=True, color="888888", name="Arial", size=9)

    cabeceras = ["Dia", "Turno", "Nombre", "Grupo"]
    for col, txt in enumerate(cabeceras, start=1):
        cell = ws.cell(row=2, column=col, value=txt)
        _estilo_cabecera(cell, "546E7A")

    for fila, (_, row) in enumerate(df.sort_values(["Dia", "Turno"]).iterrows(), start=3):
        for col, campo in enumerate(cabeceras, start=1):
            ws.cell(row=fila, column=col, value=row[campo])

    for col_letra in ["A", "B", "C", "D"]:
        ws.column_dimensions[col_letra].width = 18

# ─────────────────────────────────────────────────────────────────────────────
# PDF — Diseño "Presentación Diapositivas"
# ─────────────────────────────────────────────────────────────────────────────
_PLANTILLA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4 landscape;
    margin: 1cm 1.2cm;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #2C3E50;
  }

  /* Aquí genero mis clases de color dinámicas por rama, igual que antes,
     por si quiero pintar el nombre de un grupo dentro de una celda. */
  {% for grupo, col in colores_grupos.items() %}
  .bg-{{ grupo|lower|replace(' ','') }} { background: #{{ col.hex }}; color: #{{ col.texto }}; }
  {% endfor %}

  /* Cabecera de página (título + subtítulo de cada cuadrante) */
  .pagina {
    width: 100%;
    height: 19cm; /* alto útil de la landscape A4 con mis márgenes */
    display: flex;
    flex-direction: column;
    page-break-after: always;
  }
  .pagina:last-child { page-break-after: auto; }

  .cabecera-pagina {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.4cm;
    border-bottom: 0.1cm solid #1C2331;
    padding-bottom: 0.25cm;
  }
  .cabecera-pagina h1 {
    font-size: 22pt;
    font-weight: 800;
    color: #1C2331;
  }
  .cabecera-pagina .subt {
    font-size: 10pt;
    color: #7F8C8D;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  /* Mi tabla de cuadrante: turnos en filas, días en columnas */
  table.cuadrante {
    width: 100%;
    height: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }
  table.cuadrante th, table.cuadrante td {
    border: 1px solid #B0BEC5;
    vertical-align: middle;
    text-align: center;
    padding: 0.15cm;
  }

  /* Esquina superior izquierda vacía */
  .celda-esquina {
    background: #1C2331;
    width: 3.2cm;
  }

  /* Cabecera de columnas = días del campamento */
  .cabecera-dia {
    background: #1C2331;
    color: #FFFFFF;
    font-size: 11pt;
    font-weight: 700;
  }
  .cabecera-dia .mes {
    display: block;
    font-size: 7pt;
    font-weight: 400;
    color: #B0BEC5;
    text-transform: uppercase;
  }

  /* Cabecera de filas = turnos, coloreada según mi paleta de turnos */
  .cabecera-turno {
    width: 3.2cm;
    color: #1C2331;
    font-size: 12pt;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .cabecera-turno .hora {
    display: block;
    font-size: 8pt;
    font-weight: 500;
    opacity: 0.75;
  }

  /* Celda de contenido: limpieza */
  .celda-limpieza {
    font-size: 11pt;
    font-weight: 700;
  }
  .celda-limpieza-vacia {
    color: #CFD8DC;
    font-size: 9pt;
    font-style: italic;
  }

  /* Celda de contenido: comedor, con salto de línea controlado
     para que la lista de nombres nunca desborde la celda */
  .celda-comedor {
    font-size: 9pt;
    line-height: 1.35;
    text-align: left;
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
  }
  .celda-comedor-vacia {
    color: #CFD8DC;
    font-size: 9pt;
    font-style: italic;
    text-align: center;
  }

  .footer-pagina {
    margin-top: 0.3cm;
    text-align: right;
    font-size: 7pt;
    color: #AAB7B8;
  }
</style>
</head>
<body>

<!-- PÁGINA 1 · CUADRANTE DE LIMPIEZA -->
<section class="pagina">
  <div class="cabecera-pagina">
    <h1>Cuadrante de Limpieza</h1>
    <span class="subt">Campamento Verano {{ anio }}</span>
  </div>

  <table class="cuadrante">
    <thead>
      <tr>
        <th class="celda-esquina"></th>
        {% for dia in dias %}
        <th class="cabecera-dia">{{ dia }}<span class="mes">jul</span></th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for turno in turnos %}
      <tr>
        <th class="cabecera-turno" style="background:#{{ colores_turnos[turno] }};">
          {{ turno }}<span class="hora">{{ horas_turno[turno] }}</span>
        </th>
        {% for dia in dias %}
        {% set grupo = matriz_limpieza[turno][dia] %}
        <td>
          {% if grupo %}
          <div class="celda-limpieza bg-{{ grupo|lower|replace(' ','') }}">{{ grupo }}</div>
          {% else %}
          <span class="celda-limpieza-vacia">—</span>
          {% endif %}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="footer-pagina">Generado el {{ fecha }}</div>
</section>

<!-- PÁGINA 2 · CUADRANTE DE COMEDOR -->
<section class="pagina">
  <div class="cabecera-pagina">
    <h1>Cuadrante de Comedor</h1>
    <span class="subt">Campamento Verano {{ anio }}</span>
  </div>

  <table class="cuadrante">
    <thead>
      <tr>
        <th class="celda-esquina"></th>
        {% for dia in dias %}
        <th class="cabecera-dia">{{ dia }}<span class="mes">jul</span></th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for turno in turnos %}
      <tr>
        <th class="cabecera-turno" style="background:#{{ colores_turnos[turno] }};">
          {{ turno }}<span class="hora">{{ horas_turno[turno] }}</span>
        </th>
        {% for dia in dias %}
        {% set responsables = matriz_comedor[turno][dia] %}
        <td>
          {% if responsables %}
          <div class="celda-comedor">{{ responsables }}</div>
          {% else %}
          <span class="celda-comedor-vacia">—</span>
          {% endif %}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="footer-pagina">Generado el {{ fecha }}</div>
</section>

</body>
</html>
"""

def generar_pdf(asignaciones: List[Dict], limpieza: Optional[List[Dict]] = None, anio: int = 2026) -> bytes:
    df = pd.DataFrame(asignaciones)
    limpieza_dict = _mapa_limpieza(limpieza)

    # Horas de referencia por turno, para mostrarlas junto al nombre en la cabecera de fila.
    horas_turno = {"Desayuno": "08:30", "Comida": "13:30", "Cena": "20:30"}

    # Aquí armo mi matriz de limpieza: turno -> dia -> grupo (o None si ese turno
    # no tiene servicio ese día, p.ej. la comida del 20 o la cena del 30).
    matriz_limpieza: Dict[str, Dict[int, Optional[str]]] = {
        turno: {dia: limpieza_dict.get((dia, turno)) for dia in DIAS}
        for turno in TURNOS
    }

    # Y aquí armo mi matriz de comedor: turno -> dia -> string con los nombres
    # de los responsables ya unidos por comas, lista para pintar en la celda.
    matriz_comedor: Dict[str, Dict[int, Optional[str]]] = {turno: {} for turno in TURNOS}
    for turno in TURNOS:
        for dia in DIAS:
            subset = df[(df["Dia"] == dia) & (df["Turno"] == turno)] if not df.empty else df
            if subset.empty:
                matriz_comedor[turno][dia] = None
            else:
                matriz_comedor[turno][dia] = ", ".join(subset["Nombre"].tolist())

    html_renderizado = Template(_PLANTILLA_HTML).render(
        dias=DIAS,
        turnos=TURNOS,
        horas_turno=horas_turno,
        matriz_limpieza=matriz_limpieza,
        matriz_comedor=matriz_comedor,
        colores_grupos=COLORES_GRUPOS,
        colores_turnos=COLORES_TURNOS,
        anio=anio,
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )

    pdf_bytes = weasyprint.HTML(string=html_renderizado).write_pdf()
    return pdf_bytes