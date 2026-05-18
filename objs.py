import datetime
from collections.abc import Iterable
from typing import Dict
from objs import *

SCORE_TYPE = {
    'c':'class_p',
    'a':'attendance',
    'h':'homework',
    'e':'exam',
    'l':'lab',
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


class Course:
    def __init__(self, name="course1") -> None:
        self.name = name
        self.students:Dict[str, Student] = {}
    
    def get_top_students(self, n, rank_by):
        key_dict = {}
        key_dict['t'] = lambda s: sum(s.calculate_score())
        
        for i, k in enumerate(SCORE_TYPE.keys()):
            key_dict[k] = lambda s: s.calculate_score()[i]
        
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