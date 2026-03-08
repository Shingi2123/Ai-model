# VPS Deploy Guide

1. Clone repository and create virtualenv.
2. `pip install -r requirements.txt`
3. Optional integrations:
   - `pip install '.[telegram,google,llm]'`
4. Copy `.env.example` to `.env` and fill secrets.
5. Run bootstrap:
   - `python main.py bootstrap`
   - `python main.py test-run`
6. Set cron using `cron/daily_pipeline.cron` template.
7. Ensure timezone on VPS matches desired posting schedule.
