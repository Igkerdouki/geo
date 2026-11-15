# Wind and ingredient demo

Run `./run.sh` from the repository root, then open http://localhost:5173/earth?stop=fresno.

1. Choose **Calm · 0.2 m/s** in **Wind & ingredient demo**. The backend computes a hypothetical two-minute release at the selected location. Cyan streaks move slowly; green and gold markers identify two example ingredients.
2. Press **Play timeline**. Five frames show one through five minutes after release. The legend shows airborne mass; toggle ingredients to inspect overlapping layers.
3. Choose **Strong · 8 m/s** and replay. Other inputs stay the same. Parcels move farther east. In-app notifications announce the preset and timeline completion.
4. Switch **Satellite / Model** to inspect the same frame. Outlines are backend dispersion moment ellipses, not exposure boundaries. Wind is uniform, not a resolved citywide flow field.
5. Click **Exit demo / clear layers**, then **Current wind** to restore weather-driven conditions.

Synthetic defaults: 1 kg applied per ingredient, 10% airborne; assumed deposition half-lives of 20 and 2 minutes. Renaming ingredients does not supply validated chemical properties. Use the investigator's Ingredient transport & timeline form for fully specified inputs. No preset establishes actual spraying, exposure, or safety; strong wind is a comparison setting, not a regulatory threshold.

Demo notifications are in-app, not email/SMS/system push. Existing watched-location alerts remain separate.
