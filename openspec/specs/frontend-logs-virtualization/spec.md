# Frontend Logs Virtualization Specification

## Purpose

Logs screen: PrimeReact VirtualScroller over the logs API with a native 300ms debounced search, server-side keyset pages, footer page numbers from total, and an accessible stack-trace modal with a focus trap.

## Requirements

### Requirement 1: Virtualized list

The logs list MUST use PrimeReact VirtualScroller with mock geometry: viewport height 480px, ROW_H=56px, OVERSCAN=4, rows positioned at top=idx*56px, spacer height = rows*56px, zebra rows (odd=subRowBg, even=cardBg). Only visible rows plus overscan MUST be in the DOM at any time.

#### Scenario: Render window

- GIVEN 38 rows in a 480px viewport
- WHEN the user scrolls to offset 1000px
- THEN the DOM contains only rows in [floor(1000/56)-4, floor(1000/56)+visCount] positioned correctly

#### Scenario: Scrolling fidelity

- GIVEN the scroller at any scrollTop
- WHEN rendering
- THEN row top positions equal idx*56px and the spacer height equals totalRows*56px

### Requirement 2: Native debounced search

The search input MUST debounce with native setTimeout/clearTimeout (NO lodash): `searchRaw` updates immediately, `searchDebounced` updates 300ms after typing stops; the "buscando..." indicator shows while searchRaw != searchDebounced; the search MUST trigger a server query against /api/v1/logs. Rapid typing MUST NOT fire a request per keystroke.

#### Scenario: Debounce behavior

- GIVEN the user types "ERR" with 50ms between keys
- WHEN 5 keystrokes occur
- THEN exactly one network request fires after the 300ms idle window with the final value

#### Scenario: Pending indicator

- GIVEN searchRaw="ERR" and searchDebounced=""
- WHEN 100ms have passed since typing
- THEN "buscando..." is visible and the list still shows the previous results

### Requirement 3: Server paging and footer

The list MUST fetch pages from /api/v1/logs (page_size aligned with viewport math); the footer MUST show "Mostrando a-b de total" and page squares derived from total/page_size with the active page styled accent; page navigation MUST fetch the corresponding page and reset scroll.

#### Scenario: Footer count

- GIVEN total=38, page_size=25, current page 1
- THEN the footer shows "Mostrando 1-25 de 38" and 2 page squares with page 1 active

### Requirement 4: Row rendering

Each row MUST render the mock grid columns (90px 130px 1fr 120px 110px): level badge (levelVisual WARNING/ERROR/CRITICAL bg+text), code mono, message ellipsized, servicio, fecha mono. Clicking a row MUST open the stack-trace modal with that row's data (fetching /api/v1/logs/{id} if stack_trace is absent from the list item).

#### Scenario: Row click

- GIVEN a visible row
- WHEN the user clicks it
- THEN the modal opens showing nivel badge, codigo, mensaje, correlation_id, servicio, creado_at and stack_trace

### Requirement 5: Stack-trace modal focus trap

The modal MUST: render role="dialog" aria-modal="true"; close on overlay mousedown (stopPropagation on the dialog); on open save document.activeElement and focus the first focusable element; Escape closes; Tab cycles within the modal and Shift+Tab wraps first<->last; on close restore focus to the trigger; the keydown listener is added on open and removed on close. Buttons: "Cerrar (Esc)" ghost and "Reintentar job" accent (in scope: closes the modal; MAY POST a RETRY_JOB remediation per syncs-api).

#### Scenario: Escape closes and restores focus

- GIVEN the modal open with focus on the close button
- WHEN the user presses Escape
- THEN the modal closes and focus returns to the element that opened it

#### Scenario: Tab wrap

- GIVEN the modal open and focus on the last focusable
- WHEN the user presses Tab
- THEN focus wraps to the first focusable inside the modal

#### Scenario: Overlay click

- GIVEN the modal open
- WHEN the user mousedowns on the overlay (not the dialog)
- THEN the modal closes

### Requirement 6: API search integration

The search MUST hit the backend contains-search (logs-api); the UI MUST NOT filter client-side only. After a search, total MUST reflect the server-filtered count and the list MUST refetch page 1.

#### Scenario: Search results

- GIVEN the user searches "DB_TIMEOUT"
- WHEN the debounced request returns {total:3, items:[...]}
- THEN the list shows the filtered rows and the footer shows "Mostrando 1-3 de 3"

## Acceptance Criteria

- VirtualScroller geometry: 56px rows, overscan 4, bounded DOM, correct positions
- Native 300ms debounce: exactly one request per typing burst, "buscando..." indicator, no lodash dependency
- Footer pages derived from API total; page navigation works
- Modal focus trap: Escape, Tab wrap, overlay click, focus restore; aria attributes present
- Server-side search integration with filtered totals
