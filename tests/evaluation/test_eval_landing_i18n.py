"""Landing-page i18n catalog (web-publish/i18n.js) — 8-language enforcement.

The Praxia landing site has its own translation table embedded in
``web-publish/i18n.js``. We require every key to have entries for the
same 8 languages as the app (en, ja, zh-CN, ko, es, fr, de, pt-BR)
so visitors don't see English fallbacks in their language pages.

This test parses the JS object literal with a forgiving regex (no JS
runtime needed) and reports any key that's missing any of the 8 langs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.evaluation


SUPPORTED = ["en", "ja", "zh-CN", "ko", "es", "fr", "de", "pt-BR"]
I18N_JS = Path(__file__).resolve().parents[2] / "web-publish" / "i18n.js"


def _parse_keys() -> dict[str, set[str]]:
    """Return {key_name: {lang_codes_present}}.

    The i18n.js entries look like:
        "feat.foo": {en:"...", ja:"...", "zh-CN":"...", ...},
    We don't need a real JS parser — a permissive regex over each line
    catches every entry well enough for the completeness check.
    """
    if not I18N_JS.exists():
        pytest.skip(f"{I18N_JS} not present in this checkout")

    text = I18N_JS.read_text(encoding="utf-8")
    # Match a key/value entry like:  "key.name": { ... },
    entry_re = re.compile(
        r'"([\w.\-+]+)"\s*:\s*\{([^{}]*)\}',
        re.DOTALL,
    )
    # Match a language code inside an entry: bareword `en:` or quoted "zh-CN":
    lang_re = re.compile(
        r'(?:"([\w-]+)"|(\w+))\s*:\s*"',
    )

    out: dict[str, set[str]] = {}
    for m in entry_re.finditer(text):
        key, body = m.group(1), m.group(2)
        # The "feat" / "scope" / etc. categories themselves are valid keys;
        # but skip the helper utility entries that don't follow the
        # {lang: "value"} shape (none currently — this is defensive).
        if not body.strip():
            continue
        langs: set[str] = set()
        for lm in lang_re.finditer(body):
            lang = lm.group(1) or lm.group(2)
            if lang in SUPPORTED:
                langs.add(lang)
        if langs:  # only count entries that have at least one supported lang
            out[key] = langs
    return out


class TestLandingI18n:
    def test_file_exists(self):
        assert I18N_JS.exists(), (
            f"Landing i18n catalog missing: {I18N_JS}"
        )

    def test_every_key_has_every_language(self):
        keys = _parse_keys()
        assert keys, "Parser found no keys — selector is wrong or file is empty"

        missing: dict[str, list[str]] = {}
        for key, langs in keys.items():
            absent = [code for code in SUPPORTED if code not in langs]
            if absent:
                missing[key] = absent

        if missing:
            head = list(missing.items())[:10]
            details = "\n".join(f"  {k}: missing {v}" for k, v in head)
            extra = (
                f"\n  ...and {len(missing) - 10} more"
                if len(missing) > 10 else ""
            )
            pytest.fail(
                f"Landing i18n catalog has {len(missing)} key(s) with "
                f"incomplete translations:\n{details}{extra}"
            )
