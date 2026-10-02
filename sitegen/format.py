"""Date formatting shared by the data models and the template filters.

Kept in its own module so :mod:`sitegen.models` and :mod:`sitegen.render` can
both use it without importing each other.
"""

from __future__ import annotations

import datetime as dt

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def month_year(value: dt.date) -> str:
    return f"{MONTHS[value.month - 1]} {value.year}"


def short_date(value: dt.date) -> str:
    return f"{MONTHS[value.month - 1][:3]} {value.year}"


def date_range(start: dt.date, end: dt.date | None, current: bool = False) -> str:
    """'Jun 2020 - Mar 2024', 'Jan 2022', or 'Apr 2024 - Present'.

    ``current`` has to be passed explicitly rather than inferred from ``end``
    being ``None``. Most items have no end date because they are finished -
    a paper from 2020 is not "ongoing" - so treating a missing end as "Present"
    labeled every publication on the site with a range that never ends. Only a
    current role gets that treatment.
    """
    if current:
        return f"{short_date(start)} - Present"
    if end is None:
        return short_date(start)
    if start.year == end.year and start.month == end.month:
        return str(start.year)
    if start.year == end.year:
        # A term-long span inside one year reads wrong collapsed to its start
        # month: "Sep 2019" for a course that ran September to December says
        # less than "Sep 2019 - Dec 2019" did. Same year still saves the repeated
        # year number, which is the only thing this branch was for.
        return f"{short_date(start)} - {short_date(end)}"
    return f"{short_date(start)} - {short_date(end)}"
