from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd


# --- Data structures ---------------------------------------------------------


@dataclass
class Aircraft:
    """Simple container for aircraft data."""
    aircraft_id: str
    parking: str
    arrival_time: int
    departure_time: int


@dataclass
class Task:
    """Simple container for task data."""
    task_id: str
    aircraft_id: str
    duration: int
    precedence: str  # "-" if no predecessor, else task_id of predecessor
    required_vehicle_type: str


@dataclass
class Vehicle:
    """Simple container for vehicle data."""
    vehicle_id: str
    type: str
    initial_position: str


# --- Core optimization model -------------------------------------------------


class GroundOpsModel:
    """
    Ground operations scheduling model.

    This class is responsible for:
    - storing the instance data (aircraft, tasks, vehicles, parking graph)
    - building the optimization model (build_model)
    - solving the model (solve)
    - extracting results in a convenient format (extract_solution)
    """

    def __init__(
        self,
        aircraft: Dict[str, Aircraft],
        tasks: List[Task],
        vehicles: Dict[str, Vehicle],
        parking_travel_time: Dict[tuple, int],
    ) -> None:
        self.aircraft = aircraft
        self.tasks = tasks
        self.vehicles = vehicles
        self.parking_travel_time = parking_travel_time

        # Solver-related attributes (to be initialized in build_model)
        self.model = None          # e.g., OR-Tools CP-SAT model or MILP solver
        self.variables = {}        # dict to store decision variables
        self.solution = None       # raw solver solution object
        self.solved = False

    # -------------------------------------------------------------------------
    # Factory method to load data from CSV files
    # -------------------------------------------------------------------------

    @classmethod
    def from_csv_folder(cls, folder: str | Path) -> "GroundOpsModel":
        """
        Load instance data from CSV files located in a folder.

        Expected files:
        - example_aircraft.csv
        - example_tasks.csv
        - example_vehicles.csv
        - parking_graph.csv
        """
        folder = Path(folder)

        aircraft_df = pd.read_csv(folder / "example_aircraft.csv")
        tasks_df = pd.read_csv(folder / "example_tasks.csv")
        vehicles_df = pd.read_csv(folder / "example_vehicles.csv")
        graph_df = pd.read_csv(folder / "parking_graph.csv")

        aircraft = {
            row["aircraft_id"]: Aircraft(
                aircraft_id=row["aircraft_id"],
                parking=row["parking"],
                arrival_time=int(row["arrival_time"]),
                departure_time=int(row["departure_time"]),
            )
            for _, row in aircraft_df.iterrows()
        }

        tasks: List[Task] = [
            Task(
                task_id=row["task_id"],
                aircraft_id=row["aircraft_id"],
                duration=int(row["duration"]),
                precedence=str(row["precedence"]),
                required_vehicle_type=row["required_vehicle_type"],
            )
            for _, row in tasks_df.iterrows()
        ]

        vehicles = {
            row["vehicle_id"]: Vehicle(
                vehicle_id=row["vehicle_id"],
                type=row["type"],
                initial_position=row["initial_position"],
            )
            for _, row in vehicles_df.iterrows()
        }

        parking_travel_time: Dict[tuple, int] = {
            (row["from"], row["to"]): int(row["travel_time"])
            for _, row in graph_df.iterrows()
        }

        return cls(
            aircraft=aircraft,
            tasks=tasks,
            vehicles=vehicles,
            parking_travel_time=parking_travel_time,
        )

    # -------------------------------------------------------------------------
    # Model building / solving / extraction
    # -------------------------------------------------------------------------

    def build_model(self) -> None:
        """
        Version V2 du modèle :

        - Chaque tâche est assignée à exactement un véhicule compatible
        - Un véhicule ne peut faire qu'une tâche à la fois
        - Ajout des temps de trajet entre parkings :
          start_j >= end_i + travel_time(parking_i, parking_j)
        - Fenêtres de temps avion (arrivée / départ)
        - Précédence entre tâches d'un même avion
        - Objectif : minimiser le makespan (fin de la dernière tâche)
        """
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()

        vehicles_list = list(self.vehicles.values())
        n_tasks = len(self.tasks)

        # --- Horizon de temps maximum ---
        max_departure = max(ac.departure_time for ac in self.aircraft.values())
        max_travel = max(self.parking_travel_time.values()) if self.parking_travel_time else 0
        horizon = max_departure + max_travel

        # --- Variables start / end pour chaque tâche ---
        start_vars: dict[int, cp_model.IntVar] = {}
        end_vars: dict[int, cp_model.IntVar] = {}
        task_location: dict[int, str] = {}

        for ti, task in enumerate(self.tasks):
            start = model.NewIntVar(0, horizon, f"start_{task.aircraft_id}_{task.task_id}_{ti}")
            end = model.NewIntVar(0, horizon, f"end_{task.aircraft_id}_{task.task_id}_{ti}")
            start_vars[ti] = start
            end_vars[ti] = end

            # parking de la tâche = parking de l'avion
            task_location[ti] = self.aircraft[task.aircraft_id].parking

        # --- Fenêtres de temps avion : arrivée / départ ---
        for ti, task in enumerate(self.tasks):
            ac = self.aircraft[task.aircraft_id]
            model.Add(start_vars[ti] >= ac.arrival_time)
            model.Add(end_vars[ti] <= ac.departure_time)

        # --- Variables d'assignation & intervalles optionnels ---
        assign_vars: dict[tuple[str, int], cp_model.BoolVar] = {}
        interval_vars: dict[tuple[str, int], cp_model.IntervalVar] = {}

        for v in vehicles_list:
            for ti, task in enumerate(self.tasks):
                if v.type != task.required_vehicle_type:
                    continue

                assign = model.NewBoolVar(f"assign_{v.vehicle_id}_{task.aircraft_id}_{task.task_id}_{ti}")
                interval = model.NewOptionalIntervalVar(
                    start_vars[ti],
                    task.duration,
                    end_vars[ti],
                    assign,
                    f"interval_{v.vehicle_id}_{task.aircraft_id}_{task.task_id}_{ti}",
                )
                assign_vars[(v.vehicle_id, ti)] = assign
                interval_vars[(v.vehicle_id, ti)] = interval

        # --- Chaque tâche doit être affectée à exactement 1 véhicule compatible ---
        for ti, task in enumerate(self.tasks):
            compatible_assigns = [
                assign_vars[(v.vehicle_id, ti)]
                for v in vehicles_list
                if (v.vehicle_id, ti) in assign_vars
            ]
            if not compatible_assigns:
                raise ValueError(f"No compatible vehicle for task {task.task_id} on aircraft {task.aircraft_id}.")
            model.Add(sum(compatible_assigns) == 1)

        # --- Variables d'ordre et temps de trajet sur chaque véhicule ---
        seq_vars: dict[tuple[str, int, int], cp_model.BoolVar] = {}

        for v in vehicles_list:
            vid = v.vehicle_id

            # Toutes les tâches que ce véhicule PEUT faire
            task_indices_for_v = [ti for ti in range(n_tasks) if (vid, ti) in assign_vars]

            for i in range(len(task_indices_for_v)):
                ti = task_indices_for_v[i]
                for j in range(i + 1, len(task_indices_for_v)):
                    tj = task_indices_for_v[j]

                    # y_ij = 1 si ti avant tj sur ce véhicule
                    y_ij = model.NewBoolVar(f"order_{vid}_{ti}_before_{tj}")
                    y_ji = model.NewBoolVar(f"order_{vid}_{tj}_before_{ti}")
                    seq_vars[(vid, ti, tj)] = y_ij
                    seq_vars[(vid, tj, ti)] = y_ji

                    a = assign_vars[(vid, ti)]
                    b = assign_vars[(vid, tj)]

                    # y <= assign
                    model.Add(y_ij <= a)
                    model.Add(y_ij <= b)
                    model.Add(y_ji <= a)
                    model.Add(y_ji <= b)

                    # Si les deux tâches sont assignées à v -> exactement un ordre
                    # a + b - 1 <= y_ij + y_ji <= 1
                    model.Add(y_ij + y_ji <= 1)
                    model.Add(a + b - 1 <= y_ij + y_ji)

                    # Temps de trajet entre parkings
                    loc_i = task_location[ti]
                    loc_j = task_location[tj]
                    travel_ij = self.parking_travel_time.get((loc_i, loc_j), 0)
                    travel_ji = self.parking_travel_time.get((loc_j, loc_i), 0)

                    # ti avant tj
                    model.Add(
                        start_vars[tj] >= end_vars[ti] + travel_ij - horizon * (1 - y_ij)
                    )
                    # tj avant ti
                    model.Add(
                        start_vars[ti] >= end_vars[tj] + travel_ji - horizon * (1 - y_ji)
                    )

            # Départ depuis la position initiale du véhicule vers sa première tâche
            for ti in task_indices_for_v:
                loc_i = task_location[ti]
                travel0 = self.parking_travel_time.get((v.initial_position, loc_i), 0)
                assign = assign_vars[(vid, ti)]
                model.Add(start_vars[ti] >= travel0 - horizon * (1 - assign))

        # --- Contraintes de précédence entre tâches d'un même avion ---
        index_by_aircraft_task = {
            (task.aircraft_id, task.task_id): ti
            for ti, task in enumerate(self.tasks)
        }

        for ti, task in enumerate(self.tasks):
            if task.precedence not in ("-", "", None):
                pred_key = (task.aircraft_id, task.precedence)
                if pred_key not in index_by_aircraft_task:
                    raise ValueError(
                        f"Predecessor {task.precedence} for task {task.task_id} on aircraft {task.aircraft_id} not found."
                    )
                pred_index = index_by_aircraft_task[pred_key]
                model.Add(start_vars[ti] >= end_vars[pred_index])

        # --- Makespan ---
        makespan = model.NewIntVar(0, horizon, "makespan")
        for ti in range(n_tasks):
            model.Add(makespan >= end_vars[ti])
        model.Minimize(makespan)

        # Stockage pour extraction
        self.model = model
        self._cp_data = {
            "start_vars": start_vars,
            "end_vars": end_vars,
            "assign_vars": assign_vars,
            "makespan": makespan,
            "vehicles_list": vehicles_list,
        }
        self.solved = False



    def solve(self, time_limit: int | None = None) -> None:
        """
        Solve the optimization model with OR-Tools CP-SAT.
        """
        if self.model is None:
            raise RuntimeError("Model has not been built yet. Call build_model() first.")

        from ortools.sat.python import cp_model

        solver = cp_model.CpSolver()
        if time_limit is not None:
            solver.parameters.max_time_in_seconds = float(time_limit)

        status = solver.Solve(self.model)
        self.solution = solver
        self.solved = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        self._status = status

    def extract_solution(self):
        """
        Extract a human-readable solution from the solver.

        Returns
        -------
        list[dict]
            List of dict describing each (aircraft, task, vehicle, start, end).
        """
        if not self.solved:
            raise RuntimeError("Model has not been solved yet. Call solve() first.")

        solver = self.solution
        start_vars = self._cp_data["start_vars"]
        end_vars = self._cp_data["end_vars"]
        assign_vars = self._cp_data["assign_vars"]
        vehicles_list = self._cp_data["vehicles_list"]

        results = []

        for ti, task in enumerate(self.tasks):
            start = solver.Value(start_vars[ti])
            end = solver.Value(end_vars[ti])

            # retrouver le véhicule choisi (assign == 1)
            chosen_vehicle_id = None
            for v in vehicles_list:
                key = (v.vehicle_id, ti)
                if key in assign_vars and solver.Value(assign_vars[key]) == 1:
                    chosen_vehicle_id = v.vehicle_id
                    break

            results.append(
                {
                    "aircraft_id": task.aircraft_id,
                    "task_id": task.task_id,
                    "vehicle_id": chosen_vehicle_id,
                    "start": start,
                    "end": end,
                }
            )

        # trier par avion puis heure de début
        results.sort(key=lambda r: (r["aircraft_id"], r["start"]))
        return results
