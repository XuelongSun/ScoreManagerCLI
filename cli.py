import cmd
import ast
import os
import re
from collections.abc import Iterable
from colorama import Fore, Style, init
from prettytable import PrettyTable

from manager import StudentManager
from objs import Student, Course, LabStudent, LAB_MANAGED_FIELDS

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
    "schema": """lab schema
Show or configure lab score schema.
Usage:
  lab schema
  lab schema mode exam|usual|split
  lab schema map <exp_no1,exp_no2,...> usual|exam
Modes:
  exam: one lab field contributes to course exam.
  usual: one lab field contributes to course usual.
  split: lab_usual contributes to usual and lab_exam contributes to exam.
Use change field lab/lab_usual/lab_exam -w <weight> to set course mix weights.""",
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

    def _format_score(self, score, display_mode=None):
        score = float(score)
        formatted = str(int(score)) if score.is_integer() else f"{score:.2f}".rstrip('0').rstrip('.')
        if display_mode:
            formatted += self.manager.course.display_mode_suffix(display_mode)
        return formatted

    def _format_score_with_extra(self, score, extra, mode):
        formatted = self._format_score(score)
        extra = float(extra)
        if extra <= 1e-9:
            return formatted
        extra_text = self._format_score(extra)
        if self.manager.course.normalize_display_mode(mode) == "percent":
            extra_text += "%"
        return f"{formatted}(+{extra_text})"

    def _parse_extra_flag(self, parts):
        return [part for part in parts if part != "--extra"], "--extra" in parts

    def _parse_date_flag(self, parts):
        if "-d" not in parts:
            return parts, None, None
        idx = parts.index("-d")
        if idx + 1 >= len(parts):
            return None, None, "Please provide a date after -d, e.g. show -d 2026-07-01"
        date = parts[idx + 1]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            return None, None, "Date must be in YYYY-MM-DD format"
        return parts[:idx] + parts[idx + 2:], date, None

    def _parse_display_modes(self, parts):
        remaining = []
        global_mode = None
        field_modes = {}
        idx = 0
        while idx < len(parts):
            token = parts[idx]
            if token in ["-m", "--mode", "--display"]:
                if idx + 1 >= len(parts):
                    return None, None, None, f"Please provide a display mode after {token}"
                global_mode, field_modes, msg = self._merge_display_mode_spec(parts[idx + 1], global_mode, field_modes)
                if msg:
                    return None, None, None, msg
                idx += 2
                continue
            if token.startswith("--display=") or token.startswith("--mode=") or token.startswith("-m="):
                spec = token.split("=", 1)[1]
                global_mode, field_modes, msg = self._merge_display_mode_spec(spec, global_mode, field_modes)
                if msg:
                    return None, None, None, msg
                idx += 1
                continue
            remaining.append(token)
            idx += 1
        return remaining, global_mode, field_modes, None

    def _merge_display_mode_spec(self, spec, global_mode, field_modes):
        field_modes = field_modes.copy()
        for item in [s.strip() for s in spec.split(',') if s.strip()]:
            if "=" in item:
                field, mode = item.split("=", 1)
            elif ":" in item:
                field, mode = item.split(":", 1)
            else:
                mode = self.manager.course.normalize_display_mode(item)
                if not mode:
                    return global_mode, field_modes, f"Unknown display mode: {item}"
                global_mode = mode
                continue
            field = self.manager.course.normalize_field_name(field.strip())
            if field not in self.manager.course.all_display_field_names():
                return global_mode, field_modes, f"Unknown score field for display mode: {field}"
            mode = self.manager.course.normalize_display_mode(mode.strip())
            if not mode:
                return global_mode, field_modes, f"Unknown display mode: {item}"
            field_modes[field] = mode
        return global_mode, field_modes, None

    def _resolve_display_mode(self, field, global_mode=None, field_modes=None):
        field = self.manager.course.normalize_field_name(field)
        field_modes = field_modes or {}
        return field_modes.get(field, global_mode or self.manager.course.default_display_mode(field))

    def _field_header(self, field, mode):
        return f"{self.manager.course.display_field_name(field)}{self.manager.course.display_mode_suffix(mode)}"

    def _color(self, text, color_name, bright=False):
        color = getattr(Fore, color_name, "")
        style = getattr(Style, "BRIGHT", "") if bright else ""
        reset = getattr(Style, "RESET_ALL", "")
        return f"{style}{color}{text}{reset}"

    def _schema_config_value(self, config, key, default=''):
        if key == "max_score":
            return config.get("max_score", config.get("max-score", default))
        return config.get(key, default)

    def _schema_primary_configs(self, schema):
        primary_configs = schema.get("primary", [])
        if isinstance(primary_configs, dict):
            primary_configs = [
                dict(config, name=name) if isinstance(config, dict) and "name" not in config else config
                for name, config in primary_configs.items()
            ]
        return primary_configs

    def _schema_secondary_configs(self, schema):
        secondary_configs = schema.get("secondary", [])
        if isinstance(secondary_configs, dict):
            secondary_configs = [
                dict(config, name=name) if isinstance(config, dict) and "name" not in config else config
                for name, config in secondary_configs.items()
            ]
        return secondary_configs

    def _schema_find_alias(self, schema, field_name, default=''):
        for config in self._schema_secondary_configs(schema):
            if self._schema_config_value(config, "name") == field_name:
                return self._schema_config_value(config, "alias", default)
        return default

    def _schema_format_number(self, value):
        if value == '' or value is None:
            return ''
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
        return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip('0').rstrip('.')

    def _print_schema_primary(self, config, indent, color_name):
        name = self._schema_config_value(config, "name")
        alias = self._schema_config_value(config, "alias", "-")
        mode = self.manager.course._normalize_mode(self._schema_config_value(config, "mode", "points"))
        max_score = self._schema_format_number(self._schema_config_value(config, "max_score"))
        weight = self._schema_format_number(self._schema_config_value(config, "weight"))
        display_name = self.manager.course.display_field_name(name)
        label = self._color(f"{display_name}({alias})", color_name, bright=True)
        print(f"{indent}- {label}: weight={weight}, max={max_score}, mode={mode}")

    def _schema_weight_display(self, value, warn_over=100):
        text = self._schema_format_number(value)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return text
        if numeric > warn_over:
            return self._color(text, "RED", bright=True)
        return text

    def _print_schema_tree(self, schema, source, path=None):
        color_name = "CYAN" if source == "cache" else "MAGENTA"
        title = "CACHE field_schema" if source == "cache" else "FILE field_schema"
        print(self._color(title, color_name, bright=True))
        if path:
            print(self._color(f"path: {path}", color_name))

        primary_configs = self._schema_primary_configs(schema)
        usual_fields = [c for c in primary_configs if self._schema_config_value(c, "group") == "usual"]
        exam_fields = [c for c in primary_configs if self._schema_config_value(c, "group") == "exam"]
        usual_weight = sum(
            float(self._schema_config_value(c, "weight", 0) or 0)
            for c in usual_fields
        )
        total_weight = sum(
            float(self._schema_config_value(c, "weight", 0) or 0)
            for c in primary_configs
        )
        usual_alias = self._schema_find_alias(schema, "usual", "u")
        total_alias = self._schema_find_alias(schema, "total", "t")

        print(f"{self._color(f'total({total_alias})', color_name, bright=True)} course_weight={self._schema_weight_display(total_weight)}")
        print(f"  {self._color(f'usual({usual_alias})', color_name, bright=True)} course_weight={self._schema_weight_display(usual_weight)}")
        for config in usual_fields:
            self._print_schema_primary(config, "    ", color_name)

        exam_weight = sum(
            float(self._schema_config_value(c, "weight", 0) or 0)
            for c in exam_fields
        )
        print(f"  {self._color('exam', color_name, bright=True)} course_weight={self._schema_weight_display(exam_weight)}")
        for config in exam_fields:
            self._print_schema_primary(config, "    ", color_name)

        other_fields = [
            c for c in primary_configs
            if self._schema_config_value(c, "group") not in ["usual", "exam"]
        ]
        if other_fields:
            print(f"  {self._color('other group', color_name, bright=True)}")
            for config in other_fields:
                self._print_schema_primary(config, "    ", color_name)

        print()

    def _schema_rows(self, schema, source):
        rows = []
        primary_configs = self._schema_primary_configs(schema)
        for config in primary_configs:
            rows.append([
                source,
                "primary",
                self._schema_config_value(config, "name"),
                self._schema_config_value(config, "alias"),
                self._schema_config_value(config, "max_score"),
                self._schema_config_value(config, "mode"),
                self._schema_config_value(config, "weight"),
                self._schema_config_value(config, "group"),
            ])
        for config in self._schema_secondary_configs(schema):
            rows.append([
                source,
                "secondary",
                self._schema_config_value(config, "name"),
                self._schema_config_value(config, "alias"),
                "",
                "",
                "",
                self._schema_config_value(config, "group"),
            ])
        return rows

    def show_field_schema(self, scope="all"):
        scope = scope or "all"
        if scope not in ["all", "cache", "file"]:
            print_info(2, "Usage: schema [cache|file|all]")
            return

        if scope in ["all", "cache"]:
            self._print_schema_tree(self.manager.course.export_field_schema(), "cache")

        if scope in ["all", "file"]:
            file_schema, path, msg = self.manager.read_file_field_schema()
            if file_schema:
                self._print_schema_tree(file_schema, "file", path)
            else:
                print_info(1, msg)

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

    def show_lab_schema(self):
        schema = self.manager.lab_course.schema
        mode = schema.get("mode", "exam")
        def course_weight(field_name):
            config = self.manager.course.primary_fields.get(field_name)
            if not config:
                return "-"
            return self._schema_format_number(config.get("weight", 0))

        print(self._color("LAB schema", "CYAN", bright=True))
        print(f"mode={mode}")
        if mode == "split":
            print(f"  lab_usual -> course usual, course field weight={course_weight('lab_usual')}")
            print(f"  lab_exam  -> course exam,  course field weight={course_weight('lab_exam')}")
        elif mode == "usual":
            print(f"  lab -> course usual, course field weight={course_weight('lab')}")
        else:
            print(f"  lab -> course exam, course field weight={course_weight('lab')}")
        print("course mix weights are configured by change field ... -w")

        print("experiments:")
        if not self.manager.lab_course.experiments:
            print("  (none)")
            return
        for exp_no, exp in self.manager.lab_course.experiments.items():
            group = self.manager.lab_course.experiment_group(exp_no)
            print(f"  - {exp_no}:{exp.name}, weight={exp.weight:g}, group={group}")
    
    def show_students(self, students, global_mode=None, field_modes=None, show_extra=False):
        if isinstance(students, Iterable):
            if self.manager.course.has_lab_fields():
                self.show_students_with_lab_breakdown(students, global_mode, field_modes, show_extra)
                return
            tab = PrettyTable()
            tab.border = True
            fields = self.manager.course.all_display_field_names()
            field_modes_by_name = {
                field: self._resolve_display_mode(field, global_mode, field_modes)
                for field in fields
            }
            tab.field_names = ['No.', 'Name', 'ID'] + [
                self._field_header(field, field_modes_by_name[field])
                for field in fields
            ]
            for s in students:
                row = [s.N, s.name, s.id]
                for field in fields:
                    mode = field_modes_by_name[field]
                    score = self.manager.course.display_field_score(s, field, mode)
                    extra = self.manager.course.display_field_extra(s, field, mode) if show_extra else 0
                    row.append(self._format_score_with_extra(score, extra, mode) if show_extra else self._format_score(score))
                tab.add_row(row)
            print(tab)
        elif isinstance(students, Student):
            if self.manager.course.has_lab_fields():
                self.show_students_with_lab_breakdown([students], global_mode, field_modes, show_extra)
                return
            print_score = f"{students.N}-{students.name}({students.id}): "
            for field in self.manager.course.all_display_field_names():
                mode = self._resolve_display_mode(field, global_mode, field_modes)
                score = self.manager.course.display_field_score(students, field, mode)
                extra = self.manager.course.display_field_extra(students, field, mode) if show_extra else 0
                display_score = self._format_score_with_extra(score, extra, mode) if show_extra else self._format_score(score)
                print_score += f"{self._field_header(field, mode)}:{display_score}, "
            print(print_score)
        else:
            return 2, f"Unknown Student {students}"

    def _student_lab_breakdown_row(self, student, theory_fields, has_usual_lab, has_exam_lab, global_mode=None, field_modes=None, show_extra=False):
        row = [student.N, student.name, student.id]
        for field in theory_fields:
            mode = self._resolve_display_mode(field, global_mode, field_modes)
            score = self.manager.course.display_field_score(student, field, mode)
            extra = self.manager.course.display_field_extra(student, field, mode) if show_extra else 0
            row.append(self._format_score_with_extra(score, extra, mode) if show_extra else self._format_score(score))

        row.append(self._format_score(self.manager.course.theory_group_percent(student, "usual")))
        if has_usual_lab:
            row.append(self._format_score(self.manager.course.lab_group_percent(student, "usual")))
            row.append(self._format_score(self.manager.course.calculate_field_score(student, "usual")))

        row.append(self._format_score(self.manager.course.theory_group_percent(student, "exam")))
        if has_exam_lab:
            row.append(self._format_score(self.manager.course.lab_group_percent(student, "exam")))
            row.append(self._format_score(self.manager.course.display_field_score(student, "exam", "percent")))
        row.append(self._format_score(self.manager.course.calculate_field_score(student, "total")))
        return row

    def show_students_with_lab_breakdown(self, students, global_mode=None, field_modes=None, show_extra=False):
        if isinstance(students, Student):
            students = [students]
        theory_fields = [
            field for field, config in self.manager.course.primary_fields.items()
            if field not in LAB_MANAGED_FIELDS and config.get("group") != "exam"
        ]
        has_usual_lab = self.manager.course.has_lab_group("usual")
        has_exam_lab = self.manager.course.has_lab_group("exam")
        headers = ['No.', 'Name', 'ID']
        headers.extend([
            self._field_header(field, self._resolve_display_mode(field, global_mode, field_modes))
            for field in theory_fields
        ])
        headers.append('t-usual(%)')
        if has_usual_lab:
            headers.extend(['l-usual(%)', 'usual(%)'])
        headers.append('t-exam(%)')
        if has_exam_lab:
            headers.extend(['l-exam(%)', 'exam(%)'])
        headers.append('total(pt)')

        tab = PrettyTable()
        tab.border = True
        tab.field_names = headers
        for student in students:
            tab.add_row(self._student_lab_breakdown_row(student, theory_fields, has_usual_lab, has_exam_lab, global_mode, field_modes, show_extra))
        print(tab)

    def _score_as_field_percent(self, field, score):
        field = self.manager.course.normalize_field_name(field)
        config = self.manager.course.primary_fields.get(field)
        if not config or not config["max_score"]:
            return 0
        return float(score) / config["max_score"] * 100

    def _students_matching_names(self, names):
        name_set = set(names)
        return [
            student
            for student in self.manager.course.students.values()
            if student.name in name_set
        ]

    def _parse_log_name_list(self, raw_names):
        try:
            names = ast.literal_eval(raw_names)
            if isinstance(names, list):
                return [str(name) for name in names]
        except (SyntaxError, ValueError):
            pass
        return [
            name.strip().strip("'\"")
            for name in raw_names.strip("[]").split(",")
            if name.strip()
        ]

    def _daily_log_records(self, target_date):
        single_re = re.compile(
            r"^Record: (?P<no>\d+)-(?P<name>.+)\[(?P<sid>[^\]]+)\]: "
            r"\+(?P<score>[-+]?\d+(?:\.\d+)?)(?:\((?P<field>[^)]+)\))"
        )
        batch_re = re.compile(
            r"^Batch record: \+(?P<score>[-+]?\d+(?:\.\d+)?)(?:\((?P<field>[^)]+)\)) "
            r"for students(?P<excluding> excluding)?: (?P<names>\[.*\])$"
        )

        for line in self.manager.logger.log:
            log_match = re.match(r"^\[(?P<date>\d{4}-\d{2}-\d{2}) [^\]]+\] (?P<message>.*)$", line.strip())
            if not log_match or log_match.group("date") != target_date:
                continue
            message = log_match.group("message")

            single_match = single_re.match(message)
            if single_match:
                field = self.manager.course.normalize_field_name(single_match.group("field"))
                if field not in self.manager.course.primary_fields:
                    continue
                student = self.manager.course.students.get(single_match.group("sid"))
                if not student:
                    student = self.manager.course.find_students_by_nos(int(single_match.group("no")))
                if student:
                    yield student, field, float(single_match.group("score"))
                continue

            batch_match = batch_re.match(message)
            if batch_match:
                field = self.manager.course.normalize_field_name(batch_match.group("field"))
                if field not in self.manager.course.primary_fields:
                    continue
                names = self._parse_log_name_list(batch_match.group("names"))
                listed_students = self._students_matching_names(names)
                listed_ids = {student.id for student in listed_students}
                if batch_match.group("excluding"):
                    students = [
                        student for student in self.manager.course.students.values()
                        if student.id not in listed_ids
                    ]
                else:
                    students = listed_students
                for student in students:
                    yield student, field, float(batch_match.group("score"))

    def show_daily_scores(self, target_date, parts):
        if not parts:
            students = list(self.manager.course.students.values())
        elif len(parts) == 2 and parts[0] == "-n":
            students = self.manager.course.find_students_by_nos([int(n) for n in parts[1].split(',')])
        elif len(parts) == 2 and parts[0] == "-N":
            students = self.manager.course.find_students_by_names([n for n in parts[1].split(',')])
        else:
            print_info(2, "Usage: show -d YYYY-MM-DD [-n No1,No2 | -N name1,name2]")
            return

        fields = self.manager.course.all_primary_field_names()
        daily_scores = {
            student.id: {field: 0 for field in fields}
            for student in self.manager.course.students.values()
        }
        for student, field, score in self._daily_log_records(target_date):
            if student.id in daily_scores:
                daily_scores[student.id][field] += self._score_as_field_percent(field, score)

        tab = PrettyTable()
        tab.title = f"Daily scores on {target_date}"
        tab.field_names = ['No.', 'Name', 'ID'] + [f"{field}(%)" for field in fields]
        for student in sorted(students, key=lambda s: s.N):
            scores = [self._format_score(daily_scores[student.id][field]) for field in fields]
            tab.add_row([student.N, student.name, student.id] + scores)
        print(tab)

    def show_lab_students(self, students):
        if isinstance(students, Iterable):
            tab = PrettyTable()
            tab.border = True
            experiments = list(self.manager.lab_course.experiments.values())
            tab.field_names = (
                ['Lab No.', 'Name', 'ID']
                + [f"{e.exp_no}:{e.name}({e.weight:g})" for e in experiments]
                + ['Lab Usual', 'Lab Exam', 'Lab Total']
            )
            for s in students:
                row = [s.N, s.name, s.id]
                for e in experiments:
                    record = s.lab_scores.get(e.exp_no)
                    row.append(record[1] if record else '')
                row.append(round(self.manager.lab_course.calculate_schema_score(s, "usual"), 2))
                row.append(round(self.manager.lab_course.calculate_schema_score(s, "exam"), 2))
                row.append(round(self.manager.lab_course.calculate_schema_score(s), 2))
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
            show [-N name1,name2,... | -n student_No1,student_No2,...] [-m point|percent|field=mode,...] [--extra]
            show -d YYYY-MM-DD [-N name1,name2,... | -n student_No1,student_No2,...]
            show field [cache|file|all]
        Examples:
            1.show all students' scores: show
            2.show students' score with No.=1,2,3: show -n 1,2,3
            3.show students' score with name=john: show -N john
            4.show all scores as percent: show -m percent
            5.show default modes but exam as points: show -m exam=point
            6.show capped scores with extra-performance notes: show --extra
            7.show field schema comparison: show field
            8.show daily equivalent scores: show -d 2026-07-01
        '''
        if not self._theory_enabled():
            return
        raw_parts = args.split() if args else []
        if raw_parts and raw_parts[0] == "field":
            if len(raw_parts) > 3 or (len(raw_parts) > 1 and raw_parts[1] != "schema" and len(raw_parts) > 2):
                print_info(2, "Usage: show field [schema] [cache|file|all]")
                return
            if len(raw_parts) > 1 and raw_parts[1] == "schema":
                scope = raw_parts[2] if len(raw_parts) == 3 else "all"
            else:
                scope = raw_parts[1] if len(raw_parts) == 2 else "all"
            self.show_field_schema(scope)
            return
        raw_parts, target_date, date_msg = self._parse_date_flag(raw_parts)
        if date_msg:
            print_info(2, date_msg)
            return
        if target_date:
            self.show_daily_scores(target_date, raw_parts)
            return
        parts, global_mode, field_modes, msg = self._parse_display_modes(raw_parts) if args else ([], None, {}, None)
        if msg:
            print_info(2, msg)
            return
        parts, show_extra = self._parse_extra_flag(parts)
        if not parts:
            self.show_students(self.manager.course.students.values(), global_mode, field_modes, show_extra)
            return
        if len(parts) != 2:
            print_info(2, "Usage: show [-N/-n <student_name>/<student_No>] [-m point|percent|field=mode,...] [--extra]")
            return

        if parts[0] == '-N':
            names = [n for n in parts[1].split(',')]
            students = self.manager.course.find_students_by_names(names)
            self.show_students(students, global_mode, field_modes, show_extra)

        elif parts[0] == '-n':
            nos = [int(s) for s in parts[1].split(',')]
            students = self.manager.course.find_students_by_nos(nos)
            self.show_students(students, global_mode, field_modes, show_extra)
    
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
            print(f"Usage: rd <student_No.> <field> <score>")
            return
        field_name = self.manager.course.normalize_field_name(args[1])
        if field_name not in self.manager.course.primary_fields:
            print_info(2, f"Field must be one of {self.manager.course.all_primary_field_names()}")
            return
        if field_name in self.manager.course.external_score_providers:
            print_info(2, f"{field_name} is computed from lab records. Use lab rd/brd instead.")
            return
        else:
            s = self.manager.course.find_students_by_nos(int(args[0]))
            if not s:
                return 
            score = float(args[2])
            self.manager.push_undo(f"record +{score}({field_name}) for {s.N}-{s.name}[{s.id}]")
            s.add_score(field_name, score)
            print(f"{s.N}-{s.name}[{s.id}]:"+ Fore.GREEN + Style.BRIGHT + f" +{self._format_score(score)}" + Style.RESET_ALL + f"({field_name})!")
            self.manager.logger.add(f"Record: {s.N}-{s.name}[{s.id}]: +{self._format_score(score)}({field_name})")
            
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
            print("Usage: brd <student_No1,student_No2,> <field> <score> {-e}")
            return
        field_name = self.manager.course.normalize_field_name(args[1])
        if field_name not in self.manager.course.primary_fields:
            print(f"Field must be one of {self.manager.course.all_primary_field_names()}")
            return
        if field_name in self.manager.course.external_score_providers:
            print_info(2, f"{field_name} is computed from lab records. Use lab rd/brd instead.")
            return
        else:
            students = self.manager.course.find_students_by_nos([int(n) for n in args[0].split(',')])
            exclusion = '-e' in args
            score = float(args[2])
            self.manager.push_undo(f"batch record +{score}({field_name})")
            f, msg = self.manager.course.add_scores(students, field_name, score, exclusion)
            print_info(f, msg)
            if not f:
                self.manager.logger.add(f"Batch record: +{self._format_score(score)}({field_name}) for students{' excluding:' if exclusion else ':'} {[s.name for s in students]}")
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
            log [-n student_No1,student_No2,...] [-c] [-a] [-h] [-e] [all] [-m point|percent|field=mode,...]
        Examples:
            1.show the last 20 (batched) logs for the whole class: log
            2.show class participation logs of students with No.=1,2,3: log -n 1,2,3 -c
            3.show all types of logs of students with No.=1,2,3: log -n 1,2,3 all
            4.the same as 3: log -n 1,2,3
            5.show score records in percent display mode: log -n 1 -m percent
        '''
        if not self._theory_enabled():
            return
        if args:
            parts, global_mode, field_modes, msg = self._parse_display_modes(args.split())
            if msg:
                print_info(2, msg)
                return
            if '-n' in parts:
                ns = parts[parts.index("-n")+1]
                students = self.manager.course.find_students_by_nos([int(n) for n in ns.split(',')])
            else:
                students = self.manager.course.students.values()
            
            data = []
            if students:
                requested_fields = [
                    self.manager.course.normalize_field_name(t.lstrip('-'))
                    for t in parts
                    if t not in ["-n", "all"]
                ]
                selected_fields = [
                    field for field in self.manager.course.all_primary_field_names()
                    if field in requested_fields
                ]
                if not selected_fields:
                    selected_fields = self.manager.course.all_primary_field_names()
                for s in students:
                    for field in selected_fields:
                        s.ensure_score_field(field)
                        for d, sc in s.scores[field]:
                            data.append((s.N, s.name, s.id, field, d, sc))
                data.sort(key=lambda x: (x[4], x[3]))
                tab = PrettyTable()
                tab.field_names = ['Date', 'No.', 'Name', 'ID', 'Score', 'Type']
                for d_no, name, sid, field, date, score in data:
                    mode = self._resolve_display_mode(field, global_mode, field_modes)
                    display_score = self.manager.course.display_record_score(field, score, mode)
                    tab.add_row([date, d_no, name, sid, "+" + self._format_score(display_score, mode), field])
                print(tab)
        else:
            for log in self.manager.logger.log[-20:]:
                print(log.strip())
    
    def do_tops(self, args):
        '''
        Show top N students by score type.
        Usage: tops [-n N] [-t type] [-m point|percent|field=mode,...] [--extra]
        type: t/u/e/h/a/c
        Examples:
            1.show top 5 students by total score: tops
            2.show top 3 students by usual score: tops -n 3 -t u
            3.show top 10 students by exam score: tops -n 10 -t e
            4.show top 5 students by homework score: tops -t h
            5.show last 5 students by homework score: tops -n -5 -t h
            6.show exam contribution points: tops -t e -m point
            7.show extra-performance notes: tops --extra
        '''
        if not self._theory_enabled():
            return
        n = 5
        rank_by = "total"
        parts, global_mode, field_modes, msg = self._parse_display_modes(args.split()) if args else ([], None, {}, None)
        if msg:
            print_info(2, msg)
            return
        parts, show_extra = self._parse_extra_flag(parts)
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
                rank_by = self.manager.course.normalize_field_name(parts[parts.index("-t")+1])
            except:
                print_info(2, f"please provide a valid type after -t: {self.manager.course.all_display_field_names()}")
                return
        
        display_mode = self._resolve_display_mode(rank_by, global_mode, field_modes)
        ranked = self.manager.course.get_top_students(n, rank_by, display_mode)
        if not ranked:
            print_info(2, f"Unknown rank field: {rank_by}")
            return
        title = f"Ranked by {rank_by} score"
        title += f'(TOP-{n}): ' if n > 0 else f'(LAST-{abs(n)}): '
        tab = PrettyTable()
        tab.title = title
        tab.field_names = ['RANK', 'No.', 'Name', 'ID', self._field_header('Score', display_mode)]
        for i, (s, score) in enumerate(ranked):
            extra = self.manager.course.display_field_extra(s, rank_by, display_mode) if show_extra else 0
            display_score = self._format_score_with_extra(score, extra, display_mode) if show_extra else self._format_score(score)
            tab.add_row([i, s.N, s.name, s.id, display_score])
        print(tab)

    def do_schema(self, args):
        '''
        Show current field schema from memory cache and/or the JSON score file.
        Usage: schema [cache|file|all]
        '''
        if not self._theory_enabled():
            return
        parts = args.split()
        if len(parts) > 1:
            print_info(2, "Usage: schema [cache|file|all]")
            return
        self.show_field_schema(parts[0] if parts else "all")

    def do_field(self, args):
        '''
        Show field schema.
        Usage: field schema [cache|file|all]
        '''
        if not self._theory_enabled():
            return
        parts = args.split()
        if not parts or parts[0] != "schema" or len(parts) > 2:
            print_info(2, "Usage: field schema [cache|file|all]")
            return
        self.show_field_schema(parts[1] if len(parts) == 2 else "all")
    
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
        if parts[0] == "field":
            print_info(1, "Field schema is fixed. Use change field <class_p|attendance|homework|exam> to modify weights or scoring mode.")
            return

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
        
    def add_field(self, parts):
        '''
        Deprecated. The score schema is fixed; use change field instead.
        '''
        print_info(1, "Field schema is fixed. Use change field <class_p|attendance|homework|exam> to modify weights or scoring mode.")

    def do_change(self, args):
        '''
        Change a score field.
        Usage:
            change field <field_name> [-n new_name] [-m max_score] [-s points|percent] [-w weight] [-a alias]
        Notes:
            - Use -a none to clear an alias.
            - "change filed ..." is also accepted as a typo-tolerant form.
        '''
        if not self._theory_enabled():
            return
        parts = args.split()
        if len(parts) < 2 or parts[0] not in ["field", "filed"]:
            print_info(2, "Usage: change field <field_name> [-n new_name] [-m max_score] [-s points|percent] [-w weight] [-a alias]")
            return

        field_name = parts[1]
        idx = 2
        new_name = None
        max_score = None
        mode = None
        weight = None
        fields = None
        alias = None
        alias_changed = False

        while idx < len(parts):
            option = parts[idx]
            if idx + 1 >= len(parts):
                print_info(2, f"Please provide a value after {option}")
                return
            value = parts[idx + 1]
            if option == "-n":
                new_name = value
            elif option == "-m":
                max_score = value
            elif option == "-s":
                mode = value
            elif option == "-w":
                weight = value
            elif option == "-f":
                fields = [field for field in value.split(',') if field]
            elif option == "-a":
                alias_changed = True
                alias = None if value in ["none", "None", "null", "-"] else value
            else:
                print_info(2, f"Unknown option for change field: {option}")
                return
            idx += 2

        normalized_field_name = self.manager.course.normalize_field_name(field_name)
        if normalized_field_name in LAB_MANAGED_FIELDS:
            if weight is None or new_name or max_score is not None or mode is not None or fields is not None or alias_changed:
                print_info(2, "Lab computed fields can only change course mix weight. Use: change field <lab|lab_usual|lab_exam> -w <weight>")
                return

        self.manager.push_undo(f"change field {field_name}")
        f, msg = self.manager.course.change_field(
            field_name,
            new_name=new_name,
            max_score=max_score,
            mode=mode,
            weight=weight,
            fields=fields,
            alias=alias,
            alias_changed=alias_changed,
        )
        if not f:
            self.manager.logger.add(f"Changed field {field_name}")
        else:
            self.manager.rollback_undo()
        print_info(f, msg)

                
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
            lab schema [mode|map]
            lab help [command]
        '''
        if not self._lab_enabled():
            return

        parts = args.split()
        if not parts:
            print_info(1, "Usage: lab import/add-exp/add/rm/rd/brd/show/find/tops/log/schema/help ...")
            return

        cmd = parts[0]
        if cmd == "help":
            if len(parts) > 2:
                print_info(2, "Usage: lab help [command]")
                return
            self.show_lab_help(parts[1] if len(parts) == 2 else None)
            return

        if cmd == "schema":
            if len(parts) == 1:
                self.show_lab_schema()
                return
            if parts[1] == "mode":
                if len(parts) != 3:
                    print_info(2, "Usage: lab schema mode exam|usual|split")
                    return
                self.manager.push_undo(f"lab schema mode {parts[2]}", scope="lab")
                f, msg = self.manager.lab_course.set_schema_mode(parts[2])
                if not f:
                    self.manager.sync_lab_schema()
                    self.manager.lab_logger.add(f"Changed lab schema mode to {parts[2]}")
                else:
                    self.manager.rollback_undo()
                print_info(f, msg)
                return
            if parts[1] in ["map", "group"]:
                if len(parts) != 4:
                    print_info(2, "Usage: lab schema map <exp_no1,exp_no2,...> usual|exam")
                    return
                exp_nos = [exp_no for exp_no in parts[2].split(',') if exp_no]
                self.manager.push_undo(f"lab schema map {parts[2]} {parts[3]}", scope="lab")
                f, msg = self.manager.lab_course.set_experiment_group(exp_nos, parts[3])
                if not f:
                    self.manager.sync_lab_schema()
                    self.manager.lab_logger.add(f"Changed lab schema experiment group: {parts[2]} -> {parts[3]}")
                else:
                    self.manager.rollback_undo()
                print_info(f, msg)
                return
            if parts[1] == "weight":
                print_info(2, "Lab schema no longer stores course mix weights. Use: change field <lab|lab_usual|lab_exam> -w <weight>")
                return
            print_info(2, "Usage: lab schema [mode|map]")
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
                self.manager.sync_lab_schema()
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
                    self.manager.sync_lab_schema()
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
                    self.manager.sync_lab_schema()
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
                    self.manager.sync_lab_schema()
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
                self.manager.sync_lab_schema()
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
                self.manager.sync_lab_schema()
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
                    (s, round(self.manager.lab_course.calculate_schema_score(s), 2))
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
