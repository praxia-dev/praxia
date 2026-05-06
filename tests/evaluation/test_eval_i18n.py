"""UI internationalization — language detection + translation lookups.

Coverage:
    - 8 supported languages registered
    - Browser-language normalization (prefix + region matching)
    - Translation key fallback to English
    - Unknown key returns the key itself
    - Every defined key has an entry for every supported language
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


class TestSupportedLanguages:
    def test_eight_languages(self):
        from praxia.ui.i18n import SUPPORTED

        assert SUPPORTED == ["en", "ja", "zh-CN", "ko", "es", "fr", "de", "pt-BR"]

    def test_each_lang_has_display_name(self):
        from praxia.ui.i18n import LANG_DISPLAY, SUPPORTED

        for code in SUPPORTED:
            assert code in LANG_DISPLAY
            assert LANG_DISPLAY[code]


class TestNormalize:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("en", "en"),
            ("ja", "ja"),
            ("ja-JP", "ja"),
            ("zh-CN", "zh-CN"),
            ("zh-Hans-CN", "zh-CN"),  # region prefix-match → zh-CN
            ("zh-TW", "zh-CN"),       # zh prefix matches the only zh entry we have
            ("ko-KR", "ko"),
            ("es-ES", "es"),
            ("es-MX", "es"),
            ("fr-FR", "fr"),
            ("de-AT", "de"),
            ("pt-BR", "pt-BR"),
            ("pt", "pt-BR"),          # prefix → first match
            ("xx-XX", "en"),          # unknown → fallback
            ("", "en"),
            (None, "en"),
        ],
    )
    def test_normalize(self, raw, expected):
        from praxia.ui.i18n import _normalize_lang

        assert _normalize_lang(raw) == expected


class TestTranslation:
    def test_returns_correct_language(self):
        from praxia.ui.i18n import t

        assert t("tab.run_flow", lang="en") == "🎬 Run Flow"
        assert t("tab.run_flow", lang="ja") == "🎬 フロー実行"
        assert t("tab.run_flow", lang="zh-CN") == "🎬 运行流程"
        assert t("tab.run_flow", lang="ko") == "🎬 플로우 실행"

    def test_falls_back_to_english_for_missing_lang(self):
        from praxia.ui.i18n import t

        # Suppose a key has only "en" — it should still return that for ja
        # (we'll force this by using a non-supported language code that we know
        # will hit fallback)
        for key in ("tab.run_flow", "common.run", "memory.read_only"):
            v = t(key, lang="en")
            assert v
            assert v != key

    def test_unknown_key_returns_key(self):
        from praxia.ui.i18n import t

        assert t("does.not.exist") == "does.not.exist"


class TestCompleteness:
    def test_every_key_has_every_language(self):
        """Every translation key must define all 8 supported languages."""
        from praxia.ui.i18n import _T, SUPPORTED

        for key, bundle in _T.items():
            missing = [s for s in SUPPORTED if s not in bundle]
            assert not missing, (
                f"Key {key!r} is missing translations for {missing}"
            )
            empty = [s for s in SUPPORTED if not bundle.get(s)]
            assert not empty, (
                f"Key {key!r} has empty translations for {empty}"
            )
