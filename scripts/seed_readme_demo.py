from __future__ import annotations

import os
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BASE = os.getenv("EMBER_DEMO_API", "http://127.0.0.1:8000/api").rstrip("/")
PROJECT_NAME = "The Glass Harbor"


def put_text(client: httpx.Client, slug: str, path: str, content: str) -> None:
    response = client.put(
        f"{BASE}/projects/{slug}/file",
        params={"path": path},
        json={"content": content},
    )
    response.raise_for_status()


def demo_reference(path: Path) -> None:
    image = Image.new("RGB", (1200, 800), "#14131a")
    draw = ImageDraw.Draw(image)
    for y in range(800):
        r = 20 + int(30 * y / 800)
        g = 19 + int(18 * y / 800)
        b = 26 + int(12 * y / 800)
        draw.line((0, y, 1200, y), fill=(r, g, b))
    draw.ellipse((80, 90, 430, 440), fill="#6f2f28", outline="#d89c73", width=5)
    draw.polygon([(470, 650), (690, 220), (910, 650)], fill="#272838", outline="#8e91ad")
    draw.rectangle((720, 110, 1110, 280), fill="#201f27", outline="#c5a46d", width=4)
    draw.text((755, 150), "REDWATER BRIDGE", fill="#f2e6d0")
    draw.text((755, 195), "CANON REFERENCE", fill="#c5a46d")
    draw.line((0, 650, 1200, 650), fill="#6f5144", width=10)
    image.save(path, format="PNG")


def checked(response: httpx.Response) -> httpx.Response:
    if response.is_error:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text}")
    return response


