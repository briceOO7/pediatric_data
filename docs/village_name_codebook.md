# Location codebooks

**Facility codes** (CAH, hub, outside hospitals): see [`facility_name_codebook.md`](facility_name_codebook.md).

---

# Village name codebook (de-identified → Maniilaq community)

## Purpose

Study CSVs used placeholder labels `Village_A` … `Village_K`. These were **mapped to real Maniilaq Association community names** by **ranking journey volume** in this extract and aligning that rank order to reference journey shares you provided (clinic-level medevac volume). This is a **structural / analytic mapping for maps and tables**, not proof that a given placeholder always corresponded to that community in the source system.

## Mapping

| Placeholder | Community name | Rank (this extract, by journeys) | Journeys (facility_1) | Your reference share |
|-------------|----------------|-----------------------------------|------------------------|----------------------|
| Village_I   | Point Hope     | 1                                 | 75                     | ~12.8%               |
| Village_D   | Selawik        | 2                                 | 52                     | ~12.5%               |
| Village_G   | Buckland       | 3                                 | 42                     | ~10.7%               |
| Village_A   | Noorvik        | 4                                 | 37                     | ~9.5%                |
| Village_B   | Noatak         | 5                                 | 26                     | ~7.3%                |
| Village_K   | Kivalina       | 6                                 | 24                     | ~6.5%                |
| Village_C   | Kiana          | 7                                 | 16                     | ~6.0%                |
| Village_J   | Shungnak       | 8                                 | 12                     | ~3.8%                |
| Village_H   | Ambler         | 9                                 | 10                     | ~2.3%                |
| Village_E   | Deering        | 10                                | 8                      | ~2.0%                |
| Village_F   | Kobuk          | 11                                | 7                      | ~1.8%                |

Machine-readable version: `docs/village_name_codebook.csv` (versioned in git; patient CSVs live only under `data/`).

## Files updated

Any CSV under `data/` that contained `Village_*` placeholders was rewritten with community names (e.g. medevac journeys, timing, outcomes, facility times, missed opportunities).

## Reverting

Keep a backup of the original extract, or re-apply inverse mapping using the codebook (swap columns).
