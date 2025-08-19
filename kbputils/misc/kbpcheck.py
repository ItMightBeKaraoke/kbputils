import dataclasses
import sys
import os
import traceback

@dataclasses.dataclass
class KBPCheckOptions:
    suggestions: bool = dataclasses.field(default=False, metadata={'doc': "Provide suggestions for fixing problems"})
    interactive: bool = dataclasses.field(default=False, metadata={'doc': "Start an interactive session to fix problems"})
    overwrite: bool = dataclasses.field(default=False, metadata={'doc': "Allow in-place overwriting of file in interactive mode. Not recommended!"})

def kbpcheck(source, args, dest):
    suggest = getattr(args, "suggestions", False)
    interact = getattr(args, "interactive", False)
    overwrite = getattr(args, "overwrite", False)
    if interact:
        # In interactive mode, prompts should be to stdout, but dest can be used for the file to write
        (output, dest) = (dest, sys.stdout)
    else:
        if dest and os.path.exists(dest) and os.path.samefile(dest, source.filename):
            sys.stderr.write("Not writing over kbp file! Leave destination argument blank or provide a suitable output file.\n")
            sys.exit(1)
        dest = open(dest, 'w') if dest else sys.stdout
    for fix in source.onload_modifications:
        dest.write(fix + "\n")
        if suggest or interact:
            dest.write(" - Fixed automatically by tolerant parsing option\n\n")
    for err in (errs := source.logicallyValidate()):
        dest.write(str(err) + "\n")
        if suggest or interact:
            solutions = err.propose_solutions(source)
            dest.write("Solutions:\n")
            dest.write("\n".join(f"  {n}) " + x.params["description"] for n, x in enumerate(solutions, 1)) + "\n")
        if interact:
            print(f"  {len(solutions)+1}) Take no action")
            print(f"  w) Save to {output or '<stdout>'} or specified filename and exit without resolving remaining errors")
            print("  x) Exit without saving")
            while True:
                choice = input(f"[{len(solutions)+1}]: ") or str(len(solutions)+1)
                if choice == 'x':
                    sys.exit(0)
                elif choice == 'w' or choice.startswith('w '):
                    fname = choice[2:] or output or sys.stdout
                    try:
                        source.writeFile(fname, allow_overwrite=overwrite)
                    except Exception:
                        print(traceback.format_exc())
                        print("Sorry, try another filename")
                        continue
                    sys.exit(0)
                else:
                    try:
                        i = int(choice) - 1
                        assert 0 <= i < len(solutions)+1
                    except Exception:
                        print(f"Please enter a number between 1 and {len(solutions)+1}, w [filename], x, or hit enter for the default (no action).")
                        continue
                    if i < len(solutions):
                        for param in solutions[i].free_params or []:
                            param_data = solutions[i].free_params[param]
                            print(f"Choose {param} to use")
                            for choice, desc in param_data:
                                print(f"  {choice}) {desc}")
                            default_choice = param_data[0][0]
                            while True:
                                try:
                                    choice = type(param_data[0][0])(input(f"[{default_choice}]: ")) or default_choice
                                    assert choice in (x for x,_ in param_data)
                                    solutions[i].params[param] = choice
                                    break
                                except Exception:
                                    print("Please choose one of the provided options")
                        if solutions[i].free_params:
                            solutions[i].free_params.clear()
                        solutions[i].run(source)

                    break
        dest.write("\n")
    if interact:
        print(f"\nDone editing file!\n")
        print(f"  w) Save to {output or '<stdout>'} or specified filename")
        print("  x) Exit without saving")
        while True:
            choice = input(f"[w]: ") or "w"
            if choice == 'x':
                sys.exit(0)
            elif choice == 'w' or choice.startswith('w '):
                fname = choice[2:] or output or sys.stdout
                try:
                    source.writeFile(fname)
                except Exception:
                    print(traceback.format_exc())
                    print("Sorry, try another filename")
                    continue
                sys.exit(0)
                
    dest.close()
    sys.exit(min(len(errs) + len(source.onload_modifications), 255))
