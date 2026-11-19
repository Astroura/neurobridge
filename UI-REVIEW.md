# NeuroBridge 0.5 UI review

Implemented against the user-approved DESIGN.md. The application remains local, and EEG processing thresholds, filtering calculations, event timing and raw exports were preserved.

## Evidence and viewport coverage

Screenshots are delivered separately in the local NeuroBridge-0.5-review folder. All visible measurements use synthetic EEG or a synthetic operator-state fixture. The fixture server is development-only and is not shipped.

| View | Captured widths | Reviewed states |
|---|---|---|
| Setup | 1440, 1240, 390, 320 | Empty trials, readiness disabled, folder/headset, import actions |
| Import | 1440, 390 | Real ZIP picker, manifest, live-only selection, selected-add enabled |
| Capture | 1440, 390 | Active timer, disabled connection, visible Stop, real-state labels |
| Raw figures | 1440, 1240, 390 | Waveforms, units, source filename, quality flags, time controls |
| Cleaning | 1440, 1240, 390, 320 | Empty, indeterminate loading, completed comparison, provenance, saved-run restore |
| Participant | 1240, 390 | Bilingual questions, Arabic font/direction, radio controls, operator-note privacy |
| Failure/data limits | 1440, 390 | Invalid exclusion with field focus, no recordings, no retained EEG, unavailable band powers |
| Supporting tables | 1440, 390 | Direct labels and units, contained horizontal scrolling, keyboard focus region |

Also checked a 200% zoom-equivalent rendering at 620x425 CSS pixels with device scale 2, corresponding to a 1240x850 physical viewport. The page did not overflow horizontally. At 390 and 320 configured widths, document scroll width matched client width; wide tables scrolled within their own labeled, focusable region. These are browser layout checks, not claims of phone headset support.

## Critique and corrections

- Replaced repeated rounded white cards with ruled sections, a paper canvas, a trial ledger, and neutral instrument wells. The working region and margin use the specified 8/4 grid, then stack at narrow widths.
- Replaced the instinct to color every state lilac with teal affordances, violet retained-data/source annotations, and labeled ochre/rust notices. Ordinary processing settings no longer look like warning banners. Raw traces are gray.
- Replaced Inter/platform font fallbacks and many tiny font sizes with bundled Plex Serif/Sans and the five approved sizes. Confirmed actual loaded title/UI fonts and Plex Arabic in the browser; unit checks cover Arabic and scientific glyphs.
- Replaced Unicode icon tiles and chart placeholders with bundled Lucide symbols and labeled SVG figures. Empty figures explain the next available action.
- Fixed a duplicated generated section during development, added a unique-ID release check, and removed duplicated figure captions.
- Fixed the recording layout pushing Stop and the timer below the mobile viewport. Active capture now removes workspace clutter and keeps these controls in the first screen.
- Removed a generic Wait heading during questions. Bilingual question groups now follow their text direction, radio controls align with the reading direction, and operator notes/paths are hidden in participant view.
- Replaced invented stage-style progress with a truthful Processing recording label and an indeterminate ruled track. No fake confidence, thinking, streaming, or comprehension inference was introduced.
- Explicitly disabled unavailable report controls, added a useful no-recordings instruction, and made invalid interval feedback field-specific with a visible focus ring.
- Fixed smooth scrolling in reduced-motion mode; CSS reveal animation reports none under the emulated preference.

## Token, accessibility and offline checks

One canonical theme.json supplies CSS variables and Matplotlib report styling. Components and SVG charts contain no palette hex literals or banned font stacks. Fonts, the Lucide sprite, and license notices are bundled and served locally. Browser resource inspection showed no external UI resource requests.

Keyboard-operable controls retain visible focus, permanent labels and 44px targets. Semantic notices use text and rules, not color alone. Figure units, time windows, source fingerprints and settings remain visible. Initial palette contrast calculations and actual CSS pairings were checked against DESIGN.md; muted text is not used on the darker instrument well. Disabled controls use explicit colors.

Scientific/HTTP/export tests, asset/unique-ID checks, JS parsing and frozen-app self-tests are required before release. Both architecture CI results are reported with the release. Live hardware Bluetooth, audio timing and native Save-dialog rehearsals on partners' Macs remain separate checks; this visual pass does not claim to have repeated them.
