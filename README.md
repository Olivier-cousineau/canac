# canac

## Workflow: run scraper + publish to econoplus

This repo includes a manual GitHub Actions workflow that runs the CANAC scraper on a **self-hosted** runner and publishes the generated JSON into the `econoplus` repo.

### What the workflow does

1. Installs Python dependencies if `requirements.txt` exists.
2. Runs the scraper (`run_all_canac_stores.py`) using `.\.venv\Scripts\python.exe` if present, otherwise `python`.
3. Publishes output to the `econoplus` repo using `scripts/publish_to_econoplus.ps1`.

The publish script:
- `git pull --rebase` in the econoplus repo.
- Replaces `econoplus/public/canac`.
- Copies JSON output from `out_canac_json` into `econoplus/public/canac/<0000-slug>/liquidations.json`.
- Commits and pushes changes.

### Required inputs (workflow_dispatch)

You can trigger the workflow manually in the GitHub UI. Inputs:
- `econoplus_path` (default `..\econoplus`): local path to the econoplus repo on the runner.
- `econoplus_repo_url` (optional): clone URL if the econoplus repo is missing locally.
- `out_dir` (default `out_canac_json`): scraper output directory.
- `commit_message` (default `Update CANAC liquidations`).

> Tip: set `GIT_USER_NAME` and `GIT_USER_EMAIL` as environment variables on the self-hosted runner if you want custom commit metadata.

## Self-hosted runner (Windows)

These steps are a short version of the official GitHub runner setup. Always copy the **exact** commands from your repository’s **Settings → Actions → Runners → New self-hosted runner** page.

1. **Download the runner** (PowerShell), from the GitHub UI-provided URL:
   ```powershell
   mkdir actions-runner; cd actions-runner
   Invoke-WebRequest -Uri <RUNNER_URL_FROM_GITHUB> -OutFile actions-runner.zip
   Expand-Archive actions-runner.zip -DestinationPath .
   ```
2. **Configure the runner** (using the token from the GitHub UI):
   ```powershell
   .\config.cmd --url https://github.com/<owner>/<repo> --token <TOKEN_FROM_GITHUB>
   ```
3. **Run the runner**:
   ```powershell
   .\run.cmd
   ```

> Keep the runner online on your PC when you trigger the workflow so GitHub can schedule the job.

## Scraper display options

By default, the scraper now runs in **headed mode** so you can see the pages scroll by while each store is scraped.

Common flags:
- `--headed` (default): show the browser UI.
- `--headless`: run without displaying the browser.
- `--max-pages N`: cap the number of pages per store.
- `--timeout-ms N`: override the page timeout.
- `--debug`: enable debug logging.

You can also force headless mode in CI by setting `CANAC_HEADLESS=1`.
