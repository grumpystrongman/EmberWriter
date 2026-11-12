"""Synthetic editorial demo only. Requires designated isolated Part 1/2 data root."""
import os
from pathlib import Path
from app import storage

root=Path(os.environ.get("EMBER_DATA_DIR","")).resolve()
if root.name != "part1-demo-data-v2":
    raise RuntimeError("Refusing to seed outside isolated synthetic demo root")
projects=storage.list_projects()
if projects:
    if len(projects)!=1 or projects[0]["name"]!="The Ashen Coast — Synthetic Editorial Review":
        raise RuntimeError("Unexpected existing projects; refusing to change them")
    print("Synthetic editorial project already exists:",projects[0]["slug"])
    raise SystemExit(0)

project=storage.create_project("The Ashen Coast — Synthetic Editorial Review")
chapters=[
("The Letter Beneath the Door",[
 "Mira opened the weather-worn letter on a stormless morning. The town bell hadn't rung in three days, and nobody would explain why.",
 "She set the letter beside the silver compass. Its needle had always pointed inland, toward the old lighthouse, but now it trembled toward the sea.",
 '"The harbor is safe," said Tavi. "It has always been safe." Mira looked past him, where the fishing boats swayed beneath an empty sky.',
 "Mira wanted to know who had sealed the lighthouse. The thought of asking her brother made her stomach tighten.",
]),
("The Empty Harbor",[
 "The hidden lantern was on a boat. The hidden lantern was on a boat. The hidden lantern was on a boat, yet none of the fishermen admitted seeing it.",
 "Tavi stood on the jetty and counted shadows. The glass compass swung toward the old lighthouse.",
 '"I know you are hiding something," Mira said. Tavi said nothing. His silence felt more dangerous than any answer.',
 "The storm came without warning. It should have driven everyone indoors, but Mara walked alone toward the water.",
]),
("The Salt Road",[
 "The road was white with sea salt. Mira watched Tavi walk three steps ahead, their argument still unfinished.",
 "They took the glass compass through a burned orchard, then past the ruined observatory where the Silent King had once kept his court.",
 "Mira thought of the letter beneath her door, and she wondered whether its warning had been meant for her or for Tavi.",
 "The hidden lantern was on a boat. Even in the orchard, she could not forget what she had seen.",
]),
("The First Confession",[
 '"I was at the lighthouse," Tavi said. "I knew the keeper. And I knew what the lantern could do."',
 "Mira held the glass compass so tightly its edge bit her palm. Trust had already been damaged, and this confession did not mend it.",
 "Tavi explained the keeper had warned him about the Silent King. He had stayed silent because he feared losing Mira, not because he intended to deceive her.",
 "Beyond the window, the hidden lantern was on a boat. Someone had brought it back to the harbor.",
]),
("The Lighthouse Opens",[
 "At dawn, Mira reached the lighthouse and found its iron gates unlocked. The glass compass finally pointed straight ahead.",
 '"You can turn back," Tavi told her. Mira shook her head. She had come too far to let fear choose for her.',
 "Inside the tower, the empty bell began to move. The hidden lantern was on a boat, but its light had somehow reached the stairwell.",
 "The keeper's journal lay open on the desk. Its final page had been torn away, leaving the mystery of the Silent King unanswered.",
]),
]
for i,(title,parts) in enumerate(chapters,1):
    text="# "+title+"\n\n"+"\n\n".join(parts)+"\n"
    storage.save_text(project["slug"],f"manuscript/{i:02d}-{title.lower().replace(' ','-')}.md",text)
print("Created isolated synthetic editorial project:",project["slug"],"with",len(chapters),"chapters")
