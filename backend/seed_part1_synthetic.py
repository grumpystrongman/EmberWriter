"""Seed ONLY the isolated synthetic visual acceptance dataset.

Requires EMBER_DATA_DIR pointing to an explicit scratch directory. Refuses
to operate on a preexisting directory with projects or a vault.
"""
from __future__ import annotations
import os
from pathlib import Path
from app import series_vault as vault, series_canon as canon, storage

root = Path(os.environ.get("EMBER_DATA_DIR", "")).resolve()
if "part1-demo-data" not in str(root).lower():
    raise RuntimeError("Refusing to seed outside the isolated part1-demo-data location")
if root.exists() and any(root.rglob("series-vault.sqlite3")):
    raise RuntimeError("Synthetic series already seeded; no changes made")
series = vault.create_series("The Astral Lanterns", "Synthetic three-book fantasy chronicle for interface testing only")
sentences = [
    [
        "Seren guards the Star Lantern beneath the Ashen Library.",
        "Seren fears the hollow sky and dreams of finding her lost brother.",
        "Mara trusts Seren to keep their oath.",
        "The Moon Compass points toward the Broken Citadel.",
        "The Star Lantern foreshadows the return of the Silent King.",
        "Seren believes the lantern is safe to carry.",
        "Readers learn that the lantern belongs to the Lost Choir.",
        "Kael speaks in clipped commands, while Seren speaks in careful riddles.",
    ],
    [
        "Seren moves the Star Lantern to the Glass Harbor.",
        "Mara doubts Seren after a secret meeting with Kael.",
        "Kael protects Mara during the burning of the Glass Harbor.",
        "Seren discovers that the lantern consumes memories.",
        "The Moon Compass reveals a passage beneath the Broken Citadel.",
        "The Silent King awakens when the sixth bell rings.",
        "Seren wants to protect Mara without betraying Kael.",
        "Readers discover Mara secretly knew the harbor would burn.",
    ],
    [
        "Seren returns the Star Lantern to the Ashen Library.",
        "Mara forgives Seren after hearing the truth of her oath.",
        "Kael reveals that he served the Silent King.",
        "The Star Lantern resolves the ancient prophecy.",
        "The Silent King falls when the choir sings at dawn.",
        "Seren no longer fears the hollow sky.",
        "The Moon Compass is hidden in the Glass Harbor.",
    ],
]
volumes=[]
for idx,rows in enumerate(sentences,1):
    text="\n\n".join(rows)
    vault.import_volume(series["id"],f"book-{idx}.md",text.encode("utf-8"),idx,
                        title=["The Library of Ash","Harbor of Glass","Dawn of the Choir"][idx-1],
                        kind="novel",edition_status="approved",rights_confirmed=True)
    volumes.append((text,vault.series_detail(series["id"])["volumes"][idx-1]["sources"][0]["id"]))
names = [
 ("Seren","character","Keeper of the Star Lantern; careful, principled, and haunted by a missing brother."),
 ("Mara","character","A fierce navigator who values trust above reputation."),
 ("Kael","character","A reluctant guardian tied to an ancient court."),
 ("Star Lantern","artifact","A relic that illuminates memory and shadow."),
 ("Moon Compass","artifact","A compass that ignores ordinary north."),
 ("Silent King","character","An ancient sovereign whose waking threatens the coast."),
 ("Ashen Library","place","A cliffside archive of forbidden histories."),
 ("Glass Harbor","place","A city of mirrors, shipwrights and salt."),
 ("Broken Citadel","place","A ruined fortress above the sea."),
 ("Lost Choir","faction","A circle of singers charged with sealing the old gates."),
]
entities={}
for name,kind,description in names:
    entities[name]=canon.add_entity(series["id"],name,kind,description=description)
def fact(book,subject,predicate,value,phrase,target=None,scope="world",knower=None,approve=True,end_book=None):
    text,source=volumes[book-1]
    start=text.index(phrase)
    item=canon.propose_fact(series["id"],entities[subject]["id"],predicate,object_text=value,
        object_entity_id=entities[target]["id"] if target else None,
        scope=scope,knower_id=entities[knower]["id"] if knower else None,
        start_book=book,end_book=end_book,source_id=source,
        quote_start=start,quote_end=start+len(phrase),quote=phrase)
    if approve:
        canon.review_fact(series["id"],item["id"],"approved")
    return item
fact(1,"Seren","located_in","Ashen Library","Seren guards the Star Lantern beneath the Ashen Library.",target="Ashen Library",end_book=1)
fact(1,"Seren","fears","the hollow sky","Seren fears the hollow sky and dreams of finding her lost brother.")
fact(1,"Seren","wants","to find her lost brother","Seren fears the hollow sky and dreams of finding her lost brother.")
fact(1,"Mara","trusts","Seren","Mara trusts Seren to keep their oath.",target="Seren")
fact(1,"Moon Compass","points_to","Broken Citadel","The Moon Compass points toward the Broken Citadel.",target="Broken Citadel")
fact(1,"Star Lantern","foreshadows","return of the Silent King","The Star Lantern foreshadows the return of the Silent King.",target="Silent King")
fact(1,"Star Lantern","believed_safe","safe to carry","Seren believes the lantern is safe to carry.",scope="character_belief",knower="Seren")
fact(1,"Star Lantern","belongs_to","Lost Choir","Readers learn that the lantern belongs to the Lost Choir.",target="Lost Choir",scope="reader_reveal")
fact(1,"Kael","speech_style","clipped commands","Kael speaks in clipped commands, while Seren speaks in careful riddles.")
fact(1,"Seren","voice","careful riddles","Kael speaks in clipped commands, while Seren speaks in careful riddles.")
fact(2,"Seren","located_in","Glass Harbor","Seren moves the Star Lantern to the Glass Harbor.",target="Glass Harbor",end_book=2)
fact(2,"Mara","distrusts","Seren","Mara doubts Seren after a secret meeting with Kael.",target="Seren")
fact(2,"Kael","protects","Mara","Kael protects Mara during the burning of the Glass Harbor.",target="Mara")
fact(2,"Star Lantern","consumes","memories","Seren discovers that the lantern consumes memories.",scope="character_belief",knower="Seren")
fact(2,"Moon Compass","reveals","passage beneath Broken Citadel","The Moon Compass reveals a passage beneath the Broken Citadel.",target="Broken Citadel")
fact(2,"Silent King","awakens_at","sixth bell","The Silent King awakens when the sixth bell rings.")
fact(2,"Seren","wants","to protect Mara","Seren wants to protect Mara without betraying Kael.")
fact(2,"Mara","conceals","foreknowledge of the fire","Readers discover Mara secretly knew the harbor would burn.",scope="reader_reveal")
fact(3,"Seren","located_in","Ashen Library","Seren returns the Star Lantern to the Ashen Library.",target="Ashen Library")
fact(3,"Mara","forgives","Seren","Mara forgives Seren after hearing the truth of her oath.",target="Seren")
fact(3,"Kael","reveals","his service to the Silent King","Kael reveals that he served the Silent King.",scope="reader_reveal")
fact(3,"Star Lantern","resolves","the ancient prophecy","The Star Lantern resolves the ancient prophecy.")
fact(3,"Silent King","falls_at","dawn","The Silent King falls when the choir sings at dawn.")
fact(3,"Moon Compass","located_in","Glass Harbor","The Moon Compass is hidden in the Glass Harbor.",target="Glass Harbor")
fact(3,"Seren","releases_fear","the hollow sky","Seren no longer fears the hollow sky.",approve=False)
print("Synthetic series created:",series["id"],"in",root)
