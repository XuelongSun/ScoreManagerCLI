import argparse
from cli import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Student score manager CLI")
    parser.add_argument("course_name", nargs="?", default="course1")
    parser.add_argument("--mode", choices=["all", "theory", "lab"], default="all")
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args()

    if args.course_name == "course1":
        print_info(1, "No class name provided, using default 'course1'")
    cli = StudentManagerCIL(args.course_name, mode=args.mode, working_dir=args.workdir)
    
    cli.cmdloop()
