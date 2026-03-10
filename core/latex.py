import os

from core import settings


def latex_escape(s):
    """Escape LaTeX special chars in plain text."""
    if s is None:
        return ""
    s = str(s)
    # Order matters: backslash first.
    repl = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for k, v in repl:
        s = s.replace(k, v)
    return s


def file_exists(value):
    if os.path.exists(value):
        return True
    return False


def debug(value):
    print(value)
    print(type(value))
    return ""  # emit nothing in TeX


def types(value):
    print(type(value))
    return ""  # emit nothing in TeX


def cmt(s):
    """Emit a single LaTeX comment line, gated by SHOW_COMMENTS."""
    if not settings.SHOW_COMMENTS or s is None:
        return ""
    return "% " + str(s).replace("\n", " ").strip() + "\n"


def cblock(s):
    """Emit multi-line LaTeX comment block, gated by SHOW_COMMENTS."""
    if not settings.SHOW_COMMENTS or s is None:
        return ""
    lines = str(s).splitlines() or [str(s)]
    return "".join("% " + line + "\n" for line in lines)


def find_pic(opt_name):
    if os.path.exists(f"./data/pics/{opt_name}.jpg"):
        return True
    else:
        return False


def get_pic(opt_name):
    return f"./data/pics/{opt_name}.jpg"
