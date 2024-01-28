from dataclasses import dataclass


@dataclass
class GCNNotice:
    notice_type: str

    run_num: int
    evt_num: int

    ra: float
    dec: float

    tjd: int
    sod: int

    gal_lon: float
    gal_lat: float

    energy: float
    signalness: float

    revision: int


class GCNParser:
    @staticmethod
    def parse(notice: str):
        lines = notice.split("\n")
        kv = {}
        for line in lines:
            pos = line.find(":")
            if pos < 0:
                continue
            kv[line[0:pos]] = line[pos + 1:].strip()

        gal_lon, gal_lat = kv['GAL_COORDS'].split('[deg]')[0].split(',')

        return GCNNotice(
            notice_type=kv['NOTICE_TYPE'],
            run_num=int(kv['RUN_NUM']),
            evt_num=int(kv['EVENT_NUM']),
            ra=float(kv['SRC_RA'].split('d')[0]),
            dec=float(kv['SRC_DEC'].split('d')[0]),
            tjd=int(kv["DISCOVERY_DATE"].split("TJD")[0]),
            sod=int(kv["DISCOVERY_TIME"].split("SOD")[0]),
            gal_lon=float(gal_lon),
            gal_lat=float(gal_lat),
            energy=float(kv["ENERGY"].split('[')[0]),
            signalness=float(kv["SIGNALNESS"].split('[')[0]),
            revision=int(kv["REVISION"])
        )
