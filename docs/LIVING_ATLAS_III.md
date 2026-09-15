# Living Atlas III

Living Atlas III separates story topology from persisted cartography. The atlas stores author-editable geographic features (coastlines, rivers, roads, forests, walls, districts, structures, rooms and other map geometry) alongside story locations and routes.

The feature model supports manuscript-derived suggestions, generated fictional geography and imported real-world GeoJSON. Suggested geometry never becomes canon automatically; authors can reshape it in World Studio and promote it deliberately.

## Design rules

- Topology answers what connects to what. Cartography describes what a place physically looks like.
- AI-derived geography is always `suggested` until the author promotes it.
- Imported real geography preserves source metadata while projecting coordinates into the story canvas.
- Generated fantasy geography is deterministic from a seed so maps can be regenerated and revised.
- Geometry is stored in atlas coordinates and can be edited vertex-by-vertex in World Studio.
