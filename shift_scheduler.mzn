% Modelo de asignación de turnos de Comedor - Campamento Verano 2026

% He mapeado los días reales del campamento (15 al 30 de julio) directamente al set de DIAS 
set of int: DIAS = 1..13;
set of int: TURNOS = 1..3; % 1: Desayuno, 2: Comida, 3: Cena
set of int: GRUPOS = 1..4; % 1: Castores/Rutas, 2: Lobatos, 3: Ranger, 4: Pioneros

int: n_personas;
set of int: PERSONAS = 1..n_personas;

% --- Datos de entrada generados el backend ---
array[PERSONAS] of GRUPOS: grupo_persona;
array[PERSONAS, DIAS] of bool: disponible;
array[PERSONAS, DIAS] of bool: teatro_comida;
array[PERSONAS, DIAS] of bool: teatro_cena;
array[PERSONAS] of int: limite_turnos;
array[PERSONAS] of int: cuota_ideal;
array[PERSONAS] of bool: disponible_siempre;

% Matrices precalculadas para simplificar el modelo matemático.
array[DIAS, TURNOS] of bool: turno_activo; 
array[DIAS, TURNOS] of 0..4: grupo_limpia; % 0 indica que ningún grupo limpia en ese turno

% Presencia real de cada rama en el campamento cada día.
array[DIAS, GRUPOS] of int: presencia_grupo;

% --- Variables de decisión ---
% Matriz booleana 3D. comedor[d, t, p] será true si asigno a la persona 'p' al día 'd' en el turno 't'.
array[DIAS, TURNOS, PERSONAS] of var bool: comedor;

int: margen_equidad;

% -----------------------------------------------------------------------------
% RESTRICCIONES ESTRICTAS (Hard Constraints)
% -----------------------------------------------------------------------------

% 1. Desactivación de turnos sin servicio.
constraint forall(d in DIAS, t in TURNOS, p in PERSONAS where not turno_activo[d, t]) (
    comedor[d, t, p] = false
);

% 2. Exactamente 6 personas sirviendo en cada turno.
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

% 6. Límite máximo de responsables del mismo grupo por turno: nunca puedo
% vaciar una rama entera de comedor, siempre debe quedar al menos 1 persona
% de esa rama con los niños.
constraint forall(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t]) (
    sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p])
        <= max(0, presencia_grupo[d, g] - 1)
);

% 7. Respeto absoluto de la cuota objetivo de turnos por responsable.
constraint forall(p in PERSONAS) (
    sum(d in DIAS, t in TURNOS)(comedor[d, t, p]) <= limite_turnos[p]
);

% 8. Nadie puede estar asignado a la comida (turno 2) y a la cena (turno 3) en el mismo día.
constraint forall(d in DIAS, p in PERSONAS) (
    not (comedor[d, 2, p] /\ comedor[d, 3, p])
);

% 9. 
constraint forall(p in PERSONAS where disponible_siempre[p]) (
    abs(sum(d in DIAS, t in TURNOS)(bool2int(comedor[d, t, p])) - cuota_ideal[p]) <= margen_equidad
);

% -----------------------------------------------------------------------------
% FUNCIÓN OBJETIVO Y RESTRICCIONES FLEXIBLES (Soft Constraints)
% -----------------------------------------------------------------------------

% Penalizo la falta de representación. Intento asegurar que haya al menos un responsable
% por grupo sirviendo (siempre que su grupo no esté limpiando).
var int: pen_representacion = sum(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t] /\ grupo_limpia[d, t] != g) (
    bool2int(sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p]) == 0)
);

% Penalizo agrupar a más de 2 personas del mismo grupo (el límite preferido es 2).
var int: pen_grupo = sum(d in DIAS, t in TURNOS, g in GRUPOS where turno_activo[d, t]) (
    max(0, sum(p in PERSONAS where grupo_persona[p] == g)(comedor[d, t, p]) - 2)
);

% Calculo la diferencia entre los turnos asignados y mi cuota ideal.
% Al elevar esta diferencia al cuadrado (pow), genero una penalización de curva 
% tipo exponencial: desviarme por 1 turno apenas suma coste, pero desviarme 
% por 3 o 4 turnos dispara la penalización, forzando al solver a repartir 
% la carga de forma mucho más justa y uniforme entre todo el kraal.
var int: pen_equidad = sum(p in PERSONAS) (
    pow(
        sum(d in DIAS, t in TURNOS)(bool2int(comedor[d, t, p])) - cuota_ideal[p], 
        2
    )
);

% El objetivo es minimizar la puntuación total. Le doy el mayor peso (por ejemplo, 100) 
% a mi nueva penalización de equidad para que el solver priorice el reparto justo por encima de todo.
solve minimize (pen_equidad * 100) + (pen_representacion * 50) + (pen_grupo * 10);
