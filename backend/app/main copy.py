from ortools.sat.python import cp_model

# Create the model
model = cp_model.CpModel()

# Engineering window: 1:00am - 4:30am
# Represent time in minutes from 1:00am
# 0 = 1:00am
# 210 = 4:30am

# Job A: track inspection, 90 minutes
start_A = model.new_int_var(0, 210 - 90, "start_A")
end_A = start_A + 90

# Job B: rail grinding, 60 minutes
start_B = model.new_int_var(0, 210 - 60, "start_B")
end_B = start_B + 60

# Create intervals
job_A = model.new_interval_var(
    start_A, 90, end_A, "job_A"
)

job_B = model.new_interval_var(
    start_B, 60, end_B, "job_B"
)

# A and B use the SAME track
# Therefore they cannot happen at the same time
model.add_no_overlap([job_A, job_B])

# Create solver
solver = cp_model.CpSolver()

# Solve
status = solver.solve(model)

# Print result

if status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
    if status == cp_model.OPTIMAL:
        status = "Optimal"

    elif status == cp_model.FEASIBLE:
        status = "Feasible"
    print(status + " schedule found!")

    print("Job A:")
    print("  Start:", solver.value(start_A), "minutes after 1:00am")
    print("  End:", solver.value(end_A), "minutes after 1:00am")

    print("Job B:")
    print("  Start:", solver.value(start_B), "minutes after 1:00am")
    print("  End:", solver.value(end_B), "minutes after 1:00am")
else:
    print("No feasible schedule!")