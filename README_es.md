# Optimizador Matemático de Turnos Scout ⛺

Aplicación web integral diseñada para automatizar y equilibrar los cuadrantes logísticos (comedor y limpieza) del kraal en campamentos de verano. Utiliza un motor de optimización matemática basado en **Constraint Programming** para garantizar un reparto estrictamente equitativo de la carga de trabajo, respetando disponibilidades parciales, incompatibilidades horarias y normativas de seguridad de las ramas.

## 🚀 Características Principales

* **Equidad estricta:** implementa penalizaciones cuadráticas para minimizar la desviación de turnos entre responsables, asegurando que quienes asisten al campamento completo tengan una carga idéntica.
* **Seguridad garantizada:** restricción dura que impide vaciar una rama por completo durante un turno. Siempre permanece al menos un responsable al cuidado directo de los educandos de su sección.
* **Gestión de incompatibilidades:** bloqueo automático de asignaciones cruzadas con equipos de limpieza diarios y horarios de ensayos de teatro.
* **Prevención de fatiga:** prohibición estricta de "dobletes" (asignación simultánea a los turnos de comida y cena en el mismo día).
* **Interfaz y dashboards:** frontend interactivo con carga de archivos CSV mediante Drag & Drop y panel de métricas en tiempo real (plazas cubiertas, carga media, kraal activo).
* **Exportación universal:** generación automática de los cuadrantes resultantes en formatos `.xlsx` (Excel) y `.pdf`.
* **Reglas de datos reales:** el campo `Disponible` vacío significa asistencia completa; los días fuera de campamento que aparezcan en el CSV se ignoran; y `Castores`/`Rutas` se unifican internamente como `CastoresRutas`.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3, Flask, Pandas (para limpieza y estructuración de datos).
* **Motor matemático:** MiniZinc, Gecode Solver.
* **Frontend:** HTML5, CSS3, JavaScript vanilla, Tabler Icons.

## 📦 Instalación y Despliegue

1. **Clonar el repositorio:**

   ```bash
   git clone https://github.com/tu-usuario/optimizador-turnos-scout.git
   cd optimizador-turnos-scout
   ```

2. **Instalar dependencias de Python:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Instalar MiniZinc:** es imprescindible tener [MiniZinc](https://www.minizinc.org/software.html) instalado en tu sistema y accesible desde el PATH para que el solver Gecode pueda compilar el modelo `.mzn`.

   Si vas a generar PDF en Linux, `WeasyPrint` puede requerir librerías del sistema como Cairo/Pango/GTK según la distribución.

4. **Ejecución en Entorno Local (Desarrollo):**

   ```bash
   python app.py
   ```

   La aplicación estará disponible en `http://127.0.0.1:5000/`.

5. **Despliegue en Producción (Recomendado):**

   Para entornos reales, utilizo el servidor WSGI Gunicorn configurado con múltiples procesos concurrentes (workers) y un tiempo máximo de respuesta ajustado (timeout) para evitar bloqueos prolongados del motor matemático:

   ```bash
   gunicorn "app:app" --workers 4 --timeout 120 --bind 0.0.0.0:8000
   ```

   El tiempo de resolución interno del solver está limitado a 6 segundos; el timeout de Gunicorn solo controla la petición HTTP.

## 📊 Formato de Datos (CSV)

El sistema se alimenta de un archivo `.csv` con la disponibilidad del kraal. Las columnas obligatorias son:

`Nombre`, `Grupo`, `Disponible`, `TeatroComida`, `TeatroCena`

Ejemplo:

```csv
Nombre,Grupo,Disponible,TeatroComida,TeatroCena
Akela,Lobatos,15; 16; 17; 18; 19,,
Baloo,Ranger,21; 22,,
```

* **Grupo:** admite `Castores`, `Lobatos`, `Ranger`, `Pioneros` y `Rutas`. Internamente `Castores` y `Rutas` se tratan como un solo grupo de optimización.
* **Disponible:** días de asistencia separados por punto y coma (`;`). Si el campo se deja vacío, el sistema asume asistencia completa.
* **Días válidos:** el sistema solo usa los días reales de campamento (`15`, `16`, `20`, `21`, `22`, `23`, `24`, `25`, `26`, `27`, `28`, `29`); si aparecen días como `17`, `18` o `19`, se descartan.
* **TeatroComida / TeatroCena:** días concretos en los que el responsable no puede servir por ensayos o funciones.

El archivo CSV tiene además un límite de subida de 2 MB.

## 🧠 Arquitectura de Restricciones (MiniZinc)

El archivo `shift_scheduler.mzn` modela el problema a través de matrices booleanas tridimensionales (`DIAS x TURNOS x PERSONAS`). El solver busca satisfacer:

1. Exactamente 6 responsables por turno.
2. Concordancia absoluta con la matriz de días disponibles de cada persona.
3. Diferencia máxima permitida respecto a la cuota teórica individual (`margen_equidad`).

El modelo se resuelve con un timeout interno de 6 segundos para priorizar tiempos de respuesta bajos.

## 👩‍💻 Autora

**Laura Sanz Lobo**

Estudiante de Ingeniería Informática (Mención en Computación y Sistemas Inteligentes) - Universidad de Granada (UGR).