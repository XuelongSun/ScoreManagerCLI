# ScoreManagerCLI
A CLI tool for course score management
```shell
python main.py course_name
```

Optional startup arguments:
```shell
python main.py course_name --mode all
python main.py course_name --mode theory
python main.py course_name --mode lab
python main.py course_name --workdir ./data
```

Theory scores use the original commands:
```shell
import theory_students.csv
rd 2 c 1
brd 1,2,3 h 5
```

Theory fields use a fixed schema: `class_p`, `attendance`, `homework`, `exam`, plus computed `usual` and `total`.

The scoring mode can be changed with `change field`:
```shell
change field class_p -m 20 -s points -w 20
change field attendance -m 8 -s points -w 8
change field homework -m 12 -s points -w 12
change field exam -m 100 -s percent -w 60
```

`points` mode records points directly into the final score, capped by `max_score` and `weight`.
`percent` mode records 0-100 scores and contributes `average_percent * weight / 100`.

The computed `usual` field is the usual-score percentage needed by school exam systems:
```shell
usual = (class_p + attendance + homework contribution) / usual_weight * 100
total = usual contribution + exam contribution
```

Examples:
```shell
rd 2 c 1
rd 2 homework 4
rd 2 exam 90
tops -t usual
```

Score display can use each field's default mode, or be forced globally/per field:
```shell
show
show -m percent
show -m points,exam=percent
show --extra
show -d 2026-07-01
log -n 1 -m percent
tops -t exam -m point
tops --extra
```

Displayed scores are marked as `(pt)` for points that count into the final score, and `(%)` for percentage style scores.
When `--extra` is used, primary fields that exceed the field cap show an extra-performance note, such as `20(+3)` or `100(+15%)`.
`show -d YYYY-MM-DD` reads the activity log for that day and shows each student's daily equivalent score by primary field. For example, an attendance record of `+2` with `attendance.max_score=8` is shown as `25` because `2 / 8 * 100 = 25`.

Field schema can be checked against the in-memory cache and the JSON score file:
```shell
schema
schema cache
schema file
field schema
show field schema
```
Schema output is shown as a hierarchy from `total` to `usual`/exam groups and primary fields, with weights and field settings. Cache and file schemas are displayed in different colors.

Lab scores are managed separately with an independent roster:
```shell
lab import lab_students.csv
lab add-exp exp1 Experiment_1 0.3
lab add-exp exp2 Experiment_2 0.7
lab rd 2 exp1 88
lab tops -t total
lab tops -t exp1
lab find Alice
lab help rd
lab show
```

`lab show` displays each experiment plus `Lab Usual`, `Lab Exam`, and `Lab Total`.

When lab roster/experiments exist, the theory field schema automatically includes lab-managed fields. Their scores are computed from each matching lab student's weighted lab total, matched by student ID.
Theory commands cannot record `lab` directly; use `lab rd` or `lab brd`.

Lab scoring can be configured separately:
```shell
lab schema
lab schema mode exam
lab schema mode usual
lab schema mode split
lab schema map exp1,exp2 usual
lab schema map exp3 exam
change field lab -w 20
change field lab_usual -w 10
change field lab_exam -w 20
```

Experiment weights from `lab add-exp` are used inside the lab score calculation. Lab field weights are normal child-field weights in the course `field_schema` and changed with `change field ... -w`. In `exam` mode, lab is added under the course exam group. In `usual` mode, lab is added under the course usual group. In `split` mode, `lab_usual` is added under usual and `lab_exam` is added under exam. The course weight of `usual` or `exam` is the sum of all child fields in that group, including lab fields. If the total course weight is greater than 100, schema display highlights it as a warning.

When a course has lab data, theory `show` uses a breakdown view with theory/lab components and the composed `usual` or `exam` score when that group contains lab. The theory-side exam field is named `theory_exam` to distinguish it from `lab_exam`.
