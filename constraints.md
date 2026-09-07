# Mathematical Formulation: CP-SAT Rail Track Allocation & Maintenance Scheduling Engine

## 1. Problem Overview & Discrete Horizon

The problem is formulated as a discrete-time Constraint Satisfaction and Optimization Problem (COP) using interval variables over a finite planning horizon:

$$\mathcal{T} = \{0, 1, 2, \dots, T_{\max}\}$$

where each discrete time step represents 1 minute. For a standard engineering window of 01:15 to 04:45, $T_{\max} = 210$ minutes.

---

## 2. Sets and Indices

* $j, k \in \mathcal{J}$: Set of maintenance requests / work orders submitted for execution.
* $s \in \mathcal{S}$: Set of discrete track sectors/blocks across the rail network.
* $z \in \mathcal{Z}$: Set of traction power feeding sections, where each zone spans a subset of physical sectors: $\mathcal{S}_z \subset \mathcal{S}$.
* $r \in \mathcal{R}$: Set of shared cumulative operational resources (e.g., Track Protection Officers, heavy tamping machines, locomotives).
* $v \in \mathcal{V}$: Set of engineering vehicles traversing between maintenance bases/depots and active work zones.
* $b \in \mathcal{B}$: Set of scheduled blackout / track closure restrictions (e.g., maintenance freezes, third-party works).

---

## 3. Parameters

### Work Order Attributes
* $D_j \in \mathbb{N}^+$: Required net execution duration for job $j$ (in minutes).
* $\mathcal{S}_j \subset \mathcal{S}$: Primary physical track sector(s) occupied by job $j$.
* $\text{Buf}(j) \subset \mathcal{S}$: Safety buffer sectors required adjacent to the work area.
* $\Omega_j = \mathcal{S}_j \cup \text{Buf}(j)$: Total spatial footprint (work site + exclusion perimeter).
* $P_j \in \{\text{OFF}, \text{ON}, \text{NONE}\}$: Required traction power status (in data schemas, legacy `"ANY"` values are normalized to `"NONE"`):
  * $\text{OFF}$: Third-rail power must be de-energized and grounded for personnel track-level access.
  * $\text{ON}$: Live third-rail power required (e.g., dynamic train testing, signaling commissioning).
  * $\text{NONE}$: Task is neutral to electrical status.
* $W_j \in [1, 10]$: Asset failure risk / criticality score assigned by predictive condition monitoring (e.g., PDSS).
* $c_{j,r} \in \mathbb{N}_0$: Quantity of resource $r$ consumed by job $j$.
* $\text{Pred}(j) \subset \mathcal{J}$: Set of immediate prerequisite work orders required before job $j$ can commence.
* $\Delta_{p,j} \in \mathbb{N}_0$: Mandatory clearance/handover buffer between prerequisite $p$ and dependent job $j$.

### Network & Resource Constraints
* $C_r \in \mathbb{N}^+$: Maximum available capacity of cumulative resource $r$ during the shift.
* $T_{\text{buffer}} \in \mathbb{N}^+$: Mandatory system clearance buffer prior to morning sweep train departure (e.g., 20 minutes).
* $\tau_{v, s} \in \mathbb{N}^+$: Travel duration for vehicle $v$ to clear transit sector $s$.
* $\text{Blackout}_b = (\mathcal{S}_b, start_b, end_b)$: Restricted interval $[start_b, end_b]$ barring work and transit over sectors $\mathcal{S}_b \subset \mathcal{S}$.

---

## 4. Decision Variables

* $y_j \in \{0, 1\}$: Binary task acceptance variable ($y_j = 1$ if job $j$ is scheduled tonight; $y_j = 0$ if deferred).
* $start_j \in [0, T_{\max} - D_j]$: Integer variable denoting the start time of job $j$.
* $end_j \in [D_j, T_{\max}]$: Integer variable denoting the completion time of job $j$.
* $I_j$: Optional interval variable defined over $[start_j, end_j, D_j]$ and guarded by boolean status $y_j$:
  $$I_j = \text{IntervalVar}(start_j, D_j, end_j) \quad \text{active if } y_j = 1$$
* $I_{v, s}$: Transit interval variable denoting the occupation of transit sector $s$ by vehicle $v$:
  $$I_{v, s} = \text{IntervalVar}(start_{v,s}, \tau_{v,s}, end_{v,s})$$

---

## 5. Hard Constraints

### A. Temporal Validity & Morning Sweep Protection
Every scheduled task must fit entirely within the designated engineering window, preserving the final revenue protection buffer:

$$start_j + D_j = end_j \quad \forall j \in \mathcal{J}$$

$$end_j \le T_{\max} - T_{\text{buffer}} \quad \forall j \in \mathcal{J} \quad \text{where } y_j = 1$$

### B. Spatial Footprint & Safety Buffer Exclusion
No two maintenance tasks may concurrently occupy overlapping physical sectors or breach each other's safety buffer zones:

$$\forall s \in \mathcal{S}: \quad \text{NoOverlap}(\{I_j \mid s \in \Omega_j\})$$

Equivalently expressed as disjunctions for any pair $j, k \in \mathcal{J}$ where $\Omega_j \cap \Omega_k \neq \emptyset$:

