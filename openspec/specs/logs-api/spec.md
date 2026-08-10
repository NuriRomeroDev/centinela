# Logs API Specification

## Purpose

Server-side filtered, keyset-paginated access to logs_errores powering the Logs screen: debounced contains-search, virtualized page rendering, and footer page numbers via total.

## Requirements

### Requirement 1: Keyset pagination

GET /api/v1/logs MUST paginate by keyset over serial logs_errores.id: newest-first (id DESC), cursor via `id < {cursor}`. Params: `cursor` (optional, last seen id), `page_size` (default 25, max 100). Response MUST include `items`, `total`, `next_cursor` (null on last page), `page_size`. MUST also support offset paging (`page`, `page_size`) so footer page numbers are computable client-side from total.

#### Scenario: First page

- GIVEN 38 logs
- WHEN GET /logs?page_size=9
- THEN items are the 9 newest, total=38, next_cursor set

#### Scenario: Cursor walk

- GIVEN the first-page cursor
- WHEN GET /logs?cursor={next_cursor}&page_size=9
- THEN the next 9 older rows return with no overlap and no gaps

#### Scenario: Footer pages

- GIVEN total=38, page_size=9
- WHEN the client computes pages from the response
- THEN ceil(38/9)=5 page squares and "Mostrando 1-9 de 38" are derivable

### Requirement 2: Search filters

The endpoint MUST support case-insensitive contains search (ILIKE) over mensaje, codigo_error, servicio_responsable via a single `search` param and/or per-field params (mensaje, codigo_error, servicio_responsable). Filters MUST compose (AND) with each other and with pagination; `total` MUST reflect the filtered count.

#### Scenario: Single field

- GIVEN logs including ERR_DB_TIMEOUT
- WHEN GET /logs?search=ERR_DB_TIMEOUT
- THEN only matching logs return and total equals the match count

#### Scenario: Composed filters

- GIVEN logs with varied servicio and codigo
- WHEN GET /logs?codigo_error=ERR_&servicio_responsable=Validation_Engine
- THEN only rows matching BOTH filters return

### Requirement 3: Detail endpoint

GET /api/v1/logs/{id} MUST return the full row including stack_trace. An unknown id MUST return 404.

#### Scenario: Detail with trace

- GIVEN an existing log id
- WHEN GET /logs/{id}
- THEN the response includes stack_trace and all list fields
- AND a nonexistent id returns 404

### Requirement 4: VirtualScroller integration contract

The list response MUST be shaped for PrimeReact VirtualScroller page rendering: each item carries the 56px-row columns (id, correlation_id, nivel_error, codigo_error, mensaje, servicio_responsable, creado_at); page_size aligns with viewport math (480px / 56px = 9 visible rows). An empty filtered result MUST return items=[], total=0, next_cursor=null.

#### Scenario: Empty result

- GIVEN a search with no matches
- WHEN GET /logs?search=zzz_none
- THEN items=[], total=0, next_cursor=null

## Acceptance Criteria

- Keyset walk returns every row exactly once (newest-first, no overlap/gaps)
- Filter correctness: case-insensitive contains, AND composition, filtered totals
- Detail returns stack_trace; 404 on unknown id
- Response shape matches the VirtualScroller contract; empty states return []; limits enforced
