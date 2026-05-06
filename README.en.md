# AnalyzerTGChat

🇬🇧 English | [🇷🇺 Русский](README.md)

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6%20%2B%20Opus%204.7-orange)
![Telegram](https://img.shields.io/badge/Telegram-Telethon-26A5E4)
![License](https://img.shields.io/badge/license-MIT-green)

A tool that takes an ordinary Telegram chat and extracts surprisingly much from it: how people have changed over the years, whose jokes became folklore, what eras the team lived through, who grew closer and who drifted apart.

It works in three steps: exports the chat via the Telegram API → splits it into AI-friendly chunks → feeds them to Claude, which writes a report for each period and then merges everything into a single big "company chronicle".

The reports turn out surprisingly accurate and warm — with gem-like quotes, portraits of participants, language fingerprints ("favorite words", "signature emoji") and a chronicle of key events. After reading, you'll want to re-read it and forward it to everyone else.

Just don't show the report to someone who isn't ready to learn too much about themselves 🙂

---

### Features:
- **Export** of any chat history (private, group, channel) to CSV.
- **Word statistics**: top words across the whole chat and per participant — saved to `data/stats/<chat>.md`.
- **AI preparation**: cleanup, merging, splitting into parts by period. Each chat goes into its own subfolder `data/parts/<chat>/`.
- **Analysis via Claude**: each part is processed separately (fast/cheap, with prompt caching), then a single final report is assembled. Reports are written to `data/reports/<chat>/`.
- **HTML rendering**: a `.html` file with light/dark themes is automatically created next to each `.md`. You can open it in a browser with a double-click. If you ever need to rebuild all HTML at once (edited `.md` by hand, updated styles, etc.) — that's done with one console line:

```bash
python -c "from tg_analyzer.config import Config; from tg_analyzer.html_render import render_all; render_all(Config.from_env())"
```

---

## 1. Installation

Requires **Python 3.10+**.

### Option A: one command (Windows)
1. Download/clone the repository.
2. Double-click `run.bat`. It will:
   - create a `.env` file from `.env.example` (fill it in);
   - create a virtual environment `.venv`;
   - install dependencies from `requirements.txt`;
   - run `main.py`.

### Option B: one command (Linux/macOS)
```bash
chmod +x run.sh
./run.sh
```

### Option C: manually
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then edit .env
python main.py
```

---

## 2. Configuring `.env`
Copy `.env.example` to `.env` and fill in the values.

### Telegram API (for export)
1. Go to <https://my.telegram.org> with your Telegram account.
2. Open the **API development tools** section.
3. Create an "application" (any name/description).
4. Copy `App api_id` and `App api_hash` into `.env`:

```dotenv
API_ID=12345678
API_HASH=abcdef0123456789abcdef0123456789
```

### Claude API (for analysis)
1. Get a key at <https://console.anthropic.com>.
2. Put it in `.env`:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
```

If you use a proxy/gateway with an Anthropic-compatible API — change `ANTHROPIC_BASE_URL`.

### Other parameters (optional)
| Variable               | Default      | What it does |
|------------------------|--------------|--------------|
| `MIN_LEN`              | `3`          | Minimum word length in statistics |
| `TOP_N`                | `30`         | Size of the top word and participant list |
| `MAX_CHARS_PER_PART`   | `250000`     | Target part size when splitting (in characters) |
| `MERGE_BURSTS_MINUTES` | `0`          | Merge consecutive messages from one author (min). `0` = don't merge |
| `MIN_TEXT_LEN`         | `1`          | Messages shorter than this are dropped |
| `NORMALIZE_LAUGHTER`   | `False`      | Collapse "hahaha"/"lololo" to a short form |
| `MODEL_PARTS`          | `claude-sonnet-4-6` | Model for analyzing individual parts |
| `MODEL_FINAL`          | `claude-opus-4-7`   | Model for the final synthesis |
| `PARALLEL_WORKERS`     | `4`          | How many parts to analyze in parallel |
| `SPLIT_BY`             | `quarter`    | `quarter` or `month` — splitting strategy |

---

## 3. Running
```
python main.py
```

A menu will open:
```
============================================================
   AnalyzerTGChat — Telegram chat analysis
============================================================
1. Export chat from Telegram
2. Word statistics from CSV export (saves to .md + HTML)
3. Split CSV into parts for AI
4. Analyze parts via Claude (+ final report)
5. Full pipeline (1 → 3 → 4)
6. Final report only (rebuild from existing part_*.md)
0. Exit
============================================================
```

On the first run of option 1, Telegram will ask for a confirmation code (it will arrive in Telegram itself). The session will be saved to `data/telegram_session.session` — you won't need to enter the code again.

---

## 4. Project structure
```
AnalyzerTGChat/
├── main.py                  # entry point
├── requirements.txt
├── .env.example             # config template
├── .gitignore
├── run.bat / run.sh         # launcher wrappers
├── prompts/                 # AI prompt templates
│   ├── company_context.md   # EDIT THIS for your company
│   ├── part_analysis.md     # prompt for analyzing a part
│   └── final_report.md      # prompt for the final synthesis
├── tg_analyzer/             # logic package
│   ├── config.py            # .env loading/validation
│   ├── prompts.py           # template loading
│   ├── exporter.py          # chat export
│   ├── stats.py             # word statistics
│   ├── splitter.py          # splitting into parts
│   ├── analyzer.py          # analysis via Claude
│   └── ui.py                # menu
└── data/                    # appears after the first run
    ├── exports/             # CSV chat exports (chat_export_<title>_<ts>.csv)
    ├── stats/               # <chat_slug>.md + .html — word statistics
    ├── parts/
    │   └── <chat_slug>/     # part_*.txt + index.md/participants.md/stats.json
    ├── reports/
    │   └── <chat_slug>/     # part_*.md + final_report.md (+ .html alongside)
    ├── telegram_session.session
    └── .last_chat.json      # last selected chat

`<chat_slug>` matches the CSV filename without the `chat_export_` prefix,
so multiple different chats don't get mixed up during analysis.
```

---

## 5. Customizing prompts
If you want a more accurate analysis — be sure to edit:

- `prompts/company_context.md` — a short description of the company, period, key names. This text gets substituted into all AI prompts.
- `prompts/part_analysis.md` — what should be in the report for one part.
- `prompts/final_report.md` — the structure of the final report.

After editing prompts, run option 4 again. Existing `part_*.md` files are skipped — manually delete them from `data/reports/` if you want to re-analyze everything with the new prompt.

---

## 6. Common problems
**`API_ID and API_HASH not set in .env`** — fill in `.env`, see section 2.

**`PEER_ID_INVALID`** during export — Telegram doesn't recognize you with this chat. Use `list` (pick from dialogs) or username.

**`max_tokens` hit** — the final report is truncated. Increase `MAX_TOKENS_FINAL` in `.env`. Or reduce input length: lower `MAX_CHARS_PER_PART` or use `SPLIT_BY=month`.

**Long request "hangs"** — analyzing a part can take several minutes. The script uses streaming, nothing fails on a 10-minute timeout.

**Interrupting work** — analysis can be stopped (Ctrl+C). On the next run, already-completed `part_*.md` files are skipped.

---

## ⭐ Liked the project?

**Give it a star**! It's the best way to say "thanks", and it helps other people who might find it useful discover the project.

Found a bug or have an idea? Open an [issue](../../issues) or send a PR — I'd be happy to hear from you.
