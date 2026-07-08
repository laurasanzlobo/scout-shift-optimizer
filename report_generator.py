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
    "Ranger1":   {"hex": "4CAF50", "texto": "FFFFFF", "bg_ligero": "E8F5E9"},  
    "Ranger2":   {"hex": "2E7D32", "texto": "FFFFFF", "bg_ligero": "C8E6C9"},  
    "Pioneros":  {"hex": "D32F2F", "texto": "FFFFFF", "bg_ligero": "FFEBEE"},  
}

COLORES_TURNOS = {
    "Desayuno": "FFF9C4",
    "Comida":   "C8E6C9",
    "Cena":     "BBDEFB",
}

DIAS = list(range(20, 31))
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
    margin: 0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #333;
    background: #FAFAFA;
  }

  /* ── CLASES DE COLORES DINÁMICOS POR RAMA ── */
  {% for grupo, col in colores.items() %}
  .bg-{{ grupo|lower|replace(' ','') }} { background: #{{ col.hex }}; color: #{{ col.texto }}; }
  .bg-light-{{ grupo|lower|replace(' ','') }} { background: #{{ col.bg_ligero }}; border-left: 5px solid #{{ col.hex }}; }
  .text-{{ grupo|lower|replace(' ','') }} { color: #{{ col.hex }}; }
  {% endfor %}

  /* ── PORTADA ── */
  .portada {
    position: relative;
    width: 29.7cm;
    height: 21cm;
    background: #F8F4EC; /* Crema muy suave y estético */
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .forma-azul {
    position: absolute; left: -5cm; top: -2cm;
    width: 12cm; height: 18cm;
    background: #2E5C8A;
    border-radius: 4cm;
    transform: rotate(25deg);
  }
  .forma-verde {
    position: absolute; right: -6cm; bottom: -3cm;
    width: 15cm; height: 14cm;
    background: #4A8259;
    border-radius: 3cm;
    transform: rotate(-15deg);
  }
  .portada-contenido {
    position: relative; z-index: 5; text-align: center;
    background: rgba(255, 255, 255, 0.6);
    padding: 2cm 3cm;
    border-radius: 1cm;
  }
  .portada-titulo {
    font-size: 58pt; font-weight: 800; color: #1C2331;
    letter-spacing: -1px; margin-bottom: 0.2cm;
  }
  .portada-subtitulo {
    font-size: 18pt; font-weight: 500; color: #555;
    letter-spacing: 3px; text-transform: uppercase;
  }

  /* ── PÁGINAS DE DÍA (DIAPOSITIVAS) ── */
  .pagina-dia {
    position: relative;
    width: 29.7cm; height: 21cm;
    padding: 1.5cm 2cm;
    display: flex; flex-direction: column;
    page-break-before: always;
    background: #FAFAFA;
    overflow: hidden;
  }
  
  /* Elementos decorativos de fondo para que parezca una plantilla */
  .slide-deco-1 {
    position: absolute; top: -2cm; right: -2cm;
    width: 6cm; height: 6cm; background: #E9ECEF;
    border-radius: 50%; opacity: 0.5; z-index: 0;
  }
  .slide-deco-2 {
    position: absolute; bottom: 1cm; left: -1cm;
    width: 3cm; height: 8cm; background: #F8F4EC;
    border-radius: 2cm; transform: rotate(45deg); z-index: 0;
  }

  .dia-header {
    position: relative; z-index: 1;
    margin-bottom: 1cm;
  }
  .dia-header h1 {
    font-size: 36pt; font-weight: 800; color: #1C2331;
    margin-bottom: 0.1cm;
  }
  .dia-header .linea-acento {
    width: 3cm; height: 0.15cm; background: #FF9800;
    border-radius: 0.1cm;
  }

  .comidas-container {
    position: relative; z-index: 1;
    flex: 1; display: flex; gap: 0.8cm;
  }

  /* ── COLUMNAS DE COMIDA ── */
  .comida-col {
    flex: 1;
    display: flex; flex-direction: column;
  }
  
  .comida-titulo-flotante {
    background: #1C2331; color: #FFF;
    padding: 0.3cm 0.6cm;
    border-radius: 0.3cm;
    font-size: 14pt; font-weight: 700;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.5cm;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05); /* Soft shadow simulada */
  }
  .comida-titulo-flotante.tono-desayuno { background: #F39C12; }
  .comida-titulo-flotante.tono-comida   { background: #27AE60; }
  .comida-titulo-flotante.tono-cena     { background: #2980B9; }
  /* ── TARJETA LIMPIEZA (Destacada y primera) ── */
  .tarjeta-limpieza {
    background: #FFFFFF;
    border-radius: 0.3cm;
    padding: 0.5cm;
    margin-bottom: 0.4cm;
    text-align: center;
  }
  .label-seccion {
    font-size: 9pt; font-weight: 700; color: #95A5A6;
    text-transform: uppercase; letter-spacing: 1.5px;
    margin-bottom: 0.3cm; display: block;
  }
  .limpieza-tag {
    display: inline-block;
    padding: 0.25cm 0.6cm;
    font-size: 13pt; font-weight: 800;
    border-radius: 0.2cm;
  }
  .limpieza-vacio {
    color: #BDC3C7; font-size: 11pt; font-style: italic;
  }

  /* ── TARJETA RESPONSABLES ── */
  .tarjeta-responsables {
    background: #FFFFFF;
    border-radius: 0.3cm;
    padding: 0.6cm 0.5cm;
    flex: 1; /* Ocupa el resto del espacio hacia abajo */
    border: 1px solid #EEEEEE;
  }
  .responsables-grid {
    display: flex; flex-direction: column; gap: 0.25cm;
  }
  .persona-fila {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.2cm 0.3cm;
    background: #F8F9FA;
    border-radius: 0.15cm;
  }
  .persona-nombre {
    font-size: 11pt; font-weight: 600; color: #34495E;
  }
  .rama-puntito {
    font-size: 8pt; font-weight: 700; text-transform: uppercase;
    padding: 0.1cm 0.2cm; border-radius: 0.1cm;
  }

  .footer-diapositiva {
    position: absolute; bottom: 1cm; right: 2cm;
    font-size: 8pt; color: #AAB7B8;
  }
</style>
</head>
<body>

<section class="portada">
  <div class="forma-azul"></div>
  <div class="forma-verde"></div>
  <div class="portada-contenido">
    <div class="portada-titulo">Organización Scout</div>
    <div class="portada-subtitulo">Campamento Verano {{ anio }}</div>
  </div>
</section>

{% for dia in dias %}
{% set comidas_del_dia = turnos_por_dia[dia] %}
<section class="pagina-dia">
  <div class="slide-deco-1"></div>
  <div class="slide-deco-2"></div>

  <div class="dia-header">
    <h1>Día {{ dia }} de Julio</h1>
    <div class="linea-acento"></div>
  </div>

  <div class="comidas-container">
    {% for entrada in comidas_del_dia %}
    <div class="comida-col">
      
      <div class="comida-titulo-flotante tono-{{ entrada.turno | lower }}">
        <span>{{ entrada.turno }}</span>
      </div>

      {% if entrada.grupo_limpieza %}
      <div class="tarjeta-limpieza bg-light-{{ entrada.grupo_limpieza | lower | replace(' ','') }}">
        <span class="label-seccion">Grupo de Limpieza</span>
        <div class="limpieza-tag bg-{{ entrada.grupo_limpieza | lower | replace(' ','') }}">
          {{ entrada.grupo_limpieza }}
        </div>
      </div>
      {% else %}
      <div class="tarjeta-limpieza" style="border: 1px dashed #E0E0E0;">
        <span class="label-seccion">Grupo de Limpieza</span>
        <div class="limpieza-vacio">Sin asignar</div>
      </div>
      {% endif %}

      <div class="tarjeta-responsables">
        <span class="label-seccion">Sirven el comedor</span>
        <div class="responsables-grid">
          {% for persona in entrada.personas %}
          <div class="persona-fila">
            <span class="persona-nombre">{{ persona.nombre }}</span>
            <span class="rama-puntito bg-{{ persona.grupo | lower | replace(' ','') }}">{{ persona.grupo }}</span>
          </div>
          {% endfor %}
        </div>
      </div>

    </div>
    {% endfor %}
  </div>

</section>
{% endfor %}

</body>
</html>
"""

def generar_pdf(asignaciones: List[Dict], limpieza: Optional[List[Dict]] = None, anio: int = 2026) -> bytes:
    df = pd.DataFrame(asignaciones)
    limpieza_dict = _mapa_limpieza(limpieza)

    turnos_por_dia: Dict[int, list] = {}
    for dia in DIAS:
        entradas = []
        for turno in TURNOS:
            subset = df[(df["Dia"] == dia) & (df["Turno"] == turno)]
            if subset.empty:
                continue
            personas = [
                {"nombre": r["Nombre"], "grupo": r["Grupo"]}
                for _, r in subset.iterrows()
            ]
            entradas.append({
                "turno": turno,
                "personas": personas,
                "grupo_limpieza": limpieza_dict.get((dia, turno)),
            })
        if entradas:
            turnos_por_dia[dia] = entradas

    html_renderizado = Template(_PLANTILLA_HTML).render(
        dias=list(turnos_por_dia.keys()),
        turnos_por_dia=turnos_por_dia,
        colores=COLORES_GRUPOS,
        anio=anio,
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )

    pdf_bytes = weasyprint.HTML(string=html_renderizado).write_pdf()
    return pdf_bytes