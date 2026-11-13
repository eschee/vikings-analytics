"""Hatewatch: run the simulation and save results for the website.

The analysis modules live in ../analysis and the ETL in ../etl, neither of
which is an installed package, so both directories are added to sys.path here.
That keeps this package runnable straight from a checkout with
`python -m hatewatch.run`.

They are APPENDED rather than inserted at the front. Putting them first would
let a file in analysis/ shadow a stdlib or installed module of the same name,
which is the kind of bug that only shows up much later.

The report CLI that used to be analysis/hatewatch.py is now analysis/guide.py.
Two things named "hatewatch" -- that module and this package -- resolved
differently depending on sys.path order, so `import hatewatch` could get either
one. The package owns the name now.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("analysis", "etl"):
    _path = os.path.join(_ROOT, _sub)
    if _path not in sys.path:
        sys.path.append(_path)

PROJECT_ROOT = _ROOT
