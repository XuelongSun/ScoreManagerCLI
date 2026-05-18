import cmd
import os
from collections.abc import Iterable
from colorama import Fore, Style, init
from prettytable import PrettyTable

from manager import StudentManager
from objs import SCORE_TYPE, Student, Course, LabStudent
import warnings

init(autoreset=True)

LAB_HELP = {
    "import": """lab import <filename>
Load the lab roster from a CSV/XLSX file. The lab roster is independent from the theory roster.""",
    "add-exp": """lab add-exp <exp_no> <name> <weight>
Add one lab experiment. Scores are out of 100. Weight accepts 0-1 or percentage style values such as 30.""",
    "add": """lab add <Name> <ID> [-n No.]
Add one lab student manually. Lab student numbers are independent from theory student numbers.""",
    "rm": """lab rm [-n No. | -N name]
Remove one lab student manually. Student numbers after the removed student will be shifted down.""",
    "rd": """lab rd <lab_student_No.> <exp_no> <score>
Record one lab score. Example: lab rd 2 1 88.""",
    "brd": """lab brd <lab_student_No1,lab_student_No2,...> <exp_no> <score> {-e}
Batch record lab scores. Use -e to record for all lab students except the listed numbers.""",
    "show": """lab show [-n lab_student_No1,lab_student_No2,... | -N name1,name2,...]
Show lab scores and weighted lab totals. With no filter, show all lab students.""",
    "find": """lab find <name_fragment>
Find lab students by name fragment and show lab No., name, and ID.""",
    "tops": """lab tops [-n N] [-t total|t|<exp_no>]
Show top or bottom lab students. Default ranks by weighted lab total. Use -t <exp_no> for one experiment.""",
    "log": """lab log
Show the last 20 lab activity logs.""",
    "help": """lab help [command]
Show help for all lab commands, or detailed help for one lab command.""",
}

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
    def __init__(self, course_name='course1', mode='all', working_dir=None):
        super().__init__()
        self.manager = StudentManager(Course(name=course_name), working_dir=working_dir)
        self.mode = mode
        mode_label = f":{mode}" if mode != "all" else ""
        self.prompt = f"Students@{self.manager.course.name}{mode_label}>>"

    def _theory_enabled(self):
        if self.mode == "lab":
            print_info(1, "Theory commands are disabled in lab mode. Use --mode all or --mode theory.")
            return False
        return True

    def _lab_enabled(self):
        if self.mode == "theory":
            print_info(1, "Lab commands are disabled in theory mode. Use --mode all or --mode lab.")
            return False
        return True

    def _format_score(self, score):
        score = float(score)
        return int(score) if score.is_integer() else score

    def _lab_label(self, exp_no):
        exp_no = str(exp_no)
        return exp_no if exp_no.lower().startswith("lab") else f"lab{exp_no}"

    def show_lab_help(self, command=None):
        if command:
            help_text = LAB_HELP.get(command)
            if help_text:
                print(help_text)
            else:
                print_info(2, f"Unknown lab command: {command}")
            return
        for help_text in LAB_HELP.values():
            print(help_text)
            print()
    
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

    def show_lab_students(self, students):
        if isinstance(students, Iterable):
            tab = PrettyTable()
            tab.border = True
            experiments = list(self.manager.lab_course.experiments.values())
            tab.field_names = (
                ['Lab No.', 'Name', 'ID']
                + [f"{e.exp_no}:{e.name}({e.weight:g})" for e in experiments]
                + ['Lab Total']
            )
            for s in students:
                row = [s.N, s.name, s.id]
                for e in experiments:
                    record = s.lab_scores.get(e.exp_no)
                    row.append(record[1] if record else '')
                row.append(round(s.calculate_lab_score(self.manager.lab_course.experiments), 2))
                tab.add_row(row)
            print(tab)
        elif isinstance(students, LabStudent):
            self.show_lab_students([students])
        else:
            return 2, f"Unknown lab student {students}"

    def do_import(self, args):
        'import <filename> to load students info.'
        if not self._theory_enabled():
            return
        if not args:
            print_info(2, "Usage: import <filename>")
            return
        try:
            self.manager.push_undo(f"import {args}")
            f, msg = self.manager.import_student(args)
            if f:
                print_info(0, f"Imported {len(self.manager.course.students)} students from {args}.")
            else:
                self.manager.rollback_undo()
                print_info(2, msg)
        except Exception as e:
            self.manager.rollback_undo()
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
        if not self._theory_enabled():
            return
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
        Usage: rd <student_No.> <type[c/a/h/e]> <score>
        examples:
            1.record class participation score 1 for student with No.=1: rd 1 c 1
            2.record exam score 90 for student with No.=2: rd 2 e 90
        '''
        if not self._theory_enabled():
            return
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
            score = int(args[2])
            self.manager.push_undo(f"record +{score}({SCORE_TYPE[args[1]]}) for {s.N}-{s.name}[{s.id}]")
            s.add_score(args[1], score)
            print(f"{s.N}-{s.name}[{s.id}]:"+ Fore.GREEN + Style.BRIGHT + f" +{score}" + Style.RESET_ALL + f"({SCORE_TYPE[args[1]]})!")
            self.manager.logger.add(f"Record: {s.N}-{s.name}[{s.id}]: +{score}({SCORE_TYPE[args[1]]})")
            
    def do_brd(self, args):
        '''
        batch record scores for multiple students.
        Usage: brd <student_No1,student_No2,...> <type[c/a/h/e]> <score> {-e}
        -e: exclude the listed students, record for all other students.
        examples:
            1.record class participation score 1 for students with No.=1,2,3: brd 1,2,3 c 1
            2.record exam score 90 for all students except No.=1,2,3: brd 1,2,3 e 90 -e
        '''
        if not self._theory_enabled():
            return
        args = args.split()
        if not args:
            print("Usage: brd <student_No1,student_No2,> <type[c/a/h/e]> <score> {-e}")
            return
        if args[1] not in SCORE_TYPE.keys():
            print(f"Type must be one of {list(SCORE_TYPE.keys())}")
            return
        else:
            students = self.manager.course.find_students_by_nos([int(n) for n in args[0].split(',')])
            exclusion = '-e' in args
            score = int(args[2])
            self.manager.push_undo(f"batch record +{score}({SCORE_TYPE[args[1]]})")
            f, msg = self.manager.course.add_scores(students, args[1], score, exclusion)
            print_info(f, msg)
            if not f:
                self.manager.logger.add(f"Batch record: +{score}({SCORE_TYPE[args[1]]}) for students{' excluding:' if exclusion else ':'} {[s.name for s in students]}")
            else:
                self.manager.rollback_undo()
    
    def do_find(self, args):
        '''
        Find students by name fragment.
        Usage: find <name_fragment>
        Example:
            1.find students with name containing "John": find John
            2.find students with name containing "张": find 张
        '''
        if not self._theory_enabled():
            return
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
            log [-n student_No1,student_No2,...] [-c] [-a] [-h] [-e] [all]
        Examples:
            1.show the last 20 (batched) logs for the whole class: log
            2.show class participation logs of students with No.=1,2,3: log -n 1,2,3 -c
            3.show all types of logs of students with No.=1,2,3: log -n 1,2,3 all
            4.the same as 3: log -n 1,2,3
        '''
        if not self._theory_enabled():
            return
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
        type: t/u/e/h/a/c
        Examples:
            1.show top 5 students by total score: tops
            2.show top 3 students by usual score: tops -n 3 -t u
            3.show top 10 students by exam score: tops -n 10 -t e
            4.show top 5 students by homework score: tops -t h
            5.show last 5 students by homework score: tops -n -5 -t h
        '''
        if not self._theory_enabled():
            return
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
        if not self._theory_enabled():
            return
        if not args:
            print("Usage: add Name ID [-n No.]")
            return
        
        parts = args.split()
        if len(parts) == 2:
            self.manager.push_undo(f"add {parts[0]}[{parts[1]}]")
            f, msg = self.manager.add_student(Student(parts[1], parts[0]))
            if not f:
                self.manager.rollback_undo()
                print_info(2, msg)
        elif len(parts) == 4 and '-n' in parts:
            ns = parts[parts.index("-n")+1]
            if ns.isdigit():
                self.manager.push_undo(f"add {parts[0]}[{parts[1]}] with No.={ns}")
                f, msg = self.manager.add_student(Student(parts[1], parts[0]), with_no=True, no=int(ns))
                if not f:
                    self.manager.rollback_undo()
                    print_info(2, msg)
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
        if not self._theory_enabled():
            return
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
                self.manager.push_undo(f"remove {student.N}-{student.name}[{student.id}]")
                self.manager.remove_student(student)
            elif user_input == "no" or user_input == "N":
                return
        
                
    def do_lab(self, args):
        '''
        Manage lab roster, experiments, and weighted lab scores.
        Usage:
            lab import <filename>
            lab add-exp <exp_no> <name> <weight>
            lab add <Name> <ID> [-n No.]
            lab rm [-n No. | -N name]
            lab rd <lab_student_No.> <exp_no> <score>
            lab brd <lab_student_No1,lab_student_No2,...> <exp_no> <score> {-e}
            lab show [-n lab_student_No1,lab_student_No2,... | -N name1,name2,...]
            lab find <name_fragment>
            lab tops [-n N] [-t total|t|<exp_no>]
            lab log
            lab help [command]
        '''
        if not self._lab_enabled():
            return

        parts = args.split()
        if not parts:
            print_info(1, "Usage: lab import/add-exp/add/rm/rd/brd/show/find/tops/log/help ...")
            return

        cmd = parts[0]
        if cmd == "help":
            if len(parts) > 2:
                print_info(2, "Usage: lab help [command]")
                return
            self.show_lab_help(parts[1] if len(parts) == 2 else None)
            return

        if cmd == "import":
            if len(parts) != 2:
                print_info(2, "Usage: lab import <filename>")
                return
            try:
                self.manager.push_undo(f"lab import {parts[1]}", scope="lab")
                f, msg = self.manager.import_lab_student(parts[1])
                if f:
                    print_info(0, msg)
                else:
                    self.manager.rollback_undo()
                    print_info(2, msg)
            except Exception as e:
                self.manager.rollback_undo()
                print_info(2, f"Error importing lab file: {e}")
            return

        if cmd == "add-exp":
            if len(parts) < 4:
                print_info(2, "Usage: lab add-exp <exp_no> <name> <weight>")
                return
            exp_no = parts[1]
            name = " ".join(parts[2:-1])
            weight = parts[-1]
            self.manager.push_undo(f"lab add experiment {exp_no}-{name}", scope="lab")
            f, msg = self.manager.lab_course.add_experiment(exp_no, name, weight)
            if not f:
                self.manager.lab_logger.add(f"Added lab experiment {exp_no}-{name}({self.manager.lab_course.experiments[exp_no].weight:g})")
            else:
                self.manager.rollback_undo()
            print_info(f, msg)
            return

        if cmd == "add":
            if len(parts) == 3:
                self.manager.push_undo(f"lab add {parts[1]}[{parts[2]}]", scope="lab")
                f, msg = self.manager.lab_course.add_student(LabStudent(parts[2], parts[1]))
                if not f:
                    self.manager.lab_logger.add(f"Added lab student {parts[1]}[{parts[2]}]")
                else:
                    self.manager.rollback_undo()
                print_info(f, msg)
                return
            if len(parts) == 5 and "-n" in parts:
                ns = parts[parts.index("-n")+1]
                if not ns.isdigit():
                    print_info(2, "The provided No. is not a digit")
                    return
                self.manager.push_undo(f"lab add {parts[1]}[{parts[2]}] with No.={ns}", scope="lab")
                f, msg = self.manager.lab_course.add_student(LabStudent(parts[2], parts[1]), with_no=True, no=int(ns))
                if not f:
                    self.manager.lab_logger.add(f"Added lab student {parts[1]}[{parts[2]}] with No.={ns}")
                else:
                    self.manager.rollback_undo()
                print_info(f, msg)
                return
            print_info(2, "Usage: lab add <Name> <ID> [-n No.]")
            return

        if cmd == "rm":
            if len(parts) != 3:
                print_info(2, "Usage: lab rm [-n No. | -N name]")
                return
            student = None
            if parts[1] == "-n":
                student = self.manager.lab_course.find_students_by_nos(int(parts[2]))
            elif parts[1] == "-N":
                student = self.manager.lab_course.find_students_by_names(parts[2])
            if not student:
                print_info(2, "Lab student not found")
                return
            user_input = input(f"{student.name}{[student.id]} will be removed from lab roster, yes(Y)/no(N)?")
            if user_input == "yes" or user_input == "Y":
                self.manager.push_undo(f"lab remove {student.N}-{student.name}[{student.id}]", scope="lab")
                f, msg = self.manager.lab_course.remove_student(student)
                if not f:
                    self.manager.lab_logger.add(f"Removed lab student {student.name}[{student.id}].")
                else:
                    self.manager.rollback_undo()
                print_info(f, msg)
            return

        if cmd == "rd":
            if len(parts) != 4:
                print_info(2, "Usage: lab rd <lab_student_No.> <exp_no> <score>")
                return
            student = self.manager.lab_course.find_students_by_nos(int(parts[1]))
            if not student:
                print_info(2, f"Lab student No. {parts[1]} not found")
                return
            self.manager.push_undo(f"lab record {parts[2]}={parts[3]} for {student.N}-{student.name}[{student.id}]", scope="lab")
            f, msg = self.manager.lab_course.record_score(student, parts[2], parts[3])
            if not f:
                self.manager.lab_logger.add(f"Lab record: {student.N}-{student.name}[{student.id}]: {parts[2]}={parts[3]}")
                score = self._format_score(parts[3])
                print(f"{student.name}[{student.id}] {self._lab_label(parts[2])} " + Fore.GREEN + Style.BRIGHT + f"+{score}" + Style.RESET_ALL + "!")
            else:
                self.manager.rollback_undo()
                print_info(f, msg)
            return

        if cmd == "brd":
            if len(parts) < 4:
                print_info(2, "Usage: lab brd <lab_student_No1,lab_student_No2,...> <exp_no> <score> {-e}")
                return
            students = self.manager.lab_course.find_students_by_nos([int(n) for n in parts[1].split(',')])
            exclusion = '-e' in parts
            self.manager.push_undo(f"lab batch record {parts[2]}={parts[3]}", scope="lab")
            f, msg = self.manager.lab_course.record_scores(students, parts[2], parts[3], exclusion)
            if not f:
                self.manager.lab_logger.add(f"Lab batch record: {parts[2]}={parts[3]} for students{' excluding:' if exclusion else ':'} {[s.name for s in students]}")
            else:
                self.manager.rollback_undo()
            print_info(f, msg)
            return

        if cmd == "tops":
            n = 5
            rank_by = "total"
            if "-n" in parts:
                try:
                    n_arg = parts[parts.index("-n")+1]
                    n = -int(n_arg[1:]) if n_arg.startswith('-') else int(n_arg)
                except:
                    print_info(2, "please type a number after -n")
                    return
            if "-t" in parts:
                try:
                    rank_by = parts[parts.index("-t")+1]
                except:
                    print_info(2, "please provide a valid type after -t: total/t or a lab experiment No.")
                    return

            if rank_by in ["t", "total"]:
                title = "Ranked by lab total score"
                ranked = [
                    (s, round(s.calculate_lab_score(self.manager.lab_course.experiments), 2))
                    for s in self.manager.lab_course.students.values()
                ]
            elif rank_by in self.manager.lab_course.experiments:
                title = f"Ranked by {self._lab_label(rank_by)} score"
                ranked = [
                    (s, s.lab_scores.get(rank_by, ['', 0])[1])
                    for s in self.manager.lab_course.students.values()
                ]
            else:
                print_info(2, f"Unknown lab rank type: {rank_by}")
                return

            if n < 0:
                ranked = sorted(ranked, key=lambda x: x[1])[:abs(n)][::-1]
            else:
                ranked = sorted(ranked, key=lambda x: x[1], reverse=True)[:n]

            title += f'(TOP-{n}): ' if n > 0 else f'(LAST-{abs(n)}): '
            tab = PrettyTable()
            tab.title = title
            tab.field_names = ['RANK', 'Lab No.', 'Name', 'ID', 'Score']
            tab.add_rows([[i, s.N, s.name, s.id, score] for i, (s, score) in enumerate(ranked)])
            print(tab)
            return

        if cmd == "find":
            if len(parts) != 2:
                print_info(2, "Usage: lab find <name_fragment>")
                return
            match = self.manager.lab_course.search_students_by_name(parts[1])
            for N, student_id, name in match:
                print(f"{N}\t{name}\t{student_id}")
            return

        if cmd == "show":
            if len(parts) == 1:
                self.show_lab_students(self.manager.lab_course.students.values())
                return
            if len(parts) != 3:
                print_info(2, "Usage: lab show [-N name1,name2,... | -n lab_student_No1,lab_student_No2,...]")
                return
            if parts[1] == "-N":
                names = [n for n in parts[2].split(',')]
                self.show_lab_students(self.manager.lab_course.find_students_by_names(names))
                return
            if parts[1] == "-n":
                nos = [int(s) for s in parts[2].split(',')]
                self.show_lab_students(self.manager.lab_course.find_students_by_nos(nos))
                return
            print_info(2, "Usage: lab show [-N name1,name2,... | -n lab_student_No1,lab_student_No2,...]")
            return

        if cmd == "log":
            for log in self.manager.lab_logger.log[-20:]:
                print(log.strip())
            return

        print_info(2, f"Unknown lab command: {cmd}")

    def do_undo(self, args):
        '''
        Undo the last successful data-changing operation.
        Usage: undo
        '''
        f, msg = self.manager.undo()
        print_info(f, msg)

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
