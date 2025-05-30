"""
This plot compares a period of days prior to
a specified date to the same number of days after a date.  The specified
date is not used in either statistical value.  If you select a period that
includes leap day, there is likely some small ambiguity with the resulting
plot labels.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.plot import figure_axes
from scipy import stats

from iemweb.autoplot import ARG_STATION

PDICT = {
    "high": "Average High Temperature",
    "low": "Average Low Temperature",
    "precip": "Total Precipitation",
}
UNITS = {"high": r"$^\circ$F", "low": r"$^\circ$F", "precip": "inch"}


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "data": True}
    desc["arguments"] = [
        ARG_STATION,
        dict(
            type="select",
            name="var",
            default="high",
            label="Which Variable:",
            options=PDICT,
        ),
        dict(type="int", name="days", default=45, label="How many days:"),
        dict(type="month", name="month", default="7", label="Select Month:"),
        dict(type="day", name="day", default="15", label="Select Day:"),
        dict(
            type="year",
            name="year",
            default=date.today().year,
            label="Year to Highlight in Chart",
        ),
    ]
    return desc


def plotter(ctx: dict):
    """Go"""
    station = ctx["station"]
    varname = ctx["var"]
    month = ctx["month"]
    day = ctx["day"]
    dt = date(2000, month, day)
    days = ctx["days"]
    year = ctx["year"]
    ctx["before_period"] = "%s-%s" % (
        (dt - timedelta(days=days)).strftime("%-d %b"),
        (dt - timedelta(days=1)).strftime("%-d %b"),
    )
    ctx["after_period"] = "%s-%s" % (
        (dt + timedelta(days=1)).strftime("%-d %b"),
        (dt + timedelta(days=days)).strftime("%-d %b"),
    )

    with get_sqlalchemy_conn("coop") as conn:
        df = pd.read_sql(
            sql_helper("""
        with data as (
            SELECT day, year,
            count(*) OVER
                (ORDER by day ASC ROWS BETWEEN :days PRECEDING AND 1 PRECEDING)
                as cb,
            avg(high) OVER
                (ORDER by day ASC ROWS BETWEEN :days PRECEDING AND 1 PRECEDING)
                as hb,
            avg(low) OVER
                (ORDER by day ASC ROWS BETWEEN :days PRECEDING AND 1 PRECEDING)
                as lb,
            sum(precip) OVER
                (ORDER by day ASC ROWS BETWEEN :days PRECEDING AND 1 PRECEDING)
                as pb,
            count(*) OVER
                (ORDER by day ASC ROWS BETWEEN 1 FOLLOWING AND :days FOLLOWING)
                as ca,
            avg(high) OVER
                (ORDER by day ASC ROWS BETWEEN 1 FOLLOWING AND :days FOLLOWING)
                as ha,
            avg(low)OVER
                (ORDER by day ASC ROWS BETWEEN 1 FOLLOWING AND :days FOLLOWING)
                as la,
            sum(precip) OVER
                (ORDER by day ASC ROWS BETWEEN 1 FOLLOWING AND :days FOLLOWING)
                as pa
            from alldata WHERE station = :station)

        SELECT year, hb as high_before, lb as low_before, pb as precip_before,
        ha as high_after, la as low_after, pa as precip_after from
        data where cb = ca and
        cb = :days and extract(month from day) = :month
        and extract(day from day) = :day
        """),
            conn,
            params={
                "days": days,
                "station": station,
                "month": month,
                "day": day,
            },
            index_col="year",
        )
    if df.empty:
        raise NoDataFound("No Data Found.")

    xvals = df[f"{varname}_before"].values
    yvals = df[f"{varname}_after"].values
    fig, ax = figure_axes(
        title=f"{ctx['_sname']} :: {PDICT.get(varname)} over",
        subtitle=f"{days} days prior to and after {dt:%-d %B}",
        apctx=ctx,
    )
    ax.scatter(xvals, yvals, zorder=2)
    if year in df.index:
        row = df.loc[year]
        ax.scatter(
            row[f"{varname}_before"],
            row[f"{varname}_after"],
            color="r",
            zorder=3,
        )
        ax.text(
            row[f"{varname}_before"],
            row[f"{varname}_after"],
            f"{year}",
            ha="right",
            va="bottom",
            color="r",
        )
    minv = min([min(xvals), min(yvals)])
    maxv = max([max(xvals), max(yvals)])
    buffer = 0.1 * (maxv - minv)
    minv = (minv - buffer) if varname != "precip" else 0 - buffer
    ax.plot(
        [minv, maxv + buffer], [minv, maxv + buffer], label="x=y", color="b"
    )
    yavg = np.average(np.array(yvals))
    xavg = np.average(np.array(xvals))
    ax.axhline(yavg, label=f"After Avg: {yavg:.2f}", color="r", lw=2)
    ax.axvline(xavg, label=f"Before Avg: {xavg:.2f}", color="g", lw=2)
    df2 = df[np.logical_and(xvals >= xavg, yvals >= yavg)]
    ax.text(
        0.98,
        0.98,
        "I: %.1f%%" % (len(df2) / float(len(xvals)) * 100.0,),
        transform=ax.transAxes,
        bbox=dict(edgecolor="tan", facecolor="white"),
        va="top",
        ha="right",
        zorder=3,
    )

    df2 = df[np.logical_and(xvals < xavg, yvals < yavg)]
    ax.text(
        0.02,
        0.02,
        "III: %.1f%%" % (len(df2) / float(len(xvals)) * 100.0,),
        transform=ax.transAxes,
        bbox=dict(edgecolor="tan", facecolor="white"),
        zorder=3,
    )

    df2 = df[np.logical_and(xvals >= xavg, yvals < yavg)]
    ax.text(
        0.98,
        0.02,
        "IV: %.1f%%" % (len(df2) / float(len(xvals)) * 100.0,),
        transform=ax.transAxes,
        bbox=dict(edgecolor="tan", facecolor="white"),
        va="bottom",
        ha="right",
        zorder=3,
    )

    df2 = df[np.logical_and(xvals < xavg, yvals >= yavg)]
    ax.text(
        0.02,
        0.98,
        "II: %.1f%%" % (len(df2) / float(len(xvals)) * 100.0,),
        transform=ax.transAxes,
        bbox=dict(edgecolor="tan", facecolor="white"),
        va="top",
        zorder=3,
    )

    ax.set_xlabel(
        "%s %s, Period: %s"
        % (PDICT.get(varname), UNITS.get(varname), ctx["before_period"])
    )
    ax.set_ylabel(
        "%s %s, Period: %s"
        % (PDICT.get(varname), UNITS.get(varname), ctx["after_period"])
    )
    ax.grid(True)
    ax.set_xlim(minv, maxv + buffer)
    ax.set_ylim(minv, maxv + buffer)

    _, _, r_value, _, _ = stats.linregress(xvals, yvals)
    ax.text(
        0.65,
        0.02,
        "R$^2$=%.2f bias=%.2f" % (r_value**2, yavg - xavg),
        ha="right",
        transform=ax.transAxes,
        bbox=dict(color="white"),
    )

    # Shrink current axis's height by 10% on the bottom
    box = ax.get_position()
    ax.set_position(
        [box.x0, box.y0 + box.height * 0.15, box.width, box.height * 0.85]
    )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.1),
        fancybox=True,
        shadow=True,
        ncol=3,
        scatterpoints=1,
        fontsize=12,
    )

    return fig, df
