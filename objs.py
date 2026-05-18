import datetime
from collections.abc import Iterable
from typing import Dict

SCORE_TYPE = {
    'c':'class_p',
    'a':'attendance',
    'h':'homework',
    'e':'exam',
}

class Score:
    def __init__(self, s_type='c', value=0) -> None:
        self.type = s_type if s_type in SCORE_TYPE.keys() else 'c'
        self.value = value if isinstance(value, (int, float)) else 0
        self.date = datetime.date.today().strftime("%Y-%m-%d")

class Student:
    N = 1
    def __init__(self, student_id, name):
        self.id = student_id
        self.name = name
        self.N = Student.N
        Student.N += 1
        for st in SCORE_TYPE.values():
            exec(f"self.{st} = []")
    
    def add_score(self, st, sv):
        date = datetime.date.today().strftime("%Y-%m-%d")
        exec(f"self.{SCORE_TYPE[st]}.append(['{date}', sv])")
        
    def calculate_score(self):
        tmp = []
        for st in SCORE_TYPE.values():
            exec(f"tmp.append(sum(score[1] for score in self.{st}))")
        return tuple(tmp)


class LabExperiment:
    def __init__(self, exp_no, name, weight):
        self.exp_no = str(exp_no)
        self.name = name
        weight = float(weight)
        self.weight = weight / 100 if weight > 1 else weight


class LabStudent:
    N = 1
    def __init__(self, student_id, name, no=None):
        self.id = student_id
        self.name = name
        if no is None:
            self.N = LabStudent.N
            LabStudent.N += 1
        else:
            self.N = int(no)
            LabStudent.N = max(LabStudent.N, self.N + 1)
        self.lab_scores = {}

    def record_score(self, exp_no, score):
        date = datetime.date.today().strftime("%Y-%m-%d")
        self.lab_scores[str(exp_no)] = [date, float(score)]

    def calculate_lab_score(self, experiments):
        total = 0
        for exp_no, record in self.lab_scores.items():
            if exp_no in experiments:
                total += record[1] * experiments[exp_no].weight
        return total


class LabCourse:
    def __init__(self, name="course1") -> None:
        self.name = name
        self.students:Dict[str, LabStudent] = {}
        self.experiments:Dict[str, LabExperiment] = {}

    def add_student(self, student:LabStudent, with_no=False, no=0):
        if student.id in self.students:
            return 2, "Student already exists"
        self.students[student.id] = student

        if with_no:
            for s in self.students.values():
                if s.N >= no:
                    s.N += 1
            self.students[student.id].N = no
            self.students = dict(sorted(self.students.items(), key=lambda x: x[1].N))
        return 0, f"Lab student {student.name} added successfully"

    def remove_student(self, student: LabStudent):
        if student.id not in self.students:
            return 2, "Lab student not found"
        self.students.pop(student.id)
        for s in self.students.values():
            if s.N > student.N:
                s.N -= 1
        return 0, f"Lab student {student.name} removed successfully"

    def add_experiment(self, exp_no, name, weight):
        exp_no = str(exp_no)
        if exp_no in self.experiments:
            return 2, f"Lab experiment {exp_no} already exists"
        try:
            experiment = LabExperiment(exp_no, name, weight)
        except ValueError:
            return 2, "Weight must be a number"
        if experiment.weight < 0:
            return 2, "Weight must not be negative"
        self.experiments[exp_no] = experiment
        return 0, f"Lab experiment {exp_no}-{name} added successfully"

    def find_students_by_nos(self, Ns):
        if isinstance(Ns, int):
            for s in self.students.values():
                if s.N == Ns:
                    return s
        elif isinstance(Ns, Iterable):
            return_s = []
            for n in Ns:
                for s in self.students.values():
                    if s.N == n:
                        return_s.append(s)
            return return_s

    def find_students_by_names(self, names):
        if isinstance(names, str):
            for s in self.students.values():
                if s.name == names:
                    return s
        elif isinstance(names, Iterable):
            return_s = []
            for n in names:
                for s in self.students.values():
                    if s.name == n:
                        return_s.append(s)
            return return_s

    def search_students_by_name(self, name_fragment):
        matches = []
        name_fragment = name_fragment.lower()

        for student_id, student in self.students.items():
            if name_fragment in student.name.lower():
                matches.append((student.N, student_id, student.name))
        return matches

    def record_score(self, student, exp_no, score):
        exp_no = str(exp_no)
        if exp_no not in self.experiments:
            return 2, f"Lab experiment {exp_no} not found"
        try:
            score = float(score)
        except ValueError:
            return 2, "Score must be a number"
        if score < 0 or score > 100:
            return 2, "Lab score must be between 0 and 100"
        student.record_score(exp_no, score)
        return 0, f"Recorded lab experiment {exp_no} score for {student.name}"

    def record_scores(self, students, exp_no, score, exclusion=False):
        exp_no = str(exp_no)
        if exp_no not in self.experiments:
            return 2, f"Lab experiment {exp_no} not found"
        if students is None:
            students = []
        student_ids = [s.id for s in students]
        target_students = []
        if exclusion:
            for k, v in self.students.items():
                if k not in student_ids:
                    target_students.append(v)
        else:
            for k, v in self.students.items():
                if k in student_ids:
                    target_students.append(v)

        for student in target_students:
            f, msg = self.record_score(student, exp_no, score)
            if f:
                return f, msg
        return 0, f"Batch recorded {len(target_students)} students' lab experiment {exp_no}"


