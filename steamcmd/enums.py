import platform


def _from_platform(linux: int, windows: int) -> int:
    if platform.system() == "Linux":
        return linux
    elif platform.system() == "Windows":
        return windows
    else:
        raise Exception("Unsupported Operating System")


class AppIds:

    GARRYSMOD = 4020
    L4D = 222840
    L4D2 = 222860
