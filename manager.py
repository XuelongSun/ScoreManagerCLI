import datetime
import csv
import copy
import os
import pandas as pd
from objs import Student, Course, Logger, SCORE_TYPE, LabStudent, LabCourse
import json
import warnings

class StudentManager:
    def __init__(self, class_obj=None, working_dir=None) -> None:
        Student.N = 1
        LabStudent.N = 1
        self.course = class_obj if class_obj else Course()
        self.lab_course = LabCourse(self.course.name)
        self.logger = Logger()
        self.lab_logger = Logger()
        self.working_dir = working_dir or ''
        self.undo_stack = []
        self.load_data()

    def theory_score_path(self):
        return os.path.join(self.working_dir, f"{self.course.name}_student_score.json")

    def read_file_field_schema(self):
        path = self.theory_score_path()
        if not os.path.exists(path):
            return None, path, f"Score file not found: {path}"
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        schema = data.get("field_schema")
        if not schema:
            return None, path, "field_schema not found in score file"
        return schema, path, ""

    def push_undo(self, description, scope="theory"):
        self.undo_stack.append({
            "description": description,
            "scope": scope,
            "course": copy.deepcopy(self.course),
            "lab_course": copy.deepcopy(self.lab_course),
            "logger": copy.deepcopy(self.logger),
            "lab_logger": copy.deepcopy(self.lab_logger),
            "log_length": len(self.logger.log),
            "lab_log_length": len(self.lab_logger.log),
            "working_dir": self.working_dir,
            "student_next_no": Student.N,
            "lab_student_next_no": LabStudent.N,
        })

    def discard_undo(self):
        if self.undo_stack:
            self.undo_stack.pop()

    def _restore_data(self, snapshot):
        self.course = snapshot["course"]
        self.lab_course = snapshot["lab_course"]
        self.working_dir = snapshot["working_dir"]
        Student.N = snapshot["student_next_no"]
        LabStudent.N = snapshot["lab_student_next_no"]

    def rollback_undo(self):
        if not self.undo_stack:
            return

        snapshot = self.undo_stack.pop()
        self._restore_data(snapshot)
        self.logger = snapshot["logger"]
        self.lab_logger = snapshot["lab_logger"]

    def undo(self):
        if not self.undo_stack:
            return 1, "Nothing to undo"

        snapshot = self.undo_stack.pop()
        description = snapshot["description"]
        undo_logs = [
            log for log in self.logger.log[snapshot["log_length"]:]
            if "] Undo:" in log
        ]
        lab_undo_logs = [
            log for log in self.lab_logger.log[snapshot["lab_log_length"]:]
            if "] Undo:" in log
        ]
        self._restore_data(snapshot)
        self.logger.log = snapshot["logger"].log + undo_logs
        self.lab_logger.log = snapshot["lab_logger"].log + lab_undo_logs
        if snapshot["scope"] == "lab":
            self.lab_logger.add(f"Undo: {description}")
        else:
            self.logger.add(f"Undo: {description}")
        return 0, f"Undid: {description}"
        
    def load_data(self):
        if os.path.exists(f"working_directories.json"):
            with open(f"working_directories.json", "r", encoding='utf-8') as f:
                wd_data = json.load(f)
                if not self.working_dir and self.course.name in wd_data.keys():
                    self.working_dir = wd_data[self.course.name]
        
        legacy_lab_records = []
        lab_file = os.path.join(self.working_dir, f"{self.course.name}_lab_score.json")
        if os.path.exists(self.theory_score_path()):
            with open(self.theory_score_path(), 'r', encoding='utf-8') as f:
                student_data = json.load(f)
                if "field_schema" in student_data:
                    self.course.load_field_schema(student_data["field_schema"])
                for student_id, data in student_data['students'].items():
                    student = Student(student_id, data['name'])
                    if "No." in data:
                        student.N = int(data["No."])
                        Student.N = max(Student.N, student.N + 1)
                    for s_t in self.course.all_primary_field_names():
                        student.ensure_score_field(s_t)
                        student.scores[s_t] = data.get(s_t, [])
                        setattr(student, s_t, student.scores[s_t])
                    self.add_student(student)
                    if not os.path.exists(lab_file) and data.get('lab'):
                        legacy_lab_records.append((student_id, data['name'], data.get("No.", student.N), data['lab']))
        
        if os.path.exists(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt")):
            with open(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt"), 'r', encoding='utf-8') as f:
                self.logger.log = f.readlines()

        if os.path.exists(lab_file):
            with open(lab_file, 'r', encoding='utf-8') as f:
                lab_data = json.load(f)
                for exp_no, data in lab_data.get('experiments', {}).items():
                    self.lab_course.add_experiment(exp_no, data['name'], data['weight'])
                for student_id, data in lab_data.get('students', {}).items():
                    student = LabStudent(student_id, data['name'], data.get("No."))
                    student.lab_scores = data.get('lab_scores', {})
                    self.lab_course.add_student(student)
        elif legacy_lab_records:
            self.lab_course.add_experiment("legacy", "legacy_lab", 1)
            for student_id, name, no, records in legacy_lab_records:
                student = LabStudent(student_id, name, no)
                total = sum(record[1] for record in records)
                if records:
                    student.lab_scores["legacy"] = [records[-1][0], total]
                self.lab_course.add_student(student)

        if os.path.exists(os.path.join(self.working_dir, f"{self.course.name}_lab_activity_log.txt")):
            with open(os.path.join(self.working_dir, f"{self.course.name}_lab_activity_log.txt"), 'r', encoding='utf-8') as f:
                self.lab_logger.log = f.readlines()
        
    def add_student(self, student:Student, log=True, with_no=False, no=0):
        if student.id in self.course.students:
            return False, "Student already exists"
        for field_name in self.course.all_primary_field_names():
            student.ensure_score_field(field_name)
        self.course.students[student.id] = student
        
        if with_no:
            for s in self.course.students.values():
                if s.N >= no:
                    s.N += 1
            self.course.students[student.id].N = no
            self.course.students = dict(sorted(self.course.students.items(), key=lambda x: x[1].N))
        if log:
            self.logger.add(f"Added {student.name}[{student.id}]")
        return True, f"Student {student.name} added successfully"
    
    def remove_student(self, student: Student):
        if student.id not in self.course.students:
            return False, "Student not found"
        self.course.students.pop(student.id)
        for s in self.course.students.values():
            if s.N > student.N:
                s.N -= 1
        self.logger.add(f"Removed {student.name}[{student.id}].")
        return True, f"Student {student.name} removed successfully"
    
    def import_student(self, fullpath):
        directory, filename = os.path.split(fullpath)
        if directory:
            self.working_dir = directory
            
        if filename:
            if filename.split(".")[-1] == 'csv':
                with open(fullpath, newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        self.add_student(Student(row['id'], row['name']), log=False)
                self.logger.add(f"Imported {len(self.course.students)} students from {filename}.")
                return True, f"import {len(self.course.students)} students from {filename} successfully"
            elif filename.split(".")[-1] == 'xlsx':
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    df = pd.read_excel(fullpath)
                students_df_d = df.iloc[:, [1, 2]]
                students_df_d.columns = ['id', 'name']
                for n, s in students_df_d[5:-1].iterrows():
                    self.add_student(Student(s['id'], s['name']), log=False)
                self.logger.add(f"Imported {len(self.course.students)} students from {filename}.")
                return True, f"import {len(self.course.students)} students from {filename} successfully"
            else:
                return False, f"Unknown file format, ONLY .csv/.xlsx supported!"
        else:
            return False, f"No Filename Provided!"

    def import_lab_student(self, fullpath):
        directory, filename = os.path.split(fullpath)
        if directory:
            self.working_dir = directory

        if filename:
            if filename.split(".")[-1] == 'csv':
                with open(fullpath, newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        self.lab_course.add_student(LabStudent(row['id'], row['name']))
                self.lab_logger.add(f"Imported {len(self.lab_course.students)} lab students from {filename}.")
                return True, f"import {len(self.lab_course.students)} lab students from {filename} successfully"
            elif filename.split(".")[-1] == 'xlsx':
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    df = pd.read_excel(fullpath)
                students_df_d = df.iloc[:, [1, 2]]
                students_df_d.columns = ['id', 'name']
                for n, s in students_df_d[5:-1].iterrows():
                    self.lab_course.add_student(LabStudent(s['id'], s['name']))
                self.lab_logger.add(f"Imported {len(self.lab_course.students)} lab students from {filename}.")
                return True, f"import {len(self.lab_course.students)} lab students from {filename} successfully"
            else:
                return False, f"Unknown file format, ONLY .csv/.xlsx supported!"
        else:
            return False, f"No Filename Provided!"

    def save_data(self):
        if self.working_dir and not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir, exist_ok=True)

        student_data = {
            'class_name':self.course.name,
            'field_schema': self.course.export_field_schema(),
            'students': {}
        }
        for sid, s in self.course.students.items():
            student_data['students'][sid] = {
                "name": s.name,
                "No.":s.N,
            }
            for s_t in self.course.all_primary_field_names():
                s.ensure_score_field(s_t)
                student_data['students'][sid][s_t] = s.scores[s_t]
        
        with open(os.path.join(self.working_dir, f"{self.course.name}_student_score.json"), 'w', encoding='utf-8') as f:
            json.dump(student_data, f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt"), 'w', encoding='utf-8') as f:
            for log in self.logger.log:
                f.write(log)

        lab_data = {
            'class_name': self.course.name,
            'experiments': {},
            'students': {},
        }
        for exp_no, exp in self.lab_course.experiments.items():
            lab_data['experiments'][exp_no] = {
                'name': exp.name,
                'weight': exp.weight,
            }
        for sid, s in self.lab_course.students.items():
            lab_data['students'][sid] = {
                'name': s.name,
                'No.': s.N,
                'lab_scores': s.lab_scores,
            }

        with open(os.path.join(self.working_dir, f"{self.course.name}_lab_score.json"), 'w', encoding='utf-8') as f:
            json.dump(lab_data, f, ensure_ascii=False, indent=2)

        with open(os.path.join(self.working_dir, f"{self.course.name}_lab_activity_log.txt"), 'w', encoding='utf-8') as f:
            for log in self.lab_logger.log:
                f.write(log)
        
        ## add working directory for course
        if os.path.exists(r"working_directories.json"):
            with open(f"working_directories.json", "r", encoding='utf-8') as f:
                wd_data = json.load(f)
                if self.course.name in wd_data.keys():
                    wd_data[self.course.name] = self.working_dir
                else:
                    wd_data.update({self.course.name: self.working_dir})
        else:
            wd_data = {}
            wd_data[self.course.name] = self.working_dir
        
        with open(f"working_directories.json", 'w', encoding='utf-8') as f:
            json.dump(wd_data, f, ensure_ascii=False, indent=2)
            
        return 0, "Data saved successfully"
