## ADDED Requirements

### Requirement: WikipediaClient supports opensearch title lookup
`WikipediaClient` SHALL expose a `search(query: str, lang: str) -> str | None` method that calls the Wikipedia opensearch API and returns the first matching article title, or `None` if no results are found.

#### Scenario: Query returns matching title
- **WHEN** `WikipediaClient.search("故宮博物院", "zh-TW")` is called and the opensearch API returns titles `["國立故宮博物院", ...]`
- **THEN** the method returns `"國立故宮博物院"`

#### Scenario: Query returns no results
- **WHEN** `WikipediaClient.search("NoSuchPlace", "zh-TW")` is called and the opensearch API returns an empty titles list
- **THEN** the method returns `None`

#### Scenario: Language code zh-TW maps to zh subdomain
- **WHEN** `WikipediaClient.search(query, "zh-TW")` is called
- **THEN** the HTTP request targets `zh.wikipedia.org`

---

### Requirement: NominatimClient performs reverse geocoding
A new `NominatimClient` class SHALL call `nominatim.openstreetmap.org/reverse` to look up the administrative address (suburb and city) for a given lat/lon pair. The client SHALL return a `NominatimAddress` dataclass with fields `suburb`, `city_district`, `city`, `town`, `village`. On any network error or non-200 response, the client SHALL return `None`.

#### Scenario: Successful reverse geocode returns suburb and city
- **WHEN** `NominatimClient.reverse(25.04, 121.53)` is called and Nominatim returns `{"address": {"suburb": "大安區", "city": "台北市"}}`
- **THEN** the returned `NominatimAddress` has `suburb == "大安區"` and `city == "台北市"`

#### Scenario: Missing suburb falls back to borough
- **WHEN** the Nominatim response contains `borough` but not `suburb`
- **THEN** `NominatimAddress.suburb` is set to the `borough` value

#### Scenario: Missing city falls back to town
- **WHEN** the Nominatim response contains `town` but not `city`
- **THEN** `NominatimAddress.city` is set to the `town` value

#### Scenario: Network error returns None
- **WHEN** the HTTP call raises any exception
- **THEN** `NominatimClient.reverse()` returns `None`

#### Scenario: Non-200 response returns None
- **WHEN** Nominatim returns HTTP 404
- **THEN** `NominatimClient.reverse()` returns `None`

#### Scenario: User-Agent header is sent
- **WHEN** `NominatimClient.reverse()` makes an HTTP request
- **THEN** the request includes a `User-Agent: ai-tour-guide/1.0` header as required by Nominatim policy

---

### Requirement: WikipediaResolver resolves POI name via 4-level fallback chain
A new `WikipediaResolver` service SHALL resolve a POI name to a `WikiArticle` using the following fallback order:
1. Search Wikipedia directly by `poi_name`
2. Search Wikipedia by `"{poi_name}，{suburb}"` (suburb from Nominatim reverse geocoding)
3. Search Wikipedia by `"{poi_name}，{city}"` (city from Nominatim reverse geocoding)
4. Return `None`

Nominatim SHALL be called at most once per resolution attempt (shared between levels 2 and 3). A level is skipped if the required location field (suburb, city) is not available from Nominatim.

#### Scenario: Direct name match succeeds
- **WHEN** `WikipediaResolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")` is called and `WikipediaClient.search("故宮博物院", ...)` returns a title
- **THEN** `WikipediaResolver.resolve()` returns the corresponding `WikiArticle` without calling `NominatimClient`

#### Scenario: Direct search fails, suburb search succeeds
- **WHEN** direct search returns `None` and Nominatim returns suburb `"大安區"` and suburb search returns a title
- **THEN** `WikipediaResolver.resolve()` returns the article found via suburb search

#### Scenario: Suburb search skipped when suburb is None
- **WHEN** Nominatim returns a `NominatimAddress` with `suburb == None` and `city_district == None`
- **THEN** level 2 (suburb search) is skipped and level 3 (city search) is attempted immediately

#### Scenario: All levels fail returns None
- **WHEN** all three search levels return no title
- **THEN** `WikipediaResolver.resolve()` returns `None`

#### Scenario: Nominatim failure short-circuits levels 2 and 3
- **WHEN** `NominatimClient.reverse()` returns `None` (network error)
- **THEN** levels 2 and 3 are skipped and `None` is returned

#### Scenario: City fallback used when suburb fails
- **WHEN** direct search and suburb search both return `None` but city search returns a title
- **THEN** `WikipediaResolver.resolve()` returns the article found via city search
