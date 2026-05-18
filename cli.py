import cmd
import os
from collections.abc import Iterable
from colorama import Fore, Style, init
from prettytable import PrettyTable

from manager import StudentManager
from objs import SCORE_TYPE, Student, Course
import warnings

init(autoreset=True)

def print_info(level, msg):
    if level == 2:
        print(Fore.RED + msg)
    elif level == 1:
        print(Fore.YELLOW + msg)
    elif level == 0:
        print(Fore.GREEN + msg)
    else:
        pass

class StudentManagerCIL(cmd.Cmd):
    intro = "Welcome to student ScoreManger V0.2@sxl, GZHU"
    def __init__(self, course_name='course1'):
        super().__init__()
        self.manager = StudentManager(Course(name=course_name))
        self.prompt = f"Students@{self.manager.course.name}>>"
    
    def show_students(self, students):
        if isinstance(students, Iterable):
            tab = PrettyTable()
            tab.border = True
            field_names = ['No.', 'Name', 'ID']
            for k, v in SCORE_TYPE.items():
                field_names.append(v)
            field_names.append('Total')
            tab.field_names = field_names
            for s in students:
                score = s.calculate_score()
                tab.add_row([s.N, s.name, s.id] + list(score) + [sum(score)])
            print(tab)
        elif isinstance(students, Student):
            score = students.calculate_score()
            print_score = f"{students.N}-{students.name}({students.id}): "
            for i, (k, v) in enumerate(SCORE_TYPE.items()):
                print_score += f"{v}:{score[i]}, "
            print_score += (Fore.GREEN + f" Total: {sum(score)}")
        else:
            return 2, f"Unknown Student {students}"

    def do_import(self, args):
        'import <filename> to load students info.'
        if not args:
            print_info(2, "Usage: import <filename>")
            return
        try:
            self.manager.import_student(args)
            print_info(0, f"Imported {len(self.manager.course.students)} students from {args}.")
        except Exception as e:
            print_info(2, f"Error importing file: {e}")
    
    def do_show(self, args):
        '''
        Show student scores by name(-N) or No.(-n), show all students with no parameter.
        Usage:
            show [-N name1,name2,... | -n student_No1,student_No2,...]
        Examples:
            1.show all students' scores: show
            2.show students' score with No.=1,2,3: show -n 1,2,3
            3.show students' score with name=john: show -N john
        '''
        if not args:
            self.show_students(self.manager.course.students.values())
            return
        else:
            parts = args.split()
            if len(parts) != 2:
                print_info(2, "Usage: show -N/-n <student_name>/<student_No>")
                return
            
            if parts[0] == '-N':
                names = [n for n in parts[1].split(',')]
                students = self.manager.course.find_students_by_names(names)
                self.show_students(students)
                
            elif parts[0] == '-n':
                nos = [int(s) for s in parts[1].split(',')]
                students = self.manager.course.find_students_by_nos(nos)
                self.show_students(students)
    
    def do_rd(self, args):
        '''
        record scores for a single student.
        Usage: rd <student_No.> <type[c/a/h/l/e]> <score>
        examples:
            1.record class participation score 1 for student with No.=1: rd 1 c 1
            2.record exam score 90 for student with No.=2: rd 2 e 90
        '''
        args = args.split()
        if not len(args) == 3:
            print(f"Usage: rd <student_No.> <type {list(SCORE_TYPE.keys())}> <score>")
            return
        if args[1] not in SCORE_TYPE.keys():
            print_info(2, f"Type must be one of {list(SCORE_TYPE.keys())}")
            return
        else:
            s = self.manager.course.find_students_by_nos(int(args[0]))
            if not s:
                return 
            s.add_score(args[1], int(args[2]))
            print(f"{s.N}-{s.name}[{s.id}]:"+ Fore.GREEN + Style.BRIGHT + f" +{int(args[2])}" + Style.RESET_ALL + f"({SCORE_TYPE[args[1]]})!")
            self.manager.logger.add(f"Record: {s.N}-{s.name}[{s.id}]: +{args[2]}({SCORE_TYPE[args[1]]})")
            
    def do_brd(self, args):
        '''
        batch record scores for multiple students.
        Usage: brd <student_No1,student_No2,...> <type[c/a/h/l/e]> <score> {-e}
        -e: exclude the listed students, record for all other students.
        examples:
            1.record class participation score 1 for students with No.=1,2,3: brd 1,2,3 c 1
            2.record exam score 90 for all students except No.=1,2,3: brd 1,2,3 e 90 -e
        '''
        args = args.split()
        if not args:
            print("Usage: brd <student_No1,student_No2,> <type[c/a/h/l/e]> <score> {-e}")
            return
        if args[1] not in SCORE_TYPE.keys():
            print(f"Type must be one of {list(SCORE_TYPE.keys())}")
            return
        else:
            students = self.manager.course.find_students_by_nos([int(n) for n in args[0].split(',')])
            exclusion = '-e' in args
            score = int(args[2])
            f, msg = self.manager.course.add_scores(students, args[1], score, exclusion)
            print_info(f, msg)
            if not f:
                self.manager.logger.add(f"Batch record: +{score}({SCORE_TYPE[args[1]]}) for students{' excluding:' if exclusion else ':'} {[s.name for s in students]}")
    
    def do_find(self, args):
        '''
        Find students by name fragment.
        Usage: find <name_fragment>
        Example:
            1.find students with name containing "John": find John
            2.find students with name containing "张": find 张
        '''
        if not args:
            print("Usage: find <name_fragment>")
            return
        
        match = self.manager.course.search_students_by_name(args)
        for N, student_id, name in match:
            print(f"{N}\t{name}\t{student_id}")
    
    def do_log(self, args):
        '''
        Show the log of recorded student scores.
        Usage:
            log [-n student_No1,student_No2,...] [-c] [-a] [-h] [-e] [-l] [all]
        Examples:
            1.show the last 20 (batched) logs for the whole class: log
            2.show class participation logs of students with No.=1,2,3: log -n 1,2,3 -c
            3.show all types of logs of students with No.=1,2,3: log -n 1,2,3 all
            4.the same as 3: log -n 1,2,3
        '''
        if args:
            parts = args.split()
            if '-n' in parts:
                ns = parts[parts.index("-n")+1]
                students = self.manager.course.find_students_by_nos([int(n) for n in ns.split(',')])
            else:
                students = self.manager.course.students.values()
            
            data = []
            if students:
                for s in students:
                    for k, v in SCORE_TYPE.items():
                        if k in parts:
                            tmp = eval(f"s.{v}")
                            for d, sc in tmp:
                                data.append((s.N, s.name, s.id, v, d, sc))
                    if not any([t in parts for t in SCORE_TYPE.keys()]):
                        for k, v in SCORE_TYPE.items():
                            tmp = eval(f"s.{v}")
                            for d, sc in tmp:
                                data.append((s.N, s.name, s.id, v, d, sc))
                data.sort(key=lambda x: (x[4], x[3]))
                tab = PrettyTable()
                tab.field_names = ['Date', 'No.', 'Name', 'ID', 'Score', 'Type']
                tab.add_rows([[x[4],x[0],x[1],x[2],"+" + str(x[-1]),x[3]] for x in data])
                print(tab)
        else:
            for log in self.manager.logger.log[-20:]:
                print(log.strip())
    
    def do_tops(self, args):
        '''
        Show top N students by score type.
        Usage: tops [-n N] [-t type]
        type: t/u/e/h/l/a/c
        Examples:
            1.show top 5 students by total score: tops
            2.show top 3 students by usual score: tops -n 3 -t u
            3.show top 10 students by exam score: tops -n 10 -t e
            4.show top 5 students by homework score: tops -t h
            5.show last 5 students by lab score: tops -n -5 -t l
        '''
        n = 5
        rank_by = "t"
        parts = args.split()
        if "-n" in parts:
            try:
                if parts[parts.index("-n")+1].startswith('-'):
                    n = -int(parts[parts.index("-n")+1][1:])
                else:
                    n = int(parts[parts.index("-n")+1])
            except:
                print_info(2, "please type a number after -n")
                return
        
        if "-t" in parts:
            try:
                rank_by = parts[parts.index("-t")+1]
            except:
                print_info(2, f"please provide a valid type after -t: {list(SCORE_TYPE.keys()) + ['t','u']}")
                return
        
        ranked = self.manager.course.get_top_students(n, rank_by)
        tmp_dict = SCORE_TYPE.copy()
        tmp_dict['t'] = 'total'
        title = f"Ranked by {tmp_dict[rank_by]} score"
        title += f'(TOP-{n}): ' if n > 0 else f'(LAST-{abs(n)}): '
        tab = PrettyTable()
        tab.title = title
        tab.field_names = ['RANK', 'No.', 'Name', 'ID', 'Score']
        tab.add_rows([[i, s.N, s.name, s.id, score] for i, (s,score) in enumerate(ranked)])
        print(tab)
    
    def do_add(self, args):
        '''
        Add a student manually with/without given No.
        Usage: add Name ID [-n No.]
        Examples:
            add John with ID=1001: add john 1001
            add Tom with ID=1002 and No.=12: add Tom 1002 -n 12 (Note that No. of students Numbered after 12 will +1)
        '''
        if not args:
            print("Usage: add Name ID [-n No.]")
            return
        
        parts = args.split()
        if len(parts) == 2:
            self.manager.add_student(Student(parts[1], parts[0]))
        elif len(parts) == 4 and '-n' in parts:
            ns = parts[parts.index("-n")+1]
            if ns.isdigit():
                self.manager.add_student(Student(parts[1], parts[0]), with_no=True, no=int(ns))
            else:
                print_info(2, "The provided No. is not a digit")
        else:
            print_info(2, "Invalid command!")
            return


    def do_rm(self, args):
        '''
        remove a student manually by No. or name. Note that the No. of student after removed student will -1.
        Usage: rm [-n No.][-N name]
        Examples:
            remove John: rm -N john
            remove student with No.=2: rm -n 2
        '''
        if not args:
            print("Usage: rm [-n No.][-N name]")
            return
        
        parts = args.split()
        
        if "-n" in parts:
            ns = parts[parts.index("-n")+1]
            student = self.manager.course.find_students_by_nos(int(ns))
        if "-N" in parts:
            ns = parts[parts.index("-N")+1]
            student = self.manager.course.find_students_by_names(ns)
        if student:
            user_input = input(f"{student.name}{[student.id]} will be removed, yes(Y)/no(N)?")
            if user_input == "yes" or user_input == "Y":
                self.manager.remove_student(student)
            elif user_input == "no" or user_input == "N":
                return
        
                
    def do_save(self, args):
        '''
        Save current data to file.
        Usage: save
        '''
        f, msg = self.manager.save_data()
        print_info(f, msg)
    
    def do_help(self, args):
        '''
        Show help information for commands.
        Usage: help [command]
        '''
        return super().do_help(args)
    
    def do_clear(self, args):
        '''
        Clear the console screen.
        Usage: clear
        '''
        # Clear the console screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def do_exit(self, args):
        '''
        Exit the CLI with/without saving the data.
        Usage: exit [-s]
        '''
        if '-s' in args:
            f, msg = self.manager.save_data()
            print_info(f, msg)
        return True