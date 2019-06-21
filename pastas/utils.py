import numpy as np
from pandas import Series, to_datetime, Timedelta, Timestamp, to_timedelta
from pandas.tseries.frequencies import to_offset
from scipy import interpolate
import logging
from logging import handlers

logger = logging.getLogger(__name__)


def frequency_is_supported(freq):
    # TODO: Rename to get_frequency_string and change Returns-documentation
    """Method to determine if a frequency is supported for a  pastas-model.
    Possible frequency-offsets are listed in:
    http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
    The frequency can be a multiple of these offsets, like '7D'. Because of the
    use in convolution, only frequencies with an equidistant offset are
    allowed. This means monthly ('M'), yearly ('Y') or even weekly ('W')
    frequencies are not allowed. Use '7D' for a weekly simulation.

    D	calendar day frequency
    H	hourly frequency
    T, min	minutely frequency
    S	secondly frequency
    L, ms	milliseconds
    U, us	microseconds
    N	nanoseconds

    Parameters
    ----------
    freq: str

    Returns
    -------
    boolean
        True when frequency can be used as a simulation frequency
    """

    offset = to_offset(freq)
    if not hasattr(offset, 'delta'):
        logger.error("Frequency %s not supported." % freq)
    else:
        if offset.n == 1:
            freq = offset.name
        else:
            freq = str(offset.n) + offset.name
    return freq


def get_stress_dt(freq):
    """Internal method to obtain a timestep in days from a frequency string
    derived by Pandas Infer method or supplied by the user as a TimeSeries
    settings.

    Parameters
    ----------
    freq: str

    Returns
    -------
    dt: float
        Approximate timestep in number of days.

    Notes
    -----
    Used for comparison to determine if a time series needs to be up or
    downsampled.

    See http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
    for the offset_aliases supported by Pandas.

    """
    # Get the frequency string and multiplier
    offset = to_offset(freq)
    if hasattr(offset, 'delta'):
        dt = offset.delta / Timedelta(1, "D")
    else:
        num = offset.n
        freq = offset.name
        if freq in ['A', 'Y', 'AS', 'YS', 'BA', 'BY', 'BAS', 'BYS']:
            # year
            dt = num * 365
        elif freq in ['BQ', 'BQS', 'Q', 'QS']:
            # quarter
            dt = num * 90
        elif freq in ['BM', 'BMS', 'CBM', 'CBMS', 'M', 'MS']:
            # month
            dt = num * 30
        elif freq in ['SM', 'SMS']:
            # semi-month
            dt = num * 15
        elif freq in ['W']:
            # week
            dt = num * 7
        elif freq in ['B', 'C']:
            # day
            dt = num
        elif freq in ['BH', 'CBH']:
            # hour
            dt = num * 1 / 24
        else:
            raise (ValueError('freq of {} not supported'.format(freq)))

    return dt


def get_dt(freq):
    """Method to obtain a timestep in DAYS from a frequency string.

    Parameters
    ----------
    freq: str

    Returns
    -------
    dt: float
        Number of days

    """
    # Get the frequency string and multiplier
    dt = to_offset(freq).delta / Timedelta(1, "D")
    return dt


def get_time_offset(t, freq):
    """ method to calculate the time offset between a TimeStamp t and a
    default Series with a frequency of freq

    Parameters
    ----------
    t: pandas.Timestamp
        Timestamp to calculate the offset from the desired freq for.
    freq: str
        String with the desired frequency.

    Returns
    -------
    offset: pandas.Timedelta
        Timedelta with the offset for the timestamp t.

    """
    return t - t.floor(freq)


def get_sample(tindex, ref_tindex):
    """Sample the index so that the frequency is not higher than the frequency
        of ref_tindex.

    Parameters
    ----------
    tindex: pandas.index
        Pandas index object
    ref_tindex: pandas.index
        Pandas index object

    Returns
    -------
    series: pandas.index

    Notes
    -----
    Find the index closest to the ref_tindex, and then return a selection
    of the index.

    """
    if len(tindex) == 1:
        return tindex
    else:
        f = interpolate.interp1d(tindex.asi8, np.arange(0, tindex.size),
                                 kind='nearest', bounds_error=False,
                                 fill_value='extrapolate')
        ind = np.unique(f(ref_tindex.asi8).astype(int))
        return tindex[ind]


def timestep_weighted_resample(series, tindex):
    """resample a timeseries to a new tindex, using an overlapping-timestep
    weighted average the new tindex does not have to be equidistant also,
    the timestep-edges of the new tindex do not have to overlap with the
    original series it is assumed the series consists of measurements that
    describe an intensity at the end of the period for which they hold
    therefore when upsampling, the values are uniformally spread over the
    new timestep (like bfill) this method unfortunately is slower than the
    pandas-reample methods.

    Parameters
    ----------
    series
    tindex

    Returns
    -------

    TODO Make faster, document and test.

    """

    # determine some arrays for the input-series
    t0e = series.index.get_values()
    dt0 = np.diff(t0e)
    dt0 = np.hstack((dt0[0], dt0))
    t0s = t0e - dt0
    v0 = series.values

    # determine some arrays for the output-series
    t1e = tindex.get_values()
    dt1 = np.diff(t1e)
    dt1 = np.hstack((dt1[0], dt1))
    t1s = t1e - dt1
    v1 = []
    for t1si, t1ei in zip(t1s, t1e):
        # determine which periods within the series are within the new tindex
        mask = (t0e > t1si) & (t0s < t1ei)
        if np.any(mask):
            # cut by the timestep-edges
            ts = t0s[mask]
            te = t0e[mask]
            ts[ts < t1si] = t1si
            te[te > t1ei] = t1ei
            # determine timestep
            dt = (te - ts).astype(float)
            # determine timestep-weighted value
            v1.append(np.sum(dt * v0[mask]) / np.sum(dt))
    # replace all values in the series
    series = Series(v1, index=tindex)
    return series


