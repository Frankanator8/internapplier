# app/sections/profile/

The Profile tab. `ProfilePage` maps each `data_store` key to an editor; every editor implements `load / get_data / merge / clear / has_data`, so the rest of the app treats the profile as one dict.

| File | Purpose |
|---|---|
| `page.py` | `ProfilePage` — sidebar of editors, plus profile-wide load/save/import. |
| `card_page.py` | `CardPage` (a list of entry cards, optionally grouped) and `EntryCard`. |
| `entries.py` | Experience, projects, education and awards editors — declared as field rows. |
| `general_info.py` | Contact, work-authorization and EEO form, declared as a layout table. |
| `string_list.py` | `StringListPage` for skills and hobbies. |
| `widgets.py` | `BulletsWidget` (with AI analysis), `CoursesWidget`. |
