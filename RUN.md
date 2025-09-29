# Running the Portfolio Tool

This project now ships with two easy ways to get started: a Python bootstrap
script that manages its own virtual environment, and self-contained binaries
built with PyInstaller.

## Option 1 – Python bootstrap (recommended)

1. Ensure Python 3.11 or newer is installed.
2. Download or clone this repository.
3. Double-click `run_portfolio.py` **or** execute it from a terminal:

   ```bash
   python run_portfolio.py
   ```

   The script will:

   - create (or reuse) a virtual environment at `~/.portfolio_tool/.venv`
     on macOS/Linux or `%APPDATA%\portfolio_tool\.venv` on Windows,
   - install the required dependencies if they are missing, and
   - launch the Textual UI (`portfolio ui`).

4. To run a CLI command instead of the UI:

   ```bash
   python run_portfolio.py --cli "positions --export md out.md"
   ```

5. To rebuild the environment from scratch:

   ```bash
   python run_portfolio.py --reset-venv
   ```

6. Contributors can install the project in editable mode with:

   ```bash
   python run_portfolio.py --dev
   ```

## Option 2 – Stand-alone executable

1. Download the appropriate binary from `dist/`:

   - Windows: `dist/portfolio.exe`
   - macOS/Linux: `dist/portfolio`

2. Run the executable directly. It bundles Python and all dependencies, so no
   additional setup is required.

## Troubleshooting

- **UI does not start:** try the CLI instead to check for errors:

  ```bash
  python run_portfolio.py --cli "positions"
  ```

- **Resetting the environment:** `python run_portfolio.py --reset-venv`
  deletes and recreates the managed virtual environment.

- **Windows SmartScreen:** Windows may warn about unknown publishers. Choose
  “More info” → “Run anyway” to continue.

- **Manual launch:** If the bootstrap fails, activate the virtual environment
  (`source ~/.portfolio_tool/.venv/bin/activate` or
  `%APPDATA%\portfolio_tool\.venv\Scripts\activate`) and run
  `python -m portfolio_tool ui`.
