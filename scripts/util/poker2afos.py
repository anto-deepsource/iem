"""Ingest the files kindly sent to me by poker"""

import glob
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

from pyiem.database import get_dbconn
from pyiem.nws.product import TextProduct
from pyiem.util import noaaport_text

BAD_CHARS = r"[^\n\r\001\003a-zA-Z0-9:\(\)\%\.,\s\*\-\?\|/><&$=\+\@]"
PGCONN = get_dbconn("afos")
XREF_SOURCE = {
    "KABE": "KPHI",
    "KABI": "KSJT",
    "KACT": "KFWD",
    "KACY": "KPHI",
    "KAEL": "KMPX",
    "KAGS": "KCAE",
    "KAHN": "KFFC",
    "KAIA": "KCYS",
    "KAID": "KIND",
    "KALB": "KALY",
    "KALO": "KDMX",
    "KALS": "KPUB",
    "KALW": "KPDT",
    "KANW": "KLBF",
    "KAPN": "KAPX",
    "KAQQ": "KTAE",
    "KARB": "KDTX",
    "KAST": "KPQR",
    "KATL": "KFFC",
    "KATR": "KALR",
    "KAUB": "KBMX",
    "KAUO": "KBMX",
    "KAUS": "KEWX",
    "KAVL": "KGSP",
    "KAVP": "KBGM",
    "KAYS": "KJAX",
    "KBAK": "KIND",
    "KBBW": "KLBF",
    "KBDL": "KBOX",
    "KBDR": "KOKX",
    "KBFF": "KCYS",
    "KBFI": "KSEW",
    "KBFL": "KHNX",
    "KBHM": "KBMX",
    "KBIE": "KOAX",
    "KBIH": "KVEF",
    "KBIL": "KBYZ",
    "KBIM": "KBMX",
    "KBIX": "KLIX",
    "KBKW": "KRLX",
    "KBLU": "KSTO",
    "KBNA": "KOHX",
    "KBNO": "KBOI",
    "KBOS": "KBOX",
    "KBPT": "KLCH",
    "KBRL": "KDVN",
    "KBTM": "KMSO",
    "KBTR": "KLIX",
    "KBVE": "KLIX",
    "KBWI": "KLWX",
    "KCAK": "KCLE",
    "KCDR": "KCYS",
    "KCEC": "KEKA",
    "KCFV": "KICT",
    "KCGI": "KPAH",
    "KCHA": "KMRX",
    "KCHH": "KBOX",
    "KCHI": "KLOT",
    "KCIC": "KSTO",
    "KCID": "KDVN",
    "KCIN": "KTIR",
    "KCIR": "KPAH",
    "KCKL": "KBMX",
    "KCLL": "KHGX",
    "KCLT": "KGSP",
    "KCMH": "KILN",
    "KCNK": "KTOP",
    "KCNU": "KICT",
    "KCON": "KGYX",
    "KCOS": "KPUB",
    "KCOU": "KLSX",
    "KCPR": "KRIW",
    "KCRW": "KRLX",
    "KCSG": "KFFC",
    "KCSM": "KOUN",
    "KCVG": "KILN",
    "KCZD": "KGID",
    "KDAB": "KMLB",
    "KDAY": "KILN",
    "KDBQ": "KDVN",
    "KDCA": "KLWX",
    "KDEN": "KBOU",
    "KDFW": "KFWD",
    "KDLF": "KEWX",
    "KDRA": "KVEF",
    "KDRT": "KEWX",
    "KDSM": "KDMX",
    "KDTL": "KFGF",
    "KDTW": "KDTX",
    "KEAR": "KGID",
    "KEAT": "KOTX",
    "KEAU": "KMPX",
    "KEDW": "KHNX",
    "KEEW": "KGRB",
    "KEKN": "KRLX",
    "KEKO": "KLKN",
    "KEKY": "KLKN",
    "KELO": "KDLH",
    "KELP": "KEPZ",
    "KELY": "KLKN",
    "KEMP": "KTOP",
    "KEND": "KOUN",
    "KENW": "KMKX",
    "KERI": "KCLE",
    "KERL": "KBOU",
    "KESC": "KMQT",
    "KESF": "KLCH",
    "KEUG": "KPQR",
    "KEVV": "KPAH",
    "KEWR": "KOKX",
    "KEYW": "KKEY",
    "KFAR": "KFGF",
    "KFAT": "KHNX",
    "KFBL": "KMPX",
    "KFCA": "KMSO",
    "KFCL": "KBOU",
    "KFFM": "KFGF",
    "KFLG": "KFGZ",
    "KFMY": "KTBW",
    "KFNB": "KOAX",
    "KFNT": "KDTX",
    "KFOE": "KTOP",
    "KFRI": "KTOP",
    "KFRM": "KMPX",
    "KFSI": "KOUN",
    "KFSM": "KLZK",
    "KFTW": "KFWD",
    "KFWA": "KIWX",
    "KGCK": "KDDC",
    "KGEG": "KOTX",
    "KGGG": "KSHV",
    "KGLS": "KHGX",
    "KGPZ": "KDLH",
    "KGRI": "KGID",
    "KGSO": "KRAH",
    "KGTF": "KTFX",
    "KGVW": "KEAX",
    "KHAR": "KCTP",
    "KHAT": "KILM",
    "KHCO": "KFGF",
    "KHDO": "KEWX",
    "KHFD": "KBOX",
    "KHLC": "KGLD",
    "KHLN": "KTFX",
    "KHMN": "KEPZ",
    "KHMS": "KPDT",
    "KHNF": "KOTX",
    "KHON": "KFSD",
    "KHOU": "KHGX",
    "KHSI": "KGID",
    "KHST": "KMFL",
    "KHSV": "KHUN",
    "KHTL": "KAPX",
    "KHTS": "KRLX",
    "KHUT": "KICT",
    "KHVN": "KOKX",
    "KHVR": "KTFX",
    "KIAB": "KICT",
    "KIAD": "KLWX",
    "KIAH": "KHGX",
    "KILG": "KPHI",
    "KIML": "KLBF",
    "KINL": "KDLH",
    "KINT": "KRAH",
    "KINW": "KFGZ",
    "KIPT": "KCTP",
    "KISN": "KBIS",
    "KIXD": "KEAX",
    "KJEF": "KLSX",
    "KJFK": "KOKX",
    "KJLN": "KSGF",
    "KJNU": "PAJK",
    "KLAA": "KPUB",
    "KLAF": "KIND",
    "KLAN": "KGRR",
    "KLAS": "KVEF",
    "KLAX": "KLOX",
    "KLBB": "KLUB",
    "KLEX": "KLMK",
    "KLGA": "KOKX",
    "KLGB": "KLOX",
    "KLIC": "KBOU",
    "KLIT": "KLZK",
    "KLIZ": "KCAR",
    "KLMT": "KMFR",
    "KLND": "KRIW",
    "KLNK": "KOAX",
    "KLSE": "KARX",
    "KLWC": "KTOP",
    "KLWS": "KOTX",
    "KLXV": "KPUB",
    "KLYH": "KRNK",
    "KMAI": "KTAE",
    "KMCI": "KEAX",
    "KMCK": "KGLD",
    "KMCN": "KFFC",
    "KMCO": "KMLB",
    "KMCW": "KDMX",
    "KMCX": "KIND",
    "KMEI": "KJAN",
    "KMEM": "KMEG",
    "KMFD": "KCLE",
    "KMGM": "KBMX",
    "KMHK": "KTOP",
    "KMIA": "KMFL",
    "KMKC": "KWNS",
    "KMKE": "KMKX",
    "KMKG": "KGRR",
    "KMHN": "KOAX",
    "KMLI": "KDVN",
    "KMML": "KFSD",
    "KMMO": "KLOT",
    "KMOD": "KSTO",
    "KMSN": "KMKX",
    "KMSP": "KMPX",
    "KMSY": "KLIX",
    "KMTJ": "KGJT",
    "KMXF": "KBMX",
    "KMYF": "KSGX",
    "KNEW": "KLIX",
    "KNFD": "KWBC",
    "KNMK": "KPHI",
    "KNMW": "KSEW",
    "KNHK": "KLWX",
    "KNHZ": "KGYX",
    "KNKX": "KSGX",
    "KNMG": "KCRP",
    "KNPA": "KTAE",
    "KNQA": "KMEG",
    "KNYC": "KOKX",
    "KOAK": "KMTR",
    "KOBS": "KGYX",
    "KODX": "KGID",
    "KOFF": "KOAX",
    "KOFK": "KOAX",
    "KOJC": "KEAX",
    "KOKC": "KOUN",
    "KOLM": "KSEW",
    "KOLU": "KOAX",
    "KOMA": "KOAX",
    "KONL": "KLBF",
    "KORD": "KLOT",
    "KORF": "KAKQ",
    "KORH": "KBOX",
    "KORK": "KMHX",
    "KOTM": "KDMX",
    "KOVE": "KSTO",
    "KOVN": "KOAX",
    "KPBI": "KMFL",
    "KPDR": "KPTR",
    "KPDX": "KPQR",
    "KPHL": "KPHI",
    "KPHX": "KPSR",
    "KPIA": "KILX",
    "KPIT": "KPBZ",
    "KPKD": "KFGF",
    "KPKF": "KMKX",
    "KPKS": "KFSD",
    "KPMD": "KLOX",
    "KPNS": "KMOB",
    "KPSP": "KSGX",
    "KPTT": "KDDC",
    "KPVD": "KBOX",
    "KPWK": "KLOT",
    "KPWM": "KGYX",
    "KPZQ": "KAPX",
    "KRAL": "KSGX",
    "KRAP": "KUNR",
    "KRBL": "KSTO",
    "KRBO": "KCRP",
    "KRDD": "KSTO",
    "KRDM": "KPDT",
    "KRDU": "KRAH",
    "KRFD": "KLOT",
    "KRIC": "KAKQ",
    "KRIV": "KSGX",
    "KRKS": "KRIW",
    "KRME": "KBGM",
    "KRMG": "KFFC",
    "KRMI": "KMFL",
    "KRND": "KEWX",
    "KRNO": "KREV",
    "KROA": "KRNK",
    "KROC": "KBUF",
    "KROK": "KOUN",
    "KROW": "KABQ",
    "KRPH": "KFWD",
    "KRSE": "KSEW",
    "KRSL": "KICT",
    "KRBN": "KOHX",
    "KRLA": "KLOX",
    "KRPI": "KPBZ",
    "KRSF": "KMTR",
    "KRST": "KARX",
    "KRTN": "KABQ",
    "KRWF": "KMPX",
    "KRWL": "KCYS",
    "KRWM": "KPDT",
    "KRZL": "KLOT",
    "KRZS": "KSEW",
    "KSAC": "KSTO",
    "KSAD": "KTWC",
    "KSAF": "KABQ",
    "KSAN": "KSGX",
    "KSAT": "KEWX",
    "KSAV": "KCHS",
    "KSAW": "KMQT",
    "KSBA": "KLOX",
    "KSBD": "KSGX",
    "KSBN": "KIWX",
    "KSBP": "KLOX",
    "KSBY": "KAKQ",
    "KSCK": "KSTO",
    "KSDB": "KLOX",
    "KSDF": "KLMK",
    "KSDM": "KSGX",
    "KSEA": "KSEW",
    "KSEP": "KFWD",
    "KSEZ": "KFGZ",
    "KSFO": "KSTO",
    "KSHK": "KOKX",
    "KSHN": "KSEW",
    "KSHR": "KBYZ",
    "KSIL": "KLIX",
    "KSJC": "KMTR",
    "KSKA": "KOTX",
    "KSLE": "KPQR",
    "KSLN": "KICT",
    "KSLO": "KLSX",
    "KSLR": "KFWD",
    "KSMF": "KSTO",
    "KSMO": "KLOX",
    "KSMP": "KPDT",
    "KSMX": "KLOX",
    "KSNA": "KSGX",
    "KSNS": "KMTR",
    "KSNT": "KPIH",
    "KSNY": "KCYS",
    "KSPD": "KPUB",
    "KSPI": "KILX",
    "KSPS": "KOUN",
    "KSRH": "KEHU",
    "KSRQ": "KTBW",
    "KSSC": "KCAE",
    "KSSI": "KJAX",
    "KSSM": "KAPX",
    "KSTC": "KMPX",
    "KSTJ": "KEAX",
    "KSTL": "KLSX",
    "KSTN": "KJAN",
    "KSTS": "KMTR",
    "KSUN": "KPIH",
    "KSUS": "KLSX",
    "KSUU": "KSTO",
    "KSUX": "KFSD",
    "KSWF": "KOKX",
    "KSXT": "KMFR",
    "KSYR": "KBGM",
    "KSZL": "KEAX",
    "KTAD": "KPUB",
    "KTCC": "KABQ",
    "KTCL": "KBMX",
    "KTCM": "KSEW",
    "KTCS": "KEPZ",
    "KTEB": "KOKX",
    "KTLH": "KTAE",
    "KTOL": "KCLE",
    "KTPA": "KTBW",
    "KTPH": "KLKN",
    "KTRI": "KMRX",
    "KTRK": "KREV",
    "KTRM": "KSGX",
    "KTTD": "KPQR",
    "KTTS": "KMLB",
    "KTUL": "KTSA",
    "KTUP": "KMEG",
    "KTUR": "KTUA",
    "KTUS": "KTWC",
    "KTVC": "KAPX",
    "KTVL": "KREV",
    "KTWF": "KBOI",
    "KTXK": "KSHV",
    "KTYR": "KSHV",
    "KTYS": "KMRX",
    "KUCA": "KBGM",
    "KUIL": "KSEW",
    "KUIN": "KLSX",
    "KUKI": "KEKA",
    "KUMN": "KSGF",
    "KUNO": "KSGF",
    "KUNV": "KCTP",
    "KVBG": "KLOX",
    "KVCT": "KCRP",
    "KVCV": "KSGX",
    "KVIH": "KSGF",
    "KVLD": "KTAE",
    "KVNY": "KLOX",
    "KVPS": "KMOB",
    "KVPZ": "KLOT",
    "KVQN": "KAKQ",
    "KVRB": "KMLB",
    "KVTN": "KLBF",
    "KWAL": "KAKQ",
    "KWJF": "KLOX",
    "KWLD": "KICT",
    "KWMC": "KLKN",
    "KWRI": "KPHI",
    "KWSH": "KWBC",
    "KWWR": "KOUN",
    "KXMR": "KMLB",
    "KYKM": "KPDT",
    "KYNG": "KCLE",
    "KYUM": "KPSR",
    "KZZV": "KPBZ",
    "PADK": "PAFC",
    "PAED": "PAFC",
    "PAEI": "PAFG",
    "PAJN": "PAJK",
    "PAVD": "PAFC",
    "PAWS": "PAFC",
    "PGUA": "PGUM",
    "PHNL": "PHFO",
    "PHOG": "PHFO",
}


