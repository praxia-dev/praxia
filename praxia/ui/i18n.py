"""Streamlit UI internationalization.

Auto-detects browser language from `Accept-Language` (where available) with
manual override via a sidebar selector. Falls back to English.

Languages: en (default), ja, zh-CN, ko, es, fr, de, pt-BR.

Usage:

    from praxia.ui.i18n import t, language_selector_in_sidebar

    language_selector_in_sidebar()   # call once, near the top
    st.title(t("app.title"))
    st.caption(t("app.tagline"))

Translation strategy mirrors the landing page: top-of-funnel + tab labels +
section headings are translated; long-form English content (skill prompt
output, framework explanations) stays English (mirroring the landing page's
"key UI strings translated" approach).
"""
from __future__ import annotations

import os
from typing import Any

SUPPORTED = ["en", "ja", "zh-CN", "ko", "es", "fr", "de", "pt-BR"]

LANG_DISPLAY = {
    "en": "English",
    "ja": "日本語",
    "zh-CN": "简体中文",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt-BR": "Português (BR)",
}

# Translation dictionary. Keys are dot-separated.
_T: dict[str, dict[str, str]] = {
    "app.title": {
        "en": "🪡 Praxia",
        "ja": "🪡 Praxia",
        "zh-CN": "🪡 Praxia",
        "ko": "🪡 Praxia",
        "es": "🪡 Praxia",
        "fr": "🪡 Praxia",
        "de": "🪡 Praxia",
        "pt-BR": "🪡 Praxia",
    },
    "app.tagline": {
        "en": "Multi-agent orchestrator with cyclic memory",
        "ja": "メモリ循環型マルチエージェント・オーケストレータ",
        "zh-CN": "带循环记忆的多智能体编排器",
        "ko": "순환 메모리를 갖춘 멀티 에이전트 오케스트레이터",
        "es": "Orquestador multi-agente con memoria cíclica",
        "fr": "Orchestrateur multi-agents avec mémoire cyclique",
        "de": "Multi-Agenten-Orchestrator mit zyklischem Speicher",
        "pt-BR": "Orquestrador multi-agente com memória cíclica",
    },
    "sidebar.user": {
        "en": "User ID (your namespace)",
        "ja": "ユーザ ID (個人ネームスペース)",
        "zh-CN": "用户 ID (您的命名空间)",
        "ko": "사용자 ID (개인 네임스페이스)",
        "es": "ID de usuario (tu espacio de nombres)",
        "fr": "ID utilisateur (votre espace de noms)",
        "de": "Benutzer-ID (Ihr Namespace)",
        "pt-BR": "ID de usuário (seu namespace)",
    },
    "sidebar.org": {
        "en": "Org ID",
        "ja": "組織 ID",
        "zh-CN": "组织 ID",
        "ko": "조직 ID",
        "es": "ID de organización",
        "fr": "ID d'organisation",
        "de": "Organisations-ID",
        "pt-BR": "ID da organização",
    },
    "sidebar.model": {
        "en": "Model",
        "ja": "モデル",
        "zh-CN": "模型",
        "ko": "모델",
        "es": "Modelo",
        "fr": "Modèle",
        "de": "Modell",
        "pt-BR": "Modelo",
    },
    "sidebar.backend": {
        "en": "Memory backend",
        "ja": "メモリバックエンド",
        "zh-CN": "记忆后端",
        "ko": "메모리 백엔드",
        "es": "Backend de memoria",
        "fr": "Backend de mémoire",
        "de": "Speicher-Backend",
        "pt-BR": "Backend de memória",
    },
    "sidebar.language": {
        "en": "Language",
        "ja": "言語",
        "zh-CN": "语言",
        "ko": "언어",
        "es": "Idioma",
        "fr": "Langue",
        "de": "Sprache",
        "pt-BR": "Idioma",
    },
    "sidebar.compact": {
        "en": "Compact mode",
        "ja": "コンパクト表示",
        "zh-CN": "紧凑模式",
        "ko": "컴팩트 모드",
        "es": "Modo compacto",
        "fr": "Mode compact",
        "de": "Kompaktansicht",
        "pt-BR": "Modo compacto",
    },
    "tab.run_flow": {
        "en": "🎬 Run Flow",
        "ja": "🎬 フロー実行",
        "zh-CN": "🎬 运行流程",
        "ko": "🎬 플로우 실행",
        "es": "🎬 Ejecutar Flujo",
        "fr": "🎬 Lancer Flux",
        "de": "🎬 Flow Ausführen",
        "pt-BR": "🎬 Executar Fluxo",
    },
    "tab.skill": {
        "en": "🛠 Skill",
        "ja": "🛠 スキル",
        "zh-CN": "🛠 技能",
        "ko": "🛠 스킬",
        "es": "🛠 Habilidad",
        "fr": "🛠 Compétence",
        "de": "🛠 Skill",
        "pt-BR": "🛠 Habilidade",
    },
    "tab.memory": {
        "en": "🧠 Memory",
        "ja": "🧠 メモリ",
        "zh-CN": "🧠 记忆",
        "ko": "🧠 메모리",
        "es": "🧠 Memoria",
        "fr": "🧠 Mémoire",
        "de": "🧠 Speicher",
        "pt-BR": "🧠 Memória",
    },
    "tab.consolidate": {
        "en": "🌙 Consolidate",
        "ja": "🌙 統合",
        "zh-CN": "🌙 整合",
        "ko": "🌙 통합",
        "es": "🌙 Consolidar",
        "fr": "🌙 Consolider",
        "de": "🌙 Konsolidieren",
        "pt-BR": "🌙 Consolidar",
    },
    "tab.dashboard": {
        "en": "📊 Dashboard",
        "ja": "📊 ダッシュボード",
        "zh-CN": "📊 仪表板",
        "ko": "📊 대시보드",
        "es": "📊 Panel",
        "fr": "📊 Tableau de bord",
        "de": "📊 Dashboard",
        "pt-BR": "📊 Painel",
    },
    "tab.prompts": {
        "en": "📝 Prompts",
        "ja": "📝 プロンプト",
        "zh-CN": "📝 提示",
        "ko": "📝 프롬프트",
        "es": "📝 Prompts",
        "fr": "📝 Prompts",
        "de": "📝 Prompts",
        "pt-BR": "📝 Prompts",
    },
    "tab.users": {
        "en": "👥 Users",
        "ja": "👥 ユーザ",
        "zh-CN": "👥 用户",
        "ko": "👥 사용자",
        "es": "👥 Usuarios",
        "fr": "👥 Utilisateurs",
        "de": "👥 Benutzer",
        "pt-BR": "👥 Usuários",
    },
    "tab.connectors": {
        "en": "🔌 Connectors",
        "ja": "🔌 コネクタ",
        "zh-CN": "🔌 连接器",
        "ko": "🔌 커넥터",
        "es": "🔌 Conectores",
        "fr": "🔌 Connecteurs",
        "de": "🔌 Konnektoren",
        "pt-BR": "🔌 Conectores",
    },
    "tab.policies": {
        "en": "🛡 Policies",
        "ja": "🛡 ポリシー",
        "zh-CN": "🛡 策略",
        "ko": "🛡 정책",
        "es": "🛡 Políticas",
        "fr": "🛡 Politiques",
        "de": "🛡 Richtlinien",
        "pt-BR": "🛡 Políticas",
    },
    "tab.admin": {
        "en": "💾 Admin",
        "ja": "💾 管理",
        "zh-CN": "💾 管理",
        "ko": "💾 관리",
        "es": "💾 Admin",
        "fr": "💾 Admin",
        "de": "💾 Admin",
        "pt-BR": "💾 Admin",
    },
    "tab.about": {
        "en": "ℹ About",
        "ja": "ℹ 情報",
        "zh-CN": "ℹ 关于",
        "ko": "ℹ 정보",
        "es": "ℹ Acerca de",
        "fr": "ℹ À propos",
        "de": "ℹ Info",
        "pt-BR": "ℹ Sobre",
    },
    "common.run": {
        "en": "Run",
        "ja": "実行",
        "zh-CN": "运行",
        "ko": "실행",
        "es": "Ejecutar",
        "fr": "Exécuter",
        "de": "Ausführen",
        "pt-BR": "Executar",
    },
    "common.save": {
        "en": "Save",
        "ja": "保存",
        "zh-CN": "保存",
        "ko": "저장",
        "es": "Guardar",
        "fr": "Enregistrer",
        "de": "Speichern",
        "pt-BR": "Salvar",
    },
    "common.delete": {
        "en": "Delete",
        "ja": "削除",
        "zh-CN": "删除",
        "ko": "삭제",
        "es": "Eliminar",
        "fr": "Supprimer",
        "de": "Löschen",
        "pt-BR": "Excluir",
    },
    "common.cancel": {
        "en": "Cancel",
        "ja": "キャンセル",
        "zh-CN": "取消",
        "ko": "취소",
        "es": "Cancelar",
        "fr": "Annuler",
        "de": "Abbrechen",
        "pt-BR": "Cancelar",
    },
    "common.input": {
        "en": "Input",
        "ja": "入力",
        "zh-CN": "输入",
        "ko": "입력",
        "es": "Entrada",
        "fr": "Entrée",
        "de": "Eingabe",
        "pt-BR": "Entrada",
    },
    "common.output": {
        "en": "Output",
        "ja": "出力",
        "zh-CN": "输出",
        "ko": "출력",
        "es": "Salida",
        "fr": "Sortie",
        "de": "Ausgabe",
        "pt-BR": "Saída",
    },
    "common.file": {
        "en": "File",
        "ja": "ファイル",
        "zh-CN": "文件",
        "ko": "파일",
        "es": "Archivo",
        "fr": "Fichier",
        "de": "Datei",
        "pt-BR": "Arquivo",
    },
    "memory.search": {
        "en": "Search",
        "ja": "検索",
        "zh-CN": "搜索",
        "ko": "검색",
        "es": "Buscar",
        "fr": "Rechercher",
        "de": "Suchen",
        "pt-BR": "Buscar",
    },
    "memory.mode": {
        "en": "Memory mode",
        "ja": "メモリモード",
        "zh-CN": "记忆模式",
        "ko": "메모리 모드",
        "es": "Modo de memoria",
        "fr": "Mode mémoire",
        "de": "Speichermodus",
        "pt-BR": "Modo de memória",
    },
    "memory.accumulate": {
        "en": "accumulate (writes pass through)",
        "ja": "accumulate (書込み有効)",
        "zh-CN": "accumulate (写入有效)",
        "ko": "accumulate (쓰기 활성)",
        "es": "accumulate (escrituras activas)",
        "fr": "accumulate (écritures actives)",
        "de": "accumulate (Schreiben aktiv)",
        "pt-BR": "accumulate (escritas ativas)",
    },
    "memory.read_only": {
        "en": "read_only (writes silently dropped)",
        "ja": "read_only (書込み無効化)",
        "zh-CN": "read_only (写入静默丢弃)",
        "ko": "read_only (쓰기 비활성)",
        "es": "read_only (escrituras silenciosamente descartadas)",
        "fr": "read_only (écritures silencieusement abandonnées)",
        "de": "read_only (Schreibvorgänge stillschweigend verworfen)",
        "pt-BR": "read_only (escritas silenciosamente descartadas)",
    },
}


