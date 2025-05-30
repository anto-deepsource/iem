""".. title:: Climatology Data

Return to `API Services </api/#cgi>`_ or the
`User Frontend </COOP/dl/normals.phml>`_.

This service emits the daily climatology, sometimes referred to as normals,
but normals is a poor name, but I digress.  You can either request entire
state's climatology values for a specific day or a single locations climatology
for the entire year.  Day values use the year 2000, but only imply the day
of the year.

Changelog
---------

- 2025-04-16: Added support for Microsoft Excel output and fixed csv download.
- 2025-01-28: Initial implementation

Example Requests
----------------

Provide the January 1 climatology for all stations in Iowa using the NCEI
1991-2020 dataset.

https://mesonet.agron.iastate.edu/cgi-bin/request/normals.py\
?mode=day&month=1&day=1&source=ncei_climate91

Provide the IEM computed period of record climatology for Ames, IA in Excel

https://mesonet.agron.iastate.edu/cgi-bin/request/normals.py\
?mode=station&station=IATAME&source=climate&fmt=excel

Provide the NCEI 1981-2010 climatology for Ames, IA in JSON, this has a source
of ncdc_climate81 due to lame reasons.

https://mesonet.agron.iastate.edu/cgi-bin/request/normals.py\
?mode=station&station=IATAME&source=ncdc_climate81&fmt=json

Same request, but view "online" instead of downloading a file.

https://mesonet.agron.iastate.edu/cgi-bin/request/normals.py\
?mode=station&station=IATAME&source=ncdc_climate81&fmt=online

Same request, but as a JSON object.

https://mesonet.agron.iastate.edu/cgi-bin/request/normals.py\
?mode=station&station=IATAME&source=ncdc_climate81&fmt=json

"""

from datetime import date
from io import BytesIO

import pandas as pd
from pydantic import Field
from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.network import Table as NetworkTable
from pyiem.webutil import CGIModel, iemapp

EXL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Schema(CGIModel):
    """See how we are called."""

    day: int = Field(
        default=1,
        description="The day of the year, only used for day mode",
        ge=1,
        le=31,
    )
    fmt: str = Field(
        default="csv",
        description="The format of the output, either csv, json, excel",
        pattern="^(csv|cdf|json|excel|online)$",
    )
    mode: str = Field(
        default="station",
        description="The mode of request, either station or day",
        pattern="^(station|day)$",
    )
    month: int = Field(
        default=1,
        description="The month of the year, only used for day mode",
        ge=1,
        le=12,
    )
    source: str = Field(
        default="ncei_climate91",
        description="The source of the data, defaults to ncei_climate91",
        pattern=r"^(climate(51|71|81)?|ncdc_climate[78]1|ncei_climate91)$",
    )
    station: str = Field(
        default="IA0000",
        description="The station identifier, only used for station mode",
    )


@iemapp(help=__doc__, schema=Schema)
def application(environ, start_response):
    """Go Main Go"""
    source = environ["source"]
    st = environ["station"][:2].upper()
    network = f"{st}CLIMATE"
    nt = NetworkTable(network, only_online=False)
    params = {
        "station": environ["station"],
        "day": date(2000, environ["month"], environ["day"]),
        "stations": list(nt.sts.keys()),
        "network": network,
    }
    if environ["mode"] == "station":
        limiter = "station = :station"
    else:  # day
        limiter = "valid = :day and station = ANY(:stations)"
    if source.startswith("ncei"):
        col = "ncdc81" if source == "ncei_climate81" else "ncei91"
        params["network"] = col.upper()
        if environ["mode"] == "station":
            with get_sqlalchemy_conn("mesosite") as conn:
                res = conn.execute(
                    sql_helper(
                        "select {col} as station from stations "
                        "where id = :station and network ~* 'CLIMATE'",
                        col=col,
                    ),
                    {"station": environ["station"]},
                )
                if res.rowcount > 0:
                    row = res.fetchone()
                    params["station"] = row[0]
        else:
            # Woof
            params["stations"] = [meta[col] for meta in nt.sts.values()]

    with get_sqlalchemy_conn("coop") as pgconn:
        climodf = pd.read_sql(
            sql_helper(
                """
        select c.*, st_x(geom) as lon, st_y(geom) as lat, name
        from {table} c, stations t WHERE c.station = t.id
        and t.network = :network and {limiter}
        """,
                table=source,
                limiter=limiter,
            ),
            pgconn,
            params=params,
        )
    if environ["fmt"] == "json":
        start_response("200 OK", [("Content-type", "application/json")])
        return climodf.to_json(orient="records")
    if environ["fmt"] == "excel":
        start_response(
            "200 OK",
            [
                ("Content-type", EXL),
                (
                    "Content-Disposition",
                    "attachment; filename=climatology.xlsx",
                ),
            ],
        )
        bio = BytesIO()
        climodf.to_excel(bio, index=False)
        return bio.getvalue()
    if environ["fmt"] == "online":
        start_response("200 OK", [("Content-type", "text/plain")])
    else:  # cdf or csv
        start_response(
            "200 OK",
            [
                ("Content-type", "application/octet-stream"),
                (
                    "Content-Disposition",
                    "attachment; filename=climatology.csv",
                ),
            ],
        )
    return climodf.to_csv(index=False)
