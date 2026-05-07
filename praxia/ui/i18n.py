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
    "sidebar.mode": {
        "en": "Mode",
        "ja": "モード",
        "zh-CN": "模式",
        "ko": "모드",
        "es": "Modo",
        "fr": "Mode",
        "de": "Modus",
        "pt-BR": "Modo",
    },
    "sidebar.readme": {
        "en": "README",
        "ja": "README",
        "zh-CN": "README",
        "ko": "README",
        "es": "README",
        "fr": "README",
        "de": "README",
        "pt-BR": "README",
    },
    "sidebar.issues": {
        "en": "Issues",
        "ja": "Issue",
        "zh-CN": "Issue",
        "ko": "이슈",
        "es": "Issues",
        "fr": "Issues",
        "de": "Issues",
        "pt-BR": "Issues",
    },
    # ===== Mode picker labels (sidebar radio) ===============================
    "mode.flow": {
        "en": "🎬 Multi-agent flow",
        "ja": "🎬 マルチエージェントフロー",
        "zh-CN": "🎬 多智能体流程",
        "ko": "🎬 멀티에이전트 플로우",
        "es": "🎬 Flujo multi-agente",
        "fr": "🎬 Flux multi-agents",
        "de": "🎬 Multi-Agenten-Flow",
        "pt-BR": "🎬 Fluxo multi-agente",
    },
    "mode.skill": {
        "en": "🛠 Skill",
        "ja": "🛠 スキル",
        "zh-CN": "🛠 技能",
        "ko": "🛠 스킬",
        "es": "🛠 Habilidad",
        "fr": "🛠 Compétence",
        "de": "🛠 Skill",
        "pt-BR": "🛠 Habilidade",
    },
    "mode.memory": {
        "en": "🧠 Memory",
        "ja": "🧠 メモリ",
        "zh-CN": "🧠 记忆",
        "ko": "🧠 메모리",
        "es": "🧠 Memoria",
        "fr": "🧠 Mémoire",
        "de": "🧠 Speicher",
        "pt-BR": "🧠 Memória",
    },
    "mode.consolidate": {
        "en": "🌙 Consolidate",
        "ja": "🌙 統合 (Consolidate)",
        "zh-CN": "🌙 整合",
        "ko": "🌙 통합",
        "es": "🌙 Consolidar",
        "fr": "🌙 Consolider",
        "de": "🌙 Konsolidieren",
        "pt-BR": "🌙 Consolidar",
    },
    "mode.dashboard": {
        "en": "📊 Dashboard",
        "ja": "📊 ダッシュボード",
        "zh-CN": "📊 仪表板",
        "ko": "📊 대시보드",
        "es": "📊 Panel",
        "fr": "📊 Tableau de bord",
        "de": "📊 Dashboard",
        "pt-BR": "📊 Painel",
    },
    "mode.prompts": {
        "en": "📝 Prompts",
        "ja": "📝 プロンプト",
        "zh-CN": "📝 提示词",
        "ko": "📝 프롬프트",
        "es": "📝 Prompts",
        "fr": "📝 Prompts",
        "de": "📝 Prompts",
        "pt-BR": "📝 Prompts",
    },
    "mode.admin": {
        "en": "⚙ Admin",
        "ja": "⚙ 管理",
        "zh-CN": "⚙ 管理",
        "ko": "⚙ 관리",
        "es": "⚙ Admin",
        "fr": "⚙ Admin",
        "de": "⚙ Admin",
        "pt-BR": "⚙ Admin",
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
    # ===== Admin tab (settings + downloads) =================================
    "admin.header": {
        "en": "💾 Admin",
        "ja": "💾 管理",
        "zh-CN": "💾 管理",
        "ko": "💾 관리",
        "es": "💾 Admin",
        "fr": "💾 Admin",
        "de": "💾 Admin",
        "pt-BR": "💾 Admin",
    },
    "admin.settings.subtab": {
        "en": "🔑 Settings",
        "ja": "🔑 設定",
        "zh-CN": "🔑 设置",
        "ko": "🔑 설정",
        "es": "🔑 Ajustes",
        "fr": "🔑 Paramètres",
        "de": "🔑 Einstellungen",
        "pt-BR": "🔑 Ajustes",
    },
    "admin.downloads.subtab": {
        "en": "💾 Exports",
        "ja": "💾 エクスポート",
        "zh-CN": "💾 导出",
        "ko": "💾 내보내기",
        "es": "💾 Exportar",
        "fr": "💾 Exports",
        "de": "💾 Exporte",
        "pt-BR": "💾 Exportar",
    },
    "admin.users.subtab": {
        "en": "👥 Users",
        "ja": "👥 ユーザ",
        "zh-CN": "👥 用户",
        "ko": "👥 사용자",
        "es": "👥 Usuarios",
        "fr": "👥 Utilisateurs",
        "de": "👥 Nutzer",
        "pt-BR": "👥 Usuários",
    },
    "admin.connectors.subtab": {
        "en": "🔌 Connectors",
        "ja": "🔌 コネクタ",
        "zh-CN": "🔌 连接器",
        "ko": "🔌 커넥터",
        "es": "🔌 Conectores",
        "fr": "🔌 Connecteurs",
        "de": "🔌 Konnektoren",
        "pt-BR": "🔌 Conectores",
    },
    "admin.policies.subtab": {
        "en": "🛡 Policies",
        "ja": "🛡 ポリシー",
        "zh-CN": "🛡 策略",
        "ko": "🛡 정책",
        "es": "🛡 Políticas",
        "fr": "🛡 Politiques",
        "de": "🛡 Richtlinien",
        "pt-BR": "🛡 Políticas",
    },
    "admin.about.subtab": {
        "en": "ℹ About",
        "ja": "ℹ 情報",
        "zh-CN": "ℹ 关于",
        "ko": "ℹ 정보",
        "es": "ℹ Acerca de",
        "fr": "ℹ À propos",
        "de": "ℹ Info",
        "pt-BR": "ℹ Sobre",
    },
    "admin.settings.runtime_h": {
        "en": "Runtime: LLM model + memory backend",
        "ja": "ランタイム: LLM モデル + メモリバックエンド",
        "zh-CN": "运行时: LLM 模型 + 记忆后端",
        "ko": "런타임: LLM 모델 + 메모리 백엔드",
        "es": "Runtime: modelo LLM + backend de memoria",
        "fr": "Runtime : modèle LLM + backend mémoire",
        "de": "Laufzeit: LLM-Modell + Memory-Backend",
        "pt-BR": "Runtime: modelo LLM + backend de memória",
    },
    "admin.settings.runtime_intro": {
        "en": "These two switches affect the running app immediately. They were previously in the sidebar but are rarely changed at runtime.",
        "ja": "この 2 つは即座にアプリに反映されます。以前はサイドバーに置いていましたが、頻繁には変更しないので設定タブへ移動しました。",
        "zh-CN": "这两个开关立即影响运行中的应用。原先位于侧边栏,但因不常更改已移至设置。",
        "ko": "이 두 가지는 실행 중인 앱에 즉시 반영됩니다. 이전에는 사이드바에 있었지만 자주 바꾸지 않으므로 설정으로 옮겼습니다.",
        "es": "Estos dos cambios afectan la app en ejecución de inmediato. Antes estaban en la barra lateral, pero rara vez se cambian en runtime.",
        "fr": "Ces deux options affectent l'app en cours immédiatement. Elles étaient dans la sidebar mais sont rarement changées en runtime.",
        "de": "Diese beiden Schalter wirken sich sofort aus. Sie waren zuvor in der Sidebar, werden aber selten zur Laufzeit geändert.",
        "pt-BR": "Estes dois ajustes afetam o app em execução imediatamente. Antes ficavam na sidebar, mas raramente são alterados em runtime.",
    },
    "admin.settings.model_label": {
        "en": "LLM model",
        "ja": "LLM モデル",
        "zh-CN": "LLM 模型",
        "ko": "LLM 모델",
        "es": "Modelo LLM",
        "fr": "Modèle LLM",
        "de": "LLM-Modell",
        "pt-BR": "Modelo LLM",
    },
    "admin.settings.model_custom": {
        "en": "Custom model string (e.g. anthropic/claude-opus-4-7)",
        "ja": "カスタムモデル文字列 (例: anthropic/claude-opus-4-7)",
        "zh-CN": "自定义模型字符串(如 anthropic/claude-opus-4-7)",
        "ko": "커스텀 모델 문자열 (예: anthropic/claude-opus-4-7)",
        "es": "Cadena de modelo personalizada (p. ej. anthropic/claude-opus-4-7)",
        "fr": "Chaîne de modèle personnalisée (ex. anthropic/claude-opus-4-7)",
        "de": "Benutzerdefinierter Modell-String (z. B. anthropic/claude-opus-4-7)",
        "pt-BR": "String de modelo personalizada (ex. anthropic/claude-opus-4-7)",
    },
    "admin.settings.backend_label": {
        "en": "Memory backend",
        "ja": "メモリバックエンド",
        "zh-CN": "记忆后端",
        "ko": "메모리 백엔드",
        "es": "Backend de memoria",
        "fr": "Backend mémoire",
        "de": "Memory-Backend",
        "pt-BR": "Backend de memória",
    },
    "admin.settings.runtime_apply": {
        "en": "Apply runtime change",
        "ja": "ランタイム変更を適用",
        "zh-CN": "应用运行时更改",
        "ko": "런타임 변경 적용",
        "es": "Aplicar cambio runtime",
        "fr": "Appliquer le changement runtime",
        "de": "Laufzeitänderung anwenden",
        "pt-BR": "Aplicar mudança em runtime",
    },
    "admin.settings.runtime_saved": {
        "en": "✅ Runtime settings updated. Reloading…",
        "ja": "✅ ランタイム設定を更新。再読み込み中…",
        "zh-CN": "✅ 运行时设置已更新,正在重新加载…",
        "ko": "✅ 런타임 설정 갱신됨. 다시 로드 중…",
        "es": "✅ Ajustes runtime actualizados. Recargando…",
        "fr": "✅ Réglages runtime mis à jour. Rechargement…",
        "de": "✅ Laufzeit-Einstellungen aktualisiert. Lade neu…",
        "pt-BR": "✅ Ajustes runtime atualizados. Recarregando…",
    },
    "admin.settings.persistent_h": {
        "en": "Persistent: API keys + service credentials",
        "ja": "永続: API キー + サービス認証情報",
        "zh-CN": "持久: API 密钥 + 服务凭据",
        "ko": "영속: API 키 + 서비스 자격증명",
        "es": "Persistente: claves API + credenciales de servicio",
        "fr": "Persistant : clés API + credentials de service",
        "de": "Persistent: API-Keys + Service-Credentials",
        "pt-BR": "Persistente: chaves API + credenciais de serviço",
    },
    "admin.settings.intro": {
        "en": "Configure API keys, memory backend, OAuth client credentials, and other runtime settings. Values are persisted to `.praxia/config.toml`. Existing environment variables / `.env` entries take precedence.",
        "ja": "API キー、メモリバックエンド、OAuth クライアント資格情報など実行時設定を変更します。値は `.praxia/config.toml` に保存。既存の環境変数 / `.env` の設定が優先されます。",
        "zh-CN": "配置 API 密钥、记忆后端、OAuth 客户端凭据等运行时设置。值持久化到 `.praxia/config.toml`。已设的环境变量 / `.env` 优先。",
        "ko": "API 키, 메모리 백엔드, OAuth 클라이언트 자격증명 등 런타임 설정을 변경합니다. 값은 `.praxia/config.toml` 에 저장. 기존 환경변수 / `.env` 가 우선됩니다.",
        "es": "Configura claves API, backend de memoria, credenciales OAuth y otros ajustes runtime. Los valores se persisten en `.praxia/config.toml`. Las variables de entorno / `.env` existentes tienen prioridad.",
        "fr": "Configurez les clés API, le backend mémoire, les identifiants OAuth et autres réglages runtime. Les valeurs sont persistées dans `.praxia/config.toml`. Les variables d'environnement / `.env` existantes ont la priorité.",
        "de": "Konfiguriere API-Keys, Memory-Backend, OAuth-Client-Credentials und andere Laufzeit-Einstellungen. Werte werden in `.praxia/config.toml` gespeichert. Vorhandene Umgebungsvariablen / `.env` haben Vorrang.",
        "pt-BR": "Configure chaves API, backend de memória, credenciais OAuth e outros ajustes runtime. Valores são persistidos em `.praxia/config.toml`. Variáveis de ambiente / `.env` existentes têm prioridade.",
    },
    "admin.settings.role_ok": {
        "en": "✅ Signed in as **{user}** (admin) — settings are editable.",
        "ja": "✅ **{user}** (admin) でサインイン中 — 設定を変更できます。",
        "zh-CN": "✅ 当前以 **{user}** (admin) 登录 — 可编辑设置。",
        "ko": "✅ **{user}** (admin) 로 로그인 중 — 설정을 편집할 수 있습니다.",
        "es": "✅ Sesión como **{user}** (admin) — los ajustes se pueden editar.",
        "fr": "✅ Connecté en tant que **{user}** (admin) — réglages éditables.",
        "de": "✅ Angemeldet als **{user}** (admin) — Einstellungen sind editierbar.",
        "pt-BR": "✅ Sessão como **{user}** (admin) — os ajustes podem ser editados.",
    },
    "admin.settings.role_unknown": {
        "en": "⚠️ Sidebar user_id `{user}` is not in the auth store. Anyone can edit settings in this dev/single-user setup. Create users via the **Users** tab to enforce role-based access.",
        "ja": "⚠️ サイドバーの user_id `{user}` は認証ストアに存在しません。このデフォルト (開発 / 単一ユーザ) 環境では誰でも設定を変更可能。**ユーザ** タブからユーザを作成すると、ロールベースの制御が有効になります。",
        "zh-CN": "⚠️ 侧边栏 user_id `{user}` 不在 auth 存储中。在此开发 / 单用户环境下任何人都可编辑设置。通过 **用户** 标签创建用户以启用基于角色的访问控制。",
        "ko": "⚠️ 사이드바 user_id `{user}` 가 auth 저장소에 없습니다. 이 개발 / 단일 사용자 환경에서는 누구나 설정을 변경할 수 있습니다. **사용자** 탭에서 사용자를 만들면 역할 기반 제어가 활성화됩니다.",
        "es": "⚠️ El user_id `{user}` del sidebar no existe en el almacén de auth. En este modo dev/usuario-único cualquiera puede editar. Crea usuarios en la pestaña **Usuarios** para aplicar control por rol.",
        "fr": "⚠️ L'user_id `{user}` du sidebar n'existe pas dans le store d'auth. En mode dev/mono-utilisateur n'importe qui peut éditer. Créez des utilisateurs dans l'onglet **Utilisateurs** pour activer le contrôle par rôle.",
        "de": "⚠️ Sidebar-user_id `{user}` ist nicht im Auth-Store. In diesem Dev-/Einzelnutzer-Modus kann jeder Einstellungen bearbeiten. Lege im **Users**-Tab Nutzer an, um rollenbasierte Kontrolle zu aktivieren.",
        "pt-BR": "⚠️ O user_id `{user}` do sidebar não existe no auth store. Neste modo dev/usuário-único qualquer um pode editar. Crie usuários na aba **Usuários** para ativar controle por papel.",
    },
    "admin.settings.role_blocked": {
        "en": "🚫 **{user}** has role `{role}` — only `admin` users should change settings. Changes will be audit-logged with this role.",
        "ja": "🚫 **{user}** のロールは `{role}` — 設定変更は `admin` ロールのユーザのみ実施すべきです。変更はこのロールで監査ログに記録されます。",
        "zh-CN": "🚫 **{user}** 的角色为 `{role}` — 仅 `admin` 应更改设置。变更将以此角色记录到审计日志。",
        "ko": "🚫 **{user}** 의 역할은 `{role}` 입니다 — 설정 변경은 `admin` 역할만 수행해야 합니다. 변경은 이 역할로 감사 로그에 기록됩니다.",
        "es": "🚫 **{user}** tiene rol `{role}` — solo usuarios `admin` deberían cambiar ajustes. Los cambios se auditan con este rol.",
        "fr": "🚫 **{user}** a le rôle `{role}` — seuls les `admin` devraient changer les réglages. Les modifications seront auditées avec ce rôle.",
        "de": "🚫 **{user}** hat Rolle `{role}` — nur `admin`-Nutzer sollten Einstellungen ändern. Änderungen werden mit dieser Rolle protokolliert.",
        "pt-BR": "🚫 **{user}** tem papel `{role}` — apenas usuários `admin` devem alterar ajustes. Mudanças são auditadas com este papel.",
    },
    "admin.settings.precedence_hint": {
        "en": "Resolution order: process env → `.env` → `.praxia/config.toml`. Editing here writes to the **lowest-precedence** layer, so a key already set in `.env` will not change unless you remove the `.env` line too.",
        "ja": "解決順序: プロセス環境変数 → `.env` → `.praxia/config.toml`。ここでの編集は **最下位の層** に書き込まれるため、`.env` で既に設定済みの値は `.env` 側を消さない限り上書きされません。",
        "zh-CN": "解析顺序: 进程环境变量 → `.env` → `.praxia/config.toml`。此处编辑写入 **最低优先级** 层,如已在 `.env` 中设置则需先移除 `.env` 中的条目。",
        "ko": "해결 순서: 프로세스 환경변수 → `.env` → `.praxia/config.toml`. 여기서의 편집은 **최하위** 레이어에 기록되므로, `.env` 에 이미 설정된 키는 `.env` 항목을 제거하지 않으면 변경되지 않습니다.",
        "es": "Orden de resolución: env del proceso → `.env` → `.praxia/config.toml`. Editar aquí escribe en la capa de **menor prioridad**; una clave ya en `.env` no cambiará a menos que también la borres del `.env`.",
        "fr": "Ordre de résolution: env processus → `.env` → `.praxia/config.toml`. Éditer ici écrit dans la couche de **plus basse priorité** ; une clé déjà dans `.env` ne changera pas tant que vous ne la supprimez pas aussi du `.env`.",
        "de": "Auflösungsreihenfolge: Prozess-Env → `.env` → `.praxia/config.toml`. Bearbeitungen hier landen in der **niedrigsten** Schicht; ein in `.env` gesetzter Key ändert sich nur, wenn du den `.env`-Eintrag ebenfalls entfernst.",
        "pt-BR": "Ordem de resolução: env do processo → `.env` → `.praxia/config.toml`. Editar aqui grava na camada de **menor prioridade**; uma chave já em `.env` não muda a menos que você também remova a linha do `.env`.",
    },
    "admin.settings.keys_label": {
        "en": "keys",
        "ja": "個",
        "zh-CN": "项",
        "ko": "개",
        "es": "claves",
        "fr": "clés",
        "de": "Keys",
        "pt-BR": "chaves",
    },
    "admin.settings.help.unset": {
        "en": "Currently unset.",
        "ja": "未設定。",
        "zh-CN": "当前未设置。",
        "ko": "현재 설정되지 않음.",
        "es": "Actualmente sin configurar.",
        "fr": "Actuellement non défini.",
        "de": "Aktuell nicht gesetzt.",
        "pt-BR": "Atualmente não definido.",
    },
    "admin.settings.help.secret_set": {
        "en": "Currently set: {masked}",
        "ja": "現在の値: {masked}",
        "zh-CN": "当前值: {masked}",
        "ko": "현재 값: {masked}",
        "es": "Valor actual: {masked}",
        "fr": "Valeur actuelle : {masked}",
        "de": "Aktueller Wert: {masked}",
        "pt-BR": "Valor atual: {masked}",
    },
    "admin.settings.help.value_set": {
        "en": "Currently set: {value}",
        "ja": "現在の値: {value}",
        "zh-CN": "当前值: {value}",
        "ko": "현재 값: {value}",
        "es": "Valor actual: {value}",
        "fr": "Valeur actuelle : {value}",
        "de": "Aktueller Wert: {value}",
        "pt-BR": "Valor atual: {value}",
    },
    "admin.settings.placeholder.unchanged": {
        "en": "(leave blank to keep current)",
        "ja": "(空欄で現在値を維持)",
        "zh-CN": "(留空保持当前值)",
        "ko": "(비워두면 현재 값 유지)",
        "es": "(en blanco para mantener)",
        "fr": "(vide pour conserver)",
        "de": "(leer lassen = aktuell behalten)",
        "pt-BR": "(em branco para manter)",
    },
    "admin.settings.save_btn": {
        "en": "Save changes",
        "ja": "変更を保存",
        "zh-CN": "保存更改",
        "ko": "변경 사항 저장",
        "es": "Guardar cambios",
        "fr": "Enregistrer les modifications",
        "de": "Änderungen speichern",
        "pt-BR": "Salvar alterações",
    },
    "admin.settings.no_changes": {
        "en": "No fields filled in — nothing was saved.",
        "ja": "入力された項目がないため、保存されませんでした。",
        "zh-CN": "未填写任何字段 — 未保存。",
        "ko": "입력된 항목이 없어 저장되지 않았습니다.",
        "es": "No se rellenó ningún campo — nada guardado.",
        "fr": "Aucun champ rempli — rien n'a été enregistré.",
        "de": "Keine Felder ausgefüllt — nichts gespeichert.",
        "pt-BR": "Nenhum campo preenchido — nada salvo.",
    },
    "admin.settings.saved": {
        "en": "✅ Saved {count} key(s) to .praxia/config.toml",
        "ja": "✅ {count} 件を .praxia/config.toml に保存しました",
        "zh-CN": "✅ 已保存 {count} 项到 .praxia/config.toml",
        "ko": "✅ {count} 건을 .praxia/config.toml 에 저장했습니다",
        "es": "✅ Se guardaron {count} clave(s) en .praxia/config.toml",
        "fr": "✅ {count} clé(s) enregistrée(s) dans .praxia/config.toml",
        "de": "✅ {count} Key(s) in .praxia/config.toml gespeichert",
        "pt-BR": "✅ {count} chave(s) salva(s) em .praxia/config.toml",
    },
    "admin.settings.restart_hint": {
        "en": "Restart the Streamlit server (or reload the page) for changes that affect already-imported modules to take effect.",
        "ja": "既にインポート済みのモジュールに影響する変更は、Streamlit サーバを再起動 (またはページをリロード) すると反映されます。",
        "zh-CN": "对已导入模块产生影响的变更,需重启 Streamlit 服务(或刷新页面)生效。",
        "ko": "이미 임포트된 모듈에 영향을 주는 변경 사항은 Streamlit 서버를 재시작 (또는 페이지 새로고침) 해야 반영됩니다.",
        "es": "Reinicia el servidor Streamlit (o recarga la página) para que los cambios que afecten a módulos ya importados surtan efecto.",
        "fr": "Redémarrez le serveur Streamlit (ou rechargez la page) pour que les modifications affectant des modules déjà importés prennent effet.",
        "de": "Starte den Streamlit-Server neu (oder lade die Seite neu), damit Änderungen an bereits importierten Modulen wirksam werden.",
        "pt-BR": "Reinicie o servidor Streamlit (ou recarregue a página) para que mudanças em módulos já importados façam efeito.",
    },
    "admin.settings.role_required": {
        "en": "🚫 Save blocked — only `admin` users can change settings.",
        "ja": "🚫 保存できません — `admin` ロールのユーザのみ設定を変更可能です。",
        "zh-CN": "🚫 保存被拒 — 仅 `admin` 用户可更改设置。",
        "ko": "🚫 저장 차단 — `admin` 사용자만 설정을 변경할 수 있습니다.",
        "es": "🚫 Guardado bloqueado — solo usuarios `admin` pueden cambiar ajustes.",
        "fr": "🚫 Enregistrement bloqué — seuls les utilisateurs `admin` peuvent modifier.",
        "de": "🚫 Speichern blockiert — nur `admin`-Nutzer dürfen Einstellungen ändern.",
        "pt-BR": "🚫 Salvamento bloqueado — apenas usuários `admin` podem alterar ajustes.",
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
