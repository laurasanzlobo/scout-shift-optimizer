# Scout Shift Mathematical Optimizer ⛺

A comprehensive web application designed to automate and balance logistics schedules (dining hall and cleaning duties) for scout staff during summer camps. It uses a mathematical optimization engine based on **Constraint Programming** to ensure a strictly equitable workload distribution, fully respecting partial availability, schedule incompatibilities, and branch safety protocols.

## 🚀 Key Features

* **Strict equity:** implements quadratic penalties to minimize shift deviations among staff members, ensuring those attending the full camp carry an identical workload.
* **Guaranteed safety:** hard constraint preventing a specific scout branch from being completely emptied during a shift. At least one leader always remains in direct care of their section's youth.
* **Incompatibility management:** automatic blocking of cross-assignments involving daily cleaning teams and theater rehearsal schedules.
* **Fatigue prevention:** strict prohibition of double shifts (simultaneous assignment to both lunch and dinner shifts on the same day).
* **Interface & dashboards:** interactive frontend featuring Drag & Drop CSV upload and a real-time metrics dashboard (filled slots, average workload, active staff).
* **Universal export:** automatic generation of final schedules in `.xlsx` (Excel) and `.pdf` formats.
* **Real data rules:** an empty `Disponible` field means full attendance; out-of-camp days written in the CSV are ignored; and `Castores`/`Rutas` are merged internally as `CastoresRutas`.

## 🛠️ Tech Stack

* **Backend:** Python 3, Flask, Pandas (for data cleaning and structuring).
* **Mathematical engine:** MiniZinc, Gecode Solver.
* **Frontend:** HTML5, CSS3, vanilla JavaScript, Tabler Icons.

## 📦 Installation & Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/optimizador-turnos-scout.git
   cd optimizador-turnos-scout
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install MiniZinc:** you must have [MiniZinc](https://www.minizinc.org/software.html) installed on your system and accessible from your PATH for the Gecode solver to successfully compile the `.mzn` model.

   On Linux, PDF generation through `WeasyPrint` may require system libraries such as Cairo/Pango/GTK depending on the distribution.

4. **Local Development Execution:**

   ```bash
   python app.py
   ```

   The application will be accessible at `http://127.0.0.1:5000/`.

5. **Production Deployment (Recommended):**

   For real-world environments, I deploy the application using the Gunicorn WSGI server, configured with multiple workers and a strict timeout to prevent the mathematical solver from hanging indefinitely:

   ```bash
   gunicorn "app:app" --workers 4 --timeout 120 --bind 0.0.0.0:8000
   ```

   The solver itself is capped internally at 6 seconds; the Gunicorn timeout only governs the HTTP request.

## 📊 Data Format (CSV)

The system is fed by a `.csv` file containing the staff's availability. The required columns are:

`Nombre`, `Grupo`, `Disponible`, `TeatroComida`, `TeatroCena`

Example:

```csv
Nombre,Grupo,Disponible,TeatroComida,TeatroCena
Akela,Lobatos,15; 16; 17; 18; 19,,
Baloo,Ranger,21; 22,,
```

* **Grupo:** supports `Castores`, `Lobatos`, `Ranger`, `Pioneros` and `Rutas`. Internally, `Castores` and `Rutas` are treated as a single optimization group.
* **Disponible:** attendance days separated by semicolons (`;`). If left completely empty, the system defaults to full camp attendance.
* **Valid days:** the system only uses the real camp days (`15`, `16`, `20`, `21`, `22`, `23`, `24`, `25`, `26`, `27`, `28`, `29`); if days like `17`, `18`, or `19` appear, they are ignored.
* **TeatroComida / TeatroCena:** specific days where the leader is unavailable due to rehearsals or performances.

The CSV upload is also limited to 2 MB.

## 🧠 Constraint Architecture (MiniZinc)

The `shift_scheduler.mzn` file models the problem through three-dimensional boolean arrays (`DIAS x TURNOS x PERSONAS`). The solver attempts to satisfy:

1. Exactly 6 leaders per shift.
2. Absolute compliance with each person's available days matrix.
3. Maximum allowed difference regarding the individual theoretical quota (`margen_equidad`).

The model is solved with an internal 6-second timeout to keep response times low.

## 👩‍💻 Author

**Laura Sanz Lobo**

Computer Engineering Student (Computing and Intelligent Systems Track) - University of Granada (UGR).