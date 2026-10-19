import os
import sys
import argparse
import subprocess

from .transpiler import compile_file

def _local_abspath(path):
    return os.path.join(os.path.dirname(__file__), path)

pyver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

def main(clang):
    parser = argparse.ArgumentParser(prog="gum", usage="%(prog)s -c [options] filepath")
    parser.add_argument("filepath", help="File path", type=str)
    parser.add_argument("-cppo", "--cppoutput", type=str, help="Put the transpiled C++ output into a file")
    parser.add_argument("-c", "--compile", action="store_true", help="Compile file")
    parser.add_argument("-o", "--output", type=str, help="Output executable name")
    parser.add_argument("-r", "--run", action="store_true", help="Run file after compilation")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    args = parser.parse_args()

    _main(args.filepath, args.compile, args.output, args.run, args.cppoutput, args.verbose)

def _main(filepath, compile_, output, run, cppo, verbose):
    if not compile_:
        print("Error: Gum no longer has an interpreter. Pass -c to compile the file "
              "(and -r to also run it after compiling).")
        sys.exit(1)

    retcode, output, cppcode = compile_file(filepath, output, verbose=verbose)
    if cppo and cppcode:
        with open(cppo, "w") as f:
            f.write(cppcode)
    if retcode != 0:
        sys.exit(retcode)
    if run:
        # Run compiled executable
        result = subprocess.run([f"{output}"])
        sys.exit(result.returncode)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main(None)
