# Book publisher directory source

The catalog is a Wikidata snapshot from November 11, 2026. It includes English labels for entities explicitly classified as book publishers, plus official website statements where available. Wikidata structured data is available under CC0. Entries can include historical publishers, inactive websites, and publishers that accept submissions only through agents.

- [Wikidata book publisher class](https://www.wikidata.org/wiki/Q1320047)
- [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)

The source query used the Wikidata Query Service.

```sparql
SELECT ?item ?label ?site WHERE {
  ?item wdt:P31 wd:Q1320047; rdfs:label ?label.
  FILTER(LANG(?label) = "en")
  OPTIONAL { ?item wdt:P856 ?site }
}
LIMIT 10000
```

The import keeps one row per Wikidata ID and prefers an HTTPS website when several are listed. The catalog contains discovery records. Weekly checks run on known guidelines pages and pages authors import successfully.
