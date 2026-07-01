import datetime
from collections.abc import Iterable
from typing import Dict

DEFAULT_PRIMARY_FIELDS = [
    {"name": "class_p", "alias": "c", "max_score": 20, "mode": "points", "weight": 20, "group": "usual"},
    {"name": "attendance", "alias": "a", "max_score": 8, "mode": "points", "weight": 8, "group": "usual"},
    {"name": "homework", "alias": "h", "max_score": 12, "mode": "points", "weight": 12, "group": "usual"},
    {"name": "exam", "alias": "e", "max_score": 100, "mode": "percent", "weight": 60, "group": "exam"},
]

DEFAULT_SECONDARY_FIELDS = [
    {"name": "usual", "alias": "u", "group": "usual"},
    {"name": "total", "alias": "t", "group": "total"},
]

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
        self.scores = {}
        for st in SCORE_TYPE.values():
            self.ensure_score_field(st)

    def ensure_score_field(self, field_name):
        if not hasattr(self, "scores"):
            self.scores = {}
        if field_name not in self.scores:
            self.scores[field_name] = []
        setattr(self, field_name, self.scores[field_name])
    
    def add_score(self, st, sv):
        date = datetime.date.today().strftime("%Y-%m-%d")
        field_name = SCORE_TYPE.get(st, st)
        self.ensure_score_field(field_name)
        self.scores[field_name].append([date, sv])
        
    def calculate_score(self, fields=None):
        fields = fields or list(SCORE_TYPE.values())
        tmp = []
        for st in fields:
            self.ensure_score_field(st)
            tmp.append(sum(score[1] for score in self.scores[st]))
        return tuple(tmp)

    def raw_score(self, field_name):
        self.ensure_score_field(field_name)
        return sum(score[1] for score in self.scores[field_name])


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
        self.primary_fields = {}
        self.secondary_fields = {}
        self.field_aliases = {}
        self._init_default_fields()

    def _init_default_fields(self):
        for config in DEFAULT_PRIMARY_FIELDS:
            self.add_primary_field(
                config["name"],
                config["max_score"],
                config["mode"],
                config["weight"],
                alias=config["alias"],
                group=config["group"],
                initializing=True,
            )
        for config in DEFAULT_SECONDARY_FIELDS:
            self.secondary_fields[config["name"]] = config.copy()
            self.field_aliases[config["alias"]] = config["name"]

    def normalize_field_name(self, field_name):
        return self.field_aliases.get(field_name, field_name)

    def all_primary_field_names(self):
        return list(self.primary_fields.keys())

    def all_secondary_field_names(self):
        return list(self.secondary_fields.keys())

    def all_display_field_names(self):
        return self.all_primary_field_names() + self.all_secondary_field_names()

    def _normalize_mode(self, mode):
        mode_map = {
            "direct": "points",
            "weighted": "percent",
            "point": "points",
            "points": "points",
            "percent": "percent",
            "percentage": "percent",
        }
        return mode_map.get(mode, mode)

    def _normalize_field_config_input(self, config):
        name = config.get("name")
        return {
            "name": name,
            "alias": config.get("alias"),
            "max_score": config.get("max_score", config.get("max-score", 100)),
            "mode": config.get("mode", "direct"),
            "weight": config.get("weight"),
            "group": config.get("group", "exam" if name == "exam" else "usual"),
            "fields": config.get("fields", []),
        }

    def normalize_display_mode(self, mode):
        mode = self._normalize_mode(mode)
        if mode in ["points", "percent"]:
            return mode
        return None

    def display_mode_suffix(self, mode):
        mode = self.normalize_display_mode(mode)
        return "(%)" if mode == "percent" else "(pt)"

    def _make_field_config(self, name, max_score, mode, weight=None, alias=None, fields=None, group="usual"):
        if not name:
            return None, "Field name must not be empty"
        if name in ["No.", "Name", "ID"]:
            return None, "No., Name, and ID are reserved display fields"
        mode = self._normalize_mode(mode)
        if mode not in ["points", "percent"]:
            return None, "Mode must be points or percent"
        try:
            max_score = float(max_score)
        except (TypeError, ValueError):
            return None, "Max score must be a number"
        if max_score <= 0:
            return None, "Max score must be positive"
        if weight is None:
            weight = max_score if mode == "points" else 0
        else:
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                return None, "Weight must be a number"
            if weight > 1:
                weight = weight
            if weight < 0:
                return None, "Weight must not be negative"
        if group not in ["usual", "exam"]:
            return None, "Group must be usual or exam"
        return {
            "name": name,
            "alias": alias,
            "max_score": max_score,
            "mode": mode,
            "weight": weight,
            "group": group,
            "fields": fields or [],
        }, ""

    def add_primary_field(self, name, max_score, mode, weight=None, alias=None, group="usual", initializing=False):
        if name in self.primary_fields or name in self.secondary_fields:
            return 2, f"Field {name} already exists"
        if alias and alias in self.field_aliases:
            return 2, f"Field alias {alias} already exists"
        config, msg = self._make_field_config(name, max_score, mode, weight, alias=alias, group=group)
        if not config:
            return 2, msg
        self.primary_fields[name] = config
        if alias:
            self.field_aliases[alias] = name
        for student in self.students.values():
            student.ensure_score_field(name)
        return 0, f"Primary field {name} added successfully"

    def add_secondary_field(self, name, max_score, mode, weight=None, fields=None, alias=None, initializing=False):
        return 2, "Secondary fields are fixed: usual and total"

    def _find_field_level(self, name):
        name = self.normalize_field_name(name)
        if name in self.primary_fields:
            return "primary", name
        if name in self.secondary_fields:
            return "secondary", name
        return None, name

    def change_field(self, name, new_name=None, max_score=None, mode=None, weight=None, fields=None, alias=None, alias_changed=False):
        level, name = self._find_field_level(name)
        if not level:
            return 2, f"Field {name} not found"
        if level == "secondary":
            return 2, "Secondary fields are computed automatically; change primary field weights or modes instead"

        configs = self.primary_fields if level == "primary" else self.secondary_fields
        old_config = configs[name]
        updated = old_config.copy()

        if new_name:
            if new_name in ["No.", "Name", "ID"]:
                return 2, "No., Name, and ID are reserved display fields"
            if new_name != name and (new_name in self.primary_fields or new_name in self.secondary_fields):
                return 2, f"Field {new_name} already exists"
            updated["name"] = new_name

        if max_score is not None:
            try:
                max_score = float(max_score)
            except (TypeError, ValueError):
                return 2, "Max score must be a number"
            if max_score <= 0:
                return 2, "Max score must be positive"
            updated["max_score"] = max_score

        if mode is not None:
            mode = self._normalize_mode(mode)
            if mode not in ["points", "percent"]:
                return 2, "Mode must be points or percent"
            updated["mode"] = mode

        if weight is not None:
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                return 2, "Weight must be a number"
            if weight < 0:
                return 2, "Weight must not be negative"
            updated["weight"] = weight

        if fields is not None:
            return 2, "Child fields are fixed by the standard schema"

        if alias_changed:
            if alias and alias in self.field_aliases and self.field_aliases[alias] != name:
                return 2, f"Field alias {alias} already exists"
            updated["alias"] = alias

        final_name = updated["name"]
        if final_name != name:
            configs.pop(name)
            configs[final_name] = updated

            for alias_key, alias_target in list(self.field_aliases.items()):
                if alias_target == name:
                    self.field_aliases[alias_key] = final_name

            if level == "primary":
                for student in self.students.values():
                    student.ensure_score_field(name)
                    if final_name not in student.scores:
                        student.scores[final_name] = student.scores.pop(name)
                    else:
                        student.scores[final_name].extend(student.scores.pop(name))
                    setattr(student, final_name, student.scores[final_name])
                    if hasattr(student, name):
                        delattr(student, name)
        else:
            configs[name] = updated

        old_alias = old_config.get("alias")
        if alias_changed:
            if old_alias in self.field_aliases:
                self.field_aliases.pop(old_alias)
            if alias:
                self.field_aliases[alias] = final_name

        return 0, f"{level.capitalize()} field {final_name} changed successfully"

    def load_field_schema(self, schema):
        self.primary_fields = {}
        self.secondary_fields = {}
        self.field_aliases = {}
        primary_configs = schema.get("primary", [])
        if isinstance(primary_configs, dict):
            primary_configs = [
                dict(config, name=name) if isinstance(config, dict) and "name" not in config else config
                for name, config in primary_configs.items()
            ]
        loaded_names = set()
        for raw_config in primary_configs:
            config = self._normalize_field_config_input(raw_config)
            self.add_primary_field(
                config["name"],
                config["max_score"],
                config["mode"],
                config["weight"],
                alias=config.get("alias"),
                group=config["group"],
                initializing=True,
            )
            loaded_names.add(config["name"])
        for default_config in DEFAULT_PRIMARY_FIELDS:
            if default_config["name"] not in loaded_names:
                self.add_primary_field(
                    default_config["name"],
                    default_config["max_score"],
                    default_config["mode"],
                    default_config["weight"],
                    alias=default_config["alias"],
                    group=default_config["group"],
                    initializing=True,
                )
        for config in DEFAULT_SECONDARY_FIELDS:
            self.secondary_fields[config["name"]] = config.copy()
            self.field_aliases[config["alias"]] = config["name"]
        if not self.primary_fields:
            self._init_default_fields()

    def export_field_schema(self):
        return {
            "primary": [config.copy() for config in self.primary_fields.values()],
            "secondary": [config.copy() for config in self.secondary_fields.values()],
        }

    def calculate_primary_score(self, student, field_name):
        field_name = self.normalize_field_name(field_name)
        if field_name not in self.primary_fields:
            return 0
        return self._field_display_score(student, self.primary_fields[field_name])

    def calculate_secondary_score(self, student, field_name):
        field_name = self.normalize_field_name(field_name)
        if field_name not in self.secondary_fields:
            return 0
        if field_name == "usual":
            usual_weight = self._group_weight("usual")
            if usual_weight == 0:
                return 0
            return self._group_contribution(student, "usual") / usual_weight * 100
        if field_name == "total":
            return self._group_contribution(student, "usual") + self._group_contribution(student, "exam")
        return 0

    def calculate_field_score(self, student, field_name):
        field_name = self.normalize_field_name(field_name)
        if field_name in self.primary_fields:
            return self.calculate_primary_score(student, field_name)
        if field_name in self.secondary_fields:
            return self.calculate_secondary_score(student, field_name)
        return 0

    def default_display_mode(self, field_name):
        field_name = self.normalize_field_name(field_name)
        if field_name in self.primary_fields:
            return self.primary_fields[field_name]["mode"]
        if field_name == "usual":
            return "percent"
        return "points"

    def display_field_score(self, student, field_name, mode=None):
        field_name = self.normalize_field_name(field_name)
        mode = self.normalize_display_mode(mode) if mode else self.default_display_mode(field_name)
        if field_name in self.primary_fields:
            config = self.primary_fields[field_name]
            if mode == "percent":
                return self._field_percent_score(student, config)
            return self._field_contribution(student, config)
        if field_name == "usual":
            if mode == "percent":
                return self.calculate_secondary_score(student, "usual")
            return self._group_contribution(student, "usual")
        if field_name == "total":
            return self.calculate_secondary_score(student, "total")
        return 0

    def display_field_extra(self, student, field_name, mode=None):
        field_name = self.normalize_field_name(field_name)
        mode = self.normalize_display_mode(mode) if mode else self.default_display_mode(field_name)
        if field_name in self.primary_fields:
            return self._field_extra_display(student, self.primary_fields[field_name], mode)
        return 0

    def display_record_score(self, field_name, score, mode=None):
        field_name = self.normalize_field_name(field_name)
        if field_name not in self.primary_fields:
            return score
        config = self.primary_fields[field_name]
        mode = self.normalize_display_mode(mode) if mode else config["mode"]
        score = float(score)
        if mode == "percent":
            if config["mode"] == "percent":
                return score / config["max_score"] * 100 if config["max_score"] else 0
            return score / config["weight"] * 100 if config["weight"] else 0
        if config["mode"] == "percent":
            return score / config["max_score"] * config["weight"] if config["max_score"] else 0
        return score

    def _field_raw_score(self, student, config):
        student.ensure_score_field(config["name"])
        records = student.scores[config["name"]]
        if not records:
            return 0
        if config["mode"] == "percent":
            return sum(score[1] for score in records) / len(records)
        return sum(score[1] for score in records)

    def _field_display_score(self, student, config):
        raw_score = self._field_raw_score(student, config)
        if config["mode"] == "points":
            return min(raw_score, config["max_score"])
        return min(raw_score, config["max_score"])

    def _field_percent_score(self, student, config):
        score = self._field_display_score(student, config)
        if config["mode"] == "percent":
            return score / config["max_score"] * 100 if config["max_score"] else 0
        if config["weight"]:
            return self._field_contribution(student, config) / config["weight"] * 100
        return 0

    def _field_extra_display(self, student, config, mode):
        extra_points = self._field_extra_contribution(student, config)
        if extra_points <= 0:
            return 0
        if mode == "percent":
            return extra_points / config["weight"] * 100 if config["weight"] else 0
        return extra_points

    def _field_contribution(self, student, config):
        raw_score = self._field_raw_score(student, config)
        if config["mode"] == "points":
            return min(raw_score, config["max_score"], config["weight"])
        if config["max_score"] == 0:
            return 0
        return min(raw_score, config["max_score"]) / config["max_score"] * config["weight"]

    def _field_extra_contribution(self, student, config):
        raw_score = self._field_raw_score(student, config)
        if config["mode"] == "points":
            cap = min(config["max_score"], config["weight"])
            return max(raw_score - cap, 0)
        if config["max_score"] == 0:
            return 0
        extra_raw = max(raw_score - config["max_score"], 0)
        return extra_raw / config["max_score"] * config["weight"]

    def _group_weight(self, group):
        return sum(config["weight"] for config in self.primary_fields.values() if config.get("group") == group)

    def _group_contribution(self, student, group):
        return sum(
            self._field_contribution(student, config)
            for config in self.primary_fields.values()
            if config.get("group") == group
        )

    def _group_extra_contribution(self, student, group):
        return sum(
            self._field_extra_contribution(student, config)
            for config in self.primary_fields.values()
            if config.get("group") == group
        )
    
    def get_top_students(self, n, rank_by, display_mode=None):
        rank_by = self.normalize_field_name(rank_by)
        if rank_by in self.primary_fields or rank_by in self.secondary_fields:
            if display_mode:
                ranked_score = [(s, self.display_field_score(s, rank_by, display_mode)) for s in self.students.values()]
            else:
                ranked_score = [(s, self.calculate_field_score(s, rank_by)) for s in self.students.values()]
        elif rank_by == "total":
            if display_mode:
                ranked_score = [(s, self.display_field_score(s, "total", display_mode)) for s in self.students.values()]
            else:
                ranked_score = [(s, self.calculate_field_score(s, "total")) for s in self.students.values()]
        else:
            return []

        if n < 0:
            return sorted(ranked_score, key=lambda x: x[1])[:abs(n)][::-1]
        else:
            return sorted(ranked_score, key=lambda x: x[1], reverse=True)[:n]
        
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
        s_type = self.normalize_field_name(s_type)
        if s_type not in self.primary_fields:
            return 2, f"Unknown primary field {s_type}"
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
        return 0, f"Batch recorded {x} students' {s_type.capitalize()}"
        
class Logger:
    def __init__(self) -> None:
        self.log = []
    
    def add(self, msg):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.append(f"[{timestamp}] {msg}\n")