def process(order):
    """Process this timestamp"""
    cursor = PGCONN.cursor()
    ts = datetime.strptime(order[:6], "%y%m%d").replace(tzinfo=timezone.utc)
    base = ts - timedelta(days=2)
    ceiling = ts + timedelta(days=2)
    subprocess.call(["tar", "-xzf", order])
    inserts = 0
    deletes = 0
    filesparsed = 0
    bad = 0
    for fn in glob.glob(f"{order[:6]}[0-2][0-9].*"):
        with open(fn, "rb") as fh:
            content = re.sub(
                BAD_CHARS, "", fh.read().decode("ascii", "ignore")
            )
        # Now we are getting closer, lets split by the delimter as we
        # may have multiple products in one file!
        for bulletin_in in content.split("\001"):
            if bulletin_in == "":
                continue
            try:
                bulletin = noaaport_text(bulletin_in)
                prod = TextProduct(bulletin, utcnow=ts, parse_segments=False)
                prod.source = XREF_SOURCE.get(prod.source, prod.source)
            except Exception:
                bad += 1
                continue
            if prod.valid < base or prod.valid > ceiling:
                bad += 1
                continue

            tt = "0712" if prod.valid.month > 6 else "0106"
            table = f"products_{prod.valid.year}_{tt}"
            cursor.execute(
                f"""
                DELETE from {table} WHERE pil = %s and
                entered = %s and source = %s and data = %s
            """,
                (prod.afos, prod.valid, prod.source, bulletin),
            )
            deletes += cursor.rowcount
            cursor.execute(
                f"""
                INSERT into {table}
                (data, pil, entered, source, wmo) values (%s,%s,%s,%s,%s)
            """,
                (bulletin, prod.afos, prod.valid, prod.source, prod.wmo),
            )
            inserts += 1

        os.unlink(fn)
        filesparsed += 1
    print(
        f"{order} Files Parsed: {filesparsed} Inserts: {inserts} "
        f"Deletes: {deletes} Bad: {bad}"
    )
    cursor.close()
    PGCONN.commit()
    # remove cruft
    for fn in glob.glob("*.wmo"):
        os.unlink(fn)
    os.rename(order, "a" + order)


def main():
    """Go Main Go"""
    os.chdir("/mesonet/tmp/poker")
    for order in glob.glob("??????.DDPLUS.tar.gz"):
        process(order)


if __name__ == "__main__":
    # do something
    main()
