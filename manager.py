import datetime
import csv
import os
import pandas as pd
from objs import Student, Course, Logger, SCORE_TYPE
import json
import warnings

class StudentManager:
    def __init__(self, class_obj=None) -> None:
        self.course = class_obj if class_obj else Course()
        self.logger = Logger()
        self.working_dir = ''
        self.load_data()
        
    def load_data(self):
        with open(f"working_directories.json", "r", encoding='utf-8') as f:
            wd_data = json.load(f)
            if self.course.name in wd_data.keys():
                self.working_dir = wd_data[self.course.name]
        
        if os.path.exists(os.path.join(self.working_dir, f"{self.course.name}_student_score.json")):
            with open(os.path.join(self.working_dir, f"{self.course.name}_student_score.json"), 'r', encoding='utf-8') as f:
                student_data = json.load(f)
                for student_id, data in student_data['students'].items():
                    student = Student(student_id, data['name'])
                    for s_t in SCORE_TYPE.values():
                        exec(f"student.{s_t} = data['{s_t}']")
                    self.add_student(student)
        
        if os.path.exists(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt")):
            with open(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt"), 'r', encoding='utf-8') as f:
                self.logger.log = f.readlines()
        
    def add_student(self, student:Student, log=True):
        if student.id in self.course.students:
            return False, "Student already exists"
        self.course.students[student.id] = student
        if log:
            self.logger.add(f"Added {student.name}[{student.id}]")
        return True, f"Student {student.name} added successfully"
    
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

    def save_data(self):
        student_data = {
            'class_name':self.course.name,
            'students': {}
        }
        for sid, s in self.course.students.items():
            student_data['students'][sid] = {
                "name": s.name,
                "No.":s.N,
            }
            for s_t in SCORE_TYPE.values():
                # exec(f"student_data['students'][sid].update({s_t," + f"s.{s_t}})")
                exec(f"student_data['students'][sid]['{s_t}']=s.{s_t}")
                # print(f"student_data['students'][sid]['{s_t}']=s.{s_t}")
        
        with open(os.path.join(self.working_dir, f"{self.course.name}_student_score.json"), 'w', encoding='utf-8') as f:
            json.dump(student_data, f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(self.working_dir, f"{self.course.name}_activity_log.txt"), 'w', encoding='utf-8') as f:
            for log in self.logger.log:
                f.write(log)
        
        ## add working directory for course
        with open(f"working_directories.json", "r", encoding='utf-8') as f:
            wd_data = json.load(f)
            if self.course.name in wd_data.keys():
                wd_data[self.course.name] = self.working_dir
            else:
                wd_data.update({self.course.name: self.working_dir})
        
        with open(f"working_directories.json", 'w', encoding='utf-8') as f:
            json.dump(wd_data, f, ensure_ascii=False, indent=2)
            
        return 0, "Data saved successfully"