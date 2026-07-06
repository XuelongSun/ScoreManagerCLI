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
