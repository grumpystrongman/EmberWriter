"""Extend the synthetic demo with observable but unreviewed book-four evidence.

Must run only with an isolated scratch EMBER_DATA_DIR containing
'part1-demo-data-v2'; never mutates real author projects.
"""
from pathlib import Path
import os

from app import series_vault as vault, series_canon as canon

root=Path(os.environ.get("EMBER_DATA_DIR","")).resolve()
if "part1-demo-data-v2" not in str(root).lower():
    raise RuntimeError("Refusing to modify anything except part1-demo-data-v2")
series=next((s for s in vault.list_series() if s["title"]=="The Astral Lanterns"),None)
if series is None: raise RuntimeError("Synthetic fixture missing")
sid=series["id"]
if any(v["ordinal"]==4 for v in vault.series_detail(sid)["volumes"]):
    raise RuntimeError("Book four was already imported; fixtures are immutable")
for name,kind,description in [
    ("Ilyra","character","An archivist whose allegiance is unproven."),
    ("Veil Tower","place","A remote tower surrounded by sea fog."),
    ("Obsidian Crown","artifact","A crown said to hum when the old roads awaken."),
    ("Dusk Order","faction","A secretive order of wardens in the northern valleys."),
]:
    canon.add_entity(sid,name,kind,description=description)
sentences=[
    "Seren guards the Obsidian Crown.",
    "Mara distrusts the Dusk Order.",
    "Kael protects Ilyra.",
    "Ilyra fears the silent winter.",
    "The Silent King seeks the Obsidian Crown.",
    "The Star Lantern reveals an ancient passage.",
    "Seren wants to rebuild the Lost Choir.",
    "Ilyra hides a silver map.",
    "Mara carries the Moon Compass.",
    "Kael guards the Veil Tower.",
    "Seren trusts Ilyra.",
    "Ilyra knows the path to the Glass Harbor.",
    "The Dusk Order guards the northern pass.",
    "The Obsidian Crown awakens the sleeping forest.",
    "Mara promises to return the Moon Compass.",
    "The Moon Compass foreshadows the last crossing.",
    "Kael discovers the sealed chamber.",
    "Ilyra reveals the truth of the old oath.",
    "Seren protects Mara.",
    "The Veil Tower hides a forgotten bell.",
    "Mara fears the seventh winter.",
    "The Lost Choir seeks the Silent King.",
    "Ilyra trusts Seren.",
    "Seren finds the missing standard.",
    "Kael carries the lantern.",
]
text="\n".join(sentences)+"\n"
vault.import_volume(
    sid,"book-four.md",text.encode("utf-8"),4,
    title="The Crown of Mists",kind="novel",edition_status="draft",
    rights_confirmed=True,
)
source=vault.series_detail(sid)["volumes"][-1]["sources"][0]["id"]
entities={e["name"]:e for e in canon.list_entities(sid)}
for idx,(subject,predicate,value,sentence,seq) in enumerate([
    ("Seren","guards","Obsidian Crown",sentences[0],5),
    ("Ilyra","fears","silent winter",sentences[3],10),
    ("Mara","carries","Moon Compass",sentences[8],15),
]):
    pos=text.index(sentence)
    fact=canon.propose_fact(sid,entities[subject]["id"],predicate,
        object_text=value,source_id=source,quote_start=pos,
        quote_end=pos+len(sentence),quote=sentence,
        start_book=4,start_sequence=seq)
    canon.review_fact(sid,fact["id"],"approved")
print("Synthetic four-book fixture",sid,"source",source)
