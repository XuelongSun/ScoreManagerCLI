import sys
from cli import *

if __name__ == "__main__":
    # get cmd args
    args = sys.argv[1:]
    if args:
        class_name = args[0]
        cli = StudentManagerCIL(class_name)
    else:
        print_info(1, "No class name provided, using default 'course1'")
        cli = StudentManagerCIL()
    
    cli.cmdloop()