$$(y_j = 1 \land y_k = 1) \implies (end_j \le start_k) \lor (end_k \le start_j)$$

### C. Traction Power Sector Compatibility
Let $\mathcal{J}_z = \{j \in \mathcal{J} \mid \Omega_j \cap \mathcal{S}_z \neq \emptyset\}$ be the set of tasks impacting power feeding section $z$. Jobs requiring opposing power conditions cannot overlap temporally in the same power zone:

$$\forall z \in \mathcal{Z}, \quad \forall j, k \in \mathcal{J}_z \quad \text{where } P_j = \text{OFF} \land P_k = \text{ON}:$$

$$(y_j = 1 \land y_k = 1) \implies (end_j \le start_k) \lor (end_k \le start_j)$$

### D. Depot Transit Corridor Interlocking
Engineering trains and maintenance vehicles moving from depots to work zones dynamically block the track sectors they traverse. Transit intervals and stationary work intervals in sector $s$ are mutually exclusive:

$$\forall s \in \mathcal{S}: \quad \text{NoOverlap}(\{I_{v, s} \mid v \in \mathcal{V}\} \cup \{I_j \mid s \in \Omega_j\})$$

### E. Cumulative Manpower & Equipment Capacities
At any minute $t \in \mathcal{T}$, total concurrent utilization of resource $r$ across all active jobs cannot exceed available fleet/crew capacity:

$$\forall r \in \mathcal{R}: \quad \text{Cumulative}\Big(\{I_j \mid c_{j,r} > 0\}, \{c_{j,r}\}, C_r\Big)$$

Which enforces:

$$\sum_{j \in \mathcal{J} : y_j = 1} c_{j,r} \cdot \mathbb{I}(start_j \le t < end_j) \le C_r \quad \forall r \in \mathcal{R}, \quad \forall t \in \mathcal{T}$$

### F. Work Order Precedence & Dependencies
If job $j$ is dependent on prerequisite task $p \in \text{Pred}(j)$:

1. **Execution Implication:** A dependent task cannot proceed if its prerequisite is deferred:
   $$y_j \le y_p \quad \forall p \in \text{Pred}(j)$$

2. **Temporal Precedence:** Task $j$ cannot start until prerequisite $p$ clears its buffer margin:
   $$(y_j = 1 \land y_p = 1) \implies start_j \ge end_p + \Delta_{p,j} \quad \forall p \in \text{Pred}(j)$$

### G. Blackout & Track Closure Exclusion
Work orders and engineering vehicle transits cannot overlap with scheduled blackout intervals in their affected sectors:

$$\forall b \in \mathcal{B}, \quad \forall s \in \mathcal{S}_b: \quad \text{NoOverlap}\Big(\{I_j \mid s \in \Omega_j\} \cup \{I_{v, s} \mid v \in \mathcal{V}\} \cup \{[start_b, end_b]\}\Big)$$

Which enforces for any active task $j$ ($y_j = 1$) where $\Omega_j \cap \mathcal{S}_b \neq \emptyset$:

$$(end_j \le start_b) \lor (start_j \ge end_b)$$

And similarly for any vehicle transit interval $I_{v,s}$ where $s \in \mathcal{S}_b$:

$$(end_{v,s} \le start_b) \lor (start_{v,s} \ge end_b)$$

---

## 6. Multi-Objective Function

The optimization maximizes high-criticality task allocation, minimizes operational delay risk (favoring early task finishes within the window), and reduces transit deadhead friction:

$$\max \quad Z = \sum_{j \in \mathcal{J}} \alpha_j \cdot y_j - \lambda_1 \sum_{j \in \mathcal{J} : y_j = 1} end_j - \lambda_2 \sum_{v \in \mathcal{V}} \sum_{s \in \mathcal{S}} \text{Duration}(I_{v,s})$$

Where:
* $\alpha_j = 1000 \cdot W_j$: High priority multiplier scaling task urgency above completion timing.
* $\lambda_1 = 1$: Schedule slack coefficient encouraging tasks to finish early, expanding the buffer before revenue service resumes.
* $\lambda_2 = 5$: Transit penalization factor to prioritize efficient depot routes and reduce network deadheading.

---

## 7. Infeasibility Resolution & Relaxation Strategy

When constraints make scheduling all work orders mathematically infeasible, the engine calculates the **Minimal Unsatisfiable Subset (MUS)**:

1. Identify the minimal set of conflicting request IDs $\mathcal{J}_{\text{conflict}} \subset \mathcal{J}$.
2. Convert hard inclusion ($y_j = 1$) into soft constraints via task-drop penalties:
   $$\min \quad \sum_{j \in \mathcal{J}} W_j \cdot (1 - y_j)$$
3. Execute alternative synthesis via Pareto relaxation:
   * **Alternative A (Temporal Sequencing):** Split jobs into sub-phases to fit non-overlapping slots.
   * **Alternative B (Spatial Re-routing):** Divert heavy rail vehicles via bidirectional crossover sidings.
   * **Alternative C (Opportunistic Deferral):** Bump the task with the lowest $W_j$ to night $N+1$, bundling it with already-scheduled shutdowns in that power zone.