import datetime
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests


def parse_iso_to_xmltv(iso_str: str) -> str:
    """Converteix ISO 8601 (2026-08-28T23:42:08+02:00) a format XMLTV (YYYYMMDDHHMMSS +HHMM)."""
    if not iso_str:
        return ""
    dt = datetime.datetime.fromisoformat(iso_str)
    return dt.strftime("%Y%m%d%H%M%S %z")


def parse_duration_to_seconds(durada_str: str) -> int:
    """Converteix HH:MM:SS a segons totals."""
    if not durada_str:
        return 0
    parts = durada_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def parse_credits_from_synopsis(sinopsi: str):
    """Extreu directors, guionistes i actors quan la sinopsi conté la fitxa tècnica."""
    credits_dict = {"director": [], "writer": [], "actor": []}
    if not sinopsi:
        return credits_dict

    # Cercar direcció
    match_dir = re.search(r"Direcció:\s*([^G\n]+)", sinopsi)
    if match_dir:
        dirs = [
            d.strip()
            for d in re.split(r",| i ", match_dir.group(1))
            if d.strip()
        ]
        credits_dict["director"].extend(dirs)

    # Cercar guió
    match_gui = re.search(r"Guió:\s*([^P\n]+)", sinopsi)
    if match_gui:
        writers = [
            w.strip()
            for w in re.split(r",| i ", match_gui.group(1))
            if w.strip()
        ]
        credits_dict["writer"].extend(writers)

    # Cercar intèrprets / actors
    match_act = re.search(r"Intèrprets:\s*([^\n]+)", sinopsi)
    if match_act:
        actors = [
            a.strip()
            for a in re.split(r",| i ", match_act.group(1))
            if a.strip()
        ]
        credits_dict["actor"].extend(actors)

    return credits_dict


def main():
    url = (
        "https://dinamics.ccma.cat/wsarafem/arafem/tv/profile/noimage/geo/cat"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    tv = ET.Element("tv", {"generator-info-name": "CCMA-EPG-Scraper-Enriched"})

    canals = data.get("canal", [])
    canals_processats = set()

    for item in canals:
        canal_name = item.get("@attributes", {}).get("name")
        if not canal_name:
            continue

        if canal_name not in canals_processats:
            channel_elem = ET.SubElement(tv, "channel", id=canal_name)
            display_name = ET.SubElement(channel_elem, "display-name")
            display_name.text = canal_name.upper()
            canals_processats.add(canal_name)

        for bloc in ["ara_fem", "despres_fem"]:
            prog_data = item.get(bloc)
            if not isinstance(prog_data, dict) or not prog_data.get(
                "start_time"
            ):
                continue

            start_xmltv = parse_iso_to_xmltv(prog_data.get("start_time"))
            stop_xmltv = parse_iso_to_xmltv(prog_data.get("end_time"))

            prog_elem = ET.SubElement(
                tv,
                "programme",
                start=start_xmltv,
                stop=stop_xmltv,
                channel=canal_name,
            )

            # Títol principal
            titol = (
                prog_data.get("titol_programa")
                or prog_data.get("titol_tdt")
                or "Sense títol"
            )
            title_elem = ET.SubElement(prog_elem, "title", lang="ca")
            title_elem.text = titol

            # Subtítol / Títol del capítol
            subtitol = prog_data.get("titol_capitol")
            if subtitol:
                sub_elem = ET.SubElement(prog_elem, "sub-title", lang="ca")
                sub_elem.text = subtitol

            # Sinopsi
            sinopsi = prog_data.get("sinopsi", "")
            if sinopsi:
                desc_elem = ET.SubElement(prog_elem, "desc", lang="ca")
                desc_elem.text = sinopsi

            # Crèdits (Actors, Directors, Guionistes)
            credits_data = parse_credits_from_synopsis(sinopsi)
            if any(credits_data.values()):
                credits_elem = ET.SubElement(prog_elem, "credits")
                for role, people in credits_data.items():
                    for person in people:
                        p_elem = ET.SubElement(credits_elem, role)
                        p_elem.text = person

            # Durada en segons
            durada_sec = parse_duration_to_seconds(prog_data.get("durada", ""))
            if durada_sec > 0:
                length_elem = ET.SubElement(
                    prog_elem, "length", units="seconds"
                )
                length_elem.text = str(durada_sec)

            # Número de capítol
            capitol = prog_data.get("capitol")
            if capitol and str(capitol) != "0":
                ep_elem = ET.SubElement(
                    prog_elem, "episode-num", system="onscreen"
                )
                ep_elem.text = str(capitol)

            # Categories (Grup i Subgrup)
            classif = prog_data.get("classificacio", {})
            if isinstance(classif, dict):
                grup = classif.get("grup")
                subgrup = classif.get("subgrup")
                if grup:
                    cat1 = ET.SubElement(prog_elem, "category", lang="ca")
                    cat1.text = grup
                if subgrup and subgrup != grup:
                    cat2 = ET.SubElement(prog_elem, "category", lang="ca")
                    cat2.text = subgrup

            # Classificació d'edat / Target
            target = prog_data.get("target")
            if target:
                rating_elem = ET.SubElement(prog_elem, "rating")
                val_elem = ET.SubElement(rating_elem, "value")
                val_elem.text = target

            # Subtítols
            if (
                prog_data.get("subtitulat_catala") == "yes"
                or prog_data.get("subtitulat_vo") == "yes"
            ):
                sub_lang = (
                    "ca" if prog_data.get("subtitulat_catala") == "yes" else "vo"
                )
                ET.SubElement(
                    prog_elem,
                    "subtitles",
                    type="teletext",
                )

            # Indicador de Reemissió / Repetició
            if prog_data.get("reemissio") == "yes":
                ET.SubElement(prog_elem, "previously-shown")

            # Imatge destacada
            imatge = prog_data.get("destacat_imatge")
            if imatge:
                ET.SubElement(prog_elem, "icon", src=imatge)

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(
        indent="  "
    )

    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)


if __name__ == "__main__":
    main()