def main() -> None:
    with httpx.Client(timeout=30) as client:
        existing = checked(client.get(f"{BASE}/projects")).json()
        for item in existing:
            if item.get("name") == PROJECT_NAME:
                slug = item["slug"]
                break
        else:
            response = checked(client.post(
                f"{BASE}/projects",
                json={
                    "name": PROJECT_NAME,
                    "description": "A seeded documentation project showing EmberWriter's story-aware workflow.",
                },
            ))
            slug = response.json()["slug"]

        put_text(
            client,
            slug,
            "manuscript/chapter-001.md",
            """# Chapter 1 — The Bridge That Burned\n\nThe bells of Bellhaven were still ringing when Rowan reached Greywater Bridge. Smoke dragged low across the river, turning the sunrise copper.\n\nMira waited beside the broken milestone, coat snapping in the wind. \"If we take the king's road, Corvin sees us before noon.\"\n\nRowan looked east toward the black line of the Pineward. The forest route was slower, but the old watch road cut behind the ruined observatory and surfaced less than a mile from Highwatch.\n\n\"Then we don't take the king's road.\"\n\nBehind them, a horn sounded from the city gate. Once. Twice.\n\nMira smiled without humor. \"Good. I was worried this would be easy.\"\n\nThey crossed as the first riders appeared on the western ridge.\n""",
        )
        put_text(
            client,
            slug,
            "characters/rowan.md",
            """# Rowan\n\n## Role in the story\nReluctant field leader trying to keep a fractured expedition together.\n\n## Appearance & presence\nWeathered traveler, practical dark clothing, observant rather than showy.\n\n## Voice & speech\nMeasured, dry humor, asks questions before giving orders.\n\n## Wants, needs & fears\nWants to keep the group alive without turning their bond into another form of control. Fears becoming indispensable in the wrong way.\n\n## Continuity notes\nKnows the capital roads. Has never used the observatory trail before Chapter 1.\n""",
        )
        put_text(
            client,
            slug,
            "characters/mira.md",
            """# Mira\n\n## Role in the story\nStrategist learning to coordinate the group without controlling it.\n\n## Appearance & presence\nPoised, precise, silver and emerald details, moves like every gesture has already been considered.\n\n## Voice & speech\nEconomical, teasing when relaxed, surgical when under pressure.\n\n## History\nServed near Highwatch years earlier and knows military routes most civilians never see.\n\n## Continuity notes\nShe knows the Pineward watch road and the ruined observatory approach.\n""",
        )
        put_text(
            client,
            slug,
            "world/greywater-bridge.md",
            """# Greywater Bridge\n\n**Type:** Location\n\n## Canon\nA stone bridge east of Bellhaven spanning the Greywater. It is the fastest legal route toward Highwatch.\n\n## Current state\nOpen at the start of Chapter 1, but vulnerable to pursuit from Bellhaven's eastern gate.\n\n## Scene details\nCopper dawn, river fog, cracked milestones, long sightlines that make riders visible from a distance.\n""",
        )
        put_text(
            client,
            slug,
            "world/pineward.md",
            """# Pineward\n\n**Type:** Region\n\n## Canon\nDense old forest between Greywater and Highwatch. The king's road skirts its southern edge; an abandoned watch road passes through it.\n\n## Rules & constraints\nWagons are slow after rain. Riders can be hidden from the main road. The ruined observatory is visible only from the eastern ridge.\n""",
        )

        reference_path = Path("/tmp/greywater-bridge-reference.png")
        demo_reference(reference_path)
        with reference_path.open("rb") as handle:
            response = client.post(
                f"{BASE}/projects/{slug}/visual-assets/greywater-bridge-reference/upload",
                params={"title": "Greywater Bridge", "kind": "location"},
                files={"image": (reference_path.name, handle, "image/png")},
            )
        checked(response)

        atlas = {
            "schema_version": 1,
            "map": {"title": "The Glass Harbor — Story Atlas", "units": "miles", "background_asset_id": None},
            "travel_profiles": {
                "walk": {"speed_mph": 3, "hours_per_day": 8},
                "horse": {"speed_mph": 5, "hours_per_day": 9},
                "wagon": {"speed_mph": 3.5, "hours_per_day": 8},
                "boat": {"speed_mph": 4, "hours_per_day": 10},
                "airship": {"speed_mph": 25, "hours_per_day": 16},
                "portal": {"speed_mph": 10000, "hours_per_day": 24},
            },
            "locations": [
                {"id": "bellhaven", "name": "Bellhaven", "kind": "city", "x": -360, "y": 70, "region": "Crownlands", "summary": "Capital city and origin of the pursuit.", "terrain": ["urban"], "tags": ["capital", "pursuit"], "canon_status": "canon", "position_status": "canon", "confidence": 1, "source_paths": ["manuscript/chapter-001.md"], "known_by": ["Rowan", "Mira"], "image_asset_id": None},
                {"id": "greywater-bridge", "name": "Greywater Bridge", "kind": "landmark", "x": -120, "y": 20, "region": "Greywater", "summary": "Fast crossing with dangerous sightlines.", "terrain": ["river", "road"], "tags": ["bridge", "chokepoint"], "canon_status": "canon", "position_status": "inferred", "confidence": 0.95, "source_paths": ["manuscript/chapter-001.md", "world/greywater-bridge.md"], "known_by": ["Rowan", "Mira"], "image_asset_id": "greywater-bridge-reference"},
                {"id": "pineward", "name": "Pineward", "kind": "region", "x": 130, "y": 105, "region": "Eastern March", "summary": "Dense forest hiding an abandoned military route.", "terrain": ["forest", "mud"], "tags": ["cover", "watch-road"], "canon_status": "canon", "position_status": "inferred", "confidence": 0.9, "source_paths": ["manuscript/chapter-001.md", "world/pineward.md"], "known_by": ["Mira"], "image_asset_id": None},
                {"id": "ruined-observatory", "name": "Ruined Observatory", "kind": "ruin", "x": 310, "y": -70, "region": "Eastern March", "summary": "Abandoned landmark overlooking the eastern ridge.", "terrain": ["hills", "ruins"], "tags": ["secret", "vantage"], "canon_status": "canon", "position_status": "suggested", "confidence": 0.8, "source_paths": ["manuscript/chapter-001.md"], "known_by": ["Mira"], "image_asset_id": None},
                {"id": "highwatch", "name": "Highwatch", "kind": "fortress", "x": 520, "y": 25, "region": "Eastern March", "summary": "Fortress destination beyond the forest.", "terrain": ["hills", "fortress"], "tags": ["destination"], "canon_status": "canon", "position_status": "inferred", "confidence": 0.9, "source_paths": ["manuscript/chapter-001.md"], "known_by": ["Rowan", "Mira"], "image_asset_id": None},
            ],
            "connections": [
                {"id": "bellhaven-greywater", "from_id": "bellhaven", "to_id": "greywater-bridge", "name": "Eastern Gate Road", "distance": 12, "bidirectional": True, "mode_multipliers": {}, "terrain_multiplier": 1, "risk": 4, "drama": 4, "lore": 1, "relationship": 2, "active_from_chapter": 0, "active_until_chapter": None, "canon_status": "canon", "confidence": 1, "known_by": ["Rowan", "Mira"], "source_paths": ["manuscript/chapter-001.md"], "notes": "Fast but exposed to pursuit."},
                {"id": "greywater-kings-road", "from_id": "greywater-bridge", "to_id": "highwatch", "name": "King's Road", "distance": 42, "bidirectional": True, "mode_multipliers": {}, "terrain_multiplier": 1, "risk": 5, "drama": 3, "lore": 1, "relationship": 1, "active_from_chapter": 0, "active_until_chapter": None, "canon_status": "canon", "confidence": 0.95, "known_by": ["Rowan", "Mira"], "source_paths": ["manuscript/chapter-001.md"], "notes": "Fastest route, watched by Corvin's scouts."},
                {"id": "greywater-pineward", "from_id": "greywater-bridge", "to_id": "pineward", "name": "Old Watch Road", "distance": 19, "bidirectional": True, "mode_multipliers": {"wagon": 1.5}, "terrain_multiplier": 1.25, "risk": 2, "drama": 4, "lore": 4, "relationship": 4, "active_from_chapter": 0, "active_until_chapter": None, "canon_status": "canon", "confidence": 0.9, "known_by": ["Mira"], "source_paths": ["manuscript/chapter-001.md", "world/pineward.md"], "notes": "Slower, hidden, and ideal for character pressure."},
                {"id": "pineward-observatory", "from_id": "pineward", "to_id": "ruined-observatory", "name": "Ridge Trail", "distance": 11, "bidirectional": True, "mode_multipliers": {"wagon": 2.0}, "terrain_multiplier": 1.4, "risk": 3, "drama": 5, "lore": 5, "relationship": 4, "active_from_chapter": 0, "active_until_chapter": None, "canon_status": "inferred", "confidence": 0.82, "known_by": ["Mira"], "source_paths": ["manuscript/chapter-001.md"], "notes": "Narrow approach with excellent interception and reveal potential."},
                {"id": "observatory-highwatch", "from_id": "ruined-observatory", "to_id": "highwatch", "name": "Eastern Descent", "distance": 9, "bidirectional": True, "mode_multipliers": {}, "terrain_multiplier": 1.2, "risk": 2, "drama": 3, "lore": 3, "relationship": 2, "active_from_chapter": 0, "active_until_chapter": None, "canon_status": "suggested", "confidence": 0.75, "known_by": ["Mira"], "source_paths": [], "notes": "Suggested final approach; author can accept or revise."},
            ],
            "events": [
                {"id": "bridge-hunt-ch1", "chapter": 1, "action": "note", "target_id": "greywater-bridge", "summary": "Corvin's riders begin pursuit from Bellhaven.", "value": "pursuit", "source_path": "manuscript/chapter-001.md"}
            ],
        }
        checked(client.put(f"{BASE}/projects/{slug}/atlas", json=atlas))
        print(slug)


if __name__ == "__main__":
    main()
