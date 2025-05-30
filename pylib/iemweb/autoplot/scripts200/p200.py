"""This application generates heatmaps of Storm Prediction Center
convective outlooks.

<p><strong>Major Caveat</strong>: Due to how the IEM stores the outlook
geometries, the values presented here are for an outlook level and levels
higher.  For example, if a location was in a moderate risk and you asked
this app to total slight risks, the moderate risk would count toward the
slight risk total.</p>

<p><i class="fa fa-info"></i> This autoplot currently only considers
outlooks since 2002.  This app is also horribly slow for reasons I have
yet to fully debug :(</p>

<p><strong>Updated 31 Dec 2024</strong>: This autoplot will no longer emit
a hacky CSV/Excel file.  Instead, it will return a GeoTIFF with the analysis
grid.  If this causes you heartburn, please let me know.</p>

<p>Autoplot <a href="/plotting/auto/?q=248">248</a> is similar, but generates
chart of days per year by WFO, state.</p>
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import geopandas as gpd
import numpy as np
from affine import Affine
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import NoDataFound
from pyiem.grid.zs import CachingZonalStats
from pyiem.plot import get_cmap, pretty_bins
from pyiem.plot.geoplot import MapPlot
from pyiem.util import utc

from iemweb.autoplot import ARG_FEMA
from iemweb.util import month2months

if TYPE_CHECKING:
    import pandas as pd

PDICT5 = {
    "yes": "YES: Draw Counties/Parishes",
    "no": "NO: Do Not Draw Counties/Parishes",
}
# Note the backwards order here that we care about in p258
ISSUANCE = {
    "1.C.A": "Day 1 Convective",
    "1.C.1": "Day 1 Convective @1z",
    "1.C.20": "Day 1 Convective @20z",
    "1.C.16": "Day 1 Convective @16z",
    "1.C.13": "Day 1 Convective @13z",
    "1.C.6": "Day 1 Convective @6z",
    "1.F.A": "Day 1 Fire Weather",
    "1.F.17": "Day 1 Fire Weather @17z",
    "1.F.7": "Day 1 Fire Weather @7z",
    "1.E.A": "Day 1 Excessive Rainfall",
    "1.E.1": "Day 1 Excessive Rainfall @1z",
    "1.E.20": "Day 1 Excessive Rainfall @20z",
    "1.E.16": "Day 1 Excessive Rainfall @16z",
    "1.E.8": "Day 1 Excessive Rainfall @8z",
    "2.C.A": "Day 2 Convective",
    "2.C.17": "Day 2 Convective @17z",
    "2.C.7": "Day 2 Convective @7z",
    "2.F.A": "Day 2 Fire Weather",
    "2.F.18": "Day 2 Fire Weather @18z",
    "2.F.8": "Day 2 Fire Weather @8z",
    "2.E.A": "Day 2 Excessive Rainfall",
    "2.E.20": "Day 2 Excessive Rainfall @20z",
    "2.E.8": "Day 2 Excessive Rainfall @8z",
    "3.C.A": "Day 3 Convective",
    "3.C.20": "Day 3 Convective @20z",
    "3.C.8": "Day 3 Convective @8z",
    "3.F.21": "Day 3 Fire Weather @21z",
    "3.E.20": "Day 3 Excessive Rainfall @20z",
    "3.E.8": "Day 3 Excessive Rainfall @8z",
    "4.C.10": "Day 4 Convective @10z",
    "4.E.20": "Day 4 Excessive Rainfall @20z",
    "4.E.8": "Day 4 Excessive Rainfall @8z",
    "5.C.10": "Day 5 Convective @10z",
    "5.E.20": "Day 5 Excessive Rainfall @20z",
    "5.E.8": "Day 5 Excessive Rainfall @8z",
    "6.C.10": "Day 6 Convective @10z",
    "7.C.10": "Day 7 Convective @10z",
    "8.C.10": "Day 8 Convective @10z",
}
OUTLOOKS = {
    "ANY SEVERE.0.02": "Any Severe 2% (Day 3+)",
    "ANY SEVERE.0.05": "Any Severe 5% (Day 3+)",
    "ANY SEVERE.0.15": "Any Severe 15% (Day 3+)",
    "ANY SEVERE.0.25": "Any Severe 25% (Day 3+)",
    "ANY SEVERE.0.30": "Any Severe 30% (Day 3+)",
    "ANY SEVERE.0.35": "Any Severe 35% (Day 3+)",
    "ANY SEVERE.0.45": "Any Severe 45% (Day 3+)",
    "ANY SEVERE.0.60": "Any Severe 60% (Day 3+)",
    "ANY SEVERE.SIGN": "Any Severe Significant (Day 3+)",
    "CATEGORICAL.TSTM": "Categorical Thunderstorm Risk (Days 1-3)",
    "CATEGORICAL.MRGL": "Categorical Marginal Risk (2015+) (Days 1-3)",
    "CATEGORICAL.SLGT": "Categorical Slight Risk (Days 1-3)",
    "CATEGORICAL.ENH": "Categorical Enhanced Risk (2015+) (Days 1-3)",
    "CATEGORICAL.MDT": "Categorical Moderate Risk (Days 1-3)",
    "CATEGORICAL.HIGH": "Categorical High Risk (Days 1-3)",
    "FIRE WEATHER CATEGORICAL.CRIT": "Categorical Critical Fire Wx (Days 1-2)",
    "FIRE WEATHER CATEGORICAL.EXTM": "Categorical Extreme Fire Wx (Days 1-2)",
    "CRITICAL FIRE WEATHER AREA.0.15": (
        "Critical Fire Weather Area 15% (Days3-7)"
    ),
    "HAIL.0.05": "Hail 5% (Days 1+2)",
    "HAIL.0.15": "Hail 15% (Days 1+2)",
    "HAIL.0.25": "Hail 25% (Days 1+2)",
    "HAIL.0.30": "Hail 30% (Days 1+2)",
    "HAIL.0.35": "Hail 35% (Days 1+2)",
    "HAIL.0.45": "Hail 45% (Days 1+2)",
    "HAIL.0.60": "Hail 60% (Days 1+2)",
    "HAIL.SIGN": "Hail Significant (Days 1+2)",
    "TORNADO.0.02": "Tornado 2% (Days 1+2)",
    "TORNADO.0.05": "Tornado 5% (Days 1+2)",
    "TORNADO.0.10": "Tornado 10% (Days 1+2)",
    "TORNADO.0.15": "Tornado 15% (Days 1+2)",
    "TORNADO.0.25": "Tornado 25% (Days 1+2)",
    "TORNADO.0.30": "Tornado 30% (Days 1+2)",
    "TORNADO.0.35": "Tornado 35% (Days 1+2)",
    "TORNADO.0.45": "Tornado 45% (Days 1+2)",
    "TORNADO.0.60": "Tornado 60% (Days 1+2)",
    "TORNADO.SIGN": "Tornado Significant (Days 1+2)",
    "WIND.0.05": "Wind 5% (Days 1+2)",
    "WIND.0.15": "Wind 15% (Days 1+2)",
    "WIND.0.25": "Wind 25% (Days 1+2)",
    "WIND.0.30": "Wind 30% (Days 1+2)",
    "WIND.0.35": "Wind 35% (Days 1+2)",
    "WIND.0.45": "Wind 45% (Days 1+2)",
    "WIND.0.60": "Wind 60% (Days 1+2)",
    "WIND.SIGN": "Wind Significant (Days 1+2)",
}
PDICT = {
    "cwa": "Plot by NWS Forecast Office",
    "state": "Plot by State/Sector",
    "fema": "Plot by FEMA Region",
}
PDICT2 = {
    "avg": "Average Number of Days per Year",
    "count": "Total Number of Days",
    "lastyear": "Year of Last Issuance",
}
UNITS = {
    "avg": "days per year",
    "count": "days",
    "lastyear": "year",
}
MDICT = {
    "all": "Entire Year",
    "spring": "Spring (MAM)",
    "fall": "Fall (SON)",
    "winter": "Winter (DJF)",
    "summer": "Summer (JJA)",
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}

GRIDWEST = -139.2
GRIDEAST = -55.1
GRIDNORTH = 54.51
GRIDSOUTH = 19.47


def get_description():
    """Return a dict describing how to call this plotter"""
    desc = {"description": __doc__, "cache": 86400}
    desc["arguments"] = [
        dict(
            type="select",
            name="month",
            default="all",
            label="Month Limiter",
            options=MDICT,
        ),
        dict(
            type="select",
            name="p",
            default="3.C.8",  # day 1 is too slow to default to :(
            options=ISSUANCE,
            label="Select SPC Product Issuance",
        ),
        dict(
            type="select",
            name="level",
            default="CATEGORICAL.SLGT",
            options=OUTLOOKS,
            label="Select outlook level:",
        ),
        dict(
            type="select",
            name="t",
            default="state",
            options=PDICT,
            label="Select plot extent type:",
        ),
        dict(
            type="networkselect",
            name="station",
            network="WFO",
            default="DMX",
            label="Select WFO: (ignored if plotting state)",
        ),
        dict(
            type="csector",
            name="csector",
            default="conus",
            label="Select state/sector to plot",
        ),
        ARG_FEMA,
        dict(
            type="select",
            name="drawc",
            default="no",
            options=PDICT5,
            label="Plot County/Parish borders on maps?",
        ),
        dict(
            type="select",
            name="w",
            default="avg",
            options=PDICT2,
            label="Which metric to plot?",
        ),
        {
            "type": "date",
            "name": "sdate",
            "label": "Limit plot to start date (2002 is start):",
            "min": "2002/01/01",
            "default": "2002/01/01",
        },
        dict(
            optional=True,
            type="date",
            name="edate",
            label="Optionally limit plot to this end date:",
            min="2002/01/01",
            default=utc().strftime("%Y/%m/%d"),
        ),
        {
            "type": "float",
            "default": "-1",
            "label": "Hardcode max value for color ramp, -1 disables",
            "name": "max",
        },
        {
            "type": "cmap",
            "name": "cmap",
            "default": "jet",
            "label": "Color Ramp:",
        },
    ]
    return desc


def get_raster(ctx: dict):
    """Compute the raster."""
    level = ctx["level"]
    p = ctx["p"]
    month = ctx["month"]

    months = month2months(month)

    griddelta = 0.05
    YSZ = int((GRIDNORTH - GRIDSOUTH) / griddelta)
    XSZ = int((GRIDEAST - GRIDWEST) / griddelta)

    raster = np.zeros((int(YSZ), int(XSZ)))

    params = {
        "ot": p.split(".")[1],
        "day": p.split(".")[0],
        "t": level.split(".", 1)[1],
        "cat": level.split(".")[0],
        "months": months,
        "sdate": ctx["sdate"],
        "edate": ctx.get("edate", utc() + timedelta(days=2)),
        "west": GRIDWEST,
        "south": GRIDSOUTH,
        "east": GRIDEAST,
        "north": GRIDNORTH,
    }

    hour = p.split(".")[2]
    hour_limiter = ""
    if hour != "A":
        params["hour"] = int(hour)
        hour_limiter = " and cycle = :hour "
    with get_sqlalchemy_conn("postgis") as conn:
        df: pd.DataFrame = gpd.read_postgis(
            sql_helper(
                """
            select expire, min(issue) as min_issue,
            st_union(geom_layers) as geom,
            min(extract(year from issue at time zone 'UTC')) as year
            from spc_outlooks where outlook_type = :ot and day = :day
            {hour_limiter} and threshold = :t and category = :cat and
            ST_Intersects(geom,
                ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            and extract(month from issue) = ANY(:months)
            and product_issue > :sdate and
            product_issue < :edate
            GROUP by expire ORDER by min_issue ASC
        """,
                hour_limiter=hour_limiter,
            ),
            conn,
            params=params,
            geom_col="geom",
            index_col=None,
        )  # type: ignore
    if df.empty:
        raise NoDataFound("No results found for query")
    # The affine is the edge and not the analysis centers
    affine = Affine(
        griddelta,
        0.0,
        GRIDWEST,
        0.0,
        0 - griddelta,
        GRIDNORTH,
    )
    czs = CachingZonalStats(affine)
    czs.compute_gridnav(df["geom"], raster)
    for i, nav in enumerate(czs.gridnav):
        if nav is None:
            continue
        grid = np.ones((nav.ysz, nav.xsz))
        grid[nav.mask] = 0.0
        jslice = slice(nav.y0, nav.y0 + nav.ysz)
        islice = slice(nav.x0, nav.x0 + nav.xsz)
        if ctx["w"] == "lastyear":
            raster[jslice, islice] = np.max(
                [raster[jslice, islice], grid * df.loc[i]["year"]],
                axis=0,
            )
        else:
            raster[jslice, islice] += grid

    years = (utc() - df["min_issue"].min()).total_seconds() / 365.25 / 86400.0
    if ctx["w"] == "avg":
        raster = raster / years

    ctx["df"] = df

    return raster, affine, 4326


def plotter(ctx: dict):
    """Go"""
    raster, affine, _crs = get_raster(ctx)
    df: pd.DataFrame = ctx["df"]
    station = ctx["station"][:4]
    level = ctx["level"]
    t = ctx["t"]
    p = ctx["p"]
    month = ctx["month"]
    subtitle = (
        f"Found {len(df.index)} events for CONUS "
        f"between {df['min_issue'].min():%d %b %Y} and "
        f"{df['min_issue'].max():%d %b %Y}"
    )
    csector = ctx.pop("csector")
    if t == "cwa":
        sector = "cwa"
        subtitle = (
            f"Plotted for {ctx['_nt'].sts[station]['name']} ({station}). "
            f"{subtitle}"
        )
    elif t == "fema":
        sector = "fema_region"
        subtitle = f"Plotted for FEMA Region {ctx['fema']}. {subtitle}"
    else:
        sector = "state" if len(csector) == 2 else csector

    mp = MapPlot(
        apctx=ctx,
        sector=sector,
        state=csector,
        fema_region=ctx["fema"],
        cwa=(station if len(station) == 3 else station[1:]),
        axisbg="white",
        title=(
            f"{'WPC' if p.split('.')[1] == 'E' else 'SPC'} {ISSUANCE[p]} "
            f"Outlook [{MDICT[month]}] of at least "
            f"{OUTLOOKS[level].split('(')[0].strip()}"
        ),
        subtitle=f"{PDICT2[ctx['w']]}, {subtitle}",
        nocaption=True,
    )
    if np.nanmax(raster) == 0:
        raise NoDataFound("No Data Found")
    if ctx["w"] == "lastyear":
        if np.ma.max(raster) < 1:
            raster = np.where(raster < 1, np.nan, raster)
            rng = range(2022, 2024)
        else:
            raster = np.where(raster < 1, np.nan, raster)
            rng = range(int(np.nanmin(raster)), int(np.nanmax(raster)) + 2)
    elif ctx["w"] == "count":
        maxval = ctx["max"] if ctx["max"] > -1 else (np.nanmax(raster) + 1)
        raster = np.where(raster < 1, np.nan, raster)
        rng = np.unique(np.linspace(1, maxval, 10, dtype=int))
    else:
        maxval = ctx["max"] if ctx["max"] > -1 else (np.nanmax(raster) + 1)
        rng = pretty_bins(0, maxval)
        rng[0] = 0.01

    cmap = get_cmap(ctx["cmap"])
    cmap.set_bad("white")
    cmap.set_under("white")
    cmap.set_over("black")
    mp.imshow(
        raster,
        affine,
        "EPSG:4326",
        clevs=rng,
        cmap=cmap,
        clip_on=False,
        units=UNITS[ctx["w"]],
        extend="both" if ctx["w"] != "lastyear" else "neither",  # dragons
    )
    if ctx["drawc"] == "yes":
        mp.drawcounties()

    return mp.fig
