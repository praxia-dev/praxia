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
    "sidebar.view": {
        "en": "View",
        "ja": "ビュー",
        "zh-CN": "视图",
        "ko": "뷰",
        "es": "Vista",
        "fr": "Vue",
        "de": "Ansicht",
        "pt-BR": "Visão",
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
    "mode.run": {
        "en": "🎬 Run",
        "ja": "🎬 実行",
        "zh-CN": "🎬 运行",
        "ko": "🎬 실행",
        "es": "🎬 Ejecutar",
        "fr": "🎬 Exécuter",
        "de": "🎬 Ausführen",
        "pt-BR": "🎬 Executar",
    },
    "mode.preferences": {
        "en": "⚙ Preferences",
        "ja": "⚙ 個人設定",
        "zh-CN": "⚙ 偏好设置",
        "ko": "⚙ 환경 설정",
        "es": "⚙ Preferencias",
        "fr": "⚙ Préférences",
        "de": "⚙ Einstellungen",
        "pt-BR": "⚙ Preferências",
    },
    "preferences.h": {
        "en": "⚙ Preferences",
        "ja": "⚙ 個人設定",
        "zh-CN": "⚙ 偏好设置",
        "ko": "⚙ 환경 설정",
        "es": "⚙ Preferencias",
        "fr": "⚙ Préférences",
        "de": "⚙ Einstellungen",
        "pt-BR": "⚙ Preferências",
    },
    "preferences.intro": {
        "en": "Per-user view + runtime preferences. Available to everyone — no admin role required.",
        "ja": "ユーザ毎の表示 + 実行時設定。全ユーザが使用可能 — admin ロール不要。",
        "zh-CN": "每用户的视图 + 运行时偏好。所有用户可用 — 无需 admin 角色。",
        "ko": "사용자별 보기 + 런타임 환경 설정. 모든 사용자 사용 가능 — admin 역할 불필요.",
        "es": "Preferencias de vista y runtime por usuario. Disponible para todos — sin rol admin.",
        "fr": "Préférences d'affichage et runtime par utilisateur. Pour tous — pas de rôle admin requis.",
        "de": "Pro-Nutzer-Anzeige + Laufzeit-Einstellungen. Für alle verfügbar — kein admin nötig.",
        "pt-BR": "Preferências de visualização e runtime por usuário. Disponível para todos — sem papel admin.",
    },
    "preferences.language_h": {
        "en": "🌐 Language",
        "ja": "🌐 言語",
        "zh-CN": "🌐 语言",
        "ko": "🌐 언어",
        "es": "🌐 Idioma",
        "fr": "🌐 Langue",
        "de": "🌐 Sprache",
        "pt-BR": "🌐 Idioma",
    },
    "preferences.language_intro": {
        "en": "Auto-detected from browser/OS at first load. Override here for this session.",
        "ja": "初回起動時にブラウザ/OS から自動検出。このセッションで切替えたい場合のみ変更してください。",
        "zh-CN": "首次加载时从浏览器/OS 自动检测。需要本会话切换时在此覆盖。",
        "ko": "처음 로드 시 브라우저/OS 에서 자동 감지. 이 세션에서 다른 언어를 원하면 여기서 변경.",
        "es": "Auto-detectado del navegador/OS al inicio. Cambia aquí para esta sesión.",
        "fr": "Auto-détecté depuis le navigateur/OS au démarrage. Modifiez ici pour cette session.",
        "de": "Beim Laden vom Browser/OS automatisch erkannt. Hier für diese Sitzung ändern.",
        "pt-BR": "Auto-detectado do navegador/OS no início. Troque aqui para esta sessão.",
    },
    "preferences.language_label": {
        "en": "Display language",
        "ja": "表示言語",
        "zh-CN": "显示语言",
        "ko": "표시 언어",
        "es": "Idioma de la interfaz",
        "fr": "Langue d'affichage",
        "de": "Anzeigesprache",
        "pt-BR": "Idioma de exibição",
    },
    "preferences.llm_h": {
        "en": "🤖 LLM model",
        "ja": "🤖 LLM モデル",
        "zh-CN": "🤖 LLM 模型",
        "ko": "🤖 LLM 모델",
        "es": "🤖 Modelo LLM",
        "fr": "🤖 Modèle LLM",
        "de": "🤖 LLM-Modell",
        "pt-BR": "🤖 Modelo LLM",
    },
    "preferences.llm_intro": {
        "en": "Which LLM should answer your runs by default. Per-session — admin can pin a tenant default in Admin → Settings.",
        "ja": "実行時に既定で使う LLM。このセッション内のみ反映。テナント既定値の固定は admin の設定 → 永続から。",
        "zh-CN": "默认用于运行的 LLM。仅本会话生效。租户默认在 admin → 持久 中固定。",
        "ko": "기본 실행에 사용할 LLM. 이 세션에만 반영. 테넌트 기본값은 admin → 영속 에서 고정.",
        "es": "LLM que responde tus runs por defecto. Por sesión. El admin fija un default tenant en Admin → Settings.",
        "fr": "LLM par défaut pour vos runs. Par session. L'admin fixe un défaut tenant dans Admin → Settings.",
        "de": "Standard-LLM für deine Runs. Pro Sitzung. Admin setzt Tenant-Default unter Admin → Settings.",
        "pt-BR": "LLM padrão para seus runs. Por sessão. Admin fixa default do tenant em Admin → Settings.",
    },
    "preferences.model_label": {
        "en": "LLM model",
        "ja": "LLM モデル",
        "zh-CN": "LLM 模型",
        "ko": "LLM 모델",
        "es": "Modelo LLM",
        "fr": "Modèle LLM",
        "de": "LLM-Modell",
        "pt-BR": "Modelo LLM",
    },
    "preferences.model_custom": {
        "en": "Custom model string (e.g. anthropic/claude-opus-4-7)",
        "ja": "カスタムモデル文字列 (例: anthropic/claude-opus-4-7)",
        "zh-CN": "自定义模型字符串(如 anthropic/claude-opus-4-7)",
        "ko": "커스텀 모델 문자열 (예: anthropic/claude-opus-4-7)",
        "es": "Cadena de modelo personalizada (p. ej. anthropic/claude-opus-4-7)",
        "fr": "Chaîne de modèle personnalisée (ex. anthropic/claude-opus-4-7)",
        "de": "Benutzerdefinierter Modell-String (z. B. anthropic/claude-opus-4-7)",
        "pt-BR": "String de modelo personalizada (ex. anthropic/claude-opus-4-7)",
    },
    "preferences.apply_btn": {
        "en": "💾 Apply",
        "ja": "💾 適用",
        "zh-CN": "💾 应用",
        "ko": "💾 적용",
        "es": "💾 Aplicar",
        "fr": "💾 Appliquer",
        "de": "💾 Anwenden",
        "pt-BR": "💾 Aplicar",
    },
    "preferences.theme_h": {
        "en": "🎨 Color theme",
        "ja": "🎨 カラーテーマ",
        "zh-CN": "🎨 颜色主题",
        "ko": "🎨 색상 테마",
        "es": "🎨 Tema de color",
        "fr": "🎨 Thème de couleur",
        "de": "🎨 Farbthema",
        "pt-BR": "🎨 Tema de cores",
    },
    "preferences.theme_intro": {
        "en": "Auto follows your OS / browser preference. Light or Dark forces a specific theme for this user.",
        "ja": "自動: OS / ブラウザの設定に追従。ライト / ダーク: このユーザだけ強制的に固定。",
        "zh-CN": "自动: 跟随系统/浏览器。浅色 / 深色: 对此用户强制固定。",
        "ko": "자동: OS/브라우저 설정 따라감. 라이트/다크: 이 사용자에게만 고정.",
        "es": "Auto sigue la preferencia del SO/navegador. Claro u Oscuro lo fija para este usuario.",
        "fr": "Auto suit la préférence OS/navigateur. Clair ou Sombre force pour cet utilisateur.",
        "de": "Auto folgt der OS-/Browser-Einstellung. Hell oder Dunkel erzwingt das Thema.",
        "pt-BR": "Auto segue a preferência do SO/navegador. Claro ou Escuro força o tema.",
    },
    "preferences.theme_label": {
        "en": "Theme",
        "ja": "テーマ",
        "zh-CN": "主题",
        "ko": "테마",
        "es": "Tema",
        "fr": "Thème",
        "de": "Thema",
        "pt-BR": "Tema",
    },
    "preferences.theme.auto": {
        "en": "Auto (follow system)",
        "ja": "自動 (システムに従う)",
        "zh-CN": "自动(跟随系统)",
        "ko": "자동 (시스템 따라감)",
        "es": "Auto (seguir sistema)",
        "fr": "Auto (suivre le système)",
        "de": "Auto (System folgen)",
        "pt-BR": "Auto (seguir sistema)",
    },
    "preferences.theme.light": {
        "en": "☀ Light",
        "ja": "☀ ライト",
        "zh-CN": "☀ 浅色",
        "ko": "☀ 라이트",
        "es": "☀ Claro",
        "fr": "☀ Clair",
        "de": "☀ Hell",
        "pt-BR": "☀ Claro",
    },
    "preferences.theme.dark": {
        "en": "🌙 Dark",
        "ja": "🌙 ダーク",
        "zh-CN": "🌙 深色",
        "ko": "🌙 다크",
        "es": "🌙 Oscuro",
        "fr": "🌙 Sombre",
        "de": "🌙 Dunkel",
        "pt-BR": "🌙 Escuro",
    },
    "preferences.applied": {
        "en": "✅ Preference applied. Reloading…",
        "ja": "✅ 設定を適用しました。再読み込み中…",
        "zh-CN": "✅ 偏好已应用,正在重新加载…",
        "ko": "✅ 환경 설정 적용됨. 재로드 중…",
        "es": "✅ Preferencia aplicada. Recargando…",
        "fr": "✅ Préférence appliquée. Rechargement…",
        "de": "✅ Einstellung angewendet. Lade neu…",
        "pt-BR": "✅ Preferência aplicada. Recarregando…",
    },
    # ===== Login screen =====================================================
    "login.user_id": {
        "en": "User ID",
        "ja": "ユーザ ID",
        "zh-CN": "用户 ID",
        "ko": "사용자 ID",
        "es": "ID de usuario",
        "fr": "ID utilisateur",
        "de": "Benutzer-ID",
        "pt-BR": "ID de usuário",
    },
    "login.org_id": {
        "en": "Organization",
        "ja": "組織",
        "zh-CN": "组织",
        "ko": "조직",
        "es": "Organización",
        "fr": "Organisation",
        "de": "Organisation",
        "pt-BR": "Organização",
    },
    "login.api_key": {
        "en": "API key (optional)",
        "ja": "API キー (任意)",
        "zh-CN": "API 密钥(可选)",
        "ko": "API 키 (선택)",
        "es": "Clave API (opcional)",
        "fr": "Clé API (optionnelle)",
        "de": "API-Key (optional)",
        "pt-BR": "Chave API (opcional)",
    },
    "login.user_id_help": {
        "en": "Your username. If admin has registered users via `praxia user create`, type that name. Otherwise any name works (single-user dev mode).",
        "ja": "ユーザ名。管理者が `praxia user create` でユーザを登録済ならその名前を入力。未登録なら何でも OK (単一ユーザ開発モード)。",
        "zh-CN": "你的用户名。若管理员已用 `praxia user create` 注册过,请输入该用户名。否则任意名称即可(单用户开发模式)。",
        "ko": "사용자명. 관리자가 `praxia user create` 로 등록했다면 해당 이름을 입력. 미등록이면 아무 이름이나 가능 (단일 사용자 개발 모드).",
        "es": "Tu nombre de usuario. Si el admin lo registró con `praxia user create`, escríbelo. Si no, cualquier nombre vale (modo dev/usuario único).",
        "fr": "Votre nom d'utilisateur. Si l'admin l'a enregistré via `praxia user create`, tapez ce nom. Sinon, n'importe quel nom convient (mode dev/mono-utilisateur).",
        "de": "Dein Benutzername. Falls der admin den Nutzer mit `praxia user create` registriert hat, diesen Namen eingeben. Sonst beliebiger Name (Einzelnutzer-Dev).",
        "pt-BR": "Seu nome de usuário. Se o admin registrou via `praxia user create`, use esse nome. Caso contrário, qualquer nome serve (modo dev/usuário único).",
    },
    "login.advanced": {
        "en": "Advanced options",
        "ja": "詳細オプション",
        "zh-CN": "高级选项",
        "ko": "고급 옵션",
        "es": "Opciones avanzadas",
        "fr": "Options avancées",
        "de": "Erweiterte Optionen",
        "pt-BR": "Opções avançadas",
    },
    "login.api_key_help": {
        "en": "Your Praxia API key acts as your password. Issue one with `praxia user create <name> --role <role>`. Required if any users have been registered; optional in single-user dev mode.",
        "ja": "API キーは Praxia の **パスワード相当** です。`praxia user create <名前> --role <ロール>` で発行。ユーザ登録済の環境では必須、単一ユーザ開発モードでは任意。",
        "zh-CN": "API 密钥是 Praxia 的 **密码**。用 `praxia user create <名字> --role <角色>` 发行。已注册用户的环境必需,单用户开发模式可选。",
        "ko": "API 키는 Praxia 의 **비밀번호** 입니다. `praxia user create <이름> --role <역할>` 로 발급. 등록 사용자가 있는 환경에서는 필수, 단일 사용자 개발 모드에서는 선택.",
        "es": "Tu clave API es tu contraseña en Praxia. Emítela con `praxia user create <nombre> --role <rol>`. Requerida si hay usuarios registrados; opcional en modo dev.",
        "fr": "Votre clé API est votre mot de passe Praxia. Émettez-en une via `praxia user create <nom> --role <rôle>`. Obligatoire si des utilisateurs sont enregistrés ; optionnelle en mode dev.",
        "de": "Dein API-Key ist dein Praxia-Passwort. Mit `praxia user create <name> --role <role>` ausstellen. Pflicht bei registrierten Nutzern, optional im Dev-Modus.",
        "pt-BR": "Sua chave API é sua senha no Praxia. Emita com `praxia user create <nome> --role <papel>`. Obrigatória com usuários registrados; opcional em modo dev.",
    },
    "login.api_key_placeholder": {
        "en": "praxia_xxxxx…",
        "ja": "praxia_xxxxx…",
        "zh-CN": "praxia_xxxxx…",
        "ko": "praxia_xxxxx…",
        "es": "praxia_xxxxx…",
        "fr": "praxia_xxxxx…",
        "de": "praxia_xxxxx…",
        "pt-BR": "praxia_xxxxx…",
    },
    "login.api_key_required": {
        "en": "🔒 An API key is required because users have been registered in this instance. Run `praxia user create <name> --role <role>` to issue one (and save it — it is shown only once).",
        "ja": "🔒 このインスタンスでは既にユーザが登録されているため API キーが必須です。`praxia user create <名前> --role <ロール>` で発行 (表示は 1 回限りなので保存を)。",
        "zh-CN": "🔒 该实例已注册用户,因此需要 API 密钥。运行 `praxia user create <名字> --role <角色>` 发行(仅显示一次,务必保存)。",
        "ko": "🔒 이 인스턴스에는 사용자가 등록되어 있어 API 키가 필요합니다. `praxia user create <이름> --role <역할>` 로 발급 (한 번만 표시되므로 저장).",
        "es": "🔒 Se requiere clave API: hay usuarios registrados en esta instancia. Emite con `praxia user create <nombre> --role <rol>` (mostrada solo una vez).",
        "fr": "🔒 Clé API requise — des utilisateurs sont enregistrés. Émettez via `praxia user create <nom> --role <rôle>` (affichée une seule fois).",
        "de": "🔒 API-Key erforderlich — es sind Nutzer registriert. Mit `praxia user create <name> --role <role>` ausstellen (nur einmal angezeigt).",
        "pt-BR": "🔒 Chave API obrigatória — há usuários registrados. Emita com `praxia user create <nome> --role <papel>` (mostrada apenas uma vez).",
    },
    "login.users_exist_hint": {
        "en": "🔒 This instance has registered users — paste your API key below. Username alone is not enough.",
        "ja": "🔒 このインスタンスにはユーザが登録されています。下に API キーを入力してください。ユーザ名だけでは入れません。",
        "zh-CN": "🔒 此实例已注册用户 — 请在下方粘贴 API 密钥。仅用户名不足以登录。",
        "ko": "🔒 이 인스턴스에는 사용자가 등록되어 있습니다 — 아래에 API 키를 입력하세요. 사용자명만으로는 부족합니다.",
        "es": "🔒 Esta instancia tiene usuarios registrados — pega tu clave API abajo. Solo el nombre no basta.",
        "fr": "🔒 Cette instance a des utilisateurs enregistrés — collez votre clé API ci-dessous. Le nom seul ne suffit pas.",
        "de": "🔒 Diese Instanz hat registrierte Nutzer — API-Key unten einfügen. Nur Benutzername reicht nicht.",
        "pt-BR": "🔒 Esta instância tem usuários registrados — cole sua chave API abaixo. Só o nome não basta.",
    },
    "login.dev_mode_hint": {
        "en": "⚠️ **Single-user dev mode** — no users registered yet. Anyone reaching this URL can sign in with any username and full access. Run `praxia user create <name> --role admin` to enable role-based gating.",
        "ja": "⚠️ **単一ユーザ開発モード** — ユーザ未登録のため、この URL にアクセスできる人なら誰でも好きなユーザ名で入って全機能利用可。`praxia user create <名前> --role admin` でロールベース制御を有効化してください。",
        "zh-CN": "⚠️ **单用户开发模式** — 尚无注册用户,因此任何能访问此 URL 的人都可用任意用户名登录并拥有完整访问权限。运行 `praxia user create <名字> --role admin` 启用角色控制。",
        "ko": "⚠️ **단일 사용자 개발 모드** — 등록 사용자 없음. 이 URL 에 접근할 수 있는 누구나 임의 사용자명으로 로그인 가능. `praxia user create <이름> --role admin` 으로 역할 기반 제어 활성화.",
        "es": "⚠️ **Modo dev/usuario-único** — sin usuarios registrados. Cualquiera con la URL puede entrar con cualquier nombre. Ejecuta `praxia user create <nombre> --role admin` para activar control por rol.",
        "fr": "⚠️ **Mode dev/mono-utilisateur** — aucun utilisateur enregistré. Quiconque atteint cette URL peut se connecter avec n'importe quel nom. Exécutez `praxia user create <nom> --role admin` pour activer le contrôle par rôle.",
        "de": "⚠️ **Einzelnutzer-Dev-Modus** — keine Nutzer registriert. Jeder mit der URL kann sich mit beliebigem Namen anmelden. `praxia user create <name> --role admin` für rollenbasierte Kontrolle.",
        "pt-BR": "⚠️ **Modo dev/usuário-único** — sem usuários registrados. Qualquer um com a URL pode entrar com qualquer nome. Execute `praxia user create <nome> --role admin` para ativar controle por papel.",
    },
    "login.security_note": {
        "en": "💡 The Streamlit UI is designed for **trusted environments** (single-user / company LAN). For multi-user / internet-exposed deployments, run `praxia serve` (FastAPI + OIDC SSO) instead.",
        "ja": "💡 Streamlit UI は **信頼環境** (単一ユーザ / 社内 LAN) 向け設計です。マルチユーザ / インターネット公開向けには `praxia serve` (FastAPI + OIDC SSO) を別途デプロイしてください。",
        "zh-CN": "💡 Streamlit UI 面向 **可信环境**(单用户/内网)。多用户或公网部署请运行 `praxia serve`(FastAPI + OIDC SSO)。",
        "ko": "💡 Streamlit UI 는 **신뢰 환경** (단일 사용자 / 사내 LAN) 용 설계. 다중 사용자 / 공개망 배포는 `praxia serve` (FastAPI + OIDC SSO) 를 사용하세요.",
        "es": "💡 La UI Streamlit está diseñada para **entornos confiables** (usuario único / LAN). Para multiusuario/internet, usa `praxia serve` (FastAPI + OIDC SSO).",
        "fr": "💡 L'UI Streamlit est conçue pour des **environnements de confiance** (mono-utilisateur / LAN). Pour multi-utilisateur / internet, utilisez `praxia serve` (FastAPI + OIDC SSO).",
        "de": "💡 Die Streamlit-UI ist für **vertrauenswürdige Umgebungen** gedacht (Einzelnutzer / Firmen-LAN). Für Multi-User / Internet: `praxia serve` (FastAPI + OIDC SSO) nutzen.",
        "pt-BR": "💡 A UI Streamlit foi feita para **ambientes confiáveis** (usuário único / LAN). Para multi-usuário/internet, use `praxia serve` (FastAPI + OIDC SSO).",
    },
    "login.submit": {
        "en": "Sign in",
        "ja": "サインイン",
        "zh-CN": "登录",
        "ko": "로그인",
        "es": "Entrar",
        "fr": "Connexion",
        "de": "Anmelden",
        "pt-BR": "Entrar",
    },
    "login.user_id_required": {
        "en": "User ID is required.",
        "ja": "ユーザ ID は必須です。",
        "zh-CN": "需要用户 ID。",
        "ko": "사용자 ID 가 필요합니다.",
        "es": "Se requiere ID de usuario.",
        "fr": "ID utilisateur requis.",
        "de": "Benutzer-ID erforderlich.",
        "pt-BR": "ID de usuário obrigatório.",
    },
    "login.invalid_key": {
        "en": "❌ Invalid API key.",
        "ja": "❌ API キーが無効です。",
        "zh-CN": "❌ API 密钥无效。",
        "ko": "❌ 잘못된 API 키.",
        "es": "❌ Clave API inválida.",
        "fr": "❌ Clé API invalide.",
        "de": "❌ Ungültiger API-Key.",
        "pt-BR": "❌ Chave API inválida.",
    },
    "login.dev_hint": {
        "en": "Tip: in single-user dev mode, the User ID is just a namespace label. Create proper users via `praxia user create <name> --role admin` to enable role-based gating.",
        "ja": "ヒント: 単一ユーザの開発モードでは User ID は名前空間ラベルです。`praxia user create <名前> --role admin` でユーザを作成するとロールベース制御が有効化されます。",
        "zh-CN": "提示: 单用户开发模式下,User ID 仅是命名空间标签。运行 `praxia user create <名字> --role admin` 创建用户以启用角色控制。",
        "ko": "힌트: 단일 사용자 개발 모드에서 User ID 는 네임스페이스 라벨입니다. `praxia user create <이름> --role admin` 으로 사용자를 만들면 역할 기반 제어가 활성화됩니다.",
        "es": "Tip: en modo dev/usuario-único, User ID es una etiqueta de namespace. Crea usuarios con `praxia user create <nombre> --role admin` para activar control por rol.",
        "fr": "Astuce : en mode dev/mono-utilisateur, l'User ID est juste une étiquette de namespace. Créez des utilisateurs via `praxia user create <nom> --role admin` pour activer le contrôle par rôle.",
        "de": "Tipp: Im Einzelnutzer-Dev-Modus ist die User ID nur ein Namespace-Label. Lege Nutzer mit `praxia user create <name> --role admin` an, um rollenbasierte Kontrolle zu aktivieren.",
        "pt-BR": "Dica: em modo dev/usuário-único, User ID é apenas um label de namespace. Crie usuários com `praxia user create <nome> --role admin` para ativar controle por papel.",
    },
    "login.sign_out": {
        "en": "Sign out",
        "ja": "サインアウト",
        "zh-CN": "登出",
        "ko": "로그아웃",
        "es": "Salir",
        "fr": "Déconnexion",
        "de": "Abmelden",
        "pt-BR": "Sair",
    },
    # ===== Run view (Workflow / Skill / Agent sub-tabs) =====================
    "run.h": {
        "en": "🎬 Run",
        "ja": "🎬 実行",
        "zh-CN": "🎬 运行",
        "ko": "🎬 실행",
        "es": "🎬 Ejecutar",
        "fr": "🎬 Exécuter",
        "de": "🎬 Ausführen",
        "pt-BR": "🎬 Executar",
    },
    "run.intro": {
        "en": (
            "Two ways to invoke Praxia:\n\n"
            "- **🛠 Skill** — pick a specific domain skill (Investment, Sales, "
            "Legal, etc.) and ask one question. One call, one answer.\n"
            "- **🤖 Agent** — describe a goal; the agent decides which skills "
            "(and workflows, internally) to call, iterating until done.\n\n"
            "Pick **Skill** for known one-shot questions; pick **Agent** for "
            "fuzzy goals that need multiple tools. Pre-built workflows are "
            "still available via SDK / CLI for power users."
        ),
        "ja": (
            "Praxia の呼び出し方は 2 通り:\n\n"
            "- **🛠 スキル** — 特定ドメイン (投資 / 営業 / 法務など) のスキルを選んで 1 つ質問。1 回の呼出で 1 つの回答。\n"
            "- **🤖 エージェント** — ゴールを伝えると、エージェントが必要なスキル (内部的にはワークフローも) を選んで満足まで反復。\n\n"
            "明確な単発質問は **スキル**、ゆるい目標で複数ツールを使いたいなら **エージェント**。事前定義の Workflow は SDK / CLI 経由で利用可能 (上級ユーザ向け)。"
        ),
        "zh-CN": (
            "调用 Praxia 的 2 种方式:\n\n"
            "- **🛠 技能** — 选特定领域技能(投资/销售/法务等),问一次答一次。\n"
            "- **🤖 代理** — 给目标,代理选择需要的技能(内部也用工作流)反复执行直到完成。\n\n"
            "明确单次问题用 **技能**,模糊目标用 **代理**。预建工作流仍可通过 SDK / CLI 使用。"
        ),
        "ko": (
            "Praxia 호출 2 가지:\n\n"
            "- **🛠 스킬** — 특정 도메인 (투자/영업/법무 등) 스킬을 골라 1 회 질문.\n"
            "- **🤖 에이전트** — 목표만 주면 필요한 스킬 (내부적으로 워크플로도) 을 골라 반복 수행.\n\n"
            "명확한 단발 질문은 **스킬**, 모호한 목표는 **에이전트**. 사전 정의 Workflow 는 SDK / CLI 로 사용 가능."
        ),
        "es": (
            "Dos formas de invocar Praxia:\n\n"
            "- **🛠 Skill** — elige una habilidad de dominio y haz una pregunta.\n"
            "- **🤖 Agente** — da un objetivo; el agente elige skills (y workflows internamente) hasta terminar.\n\n"
            "Skill para preguntas únicas claras; Agent para objetivos difusos. Workflows pre-construidos siguen disponibles vía SDK / CLI."
        ),
        "fr": (
            "Deux façons d'utiliser Praxia :\n\n"
            "- **🛠 Skill** — choisissez une compétence de domaine et posez une question.\n"
            "- **🤖 Agent** — donnez un objectif ; l'agent choisit skills (et workflows en interne) jusqu'à terminer.\n\n"
            "Skill pour question ponctuelle ; Agent pour objectif flou. Les workflows pré-construits restent dispo via SDK / CLI."
        ),
        "de": (
            "Zwei Wege, Praxia zu nutzen:\n\n"
            "- **🛠 Skill** — wähle einen Domain-Skill und stelle eine Frage.\n"
            "- **🤖 Agent** — gib ein Ziel; der Agent wählt Skills (und intern Workflows), bis fertig.\n\n"
            "Skill für klare einmalige Fragen; Agent für unklare Ziele. Vordefinierte Workflows weiterhin via SDK / CLI verfügbar."
        ),
        "pt-BR": (
            "Duas formas de invocar Praxia:\n\n"
            "- **🛠 Skill** — escolha uma habilidade de domínio e faça uma pergunta.\n"
            "- **🤖 Agente** — dê um objetivo; o agente escolhe skills (e workflows internamente) até concluir.\n\n"
            "Skill para perguntas únicas; Agent para objetivos difusos. Workflows pré-construídos seguem disponíveis via SDK / CLI."
        ),
    },
    "run.tab.workflow": {
        "en": "📋 Pre-built workflow",
        "ja": "📋 定型ワークフロー",
        "zh-CN": "📋 预建工作流",
        "ko": "📋 사전 정의 워크플로",
        "es": "📋 Workflow pre-construido",
        "fr": "📋 Workflow pré-construit",
        "de": "📋 Vordefinierter Workflow",
        "pt-BR": "📋 Workflow pré-construído",
    },
    "run.tab.skill": {
        "en": "🛠 Single skill",
        "ja": "🛠 単発スキル",
        "zh-CN": "🛠 单一技能",
        "ko": "🛠 단일 스킬",
        "es": "🛠 Habilidad única",
        "fr": "🛠 Compétence unique",
        "de": "🛠 Einzel-Skill",
        "pt-BR": "🛠 Habilidade única",
    },
    "run.tab.agent": {
        "en": "🤖 Autonomous agent",
        "ja": "🤖 自律エージェント",
        "zh-CN": "🤖 自主代理",
        "ko": "🤖 자율 에이전트",
        "es": "🤖 Agente autónomo",
        "fr": "🤖 Agent autonome",
        "de": "🤖 Autonomer Agent",
        "pt-BR": "🤖 Agente autônomo",
    },
    "run.workflow.what": {
        "en": (
            "**What this is**: a *fixed sequence* of multiple agents that runs end-to-end. "
            "The 3 built-in workflows:\n\n"
            "- **sales-agent** — customer research → pain hypotheses → FAQ → proposal draft\n"
            "- **logic-checker** — structure check → contradiction check → readability review\n"
            "- **rag-optimizer** — query rewrite → retrieval → relevance eval → hallucination check loop\n\n"
            "**Pick this when** you have a *recurring procedure* that should always run the same way."
        ),
        "ja": (
            "**これは何**: 複数エージェントが **決まった手順** で連続実行される定型パイプライン。"
            "標準で 3 種類:\n\n"
            "- **sales-agent** — 顧客調査 → 課題仮説 → FAQ → 提案書ドラフト\n"
            "- **logic-checker** — 構造チェック → 矛盾チェック → 読みやすさレビュー\n"
            "- **rag-optimizer** — クエリ書換え → 検索 → 関連度評価 → ハルシネーション検証ループ\n\n"
            "**使う場面**: 毎回同じ手順を踏みたい **定型業務** がある時。"
        ),
        "zh-CN": (
            "**是什么**: 多个代理按 *固定顺序* 端到端运行。内置 3 种:\n\n"
            "- **sales-agent** — 客户调研 → 痛点假设 → FAQ → 提案草稿\n"
            "- **logic-checker** — 结构检查 → 矛盾检查 → 可读性审查\n"
            "- **rag-optimizer** — 查询改写 → 检索 → 相关度评估 → 幻觉检查循环\n\n"
            "**何时使用**: 有 *重复性流程* 且每次都应以相同方式运行时。"
        ),
        "ko": (
            "**무엇**: 여러 에이전트가 *고정된 순서* 로 끝까지 실행되는 파이프라인. 기본 3 종:\n\n"
            "- **sales-agent** — 고객 조사 → 페인포인트 가설 → FAQ → 제안서 초안\n"
            "- **logic-checker** — 구조 검토 → 모순 검토 → 가독성 리뷰\n"
            "- **rag-optimizer** — 쿼리 재작성 → 검색 → 관련도 평가 → 환각 검사 루프\n\n"
            "**언제**: 매번 같은 절차로 진행해야 하는 *반복 업무* 가 있을 때."
        ),
        "es": (
            "**Qué es**: una *secuencia fija* de varios agentes que se ejecuta de extremo a extremo. "
            "3 workflows integrados:\n\n"
            "- **sales-agent** — investigación → hipótesis → FAQ → borrador\n"
            "- **logic-checker** — estructura → contradicción → legibilidad\n"
            "- **rag-optimizer** — reescritura → recuperación → relevancia → bucle anti-alucinación\n\n"
            "**Cuándo**: tienes un procedimiento *recurrente* que siempre debe ejecutarse igual."
        ),
        "fr": (
            "**Qu'est-ce**: une *séquence fixe* de plusieurs agents qui s'exécute de bout en bout. "
            "3 workflows intégrés :\n\n"
            "- **sales-agent** — recherche → hypothèses → FAQ → brouillon\n"
            "- **logic-checker** — structure → contradiction → lisibilité\n"
            "- **rag-optimizer** — réécriture → récupération → pertinence → boucle anti-hallucination\n\n"
            "**Quand** : vous avez une procédure *récurrente* qui doit toujours s'exécuter de la même façon."
        ),
        "de": (
            "**Was ist es**: eine *feste Sequenz* mehrerer Agenten, die end-to-end läuft. "
            "3 eingebaute Workflows:\n\n"
            "- **sales-agent** — Recherche → Hypothesen → FAQ → Entwurf\n"
            "- **logic-checker** — Struktur → Widerspruch → Lesbarkeit\n"
            "- **rag-optimizer** — Query-Rewrite → Retrieval → Relevanz → Halluzinations-Loop\n\n"
            "**Wann**: für *wiederkehrende* Abläufe, die immer gleich laufen sollen."
        ),
        "pt-BR": (
            "**O que é**: uma *sequência fixa* de vários agentes que roda end-to-end. "
            "3 workflows integrados:\n\n"
            "- **sales-agent** — pesquisa → hipóteses → FAQ → rascunho\n"
            "- **logic-checker** — estrutura → contradição → legibilidade\n"
            "- **rag-optimizer** — reescrita → recuperação → relevância → loop anti-alucinação\n\n"
            "**Quando**: você tem um procedimento *recorrente* que sempre deve rodar do mesmo jeito."
        ),
    },
    "run.skill.what": {
        "en": "**What it is**: a single domain-tuned agent call (Investment / Sales / Design / Purchasing / Patent / Legal).\n\n**Pick this when** one ask = one answer is enough.",
        "ja": "**これは何**: 1 ドメイン特化のエージェント単発呼出 (投資 / 営業 / 設計 / 購買 / 特許 / 法務)。\n\n**使う場面**: 1 つの依頼を 1 回の応答で済ませたい時。",
        "zh-CN": "**是什么**: 单一领域调优的代理一次调用(投资/销售/设计/采购/专利/法务)。\n\n**何时使用**: 一次问一次答即可。",
        "ko": "**무엇**: 단일 도메인 튜닝된 에이전트 1 회 호출 (투자/영업/설계/구매/특허/법무).\n\n**언제**: 한 번의 의뢰로 끝내고 싶을 때.",
        "es": "**Qué es**: una llamada a un agente especializado por dominio (inversión / ventas / diseño / compras / patentes / legal).\n\n**Cuándo**: una pregunta = una respuesta.",
        "fr": "**Qu'est-ce**: un appel à un agent spécialisé par domaine (invest / ventes / design / achats / brevets / juridique).\n\n**Quand**: une demande = une réponse.",
        "de": "**Was ist es**: ein einzelner Domain-Skill-Agent-Aufruf (Invest / Sales / Design / Einkauf / Patent / Legal).\n\n**Wann**: eine Anfrage, eine Antwort genügt.",
        "pt-BR": "**O que é**: uma chamada a agente especializado por domínio (invest / vendas / design / compras / patentes / jurídico).\n\n**Quando**: uma pergunta = uma resposta.",
    },
    "run.agent.what": {
        "en": "**What it is**: an LLM-driven tool-use loop. You give a goal; the agent decides which tools to call (memory search, connector pulls, skills) until done.\n\n**Pick this when** you want to delegate a goal and let the LLM figure out the steps.",
        "ja": "**これは何**: LLM 駆動のツール使用ループ。ゴールだけ伝えると、エージェントが自分でツール (メモリ検索 / コネクタ pull / スキル) を選んで実行します。\n\n**使う場面**: ゴールだけ渡して手順は LLM に任せたい時。",
        "zh-CN": "**是什么**: LLM 驱动的工具使用循环。你给目标,代理自主决定调用哪些工具(记忆检索/连接器/技能)直到完成。\n\n**何时使用**: 想委托目标,让 LLM 决定步骤时。",
        "ko": "**무엇**: LLM 주도 도구 사용 루프. 목표만 전달하면 에이전트가 도구 (메모리 검색 / 커넥터 / 스킬) 를 직접 선택해 수행.\n\n**언제**: 목표만 위임하고 절차는 LLM 에 맡기고 싶을 때.",
        "es": "**Qué es**: bucle de uso de herramientas guiado por LLM. Das un objetivo; el agente decide qué herramientas usar (memoria, conectores, skills) hasta terminar.\n\n**Cuándo**: para delegar el objetivo y dejar que el LLM decida pasos.",
        "fr": "**Qu'est-ce**: boucle d'utilisation d'outils pilotée par LLM. Vous donnez un objectif ; l'agent choisit ses outils (mémoire, connecteurs, compétences) jusqu'à la fin.\n\n**Quand**: pour déléguer l'objectif et laisser le LLM décider des étapes.",
        "de": "**Was ist es**: LLM-gesteuerte Tool-Use-Schleife. Du gibst ein Ziel vor; der Agent wählt Tools (Speicher, Konnektoren, Skills) selbst.\n\n**Wann**: Ziel delegieren, LLM die Schritte überlassen.",
        "pt-BR": "**O que é**: loop de uso de ferramentas guiado por LLM. Você dá um objetivo; o agente decide quais ferramentas usar (memória, conectores, skills) até concluir.\n\n**Quando**: para delegar o objetivo e deixar o LLM decidir os passos.",
    },
    "run.agent.coming_soon": {
        "en": "🚧 Autonomous-agent UI is coming. For now, run from the CLI:",
        "ja": "🚧 自律エージェントの UI は準備中。現状は CLI から実行してください:",
        "zh-CN": "🚧 自主代理 UI 准备中。目前请通过 CLI 运行:",
        "ko": "🚧 자율 에이전트 UI 는 준비 중. 현재는 CLI 에서 실행하세요:",
        "es": "🚧 La UI del agente autónomo está en camino. Por ahora, ejecuta desde la CLI:",
        "fr": "🚧 L'UI agent autonome arrive bientôt. Pour l'instant, lancez depuis la CLI :",
        "de": "🚧 Autonomous-Agent-UI ist im Aufbau. Derzeit über CLI starten:",
        "pt-BR": "🚧 A UI do agente autônomo está a caminho. Por enquanto, execute via CLI:",
    },
    # ===== Data scope picker (in-workspace) =================================
    "scope.section_h": {
        "en": "Reference data scopes (optional)",
        "ja": "参照データ範囲 (任意)",
        "zh-CN": "参考数据范围(可选)",
        "ko": "참조 데이터 범위 (선택)",
        "es": "Alcances de datos de referencia (opcional)",
        "fr": "Portées de données de référence (optionnel)",
        "de": "Referenzdaten-Bereiche (optional)",
        "pt-BR": "Escopos de dados de referência (opcional)",
    },
    "scope.section_intro": {
        "en": "Pick which folders / memory layers to feed into this run as additional context. Manage folders under 📁 Data.",
        "ja": "今回の実行に渡す追加コンテキストを選択。フォルダの管理は 📁 データ から。",
        "zh-CN": "选择本次运行作为附加上下文的文件夹/记忆层。文件夹管理在 📁 数据。",
        "ko": "이번 실행에 추가 컨텍스트로 사용할 폴더 / 메모리 레이어를 선택. 폴더 관리는 📁 데이터.",
        "es": "Elige qué carpetas / capas de memoria alimentar como contexto extra. Gestiona carpetas en 📁 Datos.",
        "fr": "Choisissez les dossiers / couches mémoire à injecter comme contexte additionnel. Gestion sous 📁 Données.",
        "de": "Wähle Ordner / Speicherschichten als zusätzlichen Kontext. Ordner verwaltest du unter 📁 Daten.",
        "pt-BR": "Escolha quais pastas / camadas de memória usar como contexto extra. Gerencie pastas em 📁 Dados.",
    },
    "scope.builtin_h": {
        "en": "Built-in",
        "ja": "標準",
        "zh-CN": "内置",
        "ko": "기본",
        "es": "Integrado",
        "fr": "Intégré",
        "de": "Integriert",
        "pt-BR": "Integrado",
    },
    "scope.custom_h": {
        "en": "Custom folders",
        "ja": "カスタムフォルダ",
        "zh-CN": "自定义文件夹",
        "ko": "커스텀 폴더",
        "es": "Carpetas personalizadas",
        "fr": "Dossiers personnalisés",
        "de": "Eigene Ordner",
        "pt-BR": "Pastas personalizadas",
    },
    "scope.empty_hint": {
        "en": "(none yet — create one in 📁 Data)",
        "ja": "(未作成 — 📁 データ で作成)",
        "zh-CN": "(尚无 — 在 📁 数据 中创建)",
        "ko": "(없음 — 📁 데이터 에서 생성)",
        "es": "(aún ninguna — crea en 📁 Datos)",
        "fr": "(aucun — créez dans 📁 Données)",
        "de": "(noch keine — in 📁 Daten anlegen)",
        "pt-BR": "(nenhuma — crie em 📁 Dados)",
    },
    # ===== Admin: language picker (moved from sidebar) ======================
    "admin.settings.language_h": {
        "en": "Language",
        "ja": "言語",
        "zh-CN": "语言",
        "ko": "언어",
        "es": "Idioma",
        "fr": "Langue",
        "de": "Sprache",
        "pt-BR": "Idioma",
    },
    "admin.settings.language_intro": {
        "en": "Default is auto-detected from your browser/OS. Override here if you prefer a different language.",
        "ja": "既定はブラウザ/OS から自動検出。別言語を使いたい場合のみ切替えてください。",
        "zh-CN": "默认从浏览器/OS 自动检测。如需其他语言可在此切换。",
        "ko": "기본값은 브라우저/OS 에서 자동 감지. 다른 언어를 원하면 여기서 전환.",
        "es": "Por defecto se detecta del navegador/OS. Cambia aquí si prefieres otro idioma.",
        "fr": "Par défaut détecté depuis le navigateur/OS. Changez ici si vous préférez une autre langue.",
        "de": "Standard wird vom Browser/OS automatisch erkannt. Hier umstellen, wenn nötig.",
        "pt-BR": "Padrão detectado do navegador/OS. Troque aqui se preferir outro idioma.",
    },
    "admin.settings.language_label": {
        "en": "Display language",
        "ja": "表示言語",
        "zh-CN": "显示语言",
        "ko": "표시 언어",
        "es": "Idioma de la interfaz",
        "fr": "Langue d'affichage",
        "de": "Anzeigesprache",
        "pt-BR": "Idioma de exibição",
    },
    "mode.data": {
        "en": "📁 Data folders",
        "ja": "📁 データフォルダ",
        "zh-CN": "📁 数据文件夹",
        "ko": "📁 데이터 폴더",
        "es": "📁 Carpetas de datos",
        "fr": "📁 Dossiers de données",
        "de": "📁 Datenordner",
        "pt-BR": "📁 Pastas de dados",
    },
    # ===== Data scope sidebar selector ======================================
    "sidebar.scope.h": {
        "en": "Data scope",
        "ja": "データ範囲",
        "zh-CN": "数据范围",
        "ko": "데이터 범위",
        "es": "Alcance de datos",
        "fr": "Portée des données",
        "de": "Datenbereich",
        "pt-BR": "Escopo de dados",
    },
    "scope.personal_memory": {
        "en": "Personal memory",
        "ja": "個人メモリ",
        "zh-CN": "个人记忆",
        "ko": "개인 메모리",
        "es": "Memoria personal",
        "fr": "Mémoire personnelle",
        "de": "Persönlicher Speicher",
        "pt-BR": "Memória pessoal",
    },
    "scope.org_memory": {
        "en": "Org memory",
        "ja": "組織メモリ",
        "zh-CN": "组织记忆",
        "ko": "조직 메모리",
        "es": "Memoria org",
        "fr": "Mémoire org",
        "de": "Org-Speicher",
        "pt-BR": "Memória org",
    },
    "scope.frozen": {
        "en": "Frozen layer (Markdown)",
        "ja": "凍結層 (Markdown)",
        "zh-CN": "冻结层 (Markdown)",
        "ko": "동결 레이어 (Markdown)",
        "es": "Capa congelada (Markdown)",
        "fr": "Couche figée (Markdown)",
        "de": "Frozen-Layer (Markdown)",
        "pt-BR": "Camada congelada (Markdown)",
    },
    "sidebar.scope.local_h": {
        "en": "Local folders",
        "ja": "ローカルフォルダ",
        "zh-CN": "本地文件夹",
        "ko": "로컬 폴더",
        "es": "Carpetas locales",
        "fr": "Dossiers locaux",
        "de": "Lokale Ordner",
        "pt-BR": "Pastas locais",
    },
    "sidebar.scope.connector_h": {
        "en": "Connector folders",
        "ja": "コネクタフォルダ",
        "zh-CN": "连接器文件夹",
        "ko": "커넥터 폴더",
        "es": "Carpetas de conector",
        "fr": "Dossiers de connecteur",
        "de": "Konnektor-Ordner",
        "pt-BR": "Pastas de conector",
    },
    "sidebar.scope.empty_hint": {
        "en": "No custom folders yet — create one in 📁 Data folders mode.",
        "ja": "カスタムフォルダ未作成 — 📁 データフォルダ モードで作成してください。",
        "zh-CN": "尚无自定义文件夹 — 在 📁 数据文件夹 模式中创建。",
        "ko": "커스텀 폴더 없음 — 📁 데이터 폴더 모드에서 만드세요.",
        "es": "Sin carpetas personalizadas — créalas en el modo 📁 Carpetas de datos.",
        "fr": "Aucun dossier personnalisé — créez-en dans le mode 📁 Dossiers de données.",
        "de": "Noch keine eigenen Ordner — im Modus 📁 Datenordner anlegen.",
        "pt-BR": "Sem pastas personalizadas — crie no modo 📁 Pastas de dados.",
    },
    # ===== Data folder management mode ======================================
    "data.intro": {
        "en": "Manage **named folders** of data you want to target at execution time. Two kinds: **Local folders** (files you upload here) and **Connector folders** (registered paths in Box / SharePoint / Notion / etc.). Selected folders in the sidebar get auto-injected into Flow / Skill runs as additional context.",
        "ja": "実行時に対象としたい **名前付きフォルダ** を管理します。2 種類: **ローカルフォルダ** (この UI でアップロードしたファイル群) と **コネクタフォルダ** (Box / SharePoint / Notion 等の特定パス)。サイドバーで選択したフォルダの内容が、Flow / Skill 実行時に追加コンテキストとして自動注入されます。",
        "zh-CN": "管理你希望在执行时使用的**命名文件夹**。两类: **本地文件夹** (在此上传的文件) 与 **连接器文件夹** (Box / SharePoint / Notion 等的指定路径)。在侧边栏选中的文件夹会作为附加上下文自动注入到 Flow / Skill 运行中。",
        "ko": "실행 시 대상으로 삼고 싶은 **이름이 있는 폴더** 를 관리합니다. 두 종류: **로컬 폴더** (이 UI 에서 업로드한 파일) 와 **커넥터 폴더** (Box / SharePoint / Notion 등의 특정 경로). 사이드바에서 선택한 폴더가 Flow / Skill 실행 시 추가 컨텍스트로 자동 주입됩니다.",
        "es": "Administra **carpetas con nombre** que quieras usar al ejecutar. Dos tipos: **Carpetas locales** (archivos que subes aquí) y **Carpetas de conector** (rutas registradas en Box / SharePoint / Notion / etc.). Las carpetas seleccionadas en la barra lateral se inyectan automáticamente como contexto extra en Flow / Skill.",
        "fr": "Gérez des **dossiers nommés** ciblés à l'exécution. Deux types : **Dossiers locaux** (fichiers téléversés ici) et **Dossiers de connecteur** (chemins enregistrés dans Box / SharePoint / Notion / etc.). Les dossiers cochés dans la sidebar sont injectés automatiquement comme contexte additionnel pendant Flow / Skill.",
        "de": "Verwalte **benannte Ordner** mit Daten, die du zur Laufzeit nutzen willst. Zwei Arten: **Lokale Ordner** (hier hochgeladene Dateien) und **Konnektor-Ordner** (registrierte Pfade in Box / SharePoint / Notion usw.). In der Sidebar ausgewählte Ordner werden bei Flow / Skill automatisch als Zusatzkontext eingespeist.",
        "pt-BR": "Gerencie **pastas nomeadas** que você queira usar em runtime. Dois tipos: **Pastas locais** (arquivos enviados aqui) e **Pastas de conector** (caminhos registrados em Box / SharePoint / Notion / etc.). Pastas marcadas na sidebar são injetadas automaticamente como contexto adicional durante Flow / Skill.",
    },
    "data.tab.local": {
        "en": "📁 Local folders",
        "ja": "📁 ローカルフォルダ",
        "zh-CN": "📁 本地文件夹",
        "ko": "📁 로컬 폴더",
        "es": "📁 Carpetas locales",
        "fr": "📁 Dossiers locaux",
        "de": "📁 Lokale Ordner",
        "pt-BR": "📁 Pastas locais",
    },
    "data.tab.connector": {
        "en": "🔌 Connector folders",
        "ja": "🔌 コネクタフォルダ",
        "zh-CN": "🔌 连接器文件夹",
        "ko": "🔌 커넥터 폴더",
        "es": "🔌 Carpetas de conector",
        "fr": "🔌 Dossiers de connecteur",
        "de": "🔌 Konnektor-Ordner",
        "pt-BR": "🔌 Pastas de conector",
    },
    "data.tab.browse": {
        "en": "🔍 Browse",
        "ja": "🔍 ブラウズ",
        "zh-CN": "🔍 浏览",
        "ko": "🔍 탐색",
        "es": "🔍 Explorar",
        "fr": "🔍 Parcourir",
        "de": "🔍 Durchsuchen",
        "pt-BR": "🔍 Explorar",
    },
    "data.local.intro": {
        "en": "Upload files into a named folder. Folders persist across sessions.",
        "ja": "名前付きフォルダにファイルをアップロードします。セッション越えに保存されます。",
        "zh-CN": "将文件上传到命名文件夹中,跨会话保留。",
        "ko": "이름이 있는 폴더에 파일을 업로드합니다. 세션 간 유지됩니다.",
        "es": "Sube archivos a una carpeta con nombre. Persisten entre sesiones.",
        "fr": "Téléversez des fichiers dans un dossier nommé. Conservés entre sessions.",
        "de": "Lade Dateien in einen benannten Ordner. Bleiben über Sitzungen hinweg erhalten.",
        "pt-BR": "Envie arquivos para uma pasta nomeada. Persistem entre sessões.",
    },
    "data.local.empty": {
        "en": "No local folders yet. Create one below.",
        "ja": "ローカルフォルダ未作成。下から作成してください。",
        "zh-CN": "尚无本地文件夹。在下方创建。",
        "ko": "로컬 폴더 없음. 아래에서 만드세요.",
        "es": "Sin carpetas locales. Crea una abajo.",
        "fr": "Aucun dossier local. Créez-en un ci-dessous.",
        "de": "Noch keine lokalen Ordner. Unten anlegen.",
        "pt-BR": "Sem pastas locais. Crie uma abaixo.",
    },
    "data.local.add_files": {
        "en": "Add more files (drop or browse)",
        "ja": "ファイルを追加 (ドロップまたは選択)",
        "zh-CN": "追加文件 (拖放或浏览)",
        "ko": "파일 추가 (드롭 또는 선택)",
        "es": "Agregar más archivos (soltar o examinar)",
        "fr": "Ajouter d'autres fichiers (déposer ou parcourir)",
        "de": "Weitere Dateien hinzufügen (Drop oder Auswahl)",
        "pt-BR": "Adicionar mais arquivos (soltar ou navegar)",
    },
    "data.local.save_uploads": {
        "en": "💾 Save uploads",
        "ja": "💾 アップロード保存",
        "zh-CN": "💾 保存上传",
        "ko": "💾 업로드 저장",
        "es": "💾 Guardar subidas",
        "fr": "💾 Enregistrer",
        "de": "💾 Uploads speichern",
        "pt-BR": "💾 Salvar uploads",
    },
    "data.local.no_files_to_save": {
        "en": "No files selected.",
        "ja": "ファイルが選択されていません。",
        "zh-CN": "未选择文件。",
        "ko": "선택된 파일이 없습니다.",
        "es": "No hay archivos seleccionados.",
        "fr": "Aucun fichier sélectionné.",
        "de": "Keine Dateien ausgewählt.",
        "pt-BR": "Nenhum arquivo selecionado.",
    },
    "data.local.saved": {
        "en": "✅ Saved {n} file(s)",
        "ja": "✅ {n} 件のファイルを保存しました",
        "zh-CN": "✅ 已保存 {n} 个文件",
        "ko": "✅ {n} 개 파일 저장됨",
        "es": "✅ Se guardaron {n} archivo(s)",
        "fr": "✅ {n} fichier(s) enregistré(s)",
        "de": "✅ {n} Datei(en) gespeichert",
        "pt-BR": "✅ {n} arquivo(s) salvo(s)",
    },
    "data.local.delete_folder": {
        "en": "🗑 Delete folder",
        "ja": "🗑 フォルダ削除",
        "zh-CN": "🗑 删除文件夹",
        "ko": "🗑 폴더 삭제",
        "es": "🗑 Eliminar carpeta",
        "fr": "🗑 Supprimer le dossier",
        "de": "🗑 Ordner löschen",
        "pt-BR": "🗑 Excluir pasta",
    },
    "data.local.folder_deleted": {
        "en": "🗑 Folder '{name}' deleted",
        "ja": "🗑 フォルダ '{name}' を削除しました",
        "zh-CN": "🗑 已删除文件夹「{name}」",
        "ko": "🗑 '{name}' 폴더를 삭제했습니다",
        "es": "🗑 Carpeta '{name}' eliminada",
        "fr": "🗑 Dossier « {name} » supprimé",
        "de": "🗑 Ordner '{name}' gelöscht",
        "pt-BR": "🗑 Pasta '{name}' excluída",
    },
    "data.local.create_h": {
        "en": "Create a new local folder",
        "ja": "新規ローカルフォルダ作成",
        "zh-CN": "创建新的本地文件夹",
        "ko": "새 로컬 폴더 만들기",
        "es": "Crear nueva carpeta local",
        "fr": "Créer un nouveau dossier local",
        "de": "Neuen lokalen Ordner anlegen",
        "pt-BR": "Criar nova pasta local",
    },
    "data.local.create_name": {
        "en": "Folder name",
        "ja": "フォルダ名",
        "zh-CN": "文件夹名称",
        "ko": "폴더 이름",
        "es": "Nombre de la carpeta",
        "fr": "Nom du dossier",
        "de": "Ordnername",
        "pt-BR": "Nome da pasta",
    },
    "data.local.create_desc": {
        "en": "Description (optional)",
        "ja": "説明 (任意)",
        "zh-CN": "描述(可选)",
        "ko": "설명 (선택)",
        "es": "Descripción (opcional)",
        "fr": "Description (optionnel)",
        "de": "Beschreibung (optional)",
        "pt-BR": "Descrição (opcional)",
    },
    "data.local.create_files": {
        "en": "Initial files (optional)",
        "ja": "初期ファイル (任意)",
        "zh-CN": "初始文件(可选)",
        "ko": "초기 파일 (선택)",
        "es": "Archivos iniciales (opcional)",
        "fr": "Fichiers initiaux (optionnel)",
        "de": "Anfangsdateien (optional)",
        "pt-BR": "Arquivos iniciais (opcional)",
    },
    "data.local.create_btn": {
        "en": "Create folder",
        "ja": "フォルダを作成",
        "zh-CN": "创建文件夹",
        "ko": "폴더 만들기",
        "es": "Crear carpeta",
        "fr": "Créer le dossier",
        "de": "Ordner anlegen",
        "pt-BR": "Criar pasta",
    },
    "data.local.create_name_required": {
        "en": "Folder name is required.",
        "ja": "フォルダ名は必須です。",
        "zh-CN": "需要文件夹名称。",
        "ko": "폴더 이름이 필요합니다.",
        "es": "Se requiere nombre de carpeta.",
        "fr": "Le nom du dossier est requis.",
        "de": "Ordnername ist erforderlich.",
        "pt-BR": "Nome da pasta é obrigatório.",
    },
    "data.local.created": {
        "en": "✅ Created '{name}'",
        "ja": "✅ '{name}' を作成しました",
        "zh-CN": "✅ 已创建「{name}」",
        "ko": "✅ '{name}' 을(를) 만들었습니다",
        "es": "✅ Se creó '{name}'",
        "fr": "✅ « {name} » créé",
        "de": "✅ '{name}' angelegt",
        "pt-BR": "✅ '{name}' criada",
    },
    "data.connector.intro": {
        "en": (
            "Register a path inside an external system (Box / SharePoint / "
            "Notion / etc.) as a named folder you can target at run time.\n\n"
            "**Permission model**:\n"
            "- The **admin** must first enable the connector by setting "
            "`PRAXIA_CONN_<NAME>_*` env vars (CLI: `praxia config set ...`).\n"
            "- **Anyone** can then register a folder (path) under an enabled "
            "connector — the registration itself is just metadata.\n"
            "- At pull time, the connector uses *whatever credentials it was "
            "configured with*. With **per-user OAuth** providers (Box, Google, "
            "Microsoft, Dropbox, Salesforce), each Praxia user authorizes "
            "with their own account, so the external system's native ACL "
            "applies — alice only sees what alice has access to. With "
            "service-account / API-key providers, all users share the same "
            "view (admin-controlled).\n\n"
            "Connector folders you register here are visible only to you "
            "and only used when you select them as a Data scope."
        ),
        "ja": (
            "外部システム (Box / SharePoint / Notion 等) の特定パスを、"
            "実行時に対象指定できる「名前付きフォルダ」として登録します。\n\n"
            "**権限モデル**:\n"
            "- 連携は **管理者** が `PRAXIA_CONN_<NAME>_*` 環境変数で有効化 "
            "(CLI: `praxia config set ...`)。\n"
            "- 有効化済みの連携先に対して、**全ユーザ** がフォルダ (パス) を登録可能。"
            "登録自体はメタデータのみ。\n"
            "- pull 実行時は、**設定済の認証情報** で外部にアクセス。Box / Google / "
            "Microsoft / Dropbox / Salesforce など **per-user OAuth** 対応の連携先は、"
            "各 Praxia ユーザが自身のアカウントで認可するため、外部システムの ACL が"
            "そのまま反映 — alice には alice が見える範囲しか出ません。"
            "サービスアカウント / API キー方式の連携先は全ユーザが同じビューを共有 "
            "(管理者管轄)。\n\n"
            "ここで登録するコネクタフォルダは **あなたにのみ見え**、"
            "Data scope で選んだ時だけ利用されます。"
        ),
        "zh-CN": (
            "将外部系统(Box / SharePoint / Notion 等)中的路径注册为可在运行时使用的命名文件夹。\n\n"
            "**权限模型**: 管理员先通过 `PRAXIA_CONN_<NAME>_*` 环境变量启用连接器。"
            "之后所有用户可在已启用连接器下注册路径(仅元数据)。"
            "Pull 时使用配置好的凭据。Per-user OAuth 连接器(Box/Google/MS/Dropbox/Salesforce)各用户用自己账号授权,外部 ACL 生效。"
            "服务账号/API 密钥连接器所有用户共享同一视图。\n\n"
            "你注册的文件夹仅你自己可见,选作 Data scope 时才使用。"
        ),
        "ko": (
            "외부 시스템 (Box / SharePoint / Notion 등) 의 경로를 실행 시 사용할 이름 있는 폴더로 등록합니다.\n\n"
            "**권한 모델**: 관리자가 먼저 `PRAXIA_CONN_<NAME>_*` 환경변수로 커넥터를 활성화. "
            "이후 모든 사용자가 활성 커넥터에 폴더(경로) 등록 가능 (메타데이터만). "
            "Pull 시 설정된 자격증명으로 접근. Per-user OAuth (Box/Google/MS/Dropbox/Salesforce) 는 각 사용자가 자신의 계정으로 인증, 외부 ACL 적용. "
            "서비스 계정 / API 키 방식은 모든 사용자가 동일한 뷰 공유.\n\n"
            "여기서 등록한 폴더는 본인에게만 보이고, Data scope 로 선택할 때만 사용됩니다."
        ),
        "es": (
            "Registra una ruta en un sistema externo (Box / SharePoint / Notion / etc.) como carpeta con nombre que puedes usar en runtime.\n\n"
            "**Modelo de permisos**: el admin habilita primero el conector vía `PRAXIA_CONN_<NAME>_*`. "
            "Cualquiera puede registrar carpetas bajo conectores habilitados (solo metadata). "
            "El pull usa las credenciales configuradas. Conectores con per-user OAuth (Box/Google/MS/Dropbox/Salesforce) usan la cuenta de cada usuario, ACL externo se aplica. "
            "Conectores con service account / API key comparten una sola vista.\n\n"
            "Las carpetas que registres aquí solo son visibles para ti, y solo se usan al seleccionarlas como Data scope."
        ),
        "fr": (
            "Enregistrez un chemin dans un système externe (Box / SharePoint / Notion / etc.) comme dossier nommé utilisable à l'exécution.\n\n"
            "**Modèle de permissions** : l'admin active d'abord le connecteur via `PRAXIA_CONN_<NAME>_*`. "
            "Tout le monde peut alors enregistrer des dossiers sous les connecteurs activés (métadonnées uniquement). "
            "Le pull utilise les credentials configurés. Connecteurs per-user OAuth (Box/Google/MS/Dropbox/Salesforce) : chaque utilisateur s'authentifie avec son compte, ACL externe appliqué. "
            "Connecteurs service-account / API key : vue partagée.\n\n"
            "Les dossiers enregistrés ici ne sont visibles que par vous, et utilisés uniquement quand vous les sélectionnez comme Data scope."
        ),
        "de": (
            "Registriere einen Pfad in einem externen System (Box / SharePoint / Notion etc.) als benannten Ordner für Laufzeitnutzung.\n\n"
            "**Berechtigungsmodell**: Der admin aktiviert den Konnektor zuerst via `PRAXIA_CONN_<NAME>_*`. "
            "Jeder kann dann Ordner unter aktivierten Konnektoren registrieren (nur Metadaten). "
            "Pull nutzt die konfigurierten Credentials. Per-user-OAuth-Konnektoren (Box/Google/MS/Dropbox/Salesforce): jeder Nutzer authentifiziert sich selbst, externe ACL wird angewendet. "
            "Service-Account-/API-Key-Konnektoren: gemeinsame Sicht.\n\n"
            "Hier registrierte Ordner sind nur für dich sichtbar und werden nur als Data Scope genutzt."
        ),
        "pt-BR": (
            "Registre um caminho em sistema externo (Box / SharePoint / Notion / etc.) como pasta nomeada usável em runtime.\n\n"
            "**Modelo de permissões**: o admin habilita primeiro o conector via `PRAXIA_CONN_<NAME>_*`. "
            "Qualquer um pode então registrar pastas sob conectores habilitados (só metadata). "
            "O pull usa as credenciais configuradas. Conectores per-user OAuth (Box/Google/MS/Dropbox/Salesforce) usam a conta do usuário; ACL externo aplicado. "
            "Conectores service-account / API key: visão compartilhada.\n\n"
            "As pastas registradas aqui só são visíveis para você, usadas apenas quando selecionadas como Data scope."
        ),
    },
    "data.connector.empty": {
        "en": "No connector folders registered yet. Add one below.",
        "ja": "コネクタフォルダ未登録。下から追加してください。",
        "zh-CN": "尚未注册连接器文件夹。在下方添加。",
        "ko": "등록된 커넥터 폴더 없음. 아래에서 추가하세요.",
        "es": "Sin carpetas de conector registradas. Agrega una abajo.",
        "fr": "Aucun dossier de connecteur enregistré. Ajoutez-en un ci-dessous.",
        "de": "Noch keine Konnektor-Ordner. Unten hinzufügen.",
        "pt-BR": "Sem pastas de conector. Adicione uma abaixo.",
    },
    "data.connector.delete": {
        "en": "🗑 Delete registration",
        "ja": "🗑 登録を削除",
        "zh-CN": "🗑 删除注册",
        "ko": "🗑 등록 삭제",
        "es": "🗑 Eliminar registro",
        "fr": "🗑 Supprimer l'enregistrement",
        "de": "🗑 Registrierung löschen",
        "pt-BR": "🗑 Excluir registro",
    },
    "data.connector.create_h": {
        "en": "Register a new connector folder",
        "ja": "新規コネクタフォルダ登録",
        "zh-CN": "注册新的连接器文件夹",
        "ko": "새 커넥터 폴더 등록",
        "es": "Registrar nueva carpeta de conector",
        "fr": "Enregistrer un nouveau dossier de connecteur",
        "de": "Neuen Konnektor-Ordner registrieren",
        "pt-BR": "Registrar nova pasta de conector",
    },
    "data.connector.create_name": {
        "en": "Display name",
        "ja": "表示名",
        "zh-CN": "显示名称",
        "ko": "표시 이름",
        "es": "Nombre visible",
        "fr": "Nom affiché",
        "de": "Anzeigename",
        "pt-BR": "Nome de exibição",
    },
    "data.connector.create_desc": {
        "en": "Description (optional)",
        "ja": "説明 (任意)",
        "zh-CN": "描述(可选)",
        "ko": "설명 (선택)",
        "es": "Descripción (opcional)",
        "fr": "Description (optionnel)",
        "de": "Beschreibung (optional)",
        "pt-BR": "Descrição (opcional)",
    },
    "data.connector.create_connector": {
        "en": "Connector",
        "ja": "コネクタ",
        "zh-CN": "连接器",
        "ko": "커넥터",
        "es": "Conector",
        "fr": "Connecteur",
        "de": "Konnektor",
        "pt-BR": "Conector",
    },
    "data.connector.create_path": {
        "en": "Path / folder ID / SOQL / app id",
        "ja": "パス / フォルダ ID / SOQL / アプリ ID",
        "zh-CN": "路径 / 文件夹 ID / SOQL / app id",
        "ko": "경로 / 폴더 ID / SOQL / 앱 ID",
        "es": "Ruta / ID de carpeta / SOQL / ID de app",
        "fr": "Chemin / ID dossier / SOQL / ID app",
        "de": "Pfad / Ordner-ID / SOQL / App-ID",
        "pt-BR": "Caminho / ID pasta / SOQL / ID app",
    },
    "data.connector.create_btn": {
        "en": "Register folder",
        "ja": "フォルダを登録",
        "zh-CN": "注册文件夹",
        "ko": "폴더 등록",
        "es": "Registrar carpeta",
        "fr": "Enregistrer le dossier",
        "de": "Ordner registrieren",
        "pt-BR": "Registrar pasta",
    },
    "data.connector.create_required": {
        "en": "Display name and path are required.",
        "ja": "表示名とパスは必須です。",
        "zh-CN": "需要显示名称与路径。",
        "ko": "표시 이름과 경로가 필요합니다.",
        "es": "Se requieren nombre y ruta.",
        "fr": "Nom affiché et chemin requis.",
        "de": "Anzeigename und Pfad sind erforderlich.",
        "pt-BR": "Nome e caminho são obrigatórios.",
    },
    "data.browse.empty": {
        "en": "No folders to browse yet.",
        "ja": "ブラウズできるフォルダがありません。",
        "zh-CN": "尚无可浏览的文件夹。",
        "ko": "탐색할 폴더가 없습니다.",
        "es": "Aún no hay carpetas para explorar.",
        "fr": "Aucun dossier à parcourir.",
        "de": "Noch keine Ordner zum Durchsuchen.",
        "pt-BR": "Sem pastas para explorar.",
    },
    "data.browse.pick": {
        "en": "Pick a folder",
        "ja": "フォルダを選択",
        "zh-CN": "选择文件夹",
        "ko": "폴더 선택",
        "es": "Elige una carpeta",
        "fr": "Choisir un dossier",
        "de": "Ordner wählen",
        "pt-BR": "Escolha uma pasta",
    },
    "data.browse.not_found": {
        "en": "Folder not found.",
        "ja": "フォルダが見つかりません。",
        "zh-CN": "未找到文件夹。",
        "ko": "폴더를 찾을 수 없습니다.",
        "es": "Carpeta no encontrada.",
        "fr": "Dossier introuvable.",
        "de": "Ordner nicht gefunden.",
        "pt-BR": "Pasta não encontrada.",
    },
    "data.browse.connector_pull": {
        "en": "🔄 Preview pull (10 items max)",
        "ja": "🔄 プレビュー pull (最大 10 件)",
        "zh-CN": "🔄 预览 pull (最多 10 项)",
        "ko": "🔄 프리뷰 pull (최대 10 건)",
        "es": "🔄 Vista previa (máx 10)",
        "fr": "🔄 Aperçu pull (max 10)",
        "de": "🔄 Vorschau-Pull (max 10)",
        "pt-BR": "🔄 Pré-visualizar pull (máx 10)",
    },
    "data.injected": {
        "en": "📁 {n} Data scope(s) injected as additional context",
        "ja": "📁 {n} 件のデータ範囲を追加コンテキストとして注入",
        "zh-CN": "📁 已将 {n} 个数据范围作为附加上下文注入",
        "ko": "📁 {n} 개 데이터 범위를 추가 컨텍스트로 주입",
        "es": "📁 Se inyectaron {n} alcance(s) de datos como contexto extra",
        "fr": "📁 {n} portée(s) de données injectée(s) en contexte additionnel",
        "de": "📁 {n} Datenbereich(e) als Zusatzkontext eingespeist",
        "pt-BR": "📁 {n} escopo(s) de dados injetado(s) como contexto extra",
    },
    # ===== Common UI atoms ==================================================
    "common.done": {
        "en": "Done!",
        "ja": "完了!",
        "zh-CN": "完成!",
        "ko": "완료!",
        "es": "¡Listo!",
        "fr": "Terminé !",
        "de": "Fertig!",
        "pt-BR": "Concluído!",
    },
    "common.transcribing": {
        "en": "Transcribing audio…",
        "ja": "音声を文字起こし中…",
        "zh-CN": "正在转写音频…",
        "ko": "오디오 변환 중…",
        "es": "Transcribiendo audio…",
        "fr": "Transcription audio…",
        "de": "Audio wird transkribiert…",
        "pt-BR": "Transcrevendo áudio…",
    },
    "common.transcribed": {
        "en": "🎙 Transcribed: {n:,} chars",
        "ja": "🎙 文字起こし完了: {n:,} 文字",
        "zh-CN": "🎙 转写完成: {n:,} 字符",
        "ko": "🎙 변환 완료: {n:,} 문자",
        "es": "🎙 Transcrito: {n:,} caracteres",
        "fr": "🎙 Transcrit : {n:,} caractères",
        "de": "🎙 Transkribiert: {n:,} Zeichen",
        "pt-BR": "🎙 Transcrito: {n:,} caracteres",
    },
    # ===== Flow mode ========================================================
    "flow.h": {
        "en": "🎬 Run a multi-agent flow",
        "ja": "🎬 マルチエージェントフローを実行",
        "zh-CN": "🎬 运行多智能体流程",
        "ko": "🎬 멀티에이전트 플로우 실행",
        "es": "🎬 Ejecutar flujo multi-agente",
        "fr": "🎬 Lancer un flux multi-agents",
        "de": "🎬 Multi-Agenten-Flow ausführen",
        "pt-BR": "🎬 Executar fluxo multi-agente",
    },
    "flow.pick": {
        "en": "Choose a flow",
        "ja": "Flow を選択",
        "zh-CN": "选择流程",
        "ko": "플로우 선택",
        "es": "Elegir flujo",
        "fr": "Choisir un flux",
        "de": "Flow wählen",
        "pt-BR": "Escolher fluxo",
    },
    "flow.run_btn": {
        "en": "▶ Run",
        "ja": "▶ 実行",
        "zh-CN": "▶ 运行",
        "ko": "▶ 실행",
        "es": "▶ Ejecutar",
        "fr": "▶ Exécuter",
        "de": "▶ Ausführen",
        "pt-BR": "▶ Executar",
    },
    "flow.steps_h": {
        "en": "🔍 Per-step output",
        "ja": "🔍 各ステップの出力",
        "zh-CN": "🔍 每步输出",
        "ko": "🔍 단계별 출력",
        "es": "🔍 Salida por paso",
        "fr": "🔍 Sortie par étape",
        "de": "🔍 Ausgabe pro Schritt",
        "pt-BR": "🔍 Saída por etapa",
    },
    "flow.input_method": {
        "en": "Input method",
        "ja": "入力方法",
        "zh-CN": "输入方式",
        "ko": "입력 방식",
        "es": "Método de entrada",
        "fr": "Méthode d'entrée",
        "de": "Eingabemethode",
        "pt-BR": "Método de entrada",
    },
    "flow.input_method.text": {
        "en": "📋 Paste text",
        "ja": "📋 テキスト貼り付け",
        "zh-CN": "📋 粘贴文本",
        "ko": "📋 텍스트 붙여넣기",
        "es": "📋 Pegar texto",
        "fr": "📋 Coller texte",
        "de": "📋 Text einfügen",
        "pt-BR": "📋 Colar texto",
    },
    "flow.input_method.file": {
        "en": "📎 Upload file",
        "ja": "📎 ファイルアップロード",
        "zh-CN": "📎 上传文件",
        "ko": "📎 파일 업로드",
        "es": "📎 Subir archivo",
        "fr": "📎 Téléverser un fichier",
        "de": "📎 Datei hochladen",
        "pt-BR": "📎 Enviar arquivo",
    },
    "flow.input_method.voice": {
        "en": "🎙 Voice input",
        "ja": "🎙 音声入力",
        "zh-CN": "🎙 语音输入",
        "ko": "🎙 음성 입력",
        "es": "🎙 Entrada por voz",
        "fr": "🎙 Entrée vocale",
        "de": "🎙 Spracheingabe",
        "pt-BR": "🎙 Entrada por voz",
    },
    "flow.sales.customer_name": {
        "en": "Customer name",
        "ja": "顧客名",
        "zh-CN": "客户名称",
        "ko": "고객명",
        "es": "Nombre del cliente",
        "fr": "Nom du client",
        "de": "Kundenname",
        "pt-BR": "Nome do cliente",
    },
    "flow.sales.product": {
        "en": "Our product",
        "ja": "自社製品",
        "zh-CN": "我方产品",
        "ko": "자사 제품",
        "es": "Nuestro producto",
        "fr": "Notre produit",
        "de": "Unser Produkt",
        "pt-BR": "Nosso produto",
    },
    "flow.sales.context": {
        "en": "Additional context (optional)",
        "ja": "追加コンテキスト (任意)",
        "zh-CN": "附加上下文(可选)",
        "ko": "추가 컨텍스트 (선택)",
        "es": "Contexto adicional (opcional)",
        "fr": "Contexte additionnel (optionnel)",
        "de": "Zusätzlicher Kontext (optional)",
        "pt-BR": "Contexto adicional (opcional)",
    },
    "flow.sales.files": {
        "en": "📎 Supporting files (optional): IR / press / minutes — formats: {exts}",
        "ja": "📎 補助資料 (任意): IR / プレス / 議事録 などをアップロード · 対応形式: {exts}",
        "zh-CN": "📎 辅助文件(可选): IR / 新闻 / 纪要 — 支持: {exts}",
        "ko": "📎 보조 자료 (선택): IR / 보도 / 회의록 — 지원: {exts}",
        "es": "📎 Archivos de apoyo (opcional): IR / prensa / actas — formatos: {exts}",
        "fr": "📎 Fichiers complémentaires (optionnel) : IR / presse / comptes-rendus — formats : {exts}",
        "de": "📎 Hilfsdateien (optional): IR / Presse / Protokolle — Formate: {exts}",
        "pt-BR": "📎 Arquivos de apoio (opcional): IR / press / atas — formatos: {exts}",
    },
    "flow.sales.attached": {
        "en": "📎 Attached and parsed {n} file(s)",
        "ja": "📎 {n} 件のファイルを添付・解析しました",
        "zh-CN": "📎 已附加并解析 {n} 个文件",
        "ko": "📎 {n} 개 파일 첨부·파싱 완료",
        "es": "📎 Adjuntados y parseados {n} archivo(s)",
        "fr": "📎 {n} fichier(s) joint(s) et analysé(s)",
        "de": "📎 {n} Datei(en) angehängt und geparst",
        "pt-BR": "📎 {n} arquivo(s) anexado(s) e parseado(s)",
    },
    "flow.logic.file": {
        "en": "📎 Document to review — formats: {exts}",
        "ja": "📎 レビュー対象ファイル · 対応形式: {exts}",
        "zh-CN": "📎 待审查文件 — 支持: {exts}",
        "ko": "📎 검토 대상 파일 — 지원: {exts}",
        "es": "📎 Documento a revisar — formatos: {exts}",
        "fr": "📎 Document à relire — formats : {exts}",
        "de": "📎 Zu prüfendes Dokument — Formate: {exts}",
        "pt-BR": "📎 Documento a revisar — formatos: {exts}",
    },
    "flow.logic.audio_record": {
        "en": "Record from microphone (browser permission required)",
        "ja": "マイクから録音 (ブラウザ許可必須)",
        "zh-CN": "用麦克风录音(需浏览器权限)",
        "ko": "마이크로 녹음 (브라우저 권한 필요)",
        "es": "Grabar desde micrófono (permiso del navegador)",
        "fr": "Enregistrer depuis le micro (permission du navigateur)",
        "de": "Mikrofon-Aufnahme (Browser-Erlaubnis nötig)",
        "pt-BR": "Gravar do microfone (permissão do navegador)",
    },
    "flow.logic.text_input": {
        "en": "Document to review",
        "ja": "レビュー対象の文書",
        "zh-CN": "待审查文档",
        "ko": "검토 대상 문서",
        "es": "Documento a revisar",
        "fr": "Document à relire",
        "de": "Zu prüfendes Dokument",
        "pt-BR": "Documento a revisar",
    },
    "flow.rag.question": {
        "en": "Question",
        "ja": "質問",
        "zh-CN": "问题",
        "ko": "질문",
        "es": "Pregunta",
        "fr": "Question",
        "de": "Frage",
        "pt-BR": "Pergunta",
    },
    "flow.rag.retriever_note": {
        "en": "Retriever uses your personal memory (`PersonalMemory.search`). To use a different retriever, swap via the SDK with `flow.run(retriever=...)`.",
        "ja": "リトリーバは個人メモリ (`PersonalMemory.search`) を使用します。他のリトリーバを使う場合は SDK の `flow.run(retriever=...)` で差し替えてください。",
        "zh-CN": "检索器使用你的个人记忆 (`PersonalMemory.search`)。如需其他检索器,通过 SDK 的 `flow.run(retriever=...)` 替换。",
        "ko": "리트리버는 개인 메모리 (`PersonalMemory.search`) 를 사용합니다. 다른 리트리버를 사용하려면 SDK 의 `flow.run(retriever=...)` 로 교체하세요.",
        "es": "El retriever usa tu memoria personal (`PersonalMemory.search`). Para otro retriever, cambia vía SDK con `flow.run(retriever=...)`.",
        "fr": "Le retriever utilise votre mémoire personnelle (`PersonalMemory.search`). Pour un autre retriever, utilisez `flow.run(retriever=...)` via le SDK.",
        "de": "Retriever nutzt deinen persönlichen Speicher (`PersonalMemory.search`). Für einen anderen Retriever via SDK mit `flow.run(retriever=...)` tauschen.",
        "pt-BR": "O retriever usa sua memória pessoal (`PersonalMemory.search`). Para outro retriever, troque via SDK com `flow.run(retriever=...)`.",
    },
    # ===== Skill mode =======================================================
    "skill.h": {
        "en": "🛠 Run a business skill",
        "ja": "🛠 ビジネススキルを実行",
        "zh-CN": "🛠 运行业务技能",
        "ko": "🛠 비즈니스 스킬 실행",
        "es": "🛠 Ejecutar habilidad de negocio",
        "fr": "🛠 Lancer une compétence métier",
        "de": "🛠 Business-Skill ausführen",
        "pt-BR": "🛠 Executar habilidade de negócio",
    },
    "skill.pick": {
        "en": "Choose a skill",
        "ja": "スキルを選択",
        "zh-CN": "选择技能",
        "ko": "스킬 선택",
        "es": "Elegir habilidad",
        "fr": "Choisir une compétence",
        "de": "Skill wählen",
        "pt-BR": "Escolher habilidade",
    },
    "skill.input_method.text": {
        "en": "Text",
        "ja": "テキスト",
        "zh-CN": "文本",
        "ko": "텍스트",
        "es": "Texto",
        "fr": "Texte",
        "de": "Text",
        "pt-BR": "Texto",
    },
    "skill.input_method.file": {
        "en": "📎 Attach file (combinable)",
        "ja": "📎 ファイル添付 (組合せ可)",
        "zh-CN": "📎 附加文件(可组合)",
        "ko": "📎 파일 첨부 (조합 가능)",
        "es": "📎 Adjuntar archivo (combinable)",
        "fr": "📎 Joindre un fichier (combinable)",
        "de": "📎 Datei anhängen (kombinierbar)",
        "pt-BR": "📎 Anexar arquivo (combinável)",
    },
    "skill.input": {
        "en": "Input",
        "ja": "入力",
        "zh-CN": "输入",
        "ko": "입력",
        "es": "Entrada",
        "fr": "Entrée",
        "de": "Eingabe",
        "pt-BR": "Entrada",
    },
    "skill.input_placeholder": {
        "en": "Describe what you want the agent to do",
        "ja": "エージェントへの依頼内容を記入",
        "zh-CN": "描述你希望代理做什么",
        "ko": "에이전트에게 시킬 내용을 입력",
        "es": "Describe qué quieres que haga el agente",
        "fr": "Décrivez ce que l'agent doit faire",
        "de": "Beschreibe, was der Agent tun soll",
        "pt-BR": "Descreva o que o agente deve fazer",
    },
    "skill.attach_label": {
        "en": "📎 Attach files: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — supported: {exts}",
        "ja": "📎 ファイル添付: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML 等 · 対応: {exts}",
        "zh-CN": "📎 附加文件: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML 等 — 支持: {exts}",
        "ko": "📎 파일 첨부: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — 지원: {exts}",
        "es": "📎 Adjuntar archivos: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — soportados: {exts}",
        "fr": "📎 Joindre fichiers : PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — supportés : {exts}",
        "de": "📎 Dateien anhängen: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — unterstützt: {exts}",
        "pt-BR": "📎 Anexar arquivos: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML — suportados: {exts}",
    },
    "skill.audio_record": {
        "en": "Record from microphone",
        "ja": "マイクから録音",
        "zh-CN": "用麦克风录音",
        "ko": "마이크로 녹음",
        "es": "Grabar desde micrófono",
        "fr": "Enregistrer depuis le micro",
        "de": "Mikrofon-Aufnahme",
        "pt-BR": "Gravar do microfone",
    },
    "skill.audio_edit": {
        "en": "Transcribed text (editable)",
        "ja": "文字起こし結果 (編集可)",
        "zh-CN": "转写结果(可编辑)",
        "ko": "변환 결과 (편집 가능)",
        "es": "Texto transcrito (editable)",
        "fr": "Texte transcrit (modifiable)",
        "de": "Transkription (editierbar)",
        "pt-BR": "Texto transcrito (editável)",
    },
    "skill.tts_toggle": {
        "en": "🔊 Read output aloud (optional)",
        "ja": "🔊 出力を音声で読み上げ (任意)",
        "zh-CN": "🔊 朗读输出(可选)",
        "ko": "🔊 출력을 음성으로 읽기 (선택)",
        "es": "🔊 Leer salida en voz alta (opcional)",
        "fr": "🔊 Lire la sortie à voix haute (optionnel)",
        "de": "🔊 Ausgabe vorlesen (optional)",
        "pt-BR": "🔊 Ler saída em voz alta (opcional)",
    },
    "skill.tts_synthesizing": {
        "en": "Synthesizing speech…",
        "ja": "音声合成中…",
        "zh-CN": "正在合成语音…",
        "ko": "음성 합성 중…",
        "es": "Sintetizando voz…",
        "fr": "Synthèse vocale…",
        "de": "Sprache wird synthetisiert…",
        "pt-BR": "Sintetizando voz…",
    },
    "skill.use_saved_prompt": {
        "en": "📜 Load from saved prompts (optional)",
        "ja": "📜 保存済プロンプトをロード (任意)",
        "zh-CN": "📜 从已保存提示词加载(可选)",
        "ko": "📜 저장된 프롬프트에서 로드 (선택)",
        "es": "📜 Cargar desde prompts guardados (opcional)",
        "fr": "📜 Charger un prompt enregistré (optionnel)",
        "de": "📜 Aus gespeicherten Prompts laden (optional)",
        "pt-BR": "📜 Carregar de prompts salvos (opcional)",
    },
    "skill.pick_saved_prompt": {
        "en": "Pick a saved prompt",
        "ja": "保存済プロンプトを選択",
        "zh-CN": "选择已保存的提示词",
        "ko": "저장된 프롬프트 선택",
        "es": "Elige un prompt guardado",
        "fr": "Choisir un prompt enregistré",
        "de": "Gespeicherten Prompt wählen",
        "pt-BR": "Escolha um prompt salvo",
    },
    "skill.no_template": {
        "en": "(none — write input from scratch)",
        "ja": "(無し — ゼロから入力)",
        "zh-CN": "(无 — 从头输入)",
        "ko": "(없음 — 처음부터 입력)",
        "es": "(ninguno — escribe desde cero)",
        "fr": "(aucun — écrire de zéro)",
        "de": "(keiner — von Grund auf schreiben)",
        "pt-BR": "(nenhum — escrever do zero)",
    },
    "skill.load_btn": {
        "en": "📥 Load into input",
        "ja": "📥 入力欄にロード",
        "zh-CN": "📥 加载到输入框",
        "ko": "📥 입력란에 로드",
        "es": "📥 Cargar en la entrada",
        "fr": "📥 Charger dans l'entrée",
        "de": "📥 In Eingabe laden",
        "pt-BR": "📥 Carregar na entrada",
    },
    # ===== Memory mode ======================================================
    "memory.h": {
        "en": "🧠 Memory browser",
        "ja": "🧠 メモリブラウザ",
        "zh-CN": "🧠 记忆浏览器",
        "ko": "🧠 메모리 브라우저",
        "es": "🧠 Explorador de memoria",
        "fr": "🧠 Navigateur de mémoire",
        "de": "🧠 Memory-Browser",
        "pt-BR": "🧠 Navegador de memória",
    },
    "memory.personal_h": {
        "en": "Personal memory (Layer 1)",
        "ja": "個人メモリ (Layer 1)",
        "zh-CN": "个人记忆 (Layer 1)",
        "ko": "개인 메모리 (Layer 1)",
        "es": "Memoria personal (Layer 1)",
        "fr": "Mémoire personnelle (Layer 1)",
        "de": "Persönlicher Speicher (Layer 1)",
        "pt-BR": "Memória pessoal (Layer 1)",
    },
    "memory.entries_total": {
        "en": "Total entries",
        "ja": "総エントリ数",
        "zh-CN": "总条目数",
        "ko": "총 엔트리 수",
        "es": "Total de entradas",
        "fr": "Total des entrées",
        "de": "Einträge gesamt",
        "pt-BR": "Total de entradas",
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
    "memory.shared_h": {
        "en": "Shared memory (Layer 3)",
        "ja": "共有メモリ (Layer 3)",
        "zh-CN": "共享记忆 (Layer 3)",
        "ko": "공유 메모리 (Layer 3)",
        "es": "Memoria compartida (Layer 3)",
        "fr": "Mémoire partagée (Layer 3)",
        "de": "Geteilter Speicher (Layer 3)",
        "pt-BR": "Memória compartilhada (Layer 3)",
    },
    "memory.blocks_total": {
        "en": "Block count",
        "ja": "ブロック数",
        "zh-CN": "块数",
        "ko": "블록 수",
        "es": "Cantidad de bloques",
        "fr": "Nombre de blocs",
        "de": "Block-Anzahl",
        "pt-BR": "Total de blocos",
    },
    # ===== Consolidate mode =================================================
    "consolidate.h": {
        "en": "🌙 Sleep-time consolidation",
        "ja": "🌙 Sleep-time Consolidation",
        "zh-CN": "🌙 夜间整合",
        "ko": "🌙 수면 시 통합",
        "es": "🌙 Consolidación nocturna",
        "fr": "🌙 Consolidation nocturne",
        "de": "🌙 Nacht-Konsolidierung",
        "pt-BR": "🌙 Consolidação noturna",
    },
    "consolidate.intro": {
        "en": (
            "**What this does**: scans every user's personal-memory entries and "
            "**automatically promotes** the high-value ones into the org-wide "
            "shared memory layer. Three signals run in parallel:\n\n"
            "- **Frequency** — same pattern repeats across N+ users\n"
            "- **Outcome** — pattern correlated with successful flow runs\n"
            "- **LLM self-eval** — pattern scored highly for re-use value\n\n"
            "Items that pass the threshold get promoted. The rest stay personal.\n\n"
            "**When you'd run this**: typically as a nightly cron job. The button "
            "below is for manual / on-demand runs (e.g. testing, post-onboarding "
            "of a new team member).\n\n"
            "**Dry-run** previews what *would* be promoted without writing — "
            "recommended on first use."
        ),
        "ja": (
            "**何をするか**: 全ユーザの個人メモリをスキャンし、価値の高い項目を "
            "**自動的に** 組織共有メモリへ昇格させます。3 つのシグナルを並列評価:\n\n"
            "- **頻度** — N 人以上のユーザで同じパターンが繰り返される\n"
            "- **アウトカム** — フロー成功に相関するパターン\n"
            "- **LLM 自己評価** — 再利用価値のスコアリング\n\n"
            "閾値を超えた項目だけ昇格、それ以外は個人メモリに留まります。\n\n"
            "**実行タイミング**: 通常は夜間バッチで定期実行。下のボタンは手動・"
            "オンデマンド実行用 (テスト・新メンバー受け入れ後など)。\n\n"
            "**Dry-run** は何が昇格されるかを書込みなしで確認できます — 初回は推奨。"
        ),
        "zh-CN": (
            "**作用**: 扫描所有用户的个人记忆条目,**自动晋升** 高价值条目至组织共享记忆。"
            "3 个信号并行评估: 频次 (N+ 用户重复)、成果(与成功相关)、LLM 自评分。"
            "通过阈值的条目被晋升,其余留在个人。\n\n"
            "通常作为夜间定时任务,下方按钮用于手动 / 按需执行。**Dry-run** 不写入预览。"
        ),
        "ko": (
            "**무엇**: 모든 사용자의 개인 메모리 항목을 스캔하여 가치 있는 항목을 "
            "**자동으로** 조직 공유 메모리로 승격. 3 가지 시그널 병렬 평가: "
            "빈도 (N 명 이상에서 반복) / 성과 (성공과 상관) / LLM 자가 평가. "
            "임계값 통과한 항목만 승격, 나머지는 개인 메모리에 유지.\n\n"
            "보통 야간 배치로 운영. 아래 버튼은 수동 실행. **Dry-run** 은 쓰기 없이 미리보기."
        ),
        "es": (
            "**Qué hace**: escanea las entradas de memoria personal de todos los usuarios "
            "y **promueve automáticamente** las de alto valor a la memoria compartida org. "
            "3 señales en paralelo: frecuencia (repetida en N+ usuarios), outcome "
            "(correlación con éxito), auto-evaluación LLM. Los ítems que superan el "
            "umbral se promueven; el resto se queda personal.\n\n"
            "Típicamente se ejecuta como cron nocturno. El botón es para runs manuales. "
            "**Dry-run** previsualiza sin escribir."
        ),
        "fr": (
            "**Ce que cela fait** : scanne toutes les mémoires personnelles et "
            "**promeut automatiquement** les entrées à forte valeur vers la mémoire "
            "partagée de l'org. 3 signaux en parallèle : fréquence (répétée chez N+ "
            "utilisateurs), résultat (corrélé au succès), auto-éval LLM. Les éléments "
            "au-dessus du seuil sont promus.\n\n"
            "Typiquement lancé en cron nocturne. Le bouton ci-dessous sert aux runs "
            "manuels. **Dry-run** : aperçu sans écriture."
        ),
        "de": (
            "**Was es tut**: scannt die persönlichen Speicher aller Nutzer und "
            "**befördert hochwertige Einträge automatisch** in den geteilten Org-Speicher. "
            "3 Signale parallel: Frequenz (wiederholt sich bei N+ Nutzern), Outcome "
            "(korreliert mit Erfolg), LLM-Selbstbewertung. Einträge über der Schwelle "
            "werden befördert.\n\n"
            "Typisch als nächtlicher Cron-Job. Der Button startet manuell. "
            "**Dry-run**: Vorschau ohne Schreibzugriff."
        ),
        "pt-BR": (
            "**O que faz**: varre as memórias pessoais de todos os usuários e "
            "**promove automaticamente** entradas valiosas para a memória compartilhada "
            "da org. 3 sinais paralelos: frequência (repetido em N+ usuários), outcome "
            "(correlacionado com sucesso), auto-avaliação LLM.\n\n"
            "Tipicamente roda como cron noturno. Botão abaixo: execução manual. "
            "**Dry-run** prévia sem gravar."
        ),
    },
    "consolidate.threshold": {
        "en": "Auto-promote threshold",
        "ja": "Auto-promote 閾値",
        "zh-CN": "自动晋升阈值",
        "ko": "자동 승격 임계값",
        "es": "Umbral de auto-promoción",
        "fr": "Seuil d'auto-promotion",
        "de": "Auto-Promote-Schwelle",
        "pt-BR": "Limite de auto-promoção",
    },
    "consolidate.dry_run": {
        "en": "Dry run (preview only — no writes)",
        "ja": "Dry run (実際の書き込みはしない)",
        "zh-CN": "Dry run(仅预览,不写入)",
        "ko": "Dry run (미리보기만, 쓰기 없음)",
        "es": "Dry run (solo vista previa — sin escribir)",
        "fr": "Dry run (aperçu uniquement — pas d'écriture)",
        "de": "Dry-Run (nur Vorschau — keine Schreibzugriffe)",
        "pt-BR": "Dry run (apenas pré-visualização — sem escritas)",
    },
    "consolidate.run": {
        "en": "🌙 Consolidate",
        "ja": "🌙 Consolidate",
        "zh-CN": "🌙 整合",
        "ko": "🌙 통합",
        "es": "🌙 Consolidar",
        "fr": "🌙 Consolider",
        "de": "🌙 Konsolidieren",
        "pt-BR": "🌙 Consolidar",
    },
    # ===== Dashboard mode ===================================================
    "dashboard.h": {
        "en": "📊 Dashboard",
        "ja": "📊 ダッシュボード",
        "zh-CN": "📊 仪表板",
        "ko": "📊 대시보드",
        "es": "📊 Panel",
        "fr": "📊 Tableau de bord",
        "de": "📊 Dashboard",
        "pt-BR": "📊 Painel",
    },
    # ===== Prompts mode =====================================================
    "prompts.h": {
        "en": "📝 Custom prompts",
        "ja": "📝 カスタムプロンプト",
        "zh-CN": "📝 自定义提示词",
        "ko": "📝 커스텀 프롬프트",
        "es": "📝 Prompts personalizados",
        "fr": "📝 Prompts personnalisés",
        "de": "📝 Benutzerdefinierte Prompts",
        "pt-BR": "📝 Prompts personalizados",
    },
    "prompts.intro": {
        "en": "Generate a polished prompt template from a 1-line task, browse / edit / delete your saved prompts, or distribute curated prompts to your team.",
        "ja": "1 行の指示からプロンプトテンプレートを自動生成、保存済プロンプトの閲覧・編集・削除、またはチームへの配布。",
        "zh-CN": "从一行任务生成精炼的提示模板,浏览/编辑/删除保存的提示词,或向团队分发已审核的提示。",
        "ko": "1 줄 작업으로 프롬프트 템플릿 생성, 저장된 프롬프트 열람·편집·삭제, 또는 팀에 배포.",
        "es": "Genera una plantilla de prompt a partir de una tarea de 1 línea, navega/edita/elimina tus prompts guardados o distribúyelos al equipo.",
        "fr": "Générez un template de prompt à partir d'une tâche d'une ligne, parcourez/modifiez/supprimez vos prompts ou distribuez-les à l'équipe.",
        "de": "Erzeuge eine Prompt-Vorlage aus einer einzeiligen Aufgabe, durchstöbere/bearbeite/lösche gespeicherte Prompts oder verteile kuratierte Prompts ans Team.",
        "pt-BR": "Gere um template de prompt a partir de uma tarefa de 1 linha, navegue/edite/exclua prompts salvos ou distribua ao time.",
    },
    "prompts.tab.generate": {
        "en": "✨ Generate (PromptDesigner)",
        "ja": "✨ 生成 (PromptDesigner)",
        "zh-CN": "✨ 生成 (PromptDesigner)",
        "ko": "✨ 생성 (PromptDesigner)",
        "es": "✨ Generar (PromptDesigner)",
        "fr": "✨ Générer (PromptDesigner)",
        "de": "✨ Generieren (PromptDesigner)",
        "pt-BR": "✨ Gerar (PromptDesigner)",
    },
    "prompts.tab.browse": {
        "en": "📚 Browse & edit",
        "ja": "📚 一覧・編集",
        "zh-CN": "📚 浏览与编辑",
        "ko": "📚 목록·편집",
        "es": "📚 Explorar y editar",
        "fr": "📚 Parcourir et éditer",
        "de": "📚 Durchsuchen & Bearbeiten",
        "pt-BR": "📚 Explorar e editar",
    },
    "prompts.tab.distribute": {
        "en": "📤 Distribute (admin)",
        "ja": "📤 配信 (管理者)",
        "zh-CN": "📤 分发 (管理员)",
        "ko": "📤 배포 (관리자)",
        "es": "📤 Distribuir (admin)",
        "fr": "📤 Distribuer (admin)",
        "de": "📤 Verteilen (Admin)",
        "pt-BR": "📤 Distribuir (admin)",
    },
    # ----- Generate (PromptDesigner) -----
    "prompts.generate.intro": {
        "en": "Describe your task in 1 line — get a production-grade prompt template back: tuned system message, `${variable}` user template, 2-3 few-shot examples, 5-criterion eval rubric. Per-LLM idioms applied automatically.",
        "ja": "やりたいことを 1 行で書くだけで、本番品質のプロンプト設計が返ってきます — チューニング済 system メッセージ、`${variable}` 入り user テンプレート、Few-Shot 例 2〜3 件、5 観点の評価ルーブリック付き。LLM ごとの作法を自動適用。",
        "zh-CN": "用一行描述任务,即可获得生产级提示模板: 调优 system 消息、含 `${variable}` 的 user 模板、2-3 个 few-shot 示例、5 项评估标准。自动适用 LLM 特定写法。",
        "ko": "한 줄로 작업을 설명하면 프로덕션 품질의 프롬프트 템플릿을 받습니다: 튜닝된 system 메시지, `${variable}` 포함 user 템플릿, Few-Shot 예시 2-3 개, 5 기준 루브릭. LLM 별 관용구 자동 적용.",
        "es": "Describe tu tarea en 1 línea: recibirás un template de prompt de producción — system ajustado, plantilla user con `${variable}`, 2-3 few-shot, rúbrica de 5 criterios. Idiomas por LLM aplicados automáticamente.",
        "fr": "Décrivez votre tâche en 1 ligne — recevez un template de prompt prêt prod : system affûté, template user avec `${variable}`, 2-3 few-shot, rubrique à 5 critères. Idiomes par LLM appliqués auto.",
        "de": "Beschreibe deine Aufgabe in 1 Zeile — erhalte ein produktionsreifes Prompt-Template: getuneter System-Prompt, User-Template mit `${variable}`, 2-3 Few-Shot, 5-Kriterien-Rubrik. LLM-Idiome automatisch angewendet.",
        "pt-BR": "Descreva sua tarefa em 1 linha — receba um template de prompt pronto: system ajustado, template user com `${variable}`, 2-3 few-shot, rubrica de 5 critérios. Idiomas por LLM aplicados automaticamente.",
    },
    "prompts.generate.task_label": {
        "en": "Task description",
        "ja": "タスク内容",
        "zh-CN": "任务描述",
        "ko": "작업 설명",
        "es": "Descripción de la tarea",
        "fr": "Description de la tâche",
        "de": "Aufgabenbeschreibung",
        "pt-BR": "Descrição da tarefa",
    },
    "prompts.generate.task_placeholder": {
        "en": "e.g. score contract risk 1-5 in JSON",
        "ja": "例: 契約書のリスクを 1〜5 段階で JSON 評価",
        "zh-CN": "例: 以 JSON 评 1-5 级合同风险",
        "ko": "예: 계약서 리스크를 1-5 로 JSON 평가",
        "es": "p. ej. valorar riesgo de contrato 1-5 en JSON",
        "fr": "ex. noter le risque du contrat 1-5 en JSON",
        "de": "z. B. Vertragsrisiko 1-5 als JSON bewerten",
        "pt-BR": "ex. avaliar risco do contrato 1-5 em JSON",
    },
    "prompts.generate.target_llm": {
        "en": "Target LLM family",
        "ja": "対象 LLM ファミリ",
        "zh-CN": "目标 LLM 家族",
        "ko": "대상 LLM 패밀리",
        "es": "Familia LLM objetivo",
        "fr": "Famille LLM cible",
        "de": "Ziel-LLM-Familie",
        "pt-BR": "Família LLM alvo",
    },
    "prompts.generate.target_llm_auto": {
        "en": "(auto — use current LLM)",
        "ja": "(自動 — 現在の LLM を使用)",
        "zh-CN": "(自动 — 使用当前 LLM)",
        "ko": "(자동 — 현재 LLM 사용)",
        "es": "(auto — usar LLM actual)",
        "fr": "(auto — utiliser le LLM actuel)",
        "de": "(auto — aktuelles LLM)",
        "pt-BR": "(auto — usar LLM atual)",
    },
    "prompts.generate.output_format": {
        "en": "Expected output format",
        "ja": "出力形式",
        "zh-CN": "期望输出格式",
        "ko": "출력 형식",
        "es": "Formato de salida",
        "fr": "Format de sortie",
        "de": "Ausgabeformat",
        "pt-BR": "Formato de saída",
    },
    "prompts.generate.include_examples": {
        "en": "Include 2-3 few-shot examples",
        "ja": "Few-shot 例 2〜3 件を含める",
        "zh-CN": "包含 2-3 个 few-shot 示例",
        "ko": "Few-shot 예시 2-3 개 포함",
        "es": "Incluir 2-3 ejemplos few-shot",
        "fr": "Inclure 2-3 exemples few-shot",
        "de": "2-3 Few-Shot-Beispiele einschließen",
        "pt-BR": "Incluir 2-3 exemplos few-shot",
    },
    "prompts.generate.constraint": {
        "en": "Constraint level",
        "ja": "制約レベル",
        "zh-CN": "约束级别",
        "ko": "제약 수준",
        "es": "Nivel de restricción",
        "fr": "Niveau de contrainte",
        "de": "Constraint-Level",
        "pt-BR": "Nível de restrição",
    },
    "prompts.generate.btn": {
        "en": "✨ Generate template",
        "ja": "✨ テンプレート生成",
        "zh-CN": "✨ 生成模板",
        "ko": "✨ 템플릿 생성",
        "es": "✨ Generar template",
        "fr": "✨ Générer le template",
        "de": "✨ Template erzeugen",
        "pt-BR": "✨ Gerar template",
    },
    "prompts.generate.task_required": {
        "en": "Task description is required.",
        "ja": "タスク内容は必須です。",
        "zh-CN": "需要任务描述。",
        "ko": "작업 설명이 필요합니다.",
        "es": "Se requiere descripción de tarea.",
        "fr": "Description de la tâche requise.",
        "de": "Aufgabenbeschreibung erforderlich.",
        "pt-BR": "Descrição da tarefa é obrigatória.",
    },
    "prompts.generate.designing": {
        "en": "Designing prompt template…",
        "ja": "プロンプト設計中…",
        "zh-CN": "设计提示模板中…",
        "ko": "프롬프트 템플릿 설계 중…",
        "es": "Diseñando plantilla…",
        "fr": "Création du template…",
        "de": "Erzeuge Template…",
        "pt-BR": "Projetando template…",
    },
    "prompts.generate.save_h": {
        "en": "💾 Save to your prompt library",
        "ja": "💾 プロンプトライブラリに保存",
        "zh-CN": "💾 保存到你的提示词库",
        "ko": "💾 프롬프트 라이브러리에 저장",
        "es": "💾 Guardar en tu biblioteca de prompts",
        "fr": "💾 Enregistrer dans la bibliothèque",
        "de": "💾 In Prompt-Bibliothek speichern",
        "pt-BR": "💾 Salvar na biblioteca de prompts",
    },
    "prompts.generate.save_name": {
        "en": "Name",
        "ja": "名前",
        "zh-CN": "名称",
        "ko": "이름",
        "es": "Nombre",
        "fr": "Nom",
        "de": "Name",
        "pt-BR": "Nome",
    },
    "prompts.generate.save_desc": {
        "en": "Description",
        "ja": "説明",
        "zh-CN": "描述",
        "ko": "설명",
        "es": "Descripción",
        "fr": "Description",
        "de": "Beschreibung",
        "pt-BR": "Descrição",
    },
    "prompts.generate.save_btn": {
        "en": "💾 Save to library",
        "ja": "💾 ライブラリに保存",
        "zh-CN": "💾 保存到库",
        "ko": "💾 라이브러리에 저장",
        "es": "💾 Guardar en biblioteca",
        "fr": "💾 Enregistrer",
        "de": "💾 Speichern",
        "pt-BR": "💾 Salvar",
    },
    "prompts.generate.discard_btn": {
        "en": "Discard",
        "ja": "破棄",
        "zh-CN": "丢弃",
        "ko": "버리기",
        "es": "Descartar",
        "fr": "Abandonner",
        "de": "Verwerfen",
        "pt-BR": "Descartar",
    },
    "prompts.generate.saved": {
        "en": "✅ Saved as '{name}'",
        "ja": "✅ '{name}' として保存しました",
        "zh-CN": "✅ 已保存为「{name}」",
        "ko": "✅ '{name}' 으로 저장됨",
        "es": "✅ Guardado como '{name}'",
        "fr": "✅ Enregistré sous « {name} »",
        "de": "✅ Als '{name}' gespeichert",
        "pt-BR": "✅ Salvo como '{name}'",
    },
    # ----- Browse & edit -----
    "prompts.browse.empty": {
        "en": "No prompts yet. Use the **Generate** tab to create one, or the **Create new prompt** form below to write one manually.",
        "ja": "プロンプト未登録。**生成** タブで作成、または下の **新規作成** フォームで手書き登録できます。",
        "zh-CN": "暂无提示词。使用 **生成** 标签创建,或下方 **新建** 表单手动编写。",
        "ko": "프롬프트 없음. **생성** 탭에서 만들거나 아래 **새 프롬프트** 폼에서 수동 작성하세요.",
        "es": "Sin prompts. Usa la pestaña **Generar** o el formulario **Nuevo prompt** de abajo.",
        "fr": "Aucun prompt. Utilisez l'onglet **Générer** ou le formulaire **Nouveau** ci-dessous.",
        "de": "Noch keine Prompts. Nutze den **Generieren**-Tab oder das **Neu**-Formular unten.",
        "pt-BR": "Sem prompts. Use a aba **Gerar** ou o formulário **Novo prompt** abaixo.",
    },
    "prompts.edit.body_label": {
        "en": "Prompt body",
        "ja": "プロンプト本文",
        "zh-CN": "提示词正文",
        "ko": "프롬프트 본문",
        "es": "Cuerpo del prompt",
        "fr": "Corps du prompt",
        "de": "Prompt-Inhalt",
        "pt-BR": "Corpo do prompt",
    },
    "prompts.edit.desc_label": {
        "en": "Description",
        "ja": "説明",
        "zh-CN": "描述",
        "ko": "설명",
        "es": "Descripción",
        "fr": "Description",
        "de": "Beschreibung",
        "pt-BR": "Descrição",
    },
    "prompts.edit.tags_label": {
        "en": "Tags (comma-separated)",
        "ja": "タグ (カンマ区切り)",
        "zh-CN": "标签(逗号分隔)",
        "ko": "태그 (쉼표 구분)",
        "es": "Etiquetas (separadas por coma)",
        "fr": "Tags (séparés par virgule)",
        "de": "Tags (kommagetrennt)",
        "pt-BR": "Tags (separadas por vírgula)",
    },
    "prompts.edit.save_btn": {
        "en": "💾 Save changes",
        "ja": "💾 変更を保存",
        "zh-CN": "💾 保存更改",
        "ko": "💾 변경 저장",
        "es": "💾 Guardar cambios",
        "fr": "💾 Enregistrer",
        "de": "💾 Änderungen speichern",
        "pt-BR": "💾 Salvar alterações",
    },
    "prompts.edit.delete_btn": {
        "en": "🗑 Delete prompt",
        "ja": "🗑 プロンプト削除",
        "zh-CN": "🗑 删除提示词",
        "ko": "🗑 프롬프트 삭제",
        "es": "🗑 Eliminar prompt",
        "fr": "🗑 Supprimer le prompt",
        "de": "🗑 Prompt löschen",
        "pt-BR": "🗑 Excluir prompt",
    },
    "prompts.edit.saved": {
        "en": "✅ Saved",
        "ja": "✅ 保存しました",
        "zh-CN": "✅ 已保存",
        "ko": "✅ 저장됨",
        "es": "✅ Guardado",
        "fr": "✅ Enregistré",
        "de": "✅ Gespeichert",
        "pt-BR": "✅ Salvo",
    },
    "prompts.edit.deleted": {
        "en": "🗑 Deleted",
        "ja": "🗑 削除しました",
        "zh-CN": "🗑 已删除",
        "ko": "🗑 삭제됨",
        "es": "🗑 Eliminado",
        "fr": "🗑 Supprimé",
        "de": "🗑 Gelöscht",
        "pt-BR": "🗑 Excluído",
    },
    "prompts.edit.readonly_hint": {
        "en": "Read-only — `{scope}` scope can't be edited from this view.",
        "ja": "読み取り専用 — `{scope}` スコープはこの画面から編集できません。",
        "zh-CN": "只读 — 此视图无法编辑 `{scope}` 范围。",
        "ko": "읽기 전용 — 이 뷰에서 `{scope}` 범위는 편집 불가.",
        "es": "Solo lectura — el ámbito `{scope}` no se edita aquí.",
        "fr": "Lecture seule — le scope `{scope}` n'est pas éditable ici.",
        "de": "Nur lesen — `{scope}`-Scope hier nicht editierbar.",
        "pt-BR": "Somente leitura — escopo `{scope}` não é editável aqui.",
    },
    # ----- Create new prompt -----
    "prompts.create.h": {
        "en": "✏️ Create a new prompt manually",
        "ja": "✏️ 新規プロンプト手動作成",
        "zh-CN": "✏️ 手动新建提示词",
        "ko": "✏️ 새 프롬프트 수동 생성",
        "es": "✏️ Crear nuevo prompt manualmente",
        "fr": "✏️ Créer un nouveau prompt manuellement",
        "de": "✏️ Neuen Prompt manuell erstellen",
        "pt-BR": "✏️ Criar novo prompt manualmente",
    },
    "prompts.create.name": {
        "en": "Name",
        "ja": "名前",
        "zh-CN": "名称",
        "ko": "이름",
        "es": "Nombre",
        "fr": "Nom",
        "de": "Name",
        "pt-BR": "Nome",
    },
    "prompts.create.desc": {
        "en": "Description",
        "ja": "説明",
        "zh-CN": "描述",
        "ko": "설명",
        "es": "Descripción",
        "fr": "Description",
        "de": "Beschreibung",
        "pt-BR": "Descrição",
    },
    "prompts.create.tags": {
        "en": "Tags (comma-separated)",
        "ja": "タグ (カンマ区切り)",
        "zh-CN": "标签(逗号分隔)",
        "ko": "태그 (쉼표 구분)",
        "es": "Etiquetas (separadas por coma)",
        "fr": "Tags (séparés par virgule)",
        "de": "Tags (kommagetrennt)",
        "pt-BR": "Tags (separadas por vírgula)",
    },
    "prompts.create.body": {
        "en": "Prompt body",
        "ja": "プロンプト本文",
        "zh-CN": "提示词正文",
        "ko": "프롬프트 본문",
        "es": "Cuerpo del prompt",
        "fr": "Corps du prompt",
        "de": "Prompt-Inhalt",
        "pt-BR": "Corpo do prompt",
    },
    "prompts.create.btn": {
        "en": "Create",
        "ja": "作成",
        "zh-CN": "创建",
        "ko": "생성",
        "es": "Crear",
        "fr": "Créer",
        "de": "Erstellen",
        "pt-BR": "Criar",
    },
    "prompts.create.required": {
        "en": "Name and body are required.",
        "ja": "名前と本文は必須です。",
        "zh-CN": "需要名称与正文。",
        "ko": "이름과 본문이 필요합니다.",
        "es": "Se requieren nombre y cuerpo.",
        "fr": "Nom et corps requis.",
        "de": "Name und Inhalt erforderlich.",
        "pt-BR": "Nome e corpo são obrigatórios.",
    },
    "prompts.create.saved": {
        "en": "✅ Created '{name}'",
        "ja": "✅ '{name}' を作成しました",
        "zh-CN": "✅ 已创建「{name}」",
        "ko": "✅ '{name}' 생성됨",
        "es": "✅ Creado '{name}'",
        "fr": "✅ « {name} » créé",
        "de": "✅ '{name}' erstellt",
        "pt-BR": "✅ '{name}' criado",
    },
    # ----- Distribute -----
    "prompts.distribute.intro": {
        "en": "**Admin only.** Push a curated prompt to specific users or roles.",
        "ja": "**管理者のみ。** 厳選プロンプトを特定ユーザまたはロールに配信。",
        "zh-CN": "**仅管理员。** 将精选提示推送给特定用户或角色。",
        "ko": "**관리자 전용.** 선별된 프롬프트를 특정 사용자/역할에 배포.",
        "es": "**Solo admin.** Empuja un prompt curado a usuarios o roles específicos.",
        "fr": "**Admin uniquement.** Pousse un prompt soigné vers des utilisateurs / rôles.",
        "de": "**Nur Admin.** Ausgewählten Prompt an Nutzer/Rollen verteilen.",
        "pt-BR": "**Apenas admin.** Envia um prompt curado para usuários/papéis.",
    },
    "prompts.distribute.role_required": {
        "en": "🚫 Distribute is admin-only. **{user}** has role `{role}` and can't push prompts to other users.",
        "ja": "🚫 配信は admin のみ。**{user}** のロールは `{role}` のため他ユーザへの配信不可。",
        "zh-CN": "🚫 分发仅 admin 可用。**{user}** 角色为 `{role}`,无法向其他用户分发。",
        "ko": "🚫 배포는 admin 만 가능. **{user}** 역할 `{role}` 이므로 다른 사용자에게 배포 불가.",
        "es": "🚫 La distribución es solo admin. **{user}** con rol `{role}` no puede distribuir.",
        "fr": "🚫 Distribution admin uniquement. **{user}** (rôle `{role}`) ne peut pas distribuer.",
        "de": "🚫 Verteilen nur für admin. **{user}** mit Rolle `{role}` darf nicht verteilen.",
        "pt-BR": "🚫 Distribuir apenas admin. **{user}** com papel `{role}` não pode distribuir.",
    },
    "prompts.distribute.target_users": {
        "en": "Target user IDs (comma-separated)",
        "ja": "対象ユーザ ID (カンマ区切り)",
        "zh-CN": "目标用户 ID(逗号分隔)",
        "ko": "대상 사용자 ID (쉼표 구분)",
        "es": "IDs de usuarios objetivo (coma)",
        "fr": "ID utilisateurs cibles (virgule)",
        "de": "Ziel-User-IDs (kommagetrennt)",
        "pt-BR": "IDs de usuários alvo (vírgula)",
    },
    "prompts.distribute.target_roles": {
        "en": "Target roles",
        "ja": "対象ロール",
        "zh-CN": "目标角色",
        "ko": "대상 역할",
        "es": "Roles objetivo",
        "fr": "Rôles cibles",
        "de": "Zielrollen",
        "pt-BR": "Papéis alvo",
    },
    "prompts.distribute.btn": {
        "en": "📤 Distribute",
        "ja": "📤 配信",
        "zh-CN": "📤 分发",
        "ko": "📤 배포",
        "es": "📤 Distribuir",
        "fr": "📤 Distribuer",
        "de": "📤 Verteilen",
        "pt-BR": "📤 Distribuir",
    },
    "prompts.distribute.saved": {
        "en": "✅ Distributed to {n} target(s)",
        "ja": "✅ {n} 件の対象に配信しました",
        "zh-CN": "✅ 已分发至 {n} 个目标",
        "ko": "✅ {n} 개 대상에 배포됨",
        "es": "✅ Distribuido a {n} objetivos",
        "fr": "✅ Distribué à {n} cibles",
        "de": "✅ An {n} Ziele verteilt",
        "pt-BR": "✅ Distribuído para {n} alvos",
    },
    # ===== About ============================================================
    "about.h": {
        "en": "ℹ About Praxia",
        "ja": "ℹ Praxia について",
        "zh-CN": "ℹ 关于 Praxia",
        "ko": "ℹ Praxia 정보",
        "es": "ℹ Acerca de Praxia",
        "fr": "ℹ À propos de Praxia",
        "de": "ℹ Über Praxia",
        "pt-BR": "ℹ Sobre Praxia",
    },
    "about.body": {
        "en": (
            "**Praxia** is a workflow-specialized multi-agent orchestrator "
            "that **automatically promotes** individual tacit knowledge "
            "into shared organizational know-how, via a **5-layer cyclic "
            "memory stack**.\n\n"
            "#### Supported LLMs (15+ first-class · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / o-series)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq fast / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 100+ more via LiteLLM\n\n"
            "Switch with one-line aliases (`claude` / `gpt-5` / `gemini` / ...) or "
            "`PRAXIA_LOCAL_MODEL=gemma` for air-gapped operation.\n\n"
            "#### Bundled business skills\n"
            "- Investment · Sales · Design · Purchasing · Patent · Legal\n\n"
            "#### LTM backends\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- Parallel fusion (RRF) or per-query routing for ensembles\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | License: Apache 2.0"
        ),
        "ja": (
            "**Praxia** は、業務特化型のマルチエージェント・オーケストレーターです。"
            "個人で利用するだけで暗黙知が自動蓄積され、有効なものだけが組織知へ昇格する"
            "**5層メモリ循環機構**を備えています。\n\n"
            "#### サポート LLM (15+ 標準 · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / o-series)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq fast / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 他、LiteLLM 経由で 100+\n\n"
            "1 行エイリアスで切替 (`claude` / `gpt-5` / `gemini` 等)、もしくは "
            "`PRAXIA_LOCAL_MODEL=gemma` でエアギャップ運用。\n\n"
            "#### 同梱業務スキル\n"
            "- 投資 / 営業 / 設計 / 購買 / 特許 / 法務\n\n"
            "#### LTM バックエンド\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- 並列融合 (RRF) または query-routing で複数併用可\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | License: Apache 2.0"
        ),
        "zh-CN": (
            "**Praxia** 是面向特定工作流的多智能体编排器,通过 **5 层循环记忆栈** "
            "**自动提升** 个人隐性知识为组织共享 know-how。\n\n"
            "#### 支持的 LLM(15+ 一类 · 100+ via LiteLLM)\n"
            "- **Anthropic Claude**(Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT**(GPT-5 / o-series)\n"
            "- **Google Gemini** + **Gemma**(cloud + Ollama)\n"
            "- **Alibaba Qwen**(API + Ollama)\n"
            "- **DeepSeek**(V3 / R1 推理)· **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama**(Groq fast / Ollama)· **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- LiteLLM 还有 100+\n\n"
            "用一行别名切换(`claude` / `gpt-5` / `gemini` / ...),"
            "或 `PRAXIA_LOCAL_MODEL=gemma` 用于气隙环境。\n\n"
            "#### 内置业务技能\n"
            "- 投资 · 销售 · 设计 · 采购 · 专利 · 法务\n\n"
            "#### LTM 后端\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- 并行融合(RRF)或按查询路由,支持组合使用\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | License: Apache 2.0"
        ),
        "ko": (
            "**Praxia** 는 업무 특화 멀티 에이전트 오케스트레이터로, **5 층 순환 "
            "메모리 스택** 을 통해 개인의 암묵지를 조직 공유 노하우로 **자동 승격** 합니다.\n\n"
            "#### 지원 LLM (15+ 기본 · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / o-series)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq fast / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- LiteLLM 으로 100+ 추가\n\n"
            "한 줄 에이리어스로 전환 (`claude` / `gpt-5` / `gemini` / ...) 하거나, "
            "`PRAXIA_LOCAL_MODEL=gemma` 로 에어갭 운영.\n\n"
            "#### 동봉 비즈니스 스킬\n"
            "- 투자 · 영업 · 설계 · 구매 · 특허 · 법무\n\n"
            "#### LTM 백엔드\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- 병렬 융합 (RRF) 또는 쿼리별 라우팅으로 앙상블 가능\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | License: Apache 2.0"
        ),
        "es": (
            "**Praxia** es un orquestador multi-agente especializado en workflows que "
            "**promueve automáticamente** el conocimiento tácito individual al saber "
            "organizacional, mediante una **pila de memoria cíclica de 5 capas**.\n\n"
            "#### LLMs soportados (15+ primarios · 100+ vía LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / o-series)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq rápido / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 100+ más vía LiteLLM\n\n"
            "Cambia con alias de una línea (`claude` / `gpt-5` / `gemini` / ...) o "
            "`PRAXIA_LOCAL_MODEL=gemma` para operación air-gapped.\n\n"
            "#### Habilidades de negocio incluidas\n"
            "- Inversión · Ventas · Diseño · Compras · Patentes · Legal\n\n"
            "#### Backends LTM\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- Fusión paralela (RRF) o enrutamiento por consulta para ensambles\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | Licencia: Apache 2.0"
        ),
        "fr": (
            "**Praxia** est un orchestrateur multi-agents spécialisé par workflow qui "
            "**promeut automatiquement** la connaissance tacite individuelle en "
            "savoir-faire partagé de l'organisation, via une **pile mémoire cyclique "
            "à 5 couches**.\n\n"
            "#### LLMs supportés (15+ natifs · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / série o)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq fast / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 100+ via LiteLLM\n\n"
            "Basculez avec des alias d'une ligne (`claude` / `gpt-5` / `gemini` / ...) "
            "ou `PRAXIA_LOCAL_MODEL=gemma` pour un fonctionnement air-gapped.\n\n"
            "#### Compétences métiers incluses\n"
            "- Investissement · Ventes · Design · Achats · Brevets · Juridique\n\n"
            "#### Backends LTM\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- Fusion parallèle (RRF) ou routage par requête pour les ensembles\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | Licence : Apache 2.0"
        ),
        "de": (
            "**Praxia** ist ein workflow-spezialisierter Multi-Agenten-Orchestrator, "
            "der individuelles implizites Wissen über einen **5-schichtigen "
            "zyklischen Memory-Stack** **automatisch in geteiltes Org-Know-how "
            "befördert**.\n\n"
            "#### Unterstützte LLMs (15+ direkt · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / o-Serie)\n"
            "- **Google Gemini** + **Gemma** (Cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 Reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq fast / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 100+ weitere via LiteLLM\n\n"
            "Wechsle mit Einzeilen-Aliasen (`claude` / `gpt-5` / `gemini` / ...) oder "
            "`PRAXIA_LOCAL_MODEL=gemma` für Air-gapped-Betrieb.\n\n"
            "#### Mitgelieferte Business-Skills\n"
            "- Invest · Sales · Design · Einkauf · Patent · Legal\n\n"
            "#### LTM-Backends\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- Parallele Fusion (RRF) oder Routing pro Anfrage für Ensembles\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | Lizenz: Apache 2.0"
        ),
        "pt-BR": (
            "**Praxia** é um orquestrador multi-agente especializado em workflows que "
            "**promove automaticamente** o conhecimento tácito individual em know-how "
            "organizacional compartilhado, via uma **pilha cíclica de memória de 5 "
            "camadas**.\n\n"
            "#### LLMs suportados (15+ primários · 100+ via LiteLLM)\n"
            "- **Anthropic Claude** (Opus / Sonnet / Haiku)\n"
            "- **OpenAI ChatGPT** (GPT-5 / série o)\n"
            "- **Google Gemini** + **Gemma** (cloud + Ollama)\n"
            "- **Alibaba Qwen** (API + Ollama)\n"
            "- **DeepSeek** (V3 / R1 reasoning) · **Mistral** + **Codestral**\n"
            "- **xAI Grok** · **Meta Llama** (Groq rápido / Ollama) · **Microsoft Phi**\n"
            "- **Cohere Command R+** · **Perplexity Sonar**\n"
            "- 100+ via LiteLLM\n\n"
            "Troque com aliases de uma linha (`claude` / `gpt-5` / `gemini` / ...) ou "
            "`PRAXIA_LOCAL_MODEL=gemma` para operação air-gapped.\n\n"
            "#### Habilidades de negócio incluídas\n"
            "- Investimento · Vendas · Design · Compras · Patentes · Jurídico\n\n"
            "#### Backends LTM\n"
            "- Mem0 / LangMem / Letta / Zep / HindSight / JSON\n"
            "- Fusão paralela (RRF) ou roteamento por consulta para ensembles\n\n"
            "[GitHub](https://github.com/praxia-dev/praxia) | Licença: Apache 2.0"
        ),
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
    "admin.settings.backend_h": {
        "en": "Tenant memory backend",
        "ja": "テナントのメモリバックエンド",
        "zh-CN": "租户记忆后端",
        "ko": "테넌트 메모리 백엔드",
        "es": "Backend de memoria del tenant",
        "fr": "Backend mémoire du tenant",
        "de": "Tenant-Memory-Backend",
        "pt-BR": "Backend de memória do tenant",
    },
    "admin.settings.backend_intro": {
        "en": "Which LTM backend the entire instance uses (JSON / Mem0 / LangMem / Letta / Zep). Tenant-wide — applies to all users.",
        "ja": "このインスタンス全体で使う LTM バックエンド (JSON / Mem0 / LangMem / Letta / Zep)。テナント単位 — 全ユーザに適用。",
        "zh-CN": "整个实例使用的 LTM 后端(JSON / Mem0 / LangMem / Letta / Zep)。租户级 — 对所有用户生效。",
        "ko": "이 인스턴스 전체가 사용하는 LTM 백엔드 (JSON / Mem0 / LangMem / Letta / Zep). 테넌트 단위 — 모든 사용자에 적용.",
        "es": "Backend LTM usado por toda la instancia (JSON / Mem0 / LangMem / Letta / Zep). Nivel tenant — aplica a todos los usuarios.",
        "fr": "Backend LTM utilisé par toute l'instance (JSON / Mem0 / LangMem / Letta / Zep). Niveau tenant — pour tous les utilisateurs.",
        "de": "LTM-Backend für die gesamte Instanz (JSON / Mem0 / LangMem / Letta / Zep). Tenant-weit — für alle Nutzer.",
        "pt-BR": "Backend LTM usado pela instância inteira (JSON / Mem0 / LangMem / Letta / Zep). Nível tenant — aplica a todos.",
    },
    "admin.settings.backend_apply": {
        "en": "💾 Apply tenant backend",
        "ja": "💾 テナントバックエンドを適用",
        "zh-CN": "💾 应用租户后端",
        "ko": "💾 테넌트 백엔드 적용",
        "es": "💾 Aplicar backend del tenant",
        "fr": "💾 Appliquer le backend tenant",
        "de": "💾 Tenant-Backend anwenden",
        "pt-BR": "💾 Aplicar backend do tenant",
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
    "admin.gate.denied": {
        "en": "🚫 Admin access denied for **{user}** (role: `{role}`). Only admin users can open this view.",
        "ja": "🚫 **{user}** (ロール: `{role}`) は Admin にアクセスできません。admin ロールのユーザのみ閲覧可能です。",
        "zh-CN": "🚫 **{user}** (角色: `{role}`) 无 Admin 访问权限。仅 admin 角色用户可访问。",
        "ko": "🚫 **{user}** (역할: `{role}`) 는 Admin 에 접근할 수 없습니다. admin 역할만 가능합니다.",
        "es": "🚫 Acceso a Admin denegado para **{user}** (rol: `{role}`). Solo usuarios admin.",
        "fr": "🚫 Accès Admin refusé pour **{user}** (rôle : `{role}`). Réservé aux utilisateurs admin.",
        "de": "🚫 Admin-Zugriff verweigert für **{user}** (Rolle: `{role}`). Nur admin-Nutzer.",
        "pt-BR": "🚫 Acesso Admin negado para **{user}** (papel: `{role}`). Apenas usuários admin.",
    },
    "admin.gate.howto": {
        "en": (
            "**Switch user**: change `User ID` in the sidebar to an admin "
            "username.\n\n"
            "**Create an admin user** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "Then re-open this page with `User ID = alice`."
        ),
        "ja": (
            "**ユーザを切替**: サイドバーの `User ID` を admin ユーザ名に変更。\n\n"
            "**admin ユーザを作成** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "その後 `User ID = alice` でこのページを開き直してください。"
        ),
        "zh-CN": (
            "**切换用户**: 在侧边栏将 `User ID` 改为 admin 用户名。\n\n"
            "**创建 admin 用户**(CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "随后以 `User ID = alice` 重新打开本页。"
        ),
        "ko": (
            "**사용자 전환**: 사이드바의 `User ID` 를 admin 사용자명으로 변경.\n\n"
            "**admin 사용자 생성** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "그 후 `User ID = alice` 로 본 페이지를 다시 여세요."
        ),
        "es": (
            "**Cambiar usuario**: cambia `User ID` en la sidebar a un nombre admin.\n\n"
            "**Crear usuario admin** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "Luego abre esta página con `User ID = alice`."
        ),
        "fr": (
            "**Changer d'utilisateur** : modifiez `User ID` dans la sidebar vers un nom admin.\n\n"
            "**Créer un admin** (CLI) :\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "Puis rouvrez cette page avec `User ID = alice`."
        ),
        "de": (
            "**Nutzer wechseln**: ändere `User ID` in der Sidebar zu einem admin-Namen.\n\n"
            "**Admin-Nutzer anlegen** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "Danach diese Seite mit `User ID = alice` neu öffnen."
        ),
        "pt-BR": (
            "**Trocar usuário**: mude `User ID` na sidebar para um nome admin.\n\n"
            "**Criar usuário admin** (CLI):\n\n"
            "```bash\npraxia user create alice --role admin\n```\n\n"
            "Depois reabra esta página com `User ID = alice`."
        ),
    },
    "admin.gate.dev_mode": {
        "en": "⚠️ **Dev / single-user mode** — no users have been created yet, so anyone hitting this URL can change settings. Run `praxia user create <name> --role admin` to enable proper role gating.",
        "ja": "⚠️ **開発 / 単一ユーザモード** — ユーザ未作成のため、このページにアクセスできる人は誰でも設定を変更可能。`praxia user create <名前> --role admin` でロールベース制御を有効化してください。",
        "zh-CN": "⚠️ **开发/单用户模式** — 尚未创建任何用户,因此访问此 URL 的任何人都可更改设置。运行 `praxia user create <名字> --role admin` 启用角色控制。",
        "ko": "⚠️ **개발 / 단일 사용자 모드** — 사용자가 아직 생성되지 않아 이 URL 에 접근하는 누구든 설정을 변경할 수 있습니다. `praxia user create <이름> --role admin` 으로 역할 기반 제어를 활성화하세요.",
        "es": "⚠️ **Modo dev / usuario único** — aún no hay usuarios creados, por lo que cualquiera con la URL puede cambiar ajustes. Ejecuta `praxia user create <nombre> --role admin` para activar control por rol.",
        "fr": "⚠️ **Mode dev / mono-utilisateur** — aucun utilisateur créé, n'importe qui ayant l'URL peut modifier les réglages. Exécutez `praxia user create <nom> --role admin` pour activer le contrôle par rôle.",
        "de": "⚠️ **Dev-/Einzelnutzer-Modus** — noch keine Nutzer angelegt, jeder mit der URL kann Einstellungen ändern. Führe `praxia user create <name> --role admin` aus, um rollenbasierte Kontrolle zu aktivieren.",
        "pt-BR": "⚠️ **Modo dev / usuário único** — sem usuários criados ainda; qualquer um com a URL pode alterar ajustes. Execute `praxia user create <nome> --role admin` para ativar controle por papel.",
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
