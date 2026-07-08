% Modelo de asignación de turnos de Comedor - Campamento Verano 2026

% He mapeado los días reales del campamento (15 al 30 de julio) directamente al set de DIAS 
% para mantener la coherencia con las fechas y facilitar la indexación.
set of int: DIAS = 1..13;
set of int: TURNOS = 1..3; % 1: Desayuno, 2: Comida, 3: Cena
set of int: GRUPOS = 1..5; % 1: Castores, 2: Lobatos, 3: Ranger, 4: Pioneros, 5: Rutas

int: n_personas;
set of int: PERSONAS = 1..n_personas;

% --- Datos de entrada generados por mi backend ---
array[PERSONAS] of GRUPOS: grupo_persona;
array[PERSONAS, DIAS] of bool: disponible;
array[PERSONAS, DIAS] of bool: teatro_comida;
array[PERSONAS, DIAS] of bool: teatro_cena;
array[PERSONAS] of int: limite_turnos; % Cuota calculada en Python según disponibilidad

% Matrices precalculadas para simplificar el modelo matemático.
array[DIAS, TURNOS] of bool: turno_activo; 
array[DIAS, TURNOS] of 0..5: grupo_limpia; % 0 indica que ningún grupo limpia en ese turno

% --- Variables de decisión ---
% Matriz booleana 3D. comedor[d, t, p] será true si asigno a la persona 'p' al día 'd' en el turno 't'.
array[DIAS, TURNOS, PERSONAS] of var bool: comedor;

% -----------------------------------------------------------------------------
% RESTRICCIONES ESTRICTAS (Hard Constraints)
% -----------------------------------------------------------------------------

% 1. Desactivación de turnos sin servicio (ej. desayuno del día 20 o cenas canceladas).
constraint forall(d in DIAS, t in TURNOS, p in PERSONAS where not turno_activo[d, t]) (
    comedor[d, t, p] = false
);

% 2. Exactamente 6 personas sirviendo en cada turno activo.
constraint forall(d in DIAS, t in TURNOS where turno_activo[d, t]) (
    sum(p in PERSONAS)(comedor[d, t, p]) == 6
);

% 3. Si el grupo de una persona está limpiando en un turno, esa persona no sirve en el comedor.
constraint forall(d in DIAS, t in TURNOS, p in PERSONAS where turno_activo[d, t]) (
    if grupo_persona[p] == grupo_limpia[d, t] then
        comedor[d, t, p] = false
    endif
);

% 4. Disponibilidad por día.
constraint forall(d in DIAS, t in TURNOS, p in PERSONAS) (
    if not disponible[p, d] then 
        comedor[d, t, p] = false 
    endif
);

% 5. Compatibilidad con teatro.
constraint forall(d in DIAS, p in PERSONAS) (
    (teatro_comida[p, d] -> comedor[d, 2, p] = false) /\
    (teatro_cena[p, d] -> comedor[d, 3, p] = false)
);

% 6. Límite máximo de responsables del mismo grupo por turno (Hard limit: 3).
constraint forall(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t]) (
    sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p]) <= 3
);

% 7. Respeto absoluto de la cuota objetivo de turnos por responsable.
constraint forall(p in PERSONAS) (
    sum(d in DIAS, t in TURNOS)(comedor[d, t, p]) <= limite_turnos[p]
);

% -----------------------------------------------------------------------------
% FUNCIÓN OBJETIVO Y RESTRICCIONES FLEXIBLES (Soft Constraints)
% -----------------------------------------------------------------------------

% Penalizo la falta de representación. Excluyo Rutas de esta regla porque solo hay
% un responsable y no debe bloquearse su servicio por una cobertura de grupo.
var int: pen_representacion = sum(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t] /\ grupo_limpia[d, t] != g /\ g != 5) (
    bool2int(sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p]) == 0)
);

% Penalizo agrupar a más de 2 personas del mismo grupo (el límite preferido es 2).
var int: pen_grupo = sum(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t]) (
    max(0, sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p]) - 2)
);

% Penalizo los "dobletes": hacer comida y cena el mismo día resulta agotador.
var int: pen_doblete = sum(d in DIAS, p in PERSONAS) (
    bool2int(comedor[d, 2, p] /\ comedor[d, 3, p])
);

% El objetivo es minimizar la puntuación de penalización para obtener el horario más equilibrado.
solve minimize (pen_representacion * 50) + (pen_grupo * 10) + pen_doblete;