class Course:
    def __init__(self, name="course1") -> None:
        self.name = name
        self.students:Dict[str, Student] = {}
    
    def get_top_students(self, n, rank_by):
        key_dict = {}
        key_dict['t'] = lambda s: sum(s.calculate_score())
        
        for i, k in enumerate(SCORE_TYPE.keys()):
            key_dict[k] = lambda s, index=i: s.calculate_score()[index]
        
        if rank_by in key_dict:
            ranked_score = [(s, key_dict[rank_by](s)) for s in self.students.values()]
            if n < 0:
                return sorted(ranked_score, key=lambda x: x[1])[:abs(n)][::-1]
            else:
                return sorted(ranked_score, key=lambda x: x[1], reverse=True)[:n]
        else:
            return []
        
    def search_students_by_name(self, name_fragment):
        matches = []
        name_fragment = name_fragment.lower()
    
        for student_id, student in self.students.items():
            if name_fragment in student.name.lower():
                matches.append((student.N, student_id, student.name))
        return matches
        
    def find_students_by_nos(self, Ns):
        if isinstance(Ns, int):
            for s in self.students.values():
                if s.N == Ns:
                    return s
        elif isinstance(Ns, Iterable):
            return_s = []
            for n in Ns:
                for s in self.students.values():
                    if s.N == n:
                        return_s.append(s)
            return return_s
    
    def find_students_by_names(self, names):
        if isinstance(names, str):
            for s in self.students.values():
                if s.name == names:
                    return s
        elif isinstance(names, Iterable):
            return_s = []
            for n in names:
                for s in self.students.values():
                    if s.name == n:
                        return_s.append(s)
            return return_s
    
    def add_scores(self, students, s_type, score, exclusion=False):
        date = datetime.date.today().strftime("%Y-%m-%d")
        student_ids = [s.id for s in students]
        if exclusion:
            for k, v in self.students.items():
                if k not in student_ids:
                    v.add_score(s_type, score)
        else:
            for k, v in self.students.items():
                if k in student_ids:
                    v.add_score(s_type, score)
        
        x = len(student_ids) if not exclusion else len(self.students) - len(student_ids)
        return 0, f"Batch recorded {x} students' {SCORE_TYPE[s_type].capitalize()}"
        
class Logger:
    def __init__(self) -> None:
        self.log = []
    
    def add(self, msg):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.append(f"[{timestamp}] {msg}\n")
