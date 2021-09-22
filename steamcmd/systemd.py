import argparse

from os import linesep as ls
from time import sleep
from pathlib import Path
from subprocess import run


def systemd_reload():
    result = run(
        args=[
            "/bin/systemctl",
            "daemon-reload",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise Exception(
            f"Error when reloading systemd, stdout:{ls}{result.stdout}{ls}{ls}stderr:{ls}{result.stderr}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pid", type=int, help="The PID of the process to send input to fd 0"
    )
    parser.add_argument(
        "--cmd",
        type=str,
        action="append",
        help="Text to pass to fd 0 of the process, can provide multiple each cmd will be passed with a delay set by --cmd-delay",
        required=True,
    )
    parser.add_argument(
        "--cmd-delay",
        help="Time in seconds between sending each --cmd",
        type=int,
        default=0,
        required=False,
    )
    parser.add_argument(
        "--no-newline",
        type=bool,
        help="If set newline won't be automatically appended to commands",
    )
    args, _ = parser.parse_known_args()

    proc = Path(f"/proc/{args.pid}/fd/0")
    if not proc.exists():
        raise Exception("Process stdin file descriptor does not exist")

    for i, cmd in enumerate(args.cmd, start=1):
        with open(proc, "w") as fd:
            fd.write(cmd)
            if not args.no_newline:
                fd.write(f"{ls}")
        if not i == len(args.cmd):
            sleep(args.cmd_delay)
