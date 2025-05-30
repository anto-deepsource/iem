"""
This plot displays a metric for each year.
In most cases, you can access the raw data for these plots
<a href="/climodat/" class="alert-link">here.</a>
"""

from datetime import date

import numpy as np
import pandas as pd
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.plot import figure_axes

from iemweb.autoplot import ARG_STATION

PDICT = {
    "max-high": "Maximum High",
    "avg-high": "Average High",
    "min-high": "Minimum High",
    "max-low": "Maximum Low",
    "avg-low": "Average Low",
    "min-low": "Minimum Low",
    "max-precip": "Maximum Daily Precip",
    "range-hilo": "Range between Min Low and Max High",
    "sum-precip": "Total Precipitation",
    "avg-precip": "Daily Average Precipitation",
    "avg-precip2": "Daily Average Precipitation (on wet days)",
    "days-precip": "Days with Precipitation Above (threshold)",
    "days-high-above": (
        "Days with High Temp Greater Than or Equal To (threshold)"
    ),
    "days-high-below": "Days with High Temp Below (threshold)",
    "days-lows-above": (
        "Days with Low Temp Greater Than or Equal To (threshold)"
    ),
    "days-lows-below": "Days with Low Temp Below (threshold)",
}


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "data": True}
    eyear = date.today().year
    desc["arguments"] = [
        ARG_STATION,
        dict(
            type="select",
            name="type",
            default="max-high",
            label="Which metric to plot?",
            options=PDICT,
        ),
        dict(
            type="float",
            name="threshold",
            default=-99,
            label="Threshold (optional, specify when appropriate):",
        ),
        dict(
            type="year",
            name="syear",
            default=1893,
            label="Start Year of Plot: (inclusive)",
        ),
        dict(
            type="year",
            name="eyear",
            default=eyear,
            label="End Year of Plot: (inclusive)",
        ),
    ]
    return desc


def plotter(ctx: dict):
    """Go"""
    station = ctx["station"]
    threshold = ctx["threshold"]
    ptype = ctx["type"]
    syear = ctx["syear"]
    eyear = ctx["eyear"]

    with get_sqlalchemy_conn("coop") as conn:
        df = pd.read_sql(
            sql_helper("""
        SELECT year,
        max(high) as "max-high",
        min(high) as "min-high",
        avg(high) as "avg-high",
        max(low) as "max-low",
        min(low) as "min-low",
        avg(low) as "avg-low",
        max(precip) as "max-precip",
        sum(precip) as "sum-precip",
        sum(case when high::numeric >= :t then 1 else 0 end)
            as "days-high-above",
        sum(case when high::numeric < :t then 1 else 0 end)
            as "days-high-below",
        sum(case when low::numeric >= :t then 1 else 0 end)
            as "days-lows-above",
        sum(case when low::numeric < :t then 1 else 0 end)
            as "days-lows-below",
        avg(precip) as "avg-precip",
        avg(case when precip > 0.009 then precip else null end)
            as "avg-precip2",
        sum(case when precip >= :t then 1 else 0 end) as "days-precip"
        from alldata
        where station = :station and year >= :syear and year <= :eyear
        GROUP by year ORDER by year ASC
        """),
            conn,
            params={
                "t": threshold,
                "station": station,
                "syear": syear,
                "eyear": eyear,
            },
            index_col="year",
        )
    if df.empty:
        raise NoDataFound("No Data Found.")
    df["range-hilo"] = df["max-high"] - df["min-low"]

    years = df.index.values
    title = f"{ctx['_sname']} :: {min(years)}-{max(years)}\n{PDICT[ptype]}"
    if ptype.find("days") == 0:
        title += f" ({threshold})"
    (fig, ax) = figure_axes(title=title, apctx=ctx)
    avgv = df[ptype].mean()
    data = df[ptype]

    # Compute 30 year trailing average
    tavg = [None] * 30
    for i in range(30, len(data)):
        tavg.append(np.average(data.values[i - 30 : i]))

    a1981_2010 = df.loc[1981:2011, ptype].mean()

    colorabove = "tomato"
    colorbelow = "dodgerblue"
    precision = "%.1f"
    if ptype in [
        "max-precip",
        "sum-precip",
        "avg-precip",
        "avg-precip2",
        "days-precip",
    ]:
        colorabove = "dodgerblue"
        colorbelow = "tomato"
        precision = "%.2f"
    bars = ax.bar(
        np.array(years),
        data.values,
        fc=colorabove,
        ec=colorabove,
        align="center",
    )
    for i, mybar in enumerate(bars):
        if data.values[i] < avgv:
            mybar.set_facecolor(colorbelow)
            mybar.set_edgecolor(colorbelow)
    lbl = "Avg: " + precision % (avgv,)
    ax.axhline(avgv, lw=2, color="k", zorder=2, label=lbl)
    lbl = "1981-2010: " + precision % (a1981_2010,)
    ax.axhline(a1981_2010, lw=2, color="brown", zorder=2, label=lbl)
    if len(years) == len(tavg):
        ax.plot(
            years, tavg, lw=1.5, color="g", zorder=4, label="Trailing 30yr"
        )
        ax.plot(years, tavg, lw=3, color="yellow", zorder=3)
    ax.set_xlim(years[0] - 1, years[-1] + 1)
    if ptype.find("precip") == -1 and ptype.find("days") == -1:
        ax.set_ylim(data.min() - 5, data.max() + 5)

    ax.set_xlabel("Year")
    units = r"$^\circ$F"
    if ptype.find("days") > 0:
        units = "days"
    elif ptype.find("precip") > 0:
        units = "inches"
    ax.set_ylabel(f"{PDICT[ptype]} [{units}]")
    ax.grid(True)
    ax.legend(ncol=3, loc="best", fontsize=10)

    return fig, df
