# GIS folders (`mapping_data/`)

Paths use **Windows-safe** names for sync (OneDrive, Git, PC):

| Avoid | Why |
|-------|-----|
| Spaces in folder names | Scripts and some sync tools mishandle them; we use underscores. |
| `:` in filenames | **Invalid on Windows** (`:` reserved). The old Census/AK shapefile used URL-encoded `%3A` in the basename — renamed to `healthcare_facilities_safetynet.*`. |
| `Icon␍` (`Icon` + carriage return) | macOS custom-folder icon files; **break Windows** and many sync clients. Removed from this tree — do not re-add. |

## Expected layout

```
mapping_data/
├── Boroughs2020/Boroughs2020.shp
├── healthcare_facilities_safetynet/healthcare_facilities_safetynet.shp
├── facilities/          (optional)
├── alaska2019/
└── tl_2019_02_prisecroads/
```

Figure 1 code reads **borough** + **healthcare_facilities_safetynet** only.

If you obtain a fresh download with `%3A` or spaces in names, copy files into `healthcare_facilities_safetynet/` using the basename above (all of `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg` must share the same stem).
