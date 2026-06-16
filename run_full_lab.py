import subprocess
import sys


COMMANDS = [
    [sys.executable, "data/synthetic_gen.py"],
    [sys.executable, "main.py"],
    [sys.executable, "detailed_report.py"],
    [sys.executable, "check_lab.py"],
]


def main() -> None:
    for command in COMMANDS:
        print(f"\n▶ {' '.join(command)}", flush=True)
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
