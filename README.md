# GigaParts Filament Stock

A static stock tracker for Bambu Lab filament sold by GigaParts.

Run:

```sh
python3 build.py
```

The build script downloads the configured GigaParts filament product pages,
parses their embedded Magento variant data, and writes:

- `stock-data.json` - current stock snapshot
- `index.html` - self-contained static tracker

The generated page supports search, stock filtering, sorting, light/dark theme,
variant prices, SKUs, swatch colors, and in-stock hover/focus purchase links.
It also polls `stock-data.json` every hour, shows newly out-of-stock and newly
in-stock changes at the top of the page, and can send browser notifications for
newly in-stock variants while the page is open.

Each browser profile can maintain its own saved filament list using
`localStorage`. The page includes an `Email List` action that opens a local
`mailto:` draft. It does not send email from the site, which keeps the static
GitHub Pages deployment from becoming an email relay.

The included GitHub Actions workflow runs `python3 build.py` once per hour and
commits updated `index.html` and `stock-data.json` when stock changes.

To preview locally:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.
