import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests


def parse_iso_to_xmltv(iso_str: str) -> str:
    """Converteix ISO 8601 (2026-08-28T23:42:08+02:00) a format XMLTV (YYYYMMDDHHMMSS +HHMM)."""
    if not iso_str:
        return ""
    dt = datetime.datetime.fromisoformat(iso_str)
    return dt.strftime("%Y%m%d%H%M%S %z")


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

    # Arrel de l'XMLTV
    tv = ET.Element("tv", {"generator-info-name": "CCMA-EPG-Scraper"})

    canals = data.get("canal", [])
    canals_processats = set()

    for item in canals:
        canal_name = item.get("@attributes", {}).get("name")
        if not canal_name:
            continue

        # Afegir el canal a la capçalera de l'XML si no existeix
        if canal_name not in canals_processats:
            channel_elem = ET.SubElement(tv, "channel", id=canal_name)
            display_name = ET.SubElement(channel_elem, "display-name")
            display_name.text = canal_name.upper()
            canals_processats.add(canal_name)

        # Processar programes (ara_fem i despres_fem)
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

            # Títol
            titol = (
                prog_data.get("titol_programa")
                or prog_data.get("titol_tdt")
                or "Sense títol"
            )
            title_elem = ET.SubElement(prog_elem, "title", lang="ca")
            title_elem.text = titol

            # Subtítol / Capítol
            subtitol = prog_data.get("titol_capitol")
            if subtitol:
                sub_elem = ET.SubElement(prog_elem, "sub-title", lang="ca")
                sub_elem.text = subtitol

            # Sinopsi
            sinopsi = prog_data.get("sinopsi")
            if sinopsi:
                desc_elem = ET.SubElement(prog_elem, "desc", lang="ca")
                desc_elem.text = sinopsi

            # Categoria / Temàtica
            categoria = prog_data.get("classificacio", {}).get("grup")
            if categoria:
                cat_elem = ET.SubElement(prog_elem, "category", lang="ca")
                cat_elem.text = categoria

            # Imatge
            imatge = prog_data.get("destacat_imatge")
            if imatge:
                ET.SubElement(prog_elem, "icon", src=imatge)

    # Formatejar i desar l'XML amb indentació neta
    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(
        indent="  "
    )

    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)


if __name__ == "__main__":
    main()
