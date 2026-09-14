# (c) 2026 cc-Q. Calendar arithmetic, with no datetime module and no clock.
#
# Framework, not an app: the journal keys records by date, witness stamps them,
# and session asks the owner what day it is. None of them should have to own
# this, and none of them should import it from each other.
#

def ordinal(date):
    """Days since 1970-01-01 for YYYY-MM-DD. No datetime on the device.

    Howard Hinnant's days_from_civil: exact for every proleptic Gregorian date,
    which matters because the owner can set any date they like.
    """
    y, m, d = (int(x) for x in date.split('-'))
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def from_ordinal(z):
    "the exact inverse of _ordinal"
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return '%04d-%02d-%02d' % (y + (1 if m <= 2 else 0), m, d)
