import multiprocessing
from ortools.sat.python import cp_model

COUNTS = 10
MIN_VAL = 2
MAX_VAL = 4

class Slot:
    def __init__(self,model):
        self.model = model
        self.start = model.NewIntVar(-1,COUNTS-1,name="")#inclusive
        self.duration = model.NewIntVar(0,COUNTS,"")
        self.end = model.NewIntVar(-1,COUNTS,name="") #exclusive
        self.is_used = model.NewBoolVar("")
        self.is_used_table = []
        for t in range(0,COUNTS):
            self.is_used_table.append(model.NewBoolVar(""))

        #add constraints
        #only want to asign a working duration if a shift start is set
        model.Add((self.start==-1)).OnlyEnforceIf(self.is_used.Not())
        model.Add((self.start!=-1)).OnlyEnforceIf(self.is_used)
        model.Add((self.duration==0)).OnlyEnforceIf(self.is_used.Not())
        model.Add((self.duration>0)).OnlyEnforceIf(self.is_used)
        model.Add((self.start<self.end)).OnlyEnforceIf(self.is_used)
        model.Add(self.end == self.start+self.duration)

        #nothing before start
        for t in range(0,COUNTS):
            if t > 0:
                model.Add(self.start==t).OnlyEnforceIf([k.Not() for k in self.is_used_table[:t]]+[self.is_used_table[t]])
        #nothing after end
        for t in range(1,COUNTS):
            model.Add(self.end==t).OnlyEnforceIf([k.Not() for k in self.is_used_table[t:]]+[self.is_used_table[t-1]])

        #if we work at the shift there has to be at least one slot, otherwise it could let working_table be only zeroes 0
        model.Add(sum(self.is_used_table)>=self.is_used)
        #number of slots marked as 1 and duration has to match
        model.Add(sum(self.is_used_table)==self.duration)

        #fix working table to start and End
        for t in range(0,COUNTS):
            inersect = self.is_used_table[t]#
            model.Add(t >= self.start).OnlyEnforceIf([inersect,self.is_used])
            model.Add(t < self.end).OnlyEnforceIf([inersect,self.is_used])


class Handler:

    def __init__(self,model,list_count):
        self.model=model
        self.is_used_table = [model.NewBoolVar(name="") for _ in range(COUNTS)]
        self.used_changes = []
        self.possible_slots = []

        for s in range(list_count):
            self.possible_slots.append(Slot(model))
            """
            Shifts are sorted from the first to the last one. Obsolete shifts are at the end
            """
            if s > 0:
                model.Add(self.possible_slots[s].is_used==0).OnlyEnforceIf(self.possible_slots[s-1].is_used.Not())
                #sort shifts and intervals shouldn't overlap but only if they are working at that shift
                #> because otherwise shifts
                model.Add(self.possible_slots[s].start >
                          self.possible_slots[s-1].end).OnlyEnforceIf([self.possible_slots[s-1].is_used,self.possible_slots[s].is_used])
                model.Add(self.possible_slots[s].start >
                          self.possible_slots[s-1].start).OnlyEnforceIf([self.possible_slots[s-1].is_used,self.possible_slots[s].is_used])

        for t in range(0,COUNTS):
            #Combine slots with is_used_table
            overlap_list = []
            for s in self.possible_slots:
                overlap_list.append(s.is_used_table[t])

            #We just want exactly one overlap or none
            model.Add(sum(overlap_list) == self.is_used_table[t])


    def __count_used_changes(self):
        if len(self.used_changes) != 0:
            raise ValueError("count_used_changes can only be called once")
        rt = self.is_used_table
        for i,r in enumerate(rt):
            if i > 0:
                is_diff = self.model.NewBoolVar("")
                self.model.Add(r!=rt[i-1]).OnlyEnforceIf(is_diff)
                self.model.Add(r==rt[i-1]).OnlyEnforceIf(is_diff.Not())
                self.used_changes.append(is_diff)

    def get_used_changes(self):
        if len(self.used_changes) == 0:
            self.__count_used_changes()
        return self.used_changes

def refine_x_days(n_d,force_solution=False,print_to_file=None):
    model = cp_model.CpModel()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = max(1,multiprocessing.cpu_count()-1)
    handlers = []
    for d in range(n_d):
        wd = Handler(model,2)#,lambda t: has_role_restriction(d,t))
        handlers.append(wd)

    total_changes = []
    for wd in handlers:
        total_changes.extend(wd.get_used_changes())
        #dont allow ones at the start/end -> handler adds at least a cost of 2
        model.Add(wd.is_used_table[0] == 0)
        model.Add(wd.is_used_table[-1] == 0)
        model.AddSumConstraint([ws.duration for ws in wd.possible_slots],MIN_VAL,MAX_VAL)

    model.Minimize(sum([]))#basically 0
    if print_to_file != None:
        with open(print_to_file+"_before.txt","a") as f:
            f.write("######################################## \n")
            f.write(str(model.Proto()))
            f.write("######################################## \n")
    result = solver.Solve(model)
    assert result == cp_model.OPTIMAL
    model._CpModel__model.solution_hint.Clear()
    for i,field in enumerate(model._CpModel__model.variables):
        model._CpModel__model.solution_hint.vars.extend([i])
        model._CpModel__model.solution_hint.values.extend([solver._CpSolver__solution.solution[i]])

    if force_solution:
        model.Add(sum(total_changes) == n_d*2)
    model.Minimize(sum(total_changes))
    if print_to_file != None:
        with open(print_to_file+"_after.txt","a") as f:
            f.write("######################################## \n")
            f.write(str(model.Proto()))
            f.write("######################################## \n")
    result = solver.Solve(model)
    assert result == cp_model.FEASIBLE or result == cp_model.OPTIMAL
    if result == cp_model.OPTIMAL:
        assert solver.Value(sum(total_changes)) == n_d*2
    else:
        assert solver.Value(sum(total_changes)) <= n_d*2*2

#force right solution
def test_f_one():
    refine_x_days(1,True)
def test_f_two():
    refine_x_days(2,True)
def test_f_three():
    refine_x_days(3,True)
def test_f_four():
    refine_x_days(4,True)
def test_f_five():
    refine_x_days(5,True)
def test_f_six():
    refine_x_days(6,True)
def test_f_seven():
    refine_x_days(7,True)

FILE = "protos"
#don'tforce right solution
def test_one():
    refine_x_days(1,print_to_file=FILE)
def test_two():
    refine_x_days(2,print_to_file=FILE)
def test_three():
    refine_x_days(3,print_to_file=FILE)
def test_four():
    refine_x_days(4,print_to_file=FILE)
def test_five():
    refine_x_days(5,print_to_file=FILE)
def test_six():
    refine_x_days(6,print_to_file=FILE)
def test_seven():
    refine_x_days(7,print_to_file=FILE)