def excel2datetime(tindex, freq="D"):
    """Method to convert excel datetime to pandas timetime objects.

    Parameters
    ----------
    tindex: datetime index
        can be a datetime object or a pandas datetime index.
    freq: str

    Returns
    -------
    datetimes: pandas.datetimeindex

    """
    datetimes = to_datetime('1899-12-30') + to_timedelta(tindex, freq)
    return datetimes


def matlab2datetime(tindex):
    """ Transform a matlab time to a datetime, rounded to seconds

    """
    day = Timestamp.fromordinal(int(tindex))
    dayfrac = Timedelta(days=float(tindex) % 1) - Timedelta(days=366)
    return day + dayfrac


def datetime2matlab(tindex):
    mdn = tindex + Timedelta(days=366)
    frac = (tindex - tindex.round("D")).seconds / (24.0 * 60.0 * 60.0)
    return mdn.toordinal() + frac


def get_stress_tmin_tmax(ml):
    """Get the minimum and maximum time that all of the stresses have data"""
    from .model import Model
    from .project import Project
    tmin = Timestamp.min
    tmax = Timestamp.max
    if isinstance(ml, Model):
        for sm in ml.stressmodels:
            for st in ml.stressmodels[sm].stress:
                tmin = max((tmin, st.series_original.index.min()))
                tmax = min((tmax, st.series_original.index.max()))
    elif isinstance(ml, Project):
        for st in ml.stresses['series']:
            tmin = max((tmin, st.series_original.index.min()))
            tmax = min((tmax, st.series_original.index.max()))
    else:
        raise (TypeError('Unknown type {}'.format(type(ml))))
    return tmin, tmax


def initialize_logger(logger=None, level=logging.INFO):
    """Internal method to create a logger instance to log program output.

    Parameters
    -------
    logger : logging.Logger
        A Logger-instance. Use ps.logger to initialise the Logging instance
        that handles all logging throughout pastas,  including all sub modules
        and packages.

    """
    if logger is None:
        logger = logging.getLogger('pastas')
    logger.setLevel(level)
    remove_file_handlers(logger)
    set_console_handler(logger)
    # add_file_handlers(logger)


def set_console_handler(logger=None, level=logging.INFO,
                        fmt="%(levelname)s: %(message)s"):
    """Method to add a console handler to the logger of Pastas.

    Parameters
    -------
    logger : logging.Logger
        A Logger-instance. Use ps.logger to initialise the Logging instance
        that handles all logging throughout pastas,  including all sub modules
        and packages.

    """
    if logger is None:
        logger = logging.getLogger('pastas')
    remove_console_handler(logger)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter(fmt=fmt)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def set_log_level(level):
    """Set the log-level of the console. This method is just a wrapper around
    set_console_handler.

    """
    set_console_handler(level=level)


def remove_console_handler(logger=None):
    """Method to remove the console handler to the logger of Pastas.

    Parameters
    -------
    logger : logging.Logger
        A Logger-instance. Use ps.logger to initialise the Logging instance
        that handles all logging throughout pastas,  including all sub modules
        and packages.

    """
    if logger is None:
        logger = logging.getLogger('pastas')
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)


def add_file_handlers(logger=None, filenames=('info.log', 'errors.log'),
                      levels=(logging.INFO, logging.ERROR), maxBytes=10485760,
                      backupCount=20, encoding='utf8',
                      fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      datefmt='%y-%m-%d %H:%M'):
    """Method to add file handlers in the logger of Pastas

    Parameters
    -------
    logger : logging.Logger
        A Logger-instance. Use ps.logger to initialise the Logging instance
        that handles all logging throughout pastas,  including all sub modules
        and packages.

    """
    if logger is None:
        logger = logging.getLogger('pastas')
    # create formatter
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # create file handlers, set the level & formatter, and add it to the logger
    for filename, level in zip(filenames, levels):
        fh = handlers.RotatingFileHandler(filename, maxBytes=maxBytes,
                                          backupCount=backupCount,
                                          encoding=encoding)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)


def remove_file_handlers(logger=None):
    """Method to remove any file handlers in the logger of Pastas.

    Parameters
    -------
    logger : logging.Logger
        A Logger-instance. Use ps.logger to initialise the Logging instance
        that handles all logging throughout pastas,  including all sub modules
        and packages.

    """
    if logger is None:
        logger = logging.getLogger('pastas')
    for handler in logger.handlers:
        if isinstance(handler, handlers.RotatingFileHandler):
            logger.removeHandler(handler)
