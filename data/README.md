# data/ - put YOUR real dataset here

The dataset is **not included** and must never be committed (see `.gitignore`).
This project deliberately ships **no** data: results must come from a real dataset you verify.

## What the dataset must have
| Requirement | Why |
|---|---|
| At least **50,000 usable** records | academic requirement |
| A **timestamp** column | needed for time series |
| **Post text** and/or a **hashtags** column | topics are extracted from these |
| **Months to years** of history | to see rise -> decline -> quiet period -> resurgence |
| CSV, JSON-lines (`.jsonl`) or JSON file | formats the importer reads |
| A source and licence you are allowed to use for coursework | provenance |

Do not trust a title or file size - run the validator, which counts real usable records:

```powershell
python scripts/validate_dataset.py --path data\your_file.csv --col-date created_at --col-text text --col-hashtags hashtags
```

## Record the provenance (needed for the report)
Fill these in `.env`; they are shown on the dashboard's *Data & Methodology* page:
`DATASET_NAME`, `DATASET_SOURCE` (URL or citation), `DATASET_LICENSE`.
Write down the download date as well. Code cannot verify a licence - read the dataset's own licence page.

## Where to look
Search public dataset sites (for example Kaggle, Hugging Face Datasets, university research repositories) for
"tweets" / "Reddit posts" / "Instagram captions" with timestamps. Check the licence and that the date range spans
more than a year. Check that a dataset downloaded for you by someone else is really the file you validated.

## Limitations to document after validation
Platform and sampling method, language, whether hashtags exist, missing-value rate, gaps in the date range.