def _normalize_lang(raw: str | None) -> str:
    """Map a raw language string (e.g. 'ja-JP', 'zh-Hans') to a SUPPORTED key."""
    if not raw:
        return "en"
    raw = raw.strip()
    if raw in SUPPORTED:
        return raw
    prefix = raw.split("-")[0].lower()
    for s in SUPPORTED:
        if s.lower().startswith(prefix):
            return s
    return "en"


def detect_language() -> str:
    """Best-effort detection from env or Streamlit session state.

    Streamlit doesn't expose Accept-Language directly; we approximate via
    the LANG / LC_MESSAGES env vars (set by docker / kube), the session
    state override (sidebar selector), and a last-resort default.
    """
    try:
        import streamlit as st
        if "praxia_lang" in st.session_state:
            return st.session_state.praxia_lang
    except Exception:
        pass
    env = os.getenv("PRAXIA_UI_LANG") or os.getenv("LANG") or ""
    return _normalize_lang(env.split(".")[0].replace("_", "-"))


def t(key: str, lang: str | None = None) -> str:
    """Look up a translation key. Falls back to English, then the key itself."""
    lang = lang or detect_language()
    bundle = _T.get(key)
    if not bundle:
        return key
    return bundle.get(lang) or bundle.get("en") or key


def language_selector_in_sidebar() -> str:
    """Render a language selector in the Streamlit sidebar.

    Stores the chosen language in `st.session_state.praxia_lang` so subsequent
    `t(...)` calls return the right strings without needing the param.

    Returns the active language code.
    """
    try:
        import streamlit as st
    except ImportError:
        return detect_language()

    current = st.session_state.get("praxia_lang") or detect_language()
    options = SUPPORTED
    labels = [LANG_DISPLAY[c] for c in options]
    chosen_label = st.sidebar.selectbox(
        t("sidebar.language", lang=current),
        options=labels,
        index=options.index(current) if current in options else 0,
        key="praxia_lang_select",
    )
    chosen = options[labels.index(chosen_label)]
    st.session_state.praxia_lang = chosen
    return chosen


__all__ = [
    "SUPPORTED",
    "LANG_DISPLAY",
    "t",
    "detect_language",
    "language_selector_in_sidebar",
]
