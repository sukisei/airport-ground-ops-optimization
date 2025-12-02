
# Airport Ground Operations Optimization  
*A Vehicle Scheduling & Task Assignment Model using OR-Tools (CP-SAT)*

---

## ✈️ Project Overview  

This project demonstrates how to **model and solve airport ground operations** using a **Constraint Programming scheduling model** (OR-Tools CP-SAT).  
It is designed as a **portfolio project** suitable for job applications in:

- Operations Research  
- Data Science  
- Optimization Engineering  
- Algorithmic Decision Systems  
- Industrial Engineering  

The goal is to compute an **optimal schedule** of ground-handling tasks during aircraft turnaround using a limited fleet of compatible vehicles, while respecting:

- Aircraft arrival and departure windows  
- Precedence constraints between tasks  
- Non-overlapping vehicle schedules  
- Vehicle–task compatibility  
- Travel times between parking stands  

The repository contains a complete implementation and demonstration notebook with visualizations (Gantt charts).

---

## 📂 Repository Structure  

```
airport-ground-ops-optimization/
│
├── data/
│   ├── example_aircraft.csv
│   ├── example_tasks.csv
│   ├── example_vehicles.csv
│   └── parking_graph.csv
│
├── src/
│   ├── optimization/
│   │   └── ground_ops_model.py      # Full OR-Tools CP-SAT model
│   └── config/
│       └── paths.py                 # Project path utilities
│
├── 01_ground_ops_demo.ipynb         # Notebook: explanation + visualization
├── README.md                        # (this file)
└── results/
    └── plots/
        └── gantt_by_vehicle.png     # Example visualization
```

---

## 🧠 Mathematical Model  
**The COMPLETE mathematical formulation** is available inside:  

- `src/optimization/ground_ops_model.py`  
- `01_ground_ops_demo.ipynb`  

This includes:  
✔ variable definitions  
✔ reified sequencing constraints  
✔ travel times (routing-like logic)  
✔ optional interval variables  
✔ big-M linearization for task ordering  
✔ full task–vehicle assignment formulation  

Below is a summarized version.

---

## 📘 Sets  

- **A** : aircraft  
- **T(a)** : tasks for aircraft *a*  
- **V** : vehicles  
- **P** : parkings  

---

## 🔢 Parameters  

- `duration(t)` : task duration  
- `arrival(a)`, `departure(a)` : aircraft availability  
- `required_type(t)` : required vehicle type  
- `precedence(t)` : predecessor task  
- `travel_time(p1, p2)` : routing time between parkings  

---

## 🔣 Decision Variables  

- **x[v, t] ∈ {0,1}** : vehicle *v* performs task *t*  
- **start[t], end[t]** : scheduling times  
- **y[v, i, j] ∈ {0,1}** : ordering of tasks on each vehicle  

---

## 🔧 Constraints  

### ✔ Vehicle assignment  
Exactly one compatible vehicle per task.

### ✔ Non-overlapping tasks  
Using OR-Tools **optional intervals** (`NewOptionalIntervalVar`).

### ✔ Task precedence  
`start[t] ≥ end[precedence(t)]`

### ✔ Aircraft windows  
`arrival(a) ≤ start[t]`  
`end[t] ≤ departure(a]`

### ✔ Travel time constraints  
For tasks *i*, *j* on same vehicle *v*:  
```
start[j] ≥ end[i] + travel_time(i, j)     if y[i, j] = 1
start[i] ≥ end[j] + travel_time(j, i)     if y[j, i] = 1
```

### ✔ Initial movement of vehicle  
From its base position to the first task.

---

## 🎯 Objective  

**Minimize makespan**  
= finish the last task as early as possible.

This compresses the entire operation timeline and optimizes resource usage.

---

## 📈 Visualizations  

### ✓ Gantt chart by vehicle  
Shows how the schedule uses each vehicle over time.

### ✓ Gantt chart by aircraft  
Shows the entire turnaround of each aircraft, including:

- arrival  
- task sequence  
- departure  

---

## 💻 Technologies  

- Python  
- OR-Tools CP-SAT  
- Pandas  
- Matplotlib  
- Jupyter  

---

## 🌟 Why This Project Matters  

This project demonstrates my ability to:

- Understand and model a real operational problem  
- Build a complete optimization model from scratch  
- Implement complex sequencing + routing constraints  
- Produce clear visual and analytical outputs  
- Structure a clean and professional project repository  

It reflects strong skills in **Operations Research, Data Engineering, and Algorithmic Thinking**.

---

## 📬 Contact  

**Gabriel Muñoz**  
✉️ gabriel.munoz.at.work@gmail.com  
🔗 LinkedIn : (insert your link)

