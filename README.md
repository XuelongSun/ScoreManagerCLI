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
