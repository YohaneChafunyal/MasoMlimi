# MasoMlimi UI design notes

## Research-backed choices (agritech / field use)

1. **Large touch targets** (≥56dp primary buttons) — gloves, one-hand use
2. **High contrast** — deep forest green on soft off-white (not pure #FFF glare)
3. **Earth palette** — forest, leaf, soil brown, gold for warnings
4. **Solid icons** — readable in sunlight at an angle
5. **Cards + clear sections** — one decision per block
6. **Status not colour-only** — text + icon for online/offline and result severity
7. **Few taps** — farm dashboard → check → camera → result

## Colour tokens (`lib/theme.dart`)

| Token | Hex | Use |
|-------|-----|-----|
| forest | #1B5E20 | Primary, app bar, main buttons |
| leaf | #43A047 | Crop accents |
| gold / goldSoft | #F9A825 / #FFF8E1 | Pilot banner, warnings |
| danger / soft | #C62828 / #FFEBEE | Critical results |
| bg | #F3F6F2 | Screen background |
| border | #D7E3D4 | Card edges |

## Components
- `HostCard` — crop/animal rows
- `SectionTitle` — section headers with icon
- `PilotBanner` — safety notice
- `StatusPill` — online/offline
