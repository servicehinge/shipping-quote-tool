# Known-Good Dependency Versions

**Snapshot date: 2026-08-06**
**Environment: local `venv/` (Python), app running smoothly in production on Streamlit Cloud.**

> Purpose: this is a *reference snapshot* of the package versions the app is
> known to run well on. `requirements.txt` is **intentionally NOT pinned yet**
> (it still uses `>=`). If the deployed app ever breaks "for no reason" after a
> redeploy, the most likely cause is an upstream package auto-upgrading. In that
> case, pin `requirements.txt` to the versions below to reproduce this exact
> known-good state.
>
> To lock later: replace the contents of `requirements.txt` with the
> "Ready-to-lock requirements.txt" block below, commit, and redeploy.

---

## Direct dependencies (the ones in requirements.txt)

| Package        | Known-good version |
|----------------|--------------------|
| streamlit      | 1.54.0             |
| requests       | 2.32.5             |
| openpyxl       | 3.1.5              |
| pandas         | 2.3.3              |
| python-dotenv  | 1.2.1              |
| gspread        | 6.2.1              |
| google-auth    | 2.48.0             |

Also important for the retry logic added in `services/http.py`:

| Package  | Known-good version |
|----------|--------------------|
| urllib3  | 2.6.3              |

---

## Ready-to-lock requirements.txt

If/when you decide to pin, paste this into `requirements.txt`:

```
streamlit==1.54.0
requests==2.32.5
openpyxl==3.1.5
pandas==2.3.3
python-dotenv==1.2.1
gspread==6.2.1
google-auth==2.48.0
```

---

## Full environment snapshot (all installed packages, incl. transitive)

Captured from `venv/lib/.../site-packages/` on 2026-08-06. Use this if you need
to fully reproduce the environment (e.g. rebuild the venv from scratch):

```
altair==6.0.0
attrs==25.4.0
blinker==1.9.0
cachetools==6.2.6
certifi==2026.1.4
cffi==2.0.0
charset-normalizer==3.4.4
click==8.3.1
cryptography==46.0.4
et-xmlfile==2.0.0
gitdb==4.0.12
GitPython==3.1.46
google-auth==2.48.0
google-auth-oauthlib==1.2.4
gspread==6.2.1
idna==3.11
Jinja2==3.1.6
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
MarkupSafe==3.0.3
narwhals==2.16.0
numpy==2.4.2
oauthlib==3.3.1
openpyxl==3.1.5
packaging==26.0
pandas==2.3.3
pillow==12.1.0
protobuf==6.33.5
pyarrow==23.0.0
pyasn1==0.6.2
pyasn1-modules==0.4.2
pycparser==3.0
pydeck==0.9.1
python-dateutil==2.9.0.post0
python-dotenv==1.2.1
pytz==2025.2
referencing==0.37.0
requests==2.32.5
requests-oauthlib==2.0.0
rpds-py==0.30.0
rsa==4.9.1
six==1.17.0
smmap==5.0.2
streamlit==1.54.0
tenacity==9.1.3
toml==0.10.2
tornado==6.5.4
typing-extensions==4.15.0
tzdata==2025.3
urllib3==2.6.3
```
