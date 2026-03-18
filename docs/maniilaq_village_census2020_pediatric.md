# Maniilaq village denominators (2020 Census)

- **Source:** U.S. Census Bureau, 2020 Decennial Census, Demographic and Housing Characteristics (DHC), table P12 (sex by age).
- **`pediatric_pop`:** male + female under 18 (`P12_003N`–`P12_006N`, `P12_027N`–`P12_030N`).
- **Places:** city or CDP matching each community (`Noatak` = *Noatak CDP, Alaska*; others *… city, Alaska*).

Regenerate CSV:

```bash
python scripts/fetch_maniilaq_census_pediatric.py
```

The older `maniilaq_village_pop2020.csv` was approximate total population and is **not** used for Figure 1 rates after the Census pediatric file was added.
