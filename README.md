# Wikipedia CLI (wkp)

Alpha version (in development), made via vibecoding with the gpt-5.2-codex model.

Small helper CLI to download, translate, preview, and publish Wikipedia articles.

## Environment

Copy `.env.sample` to `.env` and fill your credentials. Bot passwords are the recommended way to authenticate
from scripts.

How to create a bot password:

1. Go to `Especial:BotPasswords` on es.wikipedia.org while logged in.
2. Create a new bot password (name it e.g. `wkp-cli`).
3. Grant it permissions for `edit`, `read`, and `write`.
4. Save the generated username/password pair.

```bash
WKP_USERNAME=Tin_nqn@wkp-cli
WKP_PASSWORD=bot-password-here
WKP_USER_AGENT=wkp/0.1 (https://github.com/mgaitan/wkp; contact: you@example.com)
```

Optional translation settings:

```bash
WKP_TRANSLATE_URL=https://libretranslate.de/translate
WKP_TRANSLATE_KEY=
```

## Usage

Download wikitext:

```bash
uv run wkp download https://es.wikipedia.org/wiki/Juan_Mart%C3%ADn_Maldacena
```

Translate from another language (creates a draft file):

```bash
uv run wkp translate https://de.wikipedia.org/wiki/Horacio_Casini --lang es
```

Preview local wikitext:

```bash
uv run wkp preview articles/es/Horacio_Casini.wiki --lang es
```

Publish wikitext:

```bash
uv run wkp publish articles/es/Horacio_Casini.wiki --lang es --summary "Actualiza biografia"
```

## Notes

- `translate` uses LibreTranslate by default (best-effort with wikitext).
- `publish` uses Bot Passwords; create them in `Special:BotPasswords` on Wikipedia.
- Files are stored under `articles/<lang>/`.
- Consider keeping `articles/` outside the repo or ensure it stays ignored in git.
