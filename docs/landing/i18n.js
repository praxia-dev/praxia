// Landing page i18n — auto-detect from navigator.language with manual override.
//
// Languages: en (default), ja, zh-CN, ko, es, fr, de, pt-BR.
// Supported elements: nav, hero, section headings, scenario picker labels,
// CTA buttons, footer category headings.
//
// Strategy:
//   1. Detect from navigator.language (or stored override in localStorage).
//   2. Map to supported language code (prefix match → fallback to "en").
//   3. Replace text content of every element with [data-i18n="key"].
//   4. Replace placeholders / titles via [data-i18n-placeholder] / [data-i18n-title].
//   5. Add a language switcher dropdown in the nav.
//
// Rationale: full body translation of a 1500-line landing is impractical;
// translating the top-of-funnel elements (hero, nav, CTAs, headings) is
// what affects conversion. Body content remains English with a "translation
// in progress" hint when applicable.

(function () {
  const SUPPORTED = ["en", "ja", "zh-CN", "ko", "es", "fr", "de", "pt-BR"];

  const LANG_DISPLAY = {
    "en": "English",
    "ja": "日本語",
    "zh-CN": "简体中文",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt-BR": "Português (BR)",
  };

  // Translations. Keys match data-i18n attributes in HTML.
  const T = {
    // ----- Navigation -----
    "nav.try": {
      en: "Try it",
      ja: "試す",
      "zh-CN": "试用",
      ko: "체험",
      es: "Probar",
      fr: "Essayer",
      de: "Ausprobieren",
      "pt-BR": "Experimentar",
    },
    "nav.features": {
      en: "Features",
      ja: "機能",
      "zh-CN": "功能",
      ko: "기능",
      es: "Funciones",
      fr: "Fonctionnalités",
      de: "Funktionen",
      "pt-BR": "Recursos",
    },
    "nav.who": {
      en: "Who it's for",
      ja: "対象ユーザ",
      "zh-CN": "适合谁",
      ko: "대상",
      es: "Para quién",
      fr: "Pour qui",
      de: "Für wen",
      "pt-BR": "Para quem",
    },
    "nav.oss": {
      en: "OSS edge",
      ja: "OSS の強み",
      "zh-CN": "OSS 优势",
      ko: "OSS 강점",
      es: "Ventaja OSS",
      fr: "Avantage OSS",
      de: "OSS-Vorteil",
      "pt-BR": "Vantagem OSS",
    },
    "nav.how": {
      en: "How it works",
      ja: "仕組み",
      "zh-CN": "工作原理",
      ko: "작동 방식",
      es: "Cómo funciona",
      fr: "Comment ça marche",
      de: "Funktionsweise",
      "pt-BR": "Como funciona",
    },
    "nav.examples": {
      en: "Examples",
      ja: "事例",
      "zh-CN": "示例",
      ko: "예시",
      es: "Ejemplos",
      fr: "Exemples",
      de: "Beispiele",
      "pt-BR": "Exemplos",
    },
    "nav.roi": {
      en: "ROI",
      ja: "ROI",
      "zh-CN": "投资回报",
      ko: "ROI",
      es: "ROI",
      fr: "ROI",
      de: "ROI",
      "pt-BR": "ROI",
    },
    "nav.extend": {
      en: "Extend",
      ja: "拡張",
      "zh-CN": "扩展",
      ko: "확장",
      es: "Extender",
      fr: "Étendre",
      de: "Erweitern",
      "pt-BR": "Estender",
    },
    "nav.faq": {
      en: "FAQ",
      ja: "FAQ",
      "zh-CN": "常见问题",
      ko: "자주 묻는 질문",
      es: "FAQ",
      fr: "FAQ",
      de: "FAQ",
      "pt-BR": "FAQ",
    },
    "nav.pricing": {
      en: "Pricing",
      ja: "料金",
      "zh-CN": "定价",
      ko: "가격",
      es: "Precios",
      fr: "Tarifs",
      de: "Preise",
      "pt-BR": "Preços",
    },
    "nav.portal": {
      en: "Open Portal",
      ja: "ポータルを開く",
      "zh-CN": "打开门户",
      ko: "포털 열기",
      es: "Abrir Portal",
      fr: "Ouvrir le Portail",
      de: "Portal öffnen",
      "pt-BR": "Abrir Portal",
    },

    // ----- Hero -----
    "hero.kicker": {
      en: "Open Source · Apache 2.0 · Alpha",
      ja: "オープンソース · Apache 2.0 · アルファ版",
      "zh-CN": "开源 · Apache 2.0 · Alpha 版",
      ko: "오픈 소스 · Apache 2.0 · 알파",
      es: "Open Source · Apache 2.0 · Alfa",
      fr: "Open Source · Apache 2.0 · Alpha",
      de: "Open Source · Apache 2.0 · Alpha",
      "pt-BR": "Open Source · Apache 2.0 · Alfa",
    },
    "hero.h1": {
      en: "The multi-agent layer that <em>learns</em> with your team.",
      ja: "チームと共に<em>学ぶ</em>マルチエージェント基盤。",
      "zh-CN": "与您的团队<em>共同学习</em>的多智能体层。",
      ko: "팀과 함께 <em>학습하는</em> 멀티 에이전트 레이어.",
      es: "La capa multi-agente que <em>aprende</em> con tu equipo.",
      fr: "La couche multi-agents qui <em>apprend</em> avec votre équipe.",
      de: "Die Multi-Agenten-Schicht, die <em>mit</em> Ihrem Team lernt.",
      "pt-BR": "A camada multi-agente que <em>aprende</em> com sua equipe.",
    },
    "hero.sub": {
      en: "Praxia is a workflow-specialized multi-agent orchestrator with a built-in <strong>personal-to-organizational memory loop</strong>. Your senior engineers' tacit knowledge promotes itself into shared best practices — automatically.",
      ja: "Praxia はワークフロー特化のマルチエージェント・オーケストレータ。<strong>個人 → 組織のメモリ循環</strong>を内蔵し、シニア技術者の暗黙知を組織のベストプラクティスへと自動昇格させます。",
      "zh-CN": "Praxia 是一款专注工作流的多智能体编排器,内置<strong>个人到组织的记忆循环</strong>。资深工程师的隐性知识自动晋升为团队最佳实践。",
      ko: "Praxia 는 워크플로 특화 멀티 에이전트 오케스트레이터입니다. <strong>개인 → 조직 메모리 루프</strong>가 내장되어 시니어 엔지니어의 암묵지가 자동으로 공유 베스트 프랙티스로 승격됩니다.",
      es: "Praxia es un orquestador multi-agente especializado en flujos de trabajo con un <strong>bucle de memoria personal-a-organizacional</strong> integrado. El conocimiento tácito de tus ingenieros senior se promociona automáticamente a mejores prácticas compartidas.",
      fr: "Praxia est un orchestrateur multi-agents spécialisé pour les workflows, avec une <strong>boucle de mémoire personnelle-à-organisationnelle</strong> intégrée. Les connaissances tacites de vos ingénieurs seniors se promeuvent automatiquement en meilleures pratiques partagées.",
      de: "Praxia ist ein Workflow-spezialisierter Multi-Agent-Orchestrator mit eingebauter <strong>persönlich-zu-organisationaler Speicherschleife</strong>. Das implizite Wissen Ihrer Senior-Ingenieure wird automatisch zu geteilten Best Practices.",
      "pt-BR": "Praxia é um orquestrador multi-agente especializado em workflows com um <strong>ciclo de memória pessoal-para-organizacional</strong> integrado. O conhecimento tácito dos seus engenheiros sênior é promovido automaticamente para boas práticas compartilhadas.",
    },
    "hero.cta_get_started": {
      en: "Get started",
      ja: "始める",
      "zh-CN": "开始使用",
      ko: "시작하기",
      es: "Empezar",
      fr: "Commencer",
      de: "Loslegen",
      "pt-BR": "Começar",
    },
    "hero.cta_star": {
      en: "★ Star on GitHub",
      ja: "★ GitHub で Star",
      "zh-CN": "★ 在 GitHub 上加星",
      ko: "★ GitHub에서 스타",
      es: "★ Estrella en GitHub",
      fr: "★ Étoile sur GitHub",
      de: "★ Auf GitHub markieren",
      "pt-BR": "★ Estrela no GitHub",
    },

    // ----- Section headings (kicker + h2 only) -----
    "tryit.kicker": {
      en: "Try it — pick your scenario",
      ja: "試す — シナリオを選択",
      "zh-CN": "试用 — 选择您的场景",
      ko: "체험 — 시나리오 선택",
      es: "Probar — elige tu escenario",
      fr: "Essayer — choisissez votre scénario",
      de: "Ausprobieren — wählen Sie Ihr Szenario",
      "pt-BR": "Experimentar — escolha seu cenário",
    },
    "tryit.h2": {
      en: "See exactly what Praxia does for <em>your</em> work.",
      ja: "<em>あなたの業務</em>で Praxia が何をするのかを確認。",
      "zh-CN": "看 Praxia 如何精准服务<em>您的</em>工作。",
      ko: "Praxia 가 <em>당신의 업무</em>에 어떻게 작동하는지 확인하세요.",
      es: "Mira exactamente qué hace Praxia por <em>tu</em> trabajo.",
      fr: "Voyez précisément ce que Praxia fait pour <em>votre</em> travail.",
      de: "Sehen Sie genau, was Praxia für <em>Ihre</em> Arbeit tut.",
      "pt-BR": "Veja exatamente o que o Praxia faz pelo <em>seu</em> trabalho.",
    },
    "tryit.label_role": {
      en: "I am",
      ja: "私は",
      "zh-CN": "我是",
      ko: "나는",
      es: "Soy",
      fr: "Je suis",
      de: "Ich bin",
      "pt-BR": "Sou",
    },
    "tryit.label_task": {
      en: "I want to",
      ja: "やりたいこと",
      "zh-CN": "我想",
      ko: "하고 싶은 것",
      es: "Quiero",
      fr: "Je veux",
      de: "Ich möchte",
      "pt-BR": "Quero",
    },
    "tryit.run": {
      en: "▶ Run preview",
      ja: "▶ プレビュー実行",
      "zh-CN": "▶ 运行预览",
      ko: "▶ 미리보기 실행",
      es: "▶ Ejecutar vista previa",
      fr: "▶ Lancer l'aperçu",
      de: "▶ Vorschau starten",
      "pt-BR": "▶ Executar prévia",
    },
    "tryit.copy": {
      en: "📋 Copy command",
      ja: "📋 コマンドをコピー",
      "zh-CN": "📋 复制命令",
      ko: "📋 명령 복사",
      es: "📋 Copiar comando",
      fr: "📋 Copier la commande",
      de: "📋 Befehl kopieren",
      "pt-BR": "📋 Copiar comando",
    },
    "tryit.note": {
      en: "Preview runs locally in your browser — no install, no API key.",
      ja: "プレビューはブラウザ内で動作 — インストール不要、API キー不要。",
      "zh-CN": "预览在浏览器本地运行 — 无需安装,无需 API 密钥。",
      ko: "미리보기는 브라우저에서 로컬로 실행됩니다 — 설치 불필요, API 키 불필요.",
      es: "La vista previa se ejecuta localmente en tu navegador — sin instalación, sin clave API.",
      fr: "L'aperçu s'exécute localement dans votre navigateur — sans installation, sans clé API.",
      de: "Vorschau läuft lokal in Ihrem Browser — keine Installation, kein API-Schlüssel.",
      "pt-BR": "A prévia roda localmente no seu navegador — sem instalação, sem chave API.",
    },

    "features.kicker": {
      en: "Why Praxia",
      ja: "なぜ Praxia か",
      "zh-CN": "为何选择 Praxia",
      ko: "왜 Praxia 인가",
      es: "Por qué Praxia",
      fr: "Pourquoi Praxia",
      de: "Warum Praxia",
      "pt-BR": "Por que Praxia",
    },
    "features.h2": {
      en: "38+ advantages no other framework offers in one package.",
      ja: "1 パッケージに 38+ の独自優位性。他にないラインナップ。",
      "zh-CN": "38+ 项独特优势,无其他框架可比。",
      ko: "다른 프레임워크에는 없는 38+ 가지 강점.",
      es: "38+ ventajas que ningún otro framework ofrece en un solo paquete.",
      fr: "38+ avantages qu'aucun autre framework n'offre en un seul package.",
      de: "38+ Vorteile, die kein anderes Framework in einem Paket bietet.",
      "pt-BR": "38+ vantagens que nenhum outro framework oferece em um pacote.",
    },

    "who.kicker": {
      en: "Who it's for",
      ja: "対象ユーザ",
      "zh-CN": "适合谁",
      ko: "대상 사용자",
      es: "Para quién",
      fr: "Pour qui",
      de: "Für wen",
      "pt-BR": "Para quem",
    },
    "who.h2": {
      en: "Four target personas, one platform.",
      ja: "4 つのターゲットペルソナ、1 つのプラットフォーム。",
      "zh-CN": "四类目标用户,一个平台。",
      ko: "4가지 타깃 페르소나, 하나의 플랫폼.",
      es: "Cuatro personas objetivo, una plataforma.",
      fr: "Quatre personas cibles, une seule plateforme.",
      de: "Vier Zielpersonen, eine Plattform.",
      "pt-BR": "Quatro personas-alvo, uma plataforma.",
    },

    "oss.kicker": {
      en: "Why OSS matters here",
      ja: "OSS の意義",
      "zh-CN": "OSS 的意义",
      ko: "OSS 가 중요한 이유",
      es: "Por qué OSS importa aquí",
      fr: "Pourquoi l'OSS compte ici",
      de: "Warum OSS hier wichtig ist",
      "pt-BR": "Por que OSS importa aqui",
    },
    "oss.h2": {
      en: "The capabilities you typically pay for — already in the package.",
      ja: "通常は有償である機能 — すべてパッケージに同梱。",
      "zh-CN": "通常需付费的能力 — 全部包含在内。",
      ko: "보통 유료로 제공되는 기능 — 패키지에 포함되어 있습니다.",
      es: "Las capacidades por las que normalmente pagas — ya incluidas en el paquete.",
      fr: "Les fonctionnalités habituellement payantes — déjà incluses dans le package.",
      de: "Die Funktionen, die Sie normalerweise bezahlen — bereits im Paket enthalten.",
      "pt-BR": "Os recursos pelos quais você normalmente paga — já incluídos no pacote.",
    },

    "faq.kicker": {
      en: "FAQ",
      ja: "FAQ",
      "zh-CN": "常见问题",
      ko: "자주 묻는 질문",
      es: "FAQ",
      fr: "FAQ",
      de: "FAQ",
      "pt-BR": "FAQ",
    },
    "faq.h2": {
      en: "The questions everyone asks.",
      ja: "よくある質問。",
      "zh-CN": "大家都会问的问题。",
      ko: "모두가 묻는 질문.",
      es: "Las preguntas que todos hacen.",
      fr: "Les questions que tout le monde pose.",
      de: "Die Fragen, die jeder stellt.",
      "pt-BR": "As perguntas que todos fazem.",
    },

    // ----- Footer category headings -----
    "footer.product": {
      en: "Product",
      ja: "プロダクト",
      "zh-CN": "产品",
      ko: "제품",
      es: "Producto",
      fr: "Produit",
      de: "Produkt",
      "pt-BR": "Produto",
    },
    "footer.resources": {
      en: "Resources",
      ja: "リソース",
      "zh-CN": "资源",
      ko: "리소스",
      es: "Recursos",
      fr: "Ressources",
      de: "Ressourcen",
      "pt-BR": "Recursos",
    },
    "footer.community": {
      en: "Community",
      ja: "コミュニティ",
      "zh-CN": "社区",
      ko: "커뮤니티",
      es: "Comunidad",
      fr: "Communauté",
      de: "Community",
      "pt-BR": "Comunidade",
    },
    "footer.legal": {
      en: "Legal",
      ja: "法的事項",
      "zh-CN": "法律信息",
      ko: "법적 정보",
      es: "Legal",
      fr: "Mentions légales",
      de: "Rechtliches",
      "pt-BR": "Legal",
    },
    "footer.tag": {
      en: "Bridging individual brilliance and organizational continuity.",
      ja: "個の卓越性と組織の継続性をつなぐ。",
      "zh-CN": "连接个人卓越与组织延续。",
      ko: "개인의 탁월함과 조직의 연속성을 연결합니다.",
      es: "Uniendo la brillantez individual con la continuidad organizacional.",
      fr: "Le pont entre l'excellence individuelle et la continuité organisationnelle.",
      de: "Die Brücke zwischen individueller Brillanz und organisationaler Kontinuität.",
      "pt-BR": "Conectando brilho individual e continuidade organizacional.",
    },

    // ----- Cookie consent banner -----
    "consent.title": {
      en: "We use cookies",
      ja: "Cookie について",
      "zh-CN": "我们使用 Cookie",
      ko: "쿠키 사용 안내",
      es: "Usamos cookies",
      fr: "Nous utilisons des cookies",
      de: "Wir verwenden Cookies",
      "pt-BR": "Usamos cookies",
    },
    "consent.body": {
      en: "This site (praxia.dev) uses essential cookies for language and consent preferences, and — only if you agree — privacy-respecting analytics to count anonymous visits. No third-party tracking. No personal data sold. See the <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Cookies policy</a> and <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">Privacy policy</a>.",
      ja: "本サイト (praxia.dev) では言語と同意設定の保持のための必須 Cookie を使用し、同意いただいた場合のみ匿名訪問数を計測する分析ツールを利用します。第三者トラッキング・個人データ販売は行いません。詳細は <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Cookie ポリシー</a> と <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">プライバシーポリシー</a> を参照ください。",
      "zh-CN": "本站 (praxia.dev) 使用必要 Cookie 保存语言和同意设置,仅在您同意时使用注重隐私的匿名访问统计。无第三方追踪、无个人数据出售。详见 <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Cookie 政策</a> 和 <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">隐私政策</a>。",
      ko: "본 사이트 (praxia.dev) 는 언어 및 동의 설정 저장을 위한 필수 쿠키를 사용하며, 동의하신 경우에만 익명 방문 수를 집계하는 프라이버시 친화적 분석 도구를 사용합니다. 제3자 추적 없음, 개인정보 판매 없음. 자세한 내용은 <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">쿠키 정책</a> 과 <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">개인정보 정책</a> 참조.",
      es: "Este sitio (praxia.dev) usa cookies esenciales para idioma y preferencias de consentimiento, y — solo si lo aceptas — analítica respetuosa con la privacidad para contar visitas anónimas. Sin rastreo de terceros. Sin venta de datos personales. Ver <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Política de Cookies</a> y <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">Política de Privacidad</a>.",
      fr: "Ce site (praxia.dev) utilise des cookies essentiels pour la langue et les préférences de consentement, et — uniquement si vous acceptez — des analyses respectueuses de la vie privée pour compter les visites anonymes. Pas de suivi tiers. Pas de vente de données personnelles. Voir la <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Politique de cookies</a> et la <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">Politique de confidentialité</a>.",
      de: "Diese Website (praxia.dev) verwendet essenzielle Cookies für Sprache und Einwilligungseinstellungen und – nur mit Ihrer Zustimmung – datenschutzfreundliche Analytik für anonyme Besuchszählung. Kein Drittanbieter-Tracking. Kein Verkauf personenbezogener Daten. Siehe <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Cookie-Richtlinie</a> und <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">Datenschutzerklärung</a>.",
      "pt-BR": "Este site (praxia.dev) usa cookies essenciais para idioma e preferências de consentimento, e — somente se você aceitar — análise que respeita a privacidade para contar visitas anônimas. Sem rastreamento de terceiros. Sem venda de dados pessoais. Veja a <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/COOKIES.md\">Política de Cookies</a> e <a href=\"https://github.com/genarch/praxia/blob/main/docs/legal/PRIVACY.md\">Política de Privacidade</a>.",
    },
    "consent.accept_all": {
      en: "Accept all",
      ja: "すべて許可",
      "zh-CN": "全部接受",
      ko: "모두 허용",
      es: "Aceptar todo",
      fr: "Tout accepter",
      de: "Alle akzeptieren",
      "pt-BR": "Aceitar tudo",
    },
    "consent.essential_only": {
      en: "Essential only",
      ja: "必須のみ",
      "zh-CN": "仅必要",
      ko: "필수만",
      es: "Solo esenciales",
      fr: "Essentiels uniquement",
      de: "Nur essenzielle",
      "pt-BR": "Apenas essenciais",
    },
    "consent.customize": {
      en: "Customize",
      ja: "詳細設定",
      "zh-CN": "自定义",
      ko: "사용자 지정",
      es: "Personalizar",
      fr: "Personnaliser",
      de: "Anpassen",
      "pt-BR": "Personalizar",
    },
    "consent.cat_essential": {
      en: "Essential (required for the site to work)",
      ja: "必須 (サイト動作に必要)",
      "zh-CN": "必要 (站点运行所需)",
      ko: "필수 (사이트 작동에 필요)",
      es: "Esenciales (necesarios para el sitio)",
      fr: "Essentiels (nécessaires au site)",
      de: "Essenziell (für die Funktion erforderlich)",
      "pt-BR": "Essenciais (necessários para o site)",
    },
    "consent.cat_analytics": {
      en: "Analytics (anonymous visit counts)",
      ja: "分析 (匿名訪問数の計測)",
      "zh-CN": "分析 (匿名访问统计)",
      ko: "분석 (익명 방문 통계)",
      es: "Analítica (visitas anónimas)",
      fr: "Analytique (visites anonymes)",
      de: "Analytik (anonyme Besuche)",
      "pt-BR": "Análise (visitas anônimas)",
    },
    "consent.save": {
      en: "Save preferences",
      ja: "設定を保存",
      "zh-CN": "保存偏好",
      ko: "설정 저장",
      es: "Guardar preferencias",
      fr: "Enregistrer les préférences",
      de: "Einstellungen speichern",
      "pt-BR": "Salvar preferências",
    },
    "consent.manage": {
      en: "Cookie preferences",
      ja: "Cookie 設定",
      "zh-CN": "Cookie 偏好",
      ko: "쿠키 설정",
      es: "Preferencias de cookies",
      fr: "Préférences cookies",
      de: "Cookie-Einstellungen",
      "pt-BR": "Preferências de cookies",
    },

    // ===== Feature card titles (34 cards) ============================
    "feat.autonomous_agent":     {en:"Autonomous agent (Claude-Code-style)", ja:"自律エージェント (ClaudeCode 同等)", "zh-CN":"自主代理 (Claude-Code 风格)", ko:"자율 에이전트 (Claude-Code 스타일)", es:"Agente autónomo (estilo Claude-Code)", fr:"Agent autonome (style Claude-Code)", de:"Autonomer Agent (Claude-Code-Stil)", "pt-BR":"Agente autônomo (estilo Claude-Code)"},
    "feat.autonomous_agent.body":{en:"An LLM-driven tool-use loop over your full Praxia stack — personal memory, org memory, frozen layer, skills, connectors. The agent picks tools on its own (search → run skill → pull connector → answer) with ACL gates and audit logging. Ships as <code>praxia.agent.AutonomousAgent</code>, <code>praxia agent run</code>, and an MCP meta-tool for remote clients.", ja:"Praxia スタック全体 (個人メモリ・組織メモリ・凍結層・スキル・コネクタ) を LLM 駆動のツール使用ループで自律的に活用。検索 → スキル実行 → コネクタ pull → 回答 の流れをエージェントが自分で判断し、ACL チェックと監査ログを伴って実行。<code>praxia.agent.AutonomousAgent</code> / <code>praxia agent run</code> / MCP メタツールで提供。", "zh-CN":"基于 LLM 的工具使用循环,贯穿整个 Praxia 栈 — 个人记忆、组织记忆、冻结层、技能、连接器。代理自主选择工具(搜索 → 执行技能 → 拉取连接器 → 回答),具有 ACL 检查和审计日志。提供 <code>praxia.agent.AutonomousAgent</code>、<code>praxia agent run</code> 及 MCP 元工具。", ko:"Praxia 스택 전체 (개인 메모리·조직 메모리·동결 레이어·스킬·커넥터) 위에서 LLM 주도 도구 사용 루프. 에이전트가 도구를 직접 선택 (검색 → 스킬 실행 → 커넥터 pull → 답변), ACL 게이트와 감사 로그 포함. <code>praxia.agent.AutonomousAgent</code> / <code>praxia agent run</code> / MCP 메타도구로 제공.", es:"Bucle de uso de herramientas guiado por LLM sobre toda la pila Praxia — memoria personal, memoria org, capa congelada, habilidades, conectores. El agente elige herramientas por su cuenta (buscar → ejecutar habilidad → extraer conector → responder) con ACL y auditoría. Disponible como <code>praxia.agent.AutonomousAgent</code>, <code>praxia agent run</code> y meta-herramienta MCP.", fr:"Boucle d'utilisation d'outils pilotée par LLM sur toute la pile Praxia — mémoire personnelle, mémoire org, couche figée, compétences, connecteurs. L'agent choisit ses outils (rechercher → exécuter une compétence → tirer un connecteur → répondre) avec ACL et journal d'audit. Fourni en tant que <code>praxia.agent.AutonomousAgent</code>, <code>praxia agent run</code> et méta-outil MCP.", de:"Eine LLM-gesteuerte Tool-Use-Schleife über den gesamten Praxia-Stack — persönlicher Speicher, Org-Speicher, eingefrorene Schicht, Skills, Konnektoren. Der Agent wählt selbst Werkzeuge (Suche → Skill ausführen → Konnektor abrufen → antworten) mit ACL-Gates und Audit-Log. Bereitgestellt als <code>praxia.agent.AutonomousAgent</code>, <code>praxia agent run</code> und MCP-Meta-Tool.", "pt-BR":"Loop de uso de ferramentas guiado por LLM sobre toda a stack Praxia — memória pessoal, memória org, camada congelada, habilidades, conectores. O agente escolhe ferramentas sozinho (buscar → executar habilidade → puxar conector → responder) com gates de ACL e log de auditoria. Disponível como <code>praxia.agent.AutonomousAgent</code>, <code>praxia agent run</code> e meta-ferramenta MCP."},
    "feat.memory_loop":          {en:"Personal → org memory loop", ja:"個人 → 組織のメモリ循環", "zh-CN":"个人 → 组织 记忆循环", ko:"개인 → 조직 메모리 순환", es:"Bucle memoria personal → org", fr:"Boucle mémoire personnelle → org", de:"Persönlich → Organisations-Speicherschleife", "pt-BR":"Ciclo de memória pessoal → org"},
    "feat.promotion_engine":     {en:"3-path promotion engine", ja:"3 経路の昇格エンジン", "zh-CN":"3 路晋升引擎", ko:"3 경로 승격 엔진", es:"Motor de promoción de 3 rutas", fr:"Moteur de promotion 3 voies", de:"3-Pfad-Promotion-Engine", "pt-BR":"Motor de promoção de 3 caminhos"},
    "feat.workflow_flows":       {en:"Workflow-specialized flows", ja:"業務特化フロー", "zh-CN":"工作流特化流水线", ko:"워크플로 특화 플로", es:"Flujos especializados", fr:"Flux spécialisés", de:"Workflow-spezialisierte Flows", "pt-BR":"Fluxos especializados"},
    "feat.business_skills":      {en:"6 default business skills", ja:"6 業務スキル", "zh-CN":"6 个默认业务技能", ko:"6 가지 기본 업무 스킬", es:"6 habilidades de negocio", fr:"6 compétences métier", de:"6 Geschäfts-Skills", "pt-BR":"6 habilidades de negócio"},
    "feat.evidence":             {en:"Evidence by default", ja:"エビデンス標準同梱", "zh-CN":"标配证据指标", ko:"증거 기본 탑재", es:"Evidencia por defecto", fr:"Preuves par défaut", de:"Evidenz standardmäßig", "pt-BR":"Evidência por padrão"},
    "feat.ltm_backends":         {en:"6 LTM backends", ja:"6 種の LTM バックエンド", "zh-CN":"6 种 LTM 后端", ko:"6 가지 LTM 백엔드", es:"6 backends LTM", fr:"6 backends LTM", de:"6 LTM-Backends", "pt-BR":"6 backends LTM"},
    "feat.multi_llm":            {en:"Multi-LLM (100+ providers)", ja:"複数 LLM 対応 (100+ プロバイダ)", "zh-CN":"多 LLM (100+ 提供商)", ko:"멀티 LLM (100+ 프로바이더)", es:"Multi-LLM (100+ proveedores)", fr:"Multi-LLM (100+ fournisseurs)", de:"Multi-LLM (100+ Anbieter)", "pt-BR":"Multi-LLM (100+ provedores)"},
    "feat.auth_in_oss":          {en:"Auth, RBAC, SSO, audit — in OSS", ja:"認証/RBAC/SSO/監査 — OSS 内蔵", "zh-CN":"认证/RBAC/SSO/审计 — OSS 内置", ko:"인증/RBAC/SSO/감사 — OSS 내장", es:"Auth/RBAC/SSO/auditoría — en OSS", fr:"Auth/RBAC/SSO/audit — dans l'OSS", de:"Auth/RBAC/SSO/Audit — im OSS", "pt-BR":"Auth/RBAC/SSO/auditoria — no OSS"},
    "feat.skills_promoted":      {en:"Skills also promoted", ja:"スキル自体も昇格", "zh-CN":"技能本身也会晋升", ko:"스킬 자체도 승격", es:"Las habilidades también se promueven", fr:"Les compétences sont aussi promues", de:"Skills werden auch befördert", "pt-BR":"Habilidades também são promovidas"},
    "feat.mcp_compat":           {en:"MCP / Claude Skills compatible", ja:"MCP / Claude Skills 互換", "zh-CN":"兼容 MCP / Claude Skills", ko:"MCP / Claude Skills 호환", es:"Compatible MCP / Claude Skills", fr:"Compatible MCP / Claude Skills", de:"MCP / Claude Skills kompatibel", "pt-BR":"Compatível MCP / Claude Skills"},
    "feat.outcome_tracking":     {en:"Outcome tracking built-in", ja:"成果トラッキング標準", "zh-CN":"内置成果追踪", ko:"성과 추적 내장", es:"Seguimiento de resultados integrado", fr:"Suivi des résultats intégré", de:"Ergebnisverfolgung eingebaut", "pt-BR":"Rastreio de resultados integrado"},
    "feat.apache_open":          {en:"Apache 2.0 + Open Core ready", ja:"Apache 2.0 + Open Core 対応", "zh-CN":"Apache 2.0 + Open Core 就绪", ko:"Apache 2.0 + Open Core 준비", es:"Apache 2.0 + Open Core listo", fr:"Apache 2.0 + Open Core prêt", de:"Apache 2.0 + Open-Core-fähig", "pt-BR":"Apache 2.0 + Open Core pronto"},
    "feat.acl":                  {en:"Resource access policies (ACL)", ja:"リソース ACL", "zh-CN":"资源访问策略 (ACL)", ko:"리소스 접근 정책 (ACL)", es:"Políticas de acceso a recursos (ACL)", fr:"Politiques d'accès (ACL)", de:"Ressourcen-ACL", "pt-BR":"Políticas de acesso (ACL)"},
    "feat.admin_exports":        {en:"Admin data exports", ja:"管理者データエクスポート", "zh-CN":"管理员数据导出", ko:"관리자 데이터 내보내기", es:"Exportaciones admin", fr:"Exports admin", de:"Admin-Datenexports", "pt-BR":"Exportações admin"},
    "feat.connectors":           {en:"20 storage / SaaS connectors", ja:"20 種のストレージ/SaaS コネクタ", "zh-CN":"20 个存储/SaaS 连接器", ko:"20 개 스토리지/SaaS 커넥터", es:"20 conectores de almacenamiento/SaaS", fr:"20 connecteurs stockage/SaaS", de:"20 Speicher/SaaS-Konnektoren", "pt-BR":"20 conectores armazenamento/SaaS"},
    "feat.dashboards":           {en:"Personal & org dashboards", ja:"個人/組織ダッシュボード", "zh-CN":"个人和组织仪表板", ko:"개인 / 조직 대시보드", es:"Paneles personal/org", fr:"Tableaux de bord perso/org", de:"Personal/Org-Dashboards", "pt-BR":"Painéis pessoal/org"},
    "feat.prompts_distribution": {en:"Custom prompt distribution", ja:"カスタムプロンプト配信", "zh-CN":"自定义提示分发", ko:"커스텀 프롬프트 배포", es:"Distribución de prompts", fr:"Distribution de prompts", de:"Custom-Prompt-Verteilung", "pt-BR":"Distribuição de prompts"},
    "feat.user_crud":            {en:"Full admin user CRUD", ja:"ユーザ管理 (CRUD)", "zh-CN":"完整管理员用户 CRUD", ko:"관리자 사용자 CRUD", es:"CRUD de usuarios completo", fr:"CRUD utilisateurs complet", de:"Voll Admin Benutzer-CRUD", "pt-BR":"CRUD de usuários completo"},
    "feat.parsers":              {en:"File parsers (PDF · Word · Excel · PowerPoint · CSV · HTML)", ja:"ファイルパーサ (PDF/Word/Excel/PowerPoint/CSV/HTML)", "zh-CN":"文件解析器 (PDF/Word/Excel/PowerPoint/CSV/HTML)", ko:"파일 파서 (PDF/Word/Excel/PowerPoint/CSV/HTML)", es:"Parsers de archivos (PDF/Word/Excel/PowerPoint/CSV/HTML)", fr:"Parsers de fichiers (PDF/Word/Excel/PowerPoint/CSV/HTML)", de:"Datei-Parser (PDF/Word/Excel/PowerPoint/CSV/HTML)", "pt-BR":"Parsers de arquivos (PDF/Word/Excel/PowerPoint/CSV/HTML)"},
    "feat.voice":                {en:"Voice input + voice output", ja:"音声入力 + 音声出力", "zh-CN":"语音输入 + 语音输出", ko:"음성 입력 + 출력", es:"Entrada y salida de voz", fr:"Entrée et sortie vocales", de:"Spracheingabe + Sprachausgabe", "pt-BR":"Entrada e saída de voz"},
    "feat.user_oauth":           {en:"User-delegated OAuth", ja:"ユーザ委譲 OAuth", "zh-CN":"用户委派 OAuth", ko:"사용자 위임 OAuth", es:"OAuth delegado por usuario", fr:"OAuth délégué utilisateur", de:"Benutzerdelegierter OAuth", "pt-BR":"OAuth delegado pelo usuário"},
    "feat.legal_templates":      {en:"Legal templates", ja:"法務テンプレート", "zh-CN":"法律模板", ko:"법률 템플릿", es:"Plantillas legales", fr:"Modèles juridiques", de:"Rechtsvorlagen", "pt-BR":"Modelos legais"},
    "feat.multi_ltm":            {en:"Multi-LTM fusion + routing", ja:"複数 LTM 融合 + ルーティング", "zh-CN":"多 LTM 融合 + 路由", ko:"멀티 LTM 융합 + 라우팅", es:"Fusión multi-LTM + enrutamiento", fr:"Fusion multi-LTM + routage", de:"Multi-LTM Fusion + Routing", "pt-BR":"Fusão multi-LTM + roteamento"},
    "feat.memory_mode":          {en:"Memory mode toggle", ja:"メモリモード切替 (accumulate / read_only)", "zh-CN":"记忆模式切换", ko:"메모리 모드 전환", es:"Toggle de modo de memoria", fr:"Bascule mode mémoire", de:"Speichermodus-Umschalter", "pt-BR":"Alternar modo de memória"},
    "feat.admin_ltm":            {en:"Admin-controlled LTM policy", ja:"管理者向け LTM ポリシー", "zh-CN":"管理员控制的 LTM 策略", ko:"관리자 제어 LTM 정책", es:"Política LTM admin", fr:"Politique LTM admin", de:"Admin-LTM-Richtlinie", "pt-BR":"Política LTM admin"},
    "feat.exporters":            {en:"Output exporters (HTML · PPTX · DOCX · MD · JSON)", ja:"出力エクスポータ (HTML/PPTX/DOCX/MD/JSON)", "zh-CN":"输出导出器 (HTML/PPTX/DOCX/MD/JSON)", ko:"출력 익스포터 (HTML/PPTX/DOCX/MD/JSON)", es:"Exportadores de salida (HTML/PPTX/DOCX/MD/JSON)", fr:"Exportateurs (HTML/PPTX/DOCX/MD/JSON)", de:"Output-Exporter (HTML/PPTX/DOCX/MD/JSON)", "pt-BR":"Exportadores (HTML/PPTX/DOCX/MD/JSON)"},
    "feat.gemma":                {en:"Gemma support", ja:"Gemma 対応", "zh-CN":"Gemma 支持", ko:"Gemma 지원", es:"Soporte Gemma", fr:"Support Gemma", de:"Gemma-Unterstützung", "pt-BR":"Suporte Gemma"},
    "feat.deploy_modes":         {en:"Backend-only or full-stack", ja:"バックエンドのみ or フルスタック", "zh-CN":"仅后端或全栈", ko:"백엔드 전용 또는 풀스택", es:"Solo backend o full-stack", fr:"Backend seul ou full-stack", de:"Backend-only oder Full-Stack", "pt-BR":"Apenas backend ou full-stack"},
    "feat.specs":                {en:"Formal design specs (EN + JA)", ja:"正式設計仕様書 (英 + 日)", "zh-CN":"正式设计规范 (英+日)", ko:"공식 설계 사양서 (영 + 일)", es:"Especificaciones formales (EN+JA)", fr:"Spécifications formelles (EN+JA)", de:"Formale Designspezifikationen (EN+JA)", "pt-BR":"Especificações formais (EN+JA)"},
    "feat.kms":                  {en:"KMS-backed token encryption", ja:"KMS ベースのトークン暗号化", "zh-CN":"KMS 支持的令牌加密", ko:"KMS 기반 토큰 암호화", es:"Cifrado de tokens con KMS", fr:"Chiffrement de tokens via KMS", de:"KMS-gestützte Token-Verschlüsselung", "pt-BR":"Criptografia de tokens via KMS"},
    "feat.oauth_web":            {en:"Production OAuth callback (HTTP)", ja:"本番 OAuth コールバック (HTTP)", "zh-CN":"生产 OAuth 回调 (HTTP)", ko:"프로덕션 OAuth 콜백 (HTTP)", es:"Callback OAuth de producción (HTTP)", fr:"Callback OAuth production (HTTP)", de:"Produktions-OAuth-Callback (HTTP)", "pt-BR":"Callback OAuth de produção (HTTP)"},
    "feat.ab":                   {en:"A/B experiments built in", ja:"A/B 実験フレーム同梱", "zh-CN":"内置 A/B 实验", ko:"A/B 실험 내장", es:"Experimentos A/B integrados", fr:"Expériences A/B intégrées", de:"A/B-Experimente eingebaut", "pt-BR":"Experimentos A/B integrados"},
    "feat.llm_eval":             {en:"LLM output quality eval (CI gate)", ja:"LLM 出力品質評価 (CI ガード)", "zh-CN":"LLM 输出质量评估 (CI 门禁)", ko:"LLM 출력 품질 평가 (CI 게이트)", es:"Evaluación calidad LLM (CI)", fr:"Éval qualité LLM (CI)", de:"LLM-Qualitätsbewertung (CI)", "pt-BR":"Avaliação de qualidade LLM (CI)"},
    "feat.tests":                {en:"428 regression tests", ja:"428 件のリグレッションテスト", "zh-CN":"428 项回归测试", ko:"428 개 회귀 테스트", es:"428 tests de regresión", fr:"428 tests de régression", de:"428 Regressionstests", "pt-BR":"428 testes de regressão"},
    "feat.mcp_server":           {en:"MCP server (stdio + remote HTTP/SSE)", ja:"MCP サーバ (stdio + リモート HTTP/SSE)", "zh-CN":"MCP 服务器 (stdio + 远程 HTTP/SSE)", ko:"MCP 서버 (stdio + 원격 HTTP/SSE)", es:"Servidor MCP (stdio + HTTP/SSE remoto)", fr:"Serveur MCP (stdio + HTTP/SSE distant)", de:"MCP-Server (stdio + Remote HTTP/SSE)", "pt-BR":"Servidor MCP (stdio + HTTP/SSE remoto)"},
    "feat.responsive":           {en:"Mobile-responsive UI + landing", ja:"モバイル対応 UI + サイト", "zh-CN":"移动响应式 UI + 站点", ko:"모바일 반응형 UI + 사이트", es:"UI responsive móvil + sitio", fr:"UI responsive mobile + site", de:"Mobile-responsive UI + Site", "pt-BR":"UI responsiva móvel + site"},

    // ===== Hero meta chips (18) ======================================
    "chip.py":         {en:"🐍 Python 3.11+", ja:"🐍 Python 3.11+", "zh-CN":"🐍 Python 3.11+", ko:"🐍 Python 3.11+", es:"🐍 Python 3.11+", fr:"🐍 Python 3.11+", de:"🐍 Python 3.11+", "pt-BR":"🐍 Python 3.11+"},
    "chip.ltm":        {en:"🧠 6 LTM backends + multi-LTM fusion", ja:"🧠 LTM バックエンド 6 種 + 複数融合", "zh-CN":"🧠 6 种 LTM 后端 + 多 LTM 融合", ko:"🧠 LTM 백엔드 6 종 + 멀티 LTM 융합", es:"🧠 6 backends LTM + fusión multi-LTM", fr:"🧠 6 backends LTM + fusion multi-LTM", de:"🧠 6 LTM-Backends + Multi-LTM-Fusion", "pt-BR":"🧠 6 backends LTM + fusão multi-LTM"},
    "chip.llm":        {en:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", ja:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", "zh-CN":"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", ko:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", es:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", fr:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", de:"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen", "pt-BR":"🤖 Claude · ChatGPT · Gemini · Gemma · Qwen"},
    "chip.auth":       {en:"🔐 SSO + RBAC + audit · OAuth per-user", ja:"🔐 SSO + RBAC + 監査 · ユーザ毎 OAuth", "zh-CN":"🔐 SSO + RBAC + 审计 · 用户级 OAuth", ko:"🔐 SSO + RBAC + 감사 · 사용자별 OAuth", es:"🔐 SSO + RBAC + auditoría · OAuth por usuario", fr:"🔐 SSO + RBAC + audit · OAuth par utilisateur", de:"🔐 SSO + RBAC + Audit · OAuth pro Benutzer", "pt-BR":"🔐 SSO + RBAC + auditoria · OAuth por usuário"},
    "chip.acl":        {en:"🛡 Resource ACL", ja:"🛡 リソース ACL", "zh-CN":"🛡 资源 ACL", ko:"🛡 리소스 ACL", es:"🛡 ACL de recursos", fr:"🛡 ACL de ressources", de:"🛡 Ressourcen-ACL", "pt-BR":"🛡 ACL de recursos"},
    "chip.conn6":      {en:"🔌 6 connectors (Pull + Push)", ja:"🔌 6 種コネクタ (Pull + Push)", "zh-CN":"🔌 6 个连接器 (Pull + Push)", ko:"🔌 6 종 커넥터 (Pull + Push)", es:"🔌 6 conectores (Pull + Push)", fr:"🔌 6 connecteurs (Pull + Push)", de:"🔌 6 Konnektoren (Pull + Push)", "pt-BR":"🔌 6 conectores (Pull + Push)"},
    "chip.parsers":    {en:"📄 PDF · Word · Excel · PowerPoint", ja:"📄 PDF · Word · Excel · PowerPoint", "zh-CN":"📄 PDF · Word · Excel · PowerPoint", ko:"📄 PDF · Word · Excel · PowerPoint", es:"📄 PDF · Word · Excel · PowerPoint", fr:"📄 PDF · Word · Excel · PowerPoint", de:"📄 PDF · Word · Excel · PowerPoint", "pt-BR":"📄 PDF · Word · Excel · PowerPoint"},
    "chip.exporters":  {en:"🖨 HTML / PPTX / DOCX output", ja:"🖨 HTML / PPTX / DOCX 出力", "zh-CN":"🖨 HTML / PPTX / DOCX 输出", ko:"🖨 HTML / PPTX / DOCX 출력", es:"🖨 Salida HTML / PPTX / DOCX", fr:"🖨 Sortie HTML / PPTX / DOCX", de:"🖨 HTML / PPTX / DOCX-Ausgabe", "pt-BR":"🖨 Saída HTML / PPTX / DOCX"},
    "chip.voice":      {en:"🎙 Voice in / out (STT + TTS)", ja:"🎙 音声入出力 (STT + TTS)", "zh-CN":"🎙 语音输入/输出 (STT + TTS)", ko:"🎙 음성 입출력 (STT + TTS)", es:"🎙 Voz entrada/salida (STT + TTS)", fr:"🎙 Voix E/S (STT + TTS)", de:"🎙 Sprache I/O (STT + TTS)", "pt-BR":"🎙 Voz entrada/saída (STT + TTS)"},
    "chip.memmode":    {en:"🪪 Memory mode (accumulate / read-only)", ja:"🪪 メモリモード (accumulate / read-only)", "zh-CN":"🪪 记忆模式 (accumulate / read-only)", ko:"🪪 메모리 모드 (accumulate / read-only)", es:"🪪 Modo memoria (accumulate / read-only)", fr:"🪪 Mode mémoire (accumulate / read-only)", de:"🪪 Speichermodus (accumulate / read-only)", "pt-BR":"🪪 Modo memória (accumulate / read-only)"},
    "chip.sdk":        {en:"🌐 SDK · Streamlit UI · FastAPI HTTP", ja:"🌐 SDK · Streamlit UI · FastAPI HTTP", "zh-CN":"🌐 SDK · Streamlit UI · FastAPI HTTP", ko:"🌐 SDK · Streamlit UI · FastAPI HTTP", es:"🌐 SDK · Streamlit UI · FastAPI HTTP", fr:"🌐 SDK · Streamlit UI · FastAPI HTTP", de:"🌐 SDK · Streamlit UI · FastAPI HTTP", "pt-BR":"🌐 SDK · Streamlit UI · FastAPI HTTP"},
    "chip.kms":        {en:"🔑 KMS-backed encryption (AWS / Azure / GCP / Vault)", ja:"🔑 KMS ベース暗号化 (AWS / Azure / GCP / Vault)", "zh-CN":"🔑 KMS 加密 (AWS / Azure / GCP / Vault)", ko:"🔑 KMS 기반 암호화 (AWS / Azure / GCP / Vault)", es:"🔑 Cifrado KMS (AWS / Azure / GCP / Vault)", fr:"🔑 Chiffrement KMS (AWS / Azure / GCP / Vault)", de:"🔑 KMS-Verschlüsselung (AWS / Azure / GCP / Vault)", "pt-BR":"🔑 Criptografia KMS (AWS / Azure / GCP / Vault)"},
    "chip.ab":         {en:"⚖️ A/B experiments + LLM-quality eval", ja:"⚖️ A/B 実験 + LLM 品質評価", "zh-CN":"⚖️ A/B 实验 + LLM 质量评估", ko:"⚖️ A/B 실험 + LLM 품질 평가", es:"⚖️ Experimentos A/B + eval calidad LLM", fr:"⚖️ Expériences A/B + éval qualité LLM", de:"⚖️ A/B-Experimente + LLM-Qualitätsbewertung", "pt-BR":"⚖️ Experimentos A/B + avaliação LLM"},
    "chip.mcp":        {en:"🪐 MCP (stdio + remote HTTP/SSE)", ja:"🪐 MCP (stdio + リモート HTTP/SSE)", "zh-CN":"🪐 MCP (stdio + 远程 HTTP/SSE)", ko:"🪐 MCP (stdio + 원격 HTTP/SSE)", es:"🪐 MCP (stdio + HTTP/SSE remoto)", fr:"🪐 MCP (stdio + HTTP/SSE distant)", de:"🪐 MCP (stdio + Remote HTTP/SSE)", "pt-BR":"🪐 MCP (stdio + HTTP/SSE remoto)"},
    "chip.conn20":     {en:"🔗 20 connectors (Box / Notion / Slack / Jira / GitHub / S3 / …)", ja:"🔗 20 種コネクタ (Box / Notion / Slack / Jira / GitHub / S3 等)", "zh-CN":"🔗 20 个连接器 (Box / Notion / Slack / Jira / GitHub / S3 等)", ko:"🔗 20 종 커넥터 (Box / Notion / Slack / Jira / GitHub / S3 등)", es:"🔗 20 conectores (Box / Notion / Slack / Jira / GitHub / S3 / …)", fr:"🔗 20 connecteurs (Box / Notion / Slack / Jira / GitHub / S3 / …)", de:"🔗 20 Konnektoren (Box / Notion / Slack / Jira / GitHub / S3 / …)", "pt-BR":"🔗 20 conectores (Box / Notion / Slack / Jira / GitHub / S3 / …)"},
    "chip.responsive": {en:"📱 Mobile-responsive", ja:"📱 モバイル対応", "zh-CN":"📱 移动响应式", ko:"📱 모바일 반응형", es:"📱 Responsive móvil", fr:"📱 Responsive mobile", de:"📱 Mobile-responsive", "pt-BR":"📱 Responsivo móvel"},
    "chip.agent":      {en:"🤖 Autonomous agent (Claude-Code-style)", ja:"🤖 自律エージェント (ClaudeCode 同等)", "zh-CN":"🤖 自主代理 (Claude-Code 风格)", ko:"🤖 자율 에이전트 (Claude-Code 스타일)", es:"🤖 Agente autónomo (estilo Claude-Code)", fr:"🤖 Agent autonome (style Claude-Code)", de:"🤖 Autonomer Agent (Claude-Code-Stil)", "pt-BR":"🤖 Agente autônomo (estilo Claude-Code)"},
    "chip.tests":      {en:"✅ 428 regression tests", ja:"✅ 428 件のリグレッションテスト", "zh-CN":"✅ 428 项回归测试", ko:"✅ 428 개 회귀 테스트", es:"✅ 428 tests de regresión", fr:"✅ 428 tests de régression", de:"✅ 428 Regressionstests", "pt-BR":"✅ 428 testes de regressão"},

    // ===== Feature card body texts (36 — concise summaries per locale) ======
    "feat.memory_loop.body":        {en:"Senior staff's \"magic prompts\" auto-promote into shared knowledge via three independent paths: frequency, outcome correlation, and LLM self-eval.", ja:"ベテランの「効くプロンプト」が頻度・成果連動・LLM 自己評価の 3 経路で自動的に組織知へ昇格。", "zh-CN":"资深员工的「魔法提示词」通过频率/成果关联/LLM 自评 3 条路径自动晋升为共享知识。", ko:"베테랑의 「잘 듣는 프롬프트」가 빈도·성과 연동·LLM 자가평가 3 경로로 조직 지식으로 자동 승격.", es:"Los \"prompts mágicos\" del personal sénior se promueven automáticamente al saber compartido por 3 vías: frecuencia, correlación de resultados y autoevaluación LLM.", fr:"Les \"prompts magiques\" des seniors se promeuvent automatiquement en savoir partagé par 3 voies : fréquence, corrélation des résultats et auto-évaluation LLM.", de:"Die magischen Prompts der erfahrenen Mitarbeiter werden über 3 unabhängige Pfade automatisch in geteiltes Wissen befördert: Häufigkeit, Ergebniskorrelation, LLM-Selbstbewertung.", "pt-BR":"Os \"prompts mágicos\" do pessoal sênior se promovem automaticamente para conhecimento compartilhado via 3 caminhos: frequência, correlação de resultado e autoavaliação LLM."},
    "feat.promotion_engine.body":   {en:"Frequency-based, outcome-correlated, LLM-scored. Run in parallel — never depending on a single signal. Configurable thresholds for auto-promote vs review.", ja:"頻度・成果連動・LLM スコアの 3 経路を並走。単一シグナル依存にせず、自動昇格 vs レビューの閾値を設定可能。", "zh-CN":"基于频率、成果关联、LLM 评分,并行运行 — 不依赖单一信号。可配置自动晋升 vs 审查阈值。", ko:"빈도·성과 연동·LLM 점수의 3 경로를 병행. 단일 신호 의존 회피, 자동 승격 vs 검토 임계값 설정 가능.", es:"Basado en frecuencia, correlacionado con resultados, puntuado por LLM. Se ejecutan en paralelo, sin depender de una sola señal. Umbrales configurables para auto-promoción vs revisión.", fr:"Basé sur la fréquence, corrélé aux résultats, noté par LLM. Exécution en parallèle, jamais dépendant d'un seul signal. Seuils configurables pour auto-promotion vs révision.", de:"Häufigkeitsbasiert, ergebniskorreliert, LLM-bewertet. Parallel ausgeführt – nie abhängig von einem einzelnen Signal. Konfigurierbare Schwellenwerte für Auto-Beförderung vs. Review.", "pt-BR":"Baseado em frequência, correlacionado a resultado, pontuado por LLM. Em paralelo — nunca dependendo de um único sinal. Limiares configuráveis para auto-promoção vs revisão."},
    "feat.workflow_flows.body":     {en:"Sales prep, logic checking, RAG self-correction — three production-ready multi-agent pipelines that run in 5 minutes. No bespoke orchestration code required.", ja:"営業準備・論理整合・RAG 自己修復の 3 本番向けマルチエージェントパイプラインを 5 分で実行。独自の調整コード不要。", "zh-CN":"销售准备、逻辑检查、RAG 自我纠正 — 3 条生产级多代理流水线 5 分钟即跑。无需定制编排代码。", ko:"영업 준비·논리 검증·RAG 자가 수정 — 5 분에 실행 가능한 프로덕션급 멀티 에이전트 파이프라인 3 종. 별도 조정 코드 불필요.", es:"Preparación de ventas, comprobación lógica, auto-corrección RAG — 3 pipelines multi-agente listos para producción que se ejecutan en 5 minutos. Sin código de orquestación a medida.", fr:"Préparation commerciale, vérification logique, auto-correction RAG — 3 pipelines multi-agents prêts pour la production, exécutables en 5 minutes. Aucun code d'orchestration sur mesure requis.", de:"Vertriebsvorbereitung, Logikprüfung, RAG-Selbstkorrektur – 3 produktionsreife Multi-Agent-Pipelines, in 5 Minuten ausführbar. Kein maßgeschneiderter Orchestrierungscode nötig.", "pt-BR":"Preparação de vendas, verificação lógica, autocorreção RAG — 3 pipelines multi-agente prontos para produção em 5 minutos. Sem código de orquestração sob medida."},
    "feat.business_skills.body":    {en:"Investment, sales, design, purchasing, patent, legal — domain-tuned agents with built-in guardrails (tax law, jurisdictional caveats, hallucination guards).", ja:"投資・営業・設計・購買・特許・法務 — 各業務向けに調整、税法・管轄注意・ハルシネーション防止のガードレール組込済。", "zh-CN":"投资、销售、设计、采购、专利、法务 — 领域调优代理,内置护栏(税法/管辖警示/幻觉防护)。", ko:"투자·영업·설계·구매·특허·법무 — 도메인 조정 에이전트, 가드레일 (세법·관할 주의·환각 방지) 내장.", es:"Inversión, ventas, diseño, compras, patentes, legal — agentes ajustados al dominio con guardarraíles incorporados (ley fiscal, salvedades jurisdiccionales, anti-alucinación).", fr:"Investissement, ventes, design, achats, brevets, juridique — agents adaptés au domaine avec garde-fous intégrés (droit fiscal, avertissements juridictionnels, anti-hallucination).", de:"Investment, Vertrieb, Design, Einkauf, Patent, Recht — domänenangepasste Agenten mit integrierten Leitplanken (Steuerrecht, Zuständigkeitshinweise, Halluzinationsschutz).", "pt-BR":"Investimento, vendas, design, compras, patente, jurídico — agentes ajustados ao domínio com guardrails integrados (direito tributário, ressalvas jurisdicionais, anti-alucinação)."},
    "feat.evidence.body":           {en:"Sentence-level hallucination detection and retrieval metrics ship as first-class modules. \"It works\" comes with proof attached.", ja:"文単位ハルシネーション検知と検索メトリクスを標準モジュールで同梱。「効く」根拠を必ず添付。", "zh-CN":"句级幻觉检测与检索指标作为一等模块同捆。「能用」附带证据。", ko:"문장 단위 환각 감지와 검색 지표를 일급 모듈로 동봉. 「작동」에 증거가 따라옴.", es:"Detección de alucinaciones a nivel de frase y métricas de recuperación como módulos de primera clase. \"Funciona\" viene con pruebas adjuntas.", fr:"Détection d'hallucination au niveau de la phrase et métriques de récupération en modules de première classe. « Ça marche » avec preuves jointes.", de:"Halluzinationserkennung auf Satzebene und Retrieval-Metriken als First-Class-Module. Es funktioniert kommt mit Belegen.", "pt-BR":"Detecção de alucinação em nível de frase e métricas de recuperação como módulos de primeira classe. \"Funciona\" vem com provas anexadas."},
    "feat.ltm_backends.body":       {en:"JSON, Mem0, LangMem, Letta, Zep, HindSight — switch with one line. Plus Graph layer (optional) for relationship-heavy domains. Zero vendor lock-in.", ja:"JSON / Mem0 / LangMem / Letta / Zep / HindSight を 1 行で切替。関係性重視の領域には Graph 層 (任意)。ベンダーロックイン無し。", "zh-CN":"JSON / Mem0 / LangMem / Letta / Zep / HindSight 一行切换。关系密集领域加 Graph 层(可选)。零厂商锁定。", ko:"JSON / Mem0 / LangMem / Letta / Zep / HindSight 한 줄로 전환. 관계 중심 영역에는 Graph 레이어 (옵션). 벤더 락인 없음.", es:"JSON / Mem0 / LangMem / Letta / Zep / HindSight — cambio en una línea. Más capa Graph (opcional) para dominios relacionales. Cero bloqueo de proveedor.", fr:"JSON / Mem0 / LangMem / Letta / Zep / HindSight — changement en une ligne. Plus couche Graph (optionnelle) pour les domaines relationnels. Zéro verrou fournisseur.", de:"JSON / Mem0 / LangMem / Letta / Zep / HindSight — Wechsel mit einer Zeile. Plus Graph-Schicht (optional) für beziehungsintensive Domänen. Null Vendor-Lock-in.", "pt-BR":"JSON / Mem0 / LangMem / Letta / Zep / HindSight — troca em uma linha. Mais camada Graph (opcional) para domínios relacionais. Zero lock-in."},
    "feat.multi_llm.body":          {en:"Claude, ChatGPT, Gemini, Qwen-API, Qwen-local (Ollama) + 100+ via LiteLLM. Auto-detect from env vars; switch model per-call.", ja:"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + LiteLLM 経由で 100+。環境変数自動検出、呼出単位で切替可能。", "zh-CN":"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + LiteLLM 100+。从环境变量自动检测,每次调用切换模型。", ko:"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + LiteLLM 100+. 환경변수 자동 감지, 호출 단위 모델 전환.", es:"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + 100+ vía LiteLLM. Auto-detección desde variables de entorno; cambio por llamada.", fr:"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + 100+ via LiteLLM. Détection automatique depuis les variables d'env ; changement par appel.", de:"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + 100+ via LiteLLM. Automatische Erkennung aus Umgebungsvariablen; Modellwechsel pro Aufruf.", "pt-BR":"Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama) + 100+ via LiteLLM. Auto-detecção de variáveis de ambiente; troca por chamada."},
    "feat.auth_in_oss.body":        {en:"API key + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 default roles + append-only audit log. Most competitors paywall this.", ja:"API キー + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 既定ロール + 追記専用監査ログ。多くの競合は有償化。", "zh-CN":"API 密钥 + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 默认角色 + 追加专属审计日志。多数竞品付费。", ko:"API 키 + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 기본 4 역할 + 추가 전용 감사 로그. 대부분 경쟁사는 유료.", es:"Clave API + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 roles por defecto + log de auditoría solo append. La mayoría de competidores cobran por esto.", fr:"Clé API + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 rôles par défaut + journal d'audit append-only. La plupart des concurrents le facturent.", de:"API-Key + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 Standard-Rollen + Append-only-Audit-Log. Die meisten Konkurrenten verlangen dafür Geld.", "pt-BR":"API key + JWT + OIDC (Google/MS/Okta/GitHub/Keycloak) + 4 papéis padrão + log de auditoria append-only. A maioria dos concorrentes cobra por isso."},
    "feat.skills_promoted.body":    {en:"Not just memory — your personal skills get tracked, scored, and promoted to the org skill catalog when they prove themselves.", ja:"メモリだけでなく — 個人スキルも追跡・スコア化・組織スキルカタログへ昇格 (実績を満たしたら)。", "zh-CN":"不只是记忆 — 个人技能被追踪、评分,达标后晋升至组织技能目录。", ko:"메모리뿐 아니라 — 개인 스킬도 추적·점수화·조직 스킬 카탈로그로 승격 (실적 충족 시).", es:"No solo memoria — tus habilidades personales se rastrean, puntúan y promueven al catálogo de la organización cuando se prueban.", fr:"Pas seulement la mémoire — vos compétences personnelles sont suivies, notées et promues au catalogue org quand elles font leurs preuves.", de:"Nicht nur Speicher — deine persönlichen Skills werden getrackt, bewertet und in den Org-Skill-Katalog befördert, wenn sie sich bewähren.", "pt-BR":"Não só memória — suas habilidades pessoais são rastreadas, pontuadas e promovidas ao catálogo da organização quando comprovadas."},
    "feat.mcp_compat.body":         {en:"Skills serialize to standard <code>SKILL.md</code>. Drop into Claude Skills, Cursor Skills, or any MCP-compatible registry without code changes.", ja:"スキルは標準 <code>SKILL.md</code> 形式でシリアライズ。Claude Skills / Cursor Skills / MCP 互換レジストリにコード変更なしで投入可能。", "zh-CN":"技能序列化为标准 <code>SKILL.md</code>。无需改代码即可投入 Claude Skills / Cursor Skills / 任何 MCP 兼容注册表。", ko:"스킬은 표준 <code>SKILL.md</code> 형식으로 직렬화. Claude Skills / Cursor Skills / MCP 호환 레지스트리에 코드 변경 없이 투입 가능.", es:"Las habilidades se serializan al formato estándar <code>SKILL.md</code>. Insértalas en Claude Skills, Cursor Skills o cualquier registro compatible con MCP sin cambios de código.", fr:"Les compétences sont sérialisées au format standard <code>SKILL.md</code>. Intégrez-les dans Claude Skills, Cursor Skills ou tout registre MCP sans modification de code.", de:"Skills werden in standardisiertes <code>SKILL.md</code> serialisiert. In Claude Skills, Cursor Skills oder jede MCP-kompatible Registry ohne Codeänderungen einsetzbar.", "pt-BR":"As habilidades são serializadas em <code>SKILL.md</code> padrão. Insira em Claude Skills, Cursor Skills ou qualquer registro compatível com MCP sem alterar código."},
    "feat.outcome_tracking.body":   {en:"<code>record_outcome()</code> attaches success/failure to episodes. The consolidator uses these signals statistically — no separate analytics pipeline needed.", ja:"<code>record_outcome()</code> で成功/失敗をエピソードに紐付け。Consolidator が統計的に活用 — 別途アナリティクス基盤不要。", "zh-CN":"<code>record_outcome()</code> 将成功/失败附加到回合。Consolidator 统计性使用 — 无需独立分析管道。", ko:"<code>record_outcome()</code> 로 성공/실패를 에피소드에 연결. Consolidator 가 통계적으로 활용 — 별도 분석 파이프라인 불필요.", es:"<code>record_outcome()</code> adjunta éxito/fracaso a los episodios. El consolidador los usa estadísticamente — sin necesidad de un pipeline analítico aparte.", fr:"<code>record_outcome()</code> attache succès/échec aux épisodes. Le consolidateur les utilise statistiquement — pas de pipeline analytique séparé.", de:"<code>record_outcome()</code> hängt Erfolg/Misserfolg an Episoden. Der Consolidator nutzt diese Signale statistisch – keine separate Analytics-Pipeline nötig.", "pt-BR":"<code>record_outcome()</code> anexa sucesso/falha aos episódios. O consolidador os usa estatisticamente — sem pipeline analítico separado."},
    "feat.apache_open.body":        {en:"Permissive license, commercial-friendly. NOTICE.md inventories every dependency's license. Open Core path for enterprise extras planned.", ja:"寛容ライセンス、商用利用可。NOTICE.md で全依存関係のライセンスを管理。エンタープライズ拡張への Open Core パス計画中。", "zh-CN":"宽松许可证,商用友好。NOTICE.md 列出每个依赖的许可证。规划企业增强的 Open Core 路径。", ko:"관대한 라이선스, 상용 친화적. NOTICE.md 가 모든 의존성 라이선스 관리. 엔터프라이즈 확장의 Open Core 경로 계획.", es:"Licencia permisiva, apta para uso comercial. NOTICE.md inventaria la licencia de cada dependencia. Ruta Open Core para extras empresariales planificada.", fr:"Licence permissive, compatible commercial. NOTICE.md inventorie la licence de chaque dépendance. Voie Open Core prévue pour extras entreprise.", de:"Permissive Lizenz, kommerzfreundlich. NOTICE.md listet die Lizenz jeder Abhängigkeit. Open-Core-Pfad für Enterprise-Extras geplant.", "pt-BR":"Licença permissiva, amigável a uso comercial. NOTICE.md inventaria a licença de cada dependência. Caminho Open Core para extras empresariais planejado."},
    "feat.acl.body":                {en:"Glob-pattern allow / deny rules per resource type (connector, memory, prompt, skill). Built for enterprise IS departments. Every decision audit-logged.", ja:"リソース種別ごと (コネクタ/メモリ/プロンプト/スキル) に Glob パターンの allow/deny ルール。情報システム部向け設計。全判定が監査ログ化。", "zh-CN":"按资源类型(连接器/记忆/提示/技能)Glob 模式 allow/deny 规则。面向 IS 部门设计。每次判定记入审计日志。", ko:"리소스 유형별 (커넥터/메모리/프롬프트/스킬) Glob 패턴 허용/거부 규칙. 정보시스템 부서 대상 설계. 모든 판단 감사 로그화.", es:"Reglas allow/deny tipo glob por tipo de recurso (conector, memoria, prompt, habilidad). Diseñado para departamentos IS empresariales. Cada decisión auditada.", fr:"Règles glob allow/deny par type de ressource (connecteur, mémoire, prompt, compétence). Conçu pour les services SI d'entreprise. Chaque décision auditée.", de:"Glob-Muster allow/deny-Regeln pro Ressourcentyp (Konnektor, Speicher, Prompt, Skill). Für Enterprise-IT-Abteilungen entwickelt. Jede Entscheidung im Audit-Log.", "pt-BR":"Regras allow/deny estilo glob por tipo de recurso (conector, memória, prompt, habilidade). Projetado para departamentos de TI corporativa. Cada decisão auditada."},
    "feat.admin_exports.body":      {en:"CSV / JSON / JSONL exports of audit log, users, usage, memory, policies — for compliance, SIEM, backups. Each export action self-audited.", ja:"監査ログ・ユーザ・利用量・メモリ・ポリシーを CSV / JSON / JSONL でエクスポート — 法令遵守・SIEM・バックアップ用。エクスポート操作自体も監査。", "zh-CN":"审计日志、用户、用量、记忆、策略以 CSV / JSON / JSONL 导出 — 合规/SIEM/备份用途。导出操作自身也审计。", ko:"감사 로그·사용자·사용량·메모리·정책을 CSV / JSON / JSONL 로 내보내기 — 규정 준수·SIEM·백업용. 내보내기 작업 자체도 감사.", es:"Exportaciones CSV / JSON / JSONL de log de auditoría, usuarios, uso, memoria, políticas — para cumplimiento, SIEM, copias. Cada exportación se autoaudita.", fr:"Exports CSV / JSON / JSONL du journal d'audit, utilisateurs, usage, mémoire, politiques — pour conformité, SIEM, sauvegardes. Chaque export est lui-même audité.", de:"CSV / JSON / JSONL-Exporte von Audit-Log, Nutzern, Nutzung, Speicher, Richtlinien — für Compliance, SIEM, Backups. Jede Exportaktion wird selbst auditiert.", "pt-BR":"Exportações CSV / JSON / JSONL de log de auditoria, usuários, uso, memória, políticas — para conformidade, SIEM, backups. Cada exportação é auto-auditada."},
    "feat.connectors.body":         {en:"Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce — bidirectional Pull + Push. ACL-enforced before any external call.", ja:"Box / SharePoint / Dropbox / Google Drive / kintone / Salesforce の双方向 Pull + Push。外部呼出前に ACL チェック。", "zh-CN":"Box / SharePoint / Dropbox / Google Drive / kintone / Salesforce 双向 Pull + Push。任何外部调用前 ACL 强制。", ko:"Box / SharePoint / Dropbox / Google Drive / kintone / Salesforce 양방향 Pull + Push. 외부 호출 전 ACL 강제.", es:"Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce — Pull + Push bidireccional. ACL aplicado antes de cualquier llamada externa.", fr:"Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce — Pull + Push bidirectionnel. ACL appliquée avant tout appel externe.", de:"Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce — bidirektionales Pull + Push. ACL-Prüfung vor jedem externen Aufruf.", "pt-BR":"Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce — Pull + Push bidirecional. ACL aplicado antes de qualquer chamada externa."},
    "feat.dashboards.body":         {en:"Flow / skill counts, success rate, top users, promoted blocks, frozen files, distributed skills — out of the box, with no separate analytics pipeline.", ja:"フロー/スキル数・成功率・トップユーザ・昇格ブロック・凍結ファイル・配信スキル — 標準装備、別途分析基盤不要。", "zh-CN":"流程/技能次数、成功率、Top 用户、晋升块、冻结文件、分发技能 — 开箱即用,无需独立分析管道。", ko:"플로/스킬 수·성공률·Top 사용자·승격 블록·동결 파일·배포 스킬 — 기본 탑재, 별도 분석 파이프라인 불필요.", es:"Conteos de flujo/habilidad, tasa de éxito, top usuarios, bloques promovidos, archivos congelados, habilidades distribuidas — listo, sin pipeline analítico aparte.", fr:"Compteurs de flux/compétence, taux de succès, top utilisateurs, blocs promus, fichiers figés, compétences distribuées — clé en main, sans pipeline analytique séparé.", de:"Flow-/Skill-Zähler, Erfolgsrate, Top-Nutzer, beförderte Blöcke, eingefrorene Dateien, verteilte Skills — sofort einsatzbereit, ohne separate Analytics-Pipeline.", "pt-BR":"Contagens de fluxo/habilidade, taxa de sucesso, top usuários, blocos promovidos, arquivos congelados, habilidades distribuídas — pronto, sem pipeline analítico separado."},
    "feat.prompts_distribution.body":{en:"Users save personal prompts. Admins promote them to org or push to specific roles / users. Three scopes with merge precedence.", ja:"ユーザは個人プロンプトを保存。管理者が組織に昇格、またはロール/ユーザ単位で配信。3 スコープのマージ優先順位付き。", "zh-CN":"用户保存个人提示。管理员晋升至组织级或按角色/用户分发。3 作用域合并优先级。", ko:"사용자는 개인 프롬프트를 저장. 관리자가 조직으로 승격 또는 역할/사용자 단위 배포. 3 스코프 병합 우선순위.", es:"Los usuarios guardan prompts personales. Los admins los promueven a organización o los envían a roles/usuarios concretos. Tres ámbitos con precedencia de fusión.", fr:"Les utilisateurs sauvegardent des prompts personnels. Les admins les promeuvent au niveau org ou les poussent vers rôles/utilisateurs spécifiques. Trois portées avec précédence de fusion.", de:"Nutzer speichern persönliche Prompts. Admins befördern sie in die Org oder verteilen sie an Rollen/Nutzer. Drei Geltungsbereiche mit Merge-Reihenfolge.", "pt-BR":"Usuários salvam prompts pessoais. Admins os promovem ao nível da organização ou os enviam a papéis/usuários específicos. Três escopos com precedência de mesclagem."},
    "feat.user_crud.body":          {en:"Create / update / delete / deactivate / rotate keys / change roles — all via CLI, UI, or SDK. All operations audited.", ja:"作成 / 更新 / 削除 / 無効化 / キーローテ / ロール変更 — CLI / UI / SDK で実行可能。全操作監査済み。", "zh-CN":"创建/更新/删除/停用/轮换密钥/角色变更 — 通过 CLI/UI/SDK。所有操作均审计。", ko:"생성 / 업데이트 / 삭제 / 비활성화 / 키 회전 / 역할 변경 — CLI / UI / SDK 로 실행. 모든 작업 감사.", es:"Crear / actualizar / eliminar / desactivar / rotar claves / cambiar roles — vía CLI, UI o SDK. Todas las operaciones auditadas.", fr:"Créer / mettre à jour / supprimer / désactiver / faire tourner les clés / changer les rôles — via CLI, UI ou SDK. Toutes les opérations auditées.", de:"Erstellen / aktualisieren / löschen / deaktivieren / Keys rotieren / Rollen ändern — via CLI, UI oder SDK. Alle Vorgänge auditiert.", "pt-BR":"Criar / atualizar / excluir / desativar / girar chaves / mudar papéis — via CLI, UI ou SDK. Todas as operações auditadas."},
    "feat.parsers.body":            {en:"Drop a file in — auto-dispatch by extension. PDF page-by-page, Word with heading detection, Excel as Markdown tables, PowerPoint with speaker notes. Custom formats register via entry points.", ja:"ファイル投入で拡張子により自動ディスパッチ。PDF 頁単位、Word は見出し検出、Excel は Markdown テーブル、PowerPoint は発表者ノート付き。独自形式は entry-point で登録。", "zh-CN":"放入文件 — 按扩展名自动分发。PDF 逐页、Word 含标题检测、Excel 转 Markdown 表、PowerPoint 含演讲者备注。自定义格式经入口点注册。", ko:"파일 투입 시 확장자별 자동 디스패치. PDF 페이지별, Word 헤딩 감지, Excel Markdown 테이블, PowerPoint 발표자 노트 포함. 사용자 정의 형식은 entry-point 로 등록.", es:"Suelta un archivo — despacho automático por extensión. PDF página a página, Word con detección de encabezados, Excel como tablas Markdown, PowerPoint con notas. Formatos personalizados se registran vía entry points.", fr:"Déposez un fichier — dispatch auto par extension. PDF page par page, Word avec détection de titres, Excel en tableaux Markdown, PowerPoint avec notes du présentateur. Formats personnalisés via entry points.", de:"Datei ablegen — automatischer Dispatch nach Erweiterung. PDF seitenweise, Word mit Heading-Erkennung, Excel als Markdown-Tabellen, PowerPoint mit Sprechernotizen. Eigene Formate via Entry Points registrierbar.", "pt-BR":"Solte um arquivo — despacho automático por extensão. PDF página a página, Word com detecção de cabeçalhos, Excel como tabelas Markdown, PowerPoint com notas do apresentador. Formatos próprios via entry points."},
    "feat.voice.body":              {en:"Speech-to-text (Whisper) and text-to-speech (OpenAI TTS / ElevenLabs / Piper). Embedded in Streamlit UI as record-and-go input and read-aloud output.", ja:"STT (Whisper) と TTS (OpenAI TTS / ElevenLabs / Piper)。Streamlit UI に録音入力と読み上げ出力として統合。", "zh-CN":"STT (Whisper) 与 TTS (OpenAI TTS / ElevenLabs / Piper)。Streamlit UI 内置录音输入和朗读输出。", ko:"STT (Whisper) 와 TTS (OpenAI TTS / ElevenLabs / Piper). Streamlit UI 에 녹음 입력과 낭독 출력으로 내장.", es:"Voz a texto (Whisper) y texto a voz (OpenAI TTS / ElevenLabs / Piper). Integrado en Streamlit UI como entrada por grabación y salida en lectura.", fr:"Voix vers texte (Whisper) et texte vers voix (OpenAI TTS / ElevenLabs / Piper). Intégré dans l'UI Streamlit en entrée enregistrée et sortie lecture.", de:"Sprache-zu-Text (Whisper) und Text-zu-Sprache (OpenAI TTS / ElevenLabs / Piper). In Streamlit-UI als Aufnahme-Eingabe und Vorlese-Ausgabe integriert.", "pt-BR":"Fala-para-texto (Whisper) e texto-para-fala (OpenAI TTS / ElevenLabs / Piper). Integrado na UI Streamlit como entrada por gravação e saída por leitura."},
    "feat.user_oauth.body":         {en:"Each Praxia user authorizes Box / SharePoint / Dropbox / Drive / Salesforce with their <em>own</em> credentials. The external system's native ACL is enforced per Praxia user — alice can only see what alice has access to.", ja:"各 Praxia ユーザが Box / SharePoint / Dropbox / Drive / Salesforce を自分の認証情報で認可。外部システム側 ACL がユーザ単位で適用 — alice は alice がアクセス可能な情報のみ見える。", "zh-CN":"每个 Praxia 用户用自己的凭据授权 Box / SharePoint / Dropbox / Drive / Salesforce。外部系统原生 ACL 按用户强制 — alice 只见 alice 有权访问的内容。", ko:"각 Praxia 사용자가 Box / SharePoint / Dropbox / Drive / Salesforce 를 본인의 자격으로 인가. 외부 시스템 ACL 이 사용자별 적용 — alice 는 alice 접근 가능 정보만 표시.", es:"Cada usuario de Praxia autoriza Box / SharePoint / Dropbox / Drive / Salesforce con sus <em>propias</em> credenciales. La ACL nativa del sistema externo se aplica por usuario — alice solo ve lo que alice puede ver.", fr:"Chaque utilisateur Praxia autorise Box / SharePoint / Dropbox / Drive / Salesforce avec ses <em>propres</em> identifiants. L'ACL native du système externe s'applique par utilisateur — alice ne voit que ce qu'alice peut voir.", de:"Jeder Praxia-Nutzer autorisiert Box / SharePoint / Dropbox / Drive / Salesforce mit seinen <em>eigenen</em> Zugangsdaten. Die native ACL des externen Systems wird pro Nutzer durchgesetzt — alice sieht nur, was alice sehen darf.", "pt-BR":"Cada usuário Praxia autoriza Box / SharePoint / Dropbox / Drive / Salesforce com suas <em>próprias</em> credenciais. A ACL nativa do sistema externo é aplicada por usuário — alice só vê o que alice pode ver."},
    "feat.legal_templates.body":    {en:"Terms of Service, Privacy Policy, Acceptable Use, Cookie Policy — starter templates wired into the portal sign-up. Marked clearly as templates requiring legal review before commercial use.", ja:"利用規約・プライバシーポリシー・利用規定・クッキーポリシー — ポータルサインアップに組込済のスターターテンプレ。商用利用前の法務レビュー必須を明記。", "zh-CN":"服务条款/隐私政策/可接受使用/Cookie 政策 — 入门模板已接入门户注册。明确标注商用前需法务审阅。", ko:"이용약관·개인정보보호정책·이용규정·쿠키정책 — 포털 가입에 통합된 스타터 템플릿. 상용 전 법무 검토 필수 명시.", es:"Términos de servicio, Política de privacidad, Uso aceptable, Política de cookies — plantillas iniciales conectadas al alta del portal. Marcadas como plantillas que requieren revisión legal antes de uso comercial.", fr:"Conditions d'utilisation, politique de confidentialité, usage acceptable, politique cookies — modèles de départ liés à l'inscription portail. Clairement marqués comme modèles nécessitant une revue juridique avant usage commercial.", de:"Nutzungsbedingungen, Datenschutzerklärung, Acceptable Use, Cookie-Richtlinie — Starter-Vorlagen in die Portal-Registrierung integriert. Klar als Vorlagen markiert, die vor kommerzieller Nutzung rechtlich geprüft werden müssen.", "pt-BR":"Termos de Serviço, Política de Privacidade, Uso Aceitável, Política de Cookies — modelos iniciais ligados ao cadastro do portal. Marcados claramente como modelos que requerem revisão jurídica antes de uso comercial."},
    "feat.multi_ltm.body":          {en:"Run several LTMs in parallel and fuse with Reciprocal Rank Fusion — or route per query (temporal → Zep, audit → JSON, entity → Mem0). English + Japanese keyword detection. Higher recall without picking a winner.", ja:"複数 LTM を並列実行し RRF で融合 — または質問単位ルーティング (時系列→Zep / 監査→JSON / エンティティ→Mem0)。英日キーワード検出。一つに絞らず高再現率。", "zh-CN":"多个 LTM 并行运行并以 RRF 融合 — 或按查询路由(时序→Zep / 审计→JSON / 实体→Mem0)。英日关键词检测。不必择一即可提高召回。", ko:"여러 LTM 을 병렬 실행하고 RRF 로 융합 — 또는 질의별 라우팅 (시계열 → Zep / 감사 → JSON / 엔티티 → Mem0). 영일 키워드 감지. 하나로 고르지 않아도 높은 재현율.", es:"Ejecuta varios LTM en paralelo y fusiona con RRF — o enruta por consulta (temporal → Zep, auditoría → JSON, entidad → Mem0). Detección de palabras clave inglés + japonés. Mayor recall sin elegir un único ganador.", fr:"Exécutez plusieurs LTM en parallèle et fusionnez avec RRF — ou routez par requête (temporel → Zep, audit → JSON, entité → Mem0). Détection de mots-clés EN + JA. Meilleur recall sans devoir choisir un gagnant.", de:"Mehrere LTMs parallel ausführen und mit RRF fusionieren — oder pro Anfrage routen (zeitlich → Zep, Audit → JSON, Entität → Mem0). Schlüsselworterkennung Englisch + Japanisch. Höhere Recall-Rate, ohne einen Gewinner küren zu müssen.", "pt-BR":"Execute vários LTMs em paralelo e funda com RRF — ou roteie por consulta (temporal → Zep, auditoria → JSON, entidade → Mem0). Detecção de palavras-chave EN + JA. Maior recall sem precisar eleger um único."},
    "feat.memory_mode.body":        {en:"Per-user switch: <code>accumulate</code> (default) or <code>read_only</code>. Read-only sessions silently drop writes — useful for sensitive content. Admins can lock the mode tenant-wide or by role.", ja:"ユーザ毎に <code>accumulate</code> (既定) / <code>read_only</code> 切替。read-only は書込を黙って破棄 — 機微情報利用時に有用。管理者がテナント全体やロール単位でロック可能。", "zh-CN":"每用户切换 <code>accumulate</code>(默认)/<code>read_only</code>。read-only 静默丢弃写入 — 适合敏感内容。管理员可按租户/角色锁定。", ko:"사용자별 <code>accumulate</code> (기본) / <code>read_only</code> 전환. read-only 는 쓰기 무음 폐기 — 민감 정보 처리 시 유용. 관리자가 테넌트 전체 또는 역할 단위로 잠금 가능.", es:"Conmutador por usuario: <code>accumulate</code> (por defecto) o <code>read_only</code>. Las sesiones de solo lectura descartan silenciosamente las escrituras — útil para contenido sensible. Los admins pueden bloquear el modo a nivel de tenant o por rol.", fr:"Bascule par utilisateur : <code>accumulate</code> (par défaut) ou <code>read_only</code>. Les sessions read-only abandonnent silencieusement les écritures — utile pour contenu sensible. Les admins peuvent verrouiller le mode au niveau tenant ou par rôle.", de:"Pro-Nutzer-Schalter: <code>accumulate</code> (Standard) oder <code>read_only</code>. Read-only-Sessions verwerfen Schreibzugriffe stillschweigend — nützlich für sensible Inhalte. Admins können den Modus tenantweit oder pro Rolle sperren.", "pt-BR":"Alternância por usuário: <code>accumulate</code> (padrão) ou <code>read_only</code>. Sessões read-only descartam escritas silenciosamente — útil para conteúdo sensível. Admins podem travar o modo no tenant ou por papel."},
    "feat.admin_ltm.body":          {en:"Pin which backend(s) users may pick and what the default mode is, at the tenant level. Resolution: admin enforced &gt; call-site &gt; user pref &gt; admin default.", ja:"テナント単位で利用可能バックエンドと既定モードを固定。解決順: admin 強制 &gt; 呼出側 &gt; ユーザ設定 &gt; admin 既定。", "zh-CN":"按租户固定可选后端与默认模式。解析顺序:admin 强制 &gt; 调用处 &gt; 用户偏好 &gt; admin 默认。", ko:"테넌트 단위로 선택 가능 백엔드와 기본 모드 고정. 해결 순서: admin 강제 &gt; 호출측 &gt; 사용자 설정 &gt; admin 기본.", es:"Fija qué backends pueden elegir los usuarios y cuál es el modo por defecto a nivel de tenant. Resolución: admin forzado &gt; sitio de llamada &gt; pref usuario &gt; admin por defecto.", fr:"Verrouillez les backends choisissables par les utilisateurs et le mode par défaut au niveau tenant. Résolution : admin forcé &gt; appelant &gt; préf utilisateur &gt; admin par défaut.", de:"Auf Tenant-Ebene festlegen, welche Backends Nutzer wählen dürfen und was der Standardmodus ist. Auflösung: admin erzwungen &gt; Aufrufstelle &gt; Nutzerpräferenz &gt; admin-Standard.", "pt-BR":"Fixe quais backends os usuários podem escolher e qual o modo padrão no nível do tenant. Resolução: admin forçado &gt; chamada &gt; pref do usuário &gt; admin padrão."},
    "feat.exporters.body":          {en:"Skills produce Markdown by default. <code>OutputFormatSkill</code> infers requested format from natural-language hints (\"パワポで\" → PPTX, \"as a Word doc\" → DOCX). Custom formats register via entry-point.", ja:"スキルは既定で Markdown 出力。<code>OutputFormatSkill</code> が自然言語ヒント (「パワポで」→ PPTX、\"as a Word doc\" → DOCX) から要求形式を推定。独自形式は entry-point で登録。", "zh-CN":"技能默认输出 Markdown。<code>OutputFormatSkill</code> 从自然语言提示推断格式(「パワポで」→ PPTX、\"as a Word doc\" → DOCX)。自定义格式经入口点注册。", ko:"스킬은 기본 Markdown 출력. <code>OutputFormatSkill</code> 가 자연어 힌트로 형식 추정 (「パワポで」 → PPTX, \"as a Word doc\" → DOCX). 사용자 정의 형식은 entry-point 등록.", es:"Las habilidades generan Markdown por defecto. <code>OutputFormatSkill</code> infiere el formato solicitado a partir de pistas en lenguaje natural (\"パワポで\" → PPTX, \"as a Word doc\" → DOCX). Formatos personalizados se registran vía entry-point.", fr:"Les compétences produisent du Markdown par défaut. <code>OutputFormatSkill</code> infère le format demandé d'après des indices en langage naturel (\"パワポで\" → PPTX, \"as a Word doc\" → DOCX). Formats personnalisés via entry-point.", de:"Skills erzeugen standardmäßig Markdown. <code>OutputFormatSkill</code> leitet das gewünschte Format aus natürlichsprachlichen Hinweisen ab (\"パワポで\" → PPTX, \"as a Word doc\" → DOCX). Eigene Formate via Entry-Point.", "pt-BR":"Habilidades produzem Markdown por padrão. <code>OutputFormatSkill</code> infere o formato a partir de pistas em linguagem natural (\"パワポで\" → PPTX, \"as a Word doc\" → DOCX). Formatos próprios via entry-point."},
    "feat.gemma.body":              {en:"Google's open-weight family added. <code>gemma</code> / <code>gemma-2b</code> / <code>gemma-9b</code> / <code>gemma-27b</code> via local Ollama; <code>gemma-cloud</code> via Google Vertex AI.", ja:"Google のオープンウェイト系を追加。<code>gemma</code> / <code>gemma-2b/9b/27b</code> はローカル Ollama、<code>gemma-cloud</code> は Google Vertex AI。", "zh-CN":"加入 Google 开放权重家族。<code>gemma</code> / <code>gemma-2b/9b/27b</code> 通过本地 Ollama,<code>gemma-cloud</code> 通过 Google Vertex AI。", ko:"Google 의 오픈 가중치 패밀리 추가. <code>gemma</code> / <code>gemma-2b/9b/27b</code> 는 로컬 Ollama, <code>gemma-cloud</code> 는 Google Vertex AI.", es:"Familia de pesos abiertos de Google añadida. <code>gemma</code> / <code>gemma-2b</code> / <code>gemma-9b</code> / <code>gemma-27b</code> vía Ollama local; <code>gemma-cloud</code> vía Google Vertex AI.", fr:"Famille de poids ouverts de Google ajoutée. <code>gemma</code> / <code>gemma-2b/9b/27b</code> via Ollama local ; <code>gemma-cloud</code> via Google Vertex AI.", de:"Googles Open-Weight-Familie hinzugefügt. <code>gemma</code> / <code>gemma-2b/9b/27b</code> via lokalem Ollama; <code>gemma-cloud</code> via Google Vertex AI.", "pt-BR":"Família de pesos abertos do Google adicionada. <code>gemma</code> / <code>gemma-2b/9b/27b</code> via Ollama local; <code>gemma-cloud</code> via Google Vertex AI."},
    "feat.deploy_modes.body":       {en:"Use Praxia as a brain behind your own frontend (SDK embed or <code>praxia serve</code> FastAPI HTTP API), or run the bundled Streamlit UI for the fastest path. Same auth, memory, skills.", ja:"独自フロントエンドの裏側として利用 (SDK 埋込 or <code>praxia serve</code> の FastAPI HTTP API) するか、最短経路で同梱 Streamlit UI を起動。認証/メモリ/スキルは共通。", "zh-CN":"作为自有前端背后的大脑使用(SDK 嵌入或 <code>praxia serve</code> FastAPI HTTP API),或运行内置 Streamlit UI 走最短路径。认证/记忆/技能共通。", ko:"자체 프런트엔드 뒤편의 두뇌로 사용 (SDK 임베드 또는 <code>praxia serve</code> FastAPI HTTP API) 하거나, 동봉된 Streamlit UI 로 최단 경로 실행. 인증/메모리/스킬 공통.", es:"Usa Praxia como cerebro detrás de tu propio frontend (SDK embebido o <code>praxia serve</code> FastAPI HTTP API), o lanza la UI Streamlit incluida para el camino más rápido. Mismos auth, memoria, habilidades.", fr:"Utilisez Praxia comme cerveau derrière votre propre frontend (SDK intégré ou <code>praxia serve</code> FastAPI HTTP API), ou lancez l'UI Streamlit incluse pour le chemin le plus court. Même auth, mémoire, compétences.", de:"Praxia als Gehirn hinter eigener Frontend nutzen (SDK eingebettet oder <code>praxia serve</code> FastAPI HTTP-API) oder die mitgelieferte Streamlit-UI für den schnellsten Weg. Gleiche Auth, Speicher, Skills.", "pt-BR":"Use o Praxia como cérebro atrás do seu próprio frontend (SDK embutido ou <code>praxia serve</code> FastAPI HTTP API), ou rode a UI Streamlit incluída para o caminho mais curto. Mesma auth, memória, habilidades."},
    "feat.specs.body":              {en:"Basic design / I/F spec / detailed design as procurement-ready documents in both English and Japanese. Every public surface and plugin protocol covered.", ja:"基本設計 / I/F 仕様 / 詳細設計を調達対応の英日 2 言語ドキュメントで提供。全公開 API とプラグインプロトコルを網羅。", "zh-CN":"基本设计/接口规范/详细设计以可供采购的英日双语文档形式提供。涵盖全部公共接口和插件协议。", ko:"기본 설계 / I/F 사양 / 상세 설계를 조달 가능한 영일 2 언어 문서로 제공. 모든 공개 표면과 플러그인 프로토콜 망라.", es:"Diseño básico / spec de interfaz / diseño detallado como documentos listos para procurement en inglés y japonés. Cubre cada superficie pública y protocolo de plugin.", fr:"Conception de base / spec d'interface / conception détaillée en documents prêts pour le sourcing en anglais et japonais. Chaque surface publique et protocole plugin couvert.", de:"Grunddesign / I/F-Spezifikation / Detaildesign als beschaffungsreife Dokumente auf Englisch und Japanisch. Jede öffentliche Schnittstelle und jedes Plugin-Protokoll abgedeckt.", "pt-BR":"Design básico / spec de interface / design detalhado como documentos prontos para procurement em inglês e japonês. Cobre cada superfície pública e protocolo de plugin."},
    "feat.kms.body":                {en:"OAuth tokens use envelope encryption — fresh DEK per write, AES-GCM payload, DEK wrapped by your KMS. 5 adapters: <code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>. Master key never lives on the application host.", ja:"OAuth トークンはエンベロープ暗号化 — 書込毎に新規 DEK、AES-GCM ペイロード、DEK は KMS で wrap。アダプタ 5 種 (<code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>)。マスターキーはアプリホストに置かない。", "zh-CN":"OAuth 令牌使用信封加密 — 每次写入新 DEK、AES-GCM 载荷、DEK 由 KMS 包装。5 适配器(<code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>)。主密钥从不驻留应用主机。", ko:"OAuth 토큰은 엔벨로프 암호화 — 쓰기마다 새 DEK, AES-GCM 페이로드, DEK 는 KMS 가 래핑. 5 어댑터 (<code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>). 마스터 키는 앱 호스트에 두지 않음.", es:"Los tokens OAuth usan cifrado envelope — DEK fresco por escritura, payload AES-GCM, DEK envuelto por tu KMS. 5 adaptadores: <code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>. La clave maestra nunca vive en el host de la app.", fr:"Les tokens OAuth utilisent un chiffrement envelope — DEK frais par écriture, payload AES-GCM, DEK enveloppé par votre KMS. 5 adaptateurs : <code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>. La clé maîtresse ne réside jamais sur l'hôte applicatif.", de:"OAuth-Tokens nutzen Envelope-Verschlüsselung — frischer DEK pro Schreibvorgang, AES-GCM-Payload, DEK von deinem KMS gewrappt. 5 Adapter: <code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>. Der Masterschlüssel liegt nie auf dem Anwendungs-Host.", "pt-BR":"Tokens OAuth usam criptografia envelope — DEK novo a cada escrita, payload AES-GCM, DEK encapsulado pelo seu KMS. 5 adaptadores: <code>local</code> / <code>aws</code> / <code>azure</code> / <code>gcp</code> / <code>vault</code>. A chave mestra nunca reside no host da aplicação."},
    "feat.oauth_web.body":          {en:"<code>praxia serve</code> exposes <code>/api/v1/oauth/{provider}/{start,callback,status}</code>. Multi-worker safe state cache (TTL-pruned JSON), pinned redirect URI via <code>PRAXIA_PUBLIC_URL</code>, optional success-redirect to your frontend.", ja:"<code>praxia serve</code> が <code>/api/v1/oauth/{provider}/{start,callback,status}</code> を公開。multi-worker 安全な state cache (TTL pruning の JSON)、<code>PRAXIA_PUBLIC_URL</code> で固定 redirect URI、成功時の任意フロント転送。", "zh-CN":"<code>praxia serve</code> 暴露 <code>/api/v1/oauth/{provider}/{start,callback,status}</code>。多 worker 安全的 state cache(TTL 修剪 JSON),<code>PRAXIA_PUBLIC_URL</code> 固定 redirect URI,可选成功重定向至前端。", ko:"<code>praxia serve</code> 가 <code>/api/v1/oauth/{provider}/{start,callback,status}</code> 공개. 멀티 워커 안전 state cache (TTL pruned JSON), <code>PRAXIA_PUBLIC_URL</code> 로 고정 redirect URI, 성공 시 프런트 리다이렉트 옵션.", es:"<code>praxia serve</code> expone <code>/api/v1/oauth/{provider}/{start,callback,status}</code>. State cache seguro multi-worker (JSON con TTL), redirect URI fijada vía <code>PRAXIA_PUBLIC_URL</code>, redirección de éxito opcional a tu frontend.", fr:"<code>praxia serve</code> expose <code>/api/v1/oauth/{provider}/{start,callback,status}</code>. State cache sûr en multi-worker (JSON TTL-pruné), URI de redirection fixée via <code>PRAXIA_PUBLIC_URL</code>, redirection succès optionnelle vers votre frontend.", de:"<code>praxia serve</code> stellt <code>/api/v1/oauth/{provider}/{start,callback,status}</code> bereit. Multi-Worker-sicherer State-Cache (TTL-bereinigtes JSON), feste Redirect-URI über <code>PRAXIA_PUBLIC_URL</code>, optionaler Erfolgs-Redirect zu Ihrem Frontend.", "pt-BR":"<code>praxia serve</code> expõe <code>/api/v1/oauth/{provider}/{start,callback,status}</code>. Cache de state seguro multi-worker (JSON com poda TTL), URI de redirect fixa via <code>PRAXIA_PUBLIC_URL</code>, redirect de sucesso opcional para seu frontend."},
    "feat.ab.body":                 {en:"Test prompt variants on real users with deterministic per-user assignment (SHA-256 bucket). Audience filter (roles / users / window). Outcome rollup + tentative winner detection. CLI + SDK.", ja:"プロンプト変種を決定論的にユーザ単位 (SHA-256 bucket) で実ユーザに割当。オーディエンスフィルタ (ロール/ユーザ/期間)、アウトカム集計 + 暫定 winner 検出、CLI + SDK 対応。", "zh-CN":"按用户确定性分配(SHA-256 bucket)在真实用户上测试提示变体。受众过滤(角色/用户/时段)、结果汇总 + 暂定 winner 检测、CLI + SDK 支持。", ko:"프롬프트 변형을 결정론적 사용자 단위 (SHA-256 bucket) 로 실사용자 배정. 오디언스 필터 (역할/사용자/기간), 결과 집계 + 잠정 winner 감지, CLI + SDK 지원.", es:"Prueba variantes de prompt en usuarios reales con asignación determinista por usuario (bucket SHA-256). Filtro de audiencia (roles / usuarios / ventana). Agregación de resultados + detección tentativa de ganador. CLI + SDK.", fr:"Testez des variantes de prompt sur de vrais utilisateurs avec attribution déterministe par utilisateur (bucket SHA-256). Filtre d'audience (rôles / utilisateurs / fenêtre). Agrégation des résultats + détection provisoire de gagnant. CLI + SDK.", de:"Prompt-Varianten an echten Nutzern testen mit deterministischer Zuordnung pro Nutzer (SHA-256-Bucket). Audience-Filter (Rollen / Nutzer / Zeitraum). Ergebnis-Aggregation + vorläufige Gewinnererkennung. CLI + SDK.", "pt-BR":"Teste variantes de prompt em usuários reais com atribuição determinística por usuário (bucket SHA-256). Filtro de audiência (papéis / usuários / janela). Agregação de resultados + detecção de vencedor provisório. CLI + SDK."},
    "feat.llm_eval.body":           {en:"Catch quality regressions before merge. <code>tests/llm_eval/</code> grades real LLM output against rubrics + a committed baseline. Score drop &gt; 5pt fails the build. Per-skill cases ship for all 6 skills.", ja:"品質デグレを merge 前に検知。<code>tests/llm_eval/</code> が実 LLM 出力をルーブリック + コミット済みベースラインで採点。5pt 超ドロップで build 失敗。6 スキル全件にケース同梱。", "zh-CN":"在合并前捕获质量回退。<code>tests/llm_eval/</code> 对真实 LLM 输出按评分卡 + 已提交基线打分。下降超过 5 分则构建失败。6 项技能均附用例。", ko:"머지 전 품질 회귀 감지. <code>tests/llm_eval/</code> 가 실 LLM 출력을 루브릭 + 커밋된 베이스라인 기준 채점. 5pt 초과 하락 시 빌드 실패. 6 스킬 전체 케이스 동봉.", es:"Detecta regresiones de calidad antes del merge. <code>tests/llm_eval/</code> califica salida LLM real contra rúbricas + un baseline comprometido. Caída &gt; 5pt rompe el build. Casos por habilidad para las 6 habilidades.", fr:"Détectez les régressions de qualité avant le merge. <code>tests/llm_eval/</code> note les sorties LLM réelles par rapport à des rubriques + une baseline committée. Une baisse &gt; 5pt fait échouer le build. Cas par compétence pour les 6 compétences.", de:"Qualitätsregressionen vor dem Merge erkennen. <code>tests/llm_eval/</code> bewertet echte LLM-Ausgaben gegen Rubriken + eine committete Baseline. Ein Abfall &gt; 5pt lässt den Build scheitern. Fälle pro Skill für alle 6 Skills.", "pt-BR":"Detecte regressões de qualidade antes do merge. <code>tests/llm_eval/</code> avalia saída LLM real contra rubricas + uma baseline commitada. Queda &gt; 5pt faz o build falhar. Casos por habilidade para as 6 habilidades."},
    "feat.tests.body":              {en:"Auth / memory / fusion / exporters / OAuth / parsers / CLI / extensions / experiments / connectors — every public surface has a hermetic test. CI runs on every PR. Add features without breaking existing ones.", ja:"認証/メモリ/融合/エクスポータ/OAuth/パーサ/CLI/拡張/実験/コネクタ — 全公開面に密閉テスト。PR ごとに CI 実行。既存機能を壊さず追加可能。", "zh-CN":"认证/记忆/融合/导出器/OAuth/解析器/CLI/扩展/实验/连接器 — 每个公共面都有封闭测试。每 PR 运行 CI。新增功能不破坏既有。", ko:"인증/메모리/융합/익스포터/OAuth/파서/CLI/확장/실험/커넥터 — 모든 공개 표면에 봉인된 테스트. PR 마다 CI 실행. 기존 기능 손상 없이 추가 가능.", es:"Auth / memoria / fusión / exportadores / OAuth / parsers / CLI / extensiones / experimentos / conectores — cada superficie pública tiene un test hermético. CI en cada PR. Añade funciones sin romper las existentes.", fr:"Auth / mémoire / fusion / exportateurs / OAuth / parsers / CLI / extensions / expériences / connecteurs — chaque surface publique a un test hermétique. CI sur chaque PR. Ajoutez des fonctionnalités sans casser les existantes.", de:"Auth / Speicher / Fusion / Exporter / OAuth / Parser / CLI / Erweiterungen / Experimente / Konnektoren — jede öffentliche Oberfläche hat einen hermetischen Test. CI bei jedem PR. Features hinzufügen ohne Bestehendes zu zerstören.", "pt-BR":"Auth / memória / fusão / exportadores / OAuth / parsers / CLI / extensões / experimentos / conectores — cada superfície pública tem teste hermético. CI a cada PR. Adicione funcionalidades sem quebrar as existentes."},
    "feat.connectors.body":         {en:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. Per-user OAuth means alice only sees what alice can in each system.", ja:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email。ユーザ毎 OAuth で alice は各システムで alice 権限分のみ可視。", "zh-CN":"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email。用户级 OAuth 意味着 alice 在各系统仅见 alice 可访问的内容。", ko:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. 사용자별 OAuth 로 alice 는 각 시스템에서 alice 권한 내 정보만 표시.", es:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. OAuth por usuario significa que alice solo ve lo que alice puede ver en cada sistema.", fr:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. OAuth par utilisateur : alice ne voit dans chaque système que ce qu'alice peut voir.", de:"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. OAuth pro Nutzer heißt: alice sieht in jedem System nur, was alice sehen darf.", "pt-BR":"Box / SharePoint / Dropbox / Drive / kintone / Salesforce + Notion / Confluence / Jira / Slack / Teams / GitHub / HubSpot / Zendesk / Linear / S3 / Azure Blob / GCS / WebDAV / Email. OAuth por usuário significa que alice só vê em cada sistema o que alice pode ver."},
    "feat.mcp_server.body":         {en:"Use Praxia from Claude Desktop / Cursor / Continue.dev. Local: <code>praxia mcp serve</code>. Remote (multi-host): <code>praxia serve</code> exposes <code>/api/v1/mcp</code> with auth + audit log. Every skill + flow becomes an MCP tool automatically.", ja:"Claude Desktop / Cursor / Continue.dev から Praxia を利用。ローカル: <code>praxia mcp serve</code>。リモート (multi-host): <code>praxia serve</code> が <code>/api/v1/mcp</code> を認証 + 監査ログ付きで公開。全スキル + フローが自動で MCP ツール化。", "zh-CN":"从 Claude Desktop / Cursor / Continue.dev 使用 Praxia。本地:<code>praxia mcp serve</code>。远程(多主机):<code>praxia serve</code> 暴露 <code>/api/v1/mcp</code>(含认证 + 审计日志)。每项技能 + 流程自动成为 MCP 工具。", ko:"Claude Desktop / Cursor / Continue.dev 에서 Praxia 사용. 로컬: <code>praxia mcp serve</code>. 원격 (멀티 호스트): <code>praxia serve</code> 가 인증 + 감사 로그 포함으로 <code>/api/v1/mcp</code> 공개. 모든 스킬 + 플로가 자동으로 MCP 도구화.", es:"Usa Praxia desde Claude Desktop / Cursor / Continue.dev. Local: <code>praxia mcp serve</code>. Remoto (multi-host): <code>praxia serve</code> expone <code>/api/v1/mcp</code> con auth + log de auditoría. Cada habilidad + flujo se convierte en herramienta MCP automáticamente.", fr:"Utilisez Praxia depuis Claude Desktop / Cursor / Continue.dev. Local : <code>praxia mcp serve</code>. Distant (multi-host) : <code>praxia serve</code> expose <code>/api/v1/mcp</code> avec auth + journal d'audit. Chaque compétence + flux devient outil MCP automatiquement.", de:"Praxia von Claude Desktop / Cursor / Continue.dev nutzen. Lokal: <code>praxia mcp serve</code>. Remote (Multi-Host): <code>praxia serve</code> stellt <code>/api/v1/mcp</code> mit Auth + Audit-Log bereit. Jeder Skill + Flow wird automatisch zum MCP-Tool.", "pt-BR":"Use o Praxia a partir de Claude Desktop / Cursor / Continue.dev. Local: <code>praxia mcp serve</code>. Remoto (multi-host): <code>praxia serve</code> expõe <code>/api/v1/mcp</code> com auth + log de auditoria. Cada habilidade + fluxo se torna ferramenta MCP automaticamente."},
    "feat.responsive.body":         {en:"Landing has chip-style nav on phones, scrollable tabs, ≥44px touch targets, prefers-reduced-motion respected. Streamlit UI injects responsive CSS + a \"Compact mode\" toggle for slow connections.", ja:"ランディングはモバイル時 chip 型ナビ、スクロール可能タブ、≥44px タッチターゲット、prefers-reduced-motion 準拠。Streamlit UI は応答型 CSS と低速回線向け「コンパクトモード」を注入。", "zh-CN":"落地页移动端为 chip 式导航、可滚动 Tabs、≥44px 触摸目标、遵循 prefers-reduced-motion。Streamlit UI 注入响应式 CSS 与「紧凑模式」用于慢速连接。", ko:"랜딩은 모바일에서 chip 형 내비, 스크롤 가능 탭, ≥44px 터치 타깃, prefers-reduced-motion 준수. Streamlit UI 는 반응형 CSS 와 저속 회선용 「컴팩트 모드」 주입.", es:"La landing tiene nav tipo chip en móviles, pestañas desplazables, objetivos táctiles ≥44px, respeta prefers-reduced-motion. La UI Streamlit inyecta CSS responsive + modo compacto para conexiones lentas.", fr:"La landing utilise une nav en chip sur mobile, onglets défilables, cibles tactiles ≥44px, respecte prefers-reduced-motion. L'UI Streamlit injecte CSS responsive + bascule « Mode compact » pour connexions lentes.", de:"Landing hat auf Smartphones Chip-Navigation, scrollbare Tabs, ≥44px Touch-Ziele, respektiert prefers-reduced-motion. Streamlit-UI fügt responsives CSS + Compact-Mode-Schalter für langsame Verbindungen ein.", "pt-BR":"A landing tem nav estilo chip no mobile, abas roláveis, alvos de toque ≥44px, respeita prefers-reduced-motion. A UI Streamlit injeta CSS responsivo + alternador \"Modo compacto\" para conexões lentas."},

    // ===== Persona card titles (7) ===================================
    "who.p1_title":              {en:"🏢 Information Systems / Platform team (300–5,000 employees)", ja:"🏢 情報システム / プラットフォーム部門 (300〜5,000 人規模)", "zh-CN":"🏢 信息系统 / 平台部门 (300-5,000 员工)", ko:"🏢 정보시스템 / 플랫폼 팀 (300-5,000 명 규모)", es:"🏢 Sistemas / Plataforma (300-5,000 empleados)", fr:"🏢 SI / Plateforme (300-5,000 employés)", de:"🏢 IT / Plattform-Team (300-5,000 Mitarbeiter)", "pt-BR":"🏢 TI / Plataforma (300-5,000 funcionários)"},
    "who.p2_title":              {en:"🏗️ Engineering / Product VP (50–500 in scope)", ja:"🏗️ エンジニアリング / プロダクト VP (50〜500 名スコープ)", "zh-CN":"🏗️ 工程 / 产品 VP (50-500 范围)", ko:"🏗️ 엔지니어링 / 제품 VP (50-500 명 범위)", es:"🏗️ VP Ingeniería / Producto (50-500)", fr:"🏗️ VP Ingénierie / Produit (50-500)", de:"🏗️ VP Engineering / Produkt (50-500)", "pt-BR":"🏗️ VP Engenharia / Produto (50-500)"},
    "who.p3_title":              {en:"⚖️ Legal / Compliance lead (regulated industry)", ja:"⚖️ 法務 / コンプライアンス責任者 (規制業界)", "zh-CN":"⚖️ 法务 / 合规负责人 (受监管行业)", ko:"⚖️ 법무 / 컴플라이언스 책임자 (규제 산업)", es:"⚖️ Líder Legal / Compliance (industria regulada)", fr:"⚖️ Responsable Juridique / Conformité (secteur régulé)", de:"⚖️ Leiter Recht / Compliance (regulierte Branche)", "pt-BR":"⚖️ Líder Jurídico / Compliance (setor regulado)"},
    "who.p4_title":              {en:"🧪 OSS / Research integrator (engineering team)", ja:"🧪 OSS / 研究開発インテグレータ (エンジニアリングチーム)", "zh-CN":"🧪 OSS / 研究集成方 (工程团队)", ko:"🧪 OSS / 연구 통합자 (엔지니어링 팀)", es:"🧪 Integrador OSS / I+D (equipo de ingeniería)", fr:"🧪 Intégrateur OSS / R&D (équipe ingénierie)", de:"🧪 OSS / R&D-Integrator (Engineering-Team)", "pt-BR":"🧪 Integrador OSS / P&D (equipe engenharia)"},
    "who.p5_title":              {en:"📈 Sales / Revenue Operations lead", ja:"📈 営業 / レベニューオペレーション責任者", "zh-CN":"📈 销售 / 收入运营负责人", ko:"📈 영업 / 레브뉴 오퍼레이션 책임자", es:"📈 Líder de Ventas / RevOps", fr:"📈 Responsable Ventes / RevOps", de:"📈 Vertriebs- / RevOps-Leiter", "pt-BR":"📈 Líder de Vendas / RevOps"},
    "who.p6_title":              {en:"🛒 Procurement / Supply Chain lead", ja:"🛒 購買 / サプライチェーン責任者", "zh-CN":"🛒 采购 / 供应链负责人", ko:"🛒 구매 / 공급망 책임자", es:"🛒 Líder Compras / Supply Chain", fr:"🛒 Responsable Achats / Supply Chain", de:"🛒 Einkaufs- / Supply-Chain-Leiter", "pt-BR":"🛒 Líder Compras / Supply Chain"},
    "who.p7_title":              {en:"📑 IP / Patent agent or in-house counsel", ja:"📑 知財 / 特許担当 (社内・社外)", "zh-CN":"📑 知识产权 / 专利代理 (内部 / 外部)", ko:"📑 IP / 특허 담당 (사내 / 사외)", es:"📑 Agente de Patentes / IP", fr:"📑 Conseil en IP / Brevets", de:"📑 IP- / Patentanwalt (intern oder extern)", "pt-BR":"📑 Agente de Patentes / IP"},

    // ===== OSS edge cards (6 short titles) ===========================
    "oss.c1":                    {en:"SSO + RBAC + audit are not paywalled", ja:"SSO + RBAC + 監査が有償化されていない", "zh-CN":"SSO + RBAC + 审计 不付费", ko:"SSO + RBAC + 감사 페이월 없음", es:"SSO + RBAC + auditoría sin paywall", fr:"SSO + RBAC + audit sans paywall", de:"SSO + RBAC + Audit ohne Paywall", "pt-BR":"SSO + RBAC + auditoria sem paywall"},
    "oss.c2":                    {en:"Memory format is not locked in", ja:"メモリ形式がロックインされない", "zh-CN":"记忆格式不锁定", ko:"메모리 포맷 잠금 없음", es:"Formato de memoria sin lock-in", fr:"Format mémoire sans verrouillage", de:"Speicherformat ohne Lock-in", "pt-BR":"Formato de memória sem lock-in"},
    "oss.c3":                    {en:"You can read every line", ja:"全コード読める", "zh-CN":"每一行代码可读", ko:"모든 코드 행 가독", es:"Puedes leer cada línea", fr:"Vous pouvez lire chaque ligne", de:"Sie können jede Zeile lesen", "pt-BR":"Você pode ler cada linha"},
    "oss.c4":                    {en:"Multi-LTM ensembles, not single-vendor", ja:"複数 LTM のアンサンブル運用 (単一ベンダーロックインなし)", "zh-CN":"多 LTM 集成,不是单供应商锁定", ko:"멀티 LTM 앙상블 (단일 벤더 종속 없음)", es:"Conjuntos multi-LTM, no un único proveedor", fr:"Ensembles multi-LTM, pas un seul fournisseur", de:"Multi-LTM-Ensembles, nicht Single-Vendor", "pt-BR":"Conjuntos multi-LTM, não vendor único"},
    "oss.c5":                    {en:"Per-user OAuth respects external ACL", ja:"ユーザ委譲 OAuth で連携先 ACL を尊重", "zh-CN":"每用户 OAuth 尊重外部 ACL", ko:"사용자별 OAuth 가 외부 ACL 존중", es:"OAuth por usuario respeta ACL externa", fr:"OAuth par utilisateur respecte l'ACL externe", de:"Benutzer-OAuth respektiert externe ACL", "pt-BR":"OAuth por usuário respeita ACL externa"},
    "oss.c6":                    {en:"Run fully on-prem with Gemma / Qwen", ja:"Gemma / Qwen で完全オンプレ動作", "zh-CN":"使用 Gemma / Qwen 完全本地部署", ko:"Gemma / Qwen 으로 완전 온프레미스 운용", es:"Funciona on-prem con Gemma / Qwen", fr:"Fonctionne 100% on-prem avec Gemma / Qwen", de:"Komplett on-prem mit Gemma / Qwen", "pt-BR":"Roda totalmente on-prem com Gemma / Qwen"},

    // ===== How-it-works step titles (4) ===============================
    "how.kicker":                {en:"How it works", ja:"仕組み", "zh-CN":"工作原理", ko:"작동 방식", es:"Cómo funciona", fr:"Comment ça marche", de:"Funktionsweise", "pt-BR":"Como funciona"},
    "how.h2":                    {en:"From individual usage to organizational standard — automatically.", ja:"個人利用から組織標準へ — 自動的に。", "zh-CN":"从个人使用到组织标准 — 自动完成。", ko:"개인 사용에서 조직 표준까지 — 자동으로.", es:"Del uso individual al estándar organizacional — automáticamente.", fr:"De l'usage individuel au standard organisationnel — automatiquement.", de:"Von individueller Nutzung zum Organisationsstandard — automatisch.", "pt-BR":"Do uso individual ao padrão organizacional — automaticamente."},
    "how.s1":                    {en:"You just work", ja:"普通に使うだけ", "zh-CN":"只管正常工作", ko:"평소대로 사용", es:"Solo trabajas normal", fr:"Travaillez normalement", de:"Sie arbeiten einfach", "pt-BR":"Você apenas trabalha"},
    "how.s2":                    {en:"Outcomes get attached", ja:"成果が紐付く", "zh-CN":"成果自动关联", ko:"성과가 연결됨", es:"Los resultados se vinculan", fr:"Les résultats s'attachent", de:"Ergebnisse werden zugeordnet", "pt-BR":"Resultados são anexados"},
    "how.s3":                    {en:"Nightly distillation", ja:"夜間に蒸留", "zh-CN":"夜间蒸馏", ko:"야간 증류", es:"Destilación nocturna", fr:"Distillation nocturne", de:"Nächtliche Destillation", "pt-BR":"Destilação noturna"},
    "how.s4":                    {en:"Living → frozen", ja:"生 → 凍結化", "zh-CN":"活动 → 凍結", ko:"라이브 → 동결", es:"Vivo → congelado", fr:"Vivant → figé", de:"Lebend → eingefroren", "pt-BR":"Vivo → congelado"},

    // ===== Pricing tier names (3) =====================================
    "pricing.kicker":            {en:"Pricing", ja:"料金", "zh-CN":"定价", ko:"가격", es:"Precios", fr:"Tarifs", de:"Preise", "pt-BR":"Preços"},
    "pricing.h2":                {en:"Same code, different operational support.", ja:"同じコード、運用サポートの違いだけ。", "zh-CN":"代码相同,运维支持不同。", ko:"같은 코드, 다른 운영 지원.", es:"Mismo código, soporte operativo distinto.", fr:"Même code, support opérationnel différent.", de:"Gleicher Code, unterschiedlicher Betriebssupport.", "pt-BR":"Mesmo código, suporte operacional diferente."},
    "pricing.tier1":             {en:"Open Source", ja:"オープンソース", "zh-CN":"开源", ko:"오픈 소스", es:"Open Source", fr:"Open Source", de:"Open Source", "pt-BR":"Open Source"},
    "pricing.tier2":             {en:"Team (managed)", ja:"Team (マネージド)", "zh-CN":"团队 (托管)", ko:"팀 (관리형)", es:"Team (gestionado)", fr:"Team (géré)", de:"Team (gemanagt)", "pt-BR":"Team (gerenciado)"},
    "pricing.tier3":             {en:"Enterprise", ja:"エンタープライズ", "zh-CN":"企业版", ko:"엔터프라이즈", es:"Enterprise", fr:"Enterprise", de:"Enterprise", "pt-BR":"Enterprise"},

    // ===== Where it fits =============================================
    "fit.kicker":                {en:"Where it fits", ja:"適合領域", "zh-CN":"适用场景", ko:"적합 영역", es:"Dónde encaja", fr:"Où ça s'inscrit", de:"Wo es passt", "pt-BR":"Onde se encaixa"},
    "fit.h2":                    {en:"What Praxia is best at — without putting others down.", ja:"Praxia が最も得意なこと (他を貶めず)", "zh-CN":"Praxia 最擅长的领域 — 不贬低他人。", ko:"Praxia 가 가장 잘하는 것 — 타인을 폄하하지 않고.", es:"En qué Praxia es mejor — sin denigrar a otros.", fr:"Là où Praxia excelle — sans dénigrer.", de:"Worin Praxia am besten ist — ohne andere abzuwerten.", "pt-BR":"O que Praxia faz de melhor — sem desmerecer outros."},
    "fit.best":                  {en:"Best for…", ja:"最適なケース", "zh-CN":"最适合…", ko:"가장 적합한 경우", es:"Mejor para…", fr:"Idéal pour…", de:"Am besten für…", "pt-BR":"Melhor para…"},
    "fit.less":                  {en:"Less ideal when…", ja:"あまり向かないケース", "zh-CN":"不太适合…", ko:"적합하지 않은 경우", es:"Menos ideal cuando…", fr:"Moins idéal quand…", de:"Weniger ideal wenn…", "pt-BR":"Menos ideal quando…"},
    "fit.plays":                 {en:"Plays well with…", ja:"相性が良いもの", "zh-CN":"配合良好…", ko:"잘 어울리는 것", es:"Funciona bien con…", fr:"Compatible avec…", de:"Funktioniert gut mit…", "pt-BR":"Funciona bem com…"},

    // ===== Examples section ==========================================
    "ex.kicker":                 {en:"Concrete examples", ja:"具体例", "zh-CN":"具体示例", ko:"구체적 사례", es:"Ejemplos concretos", fr:"Exemples concrets", de:"Konkrete Beispiele", "pt-BR":"Exemplos concretos"},
    "ex.h2":                     {en:"One CLI invocation, real business output.", ja:"1 行の CLI 実行で、業務出力。", "zh-CN":"一条 CLI 命令,真实业务输出。", ko:"한 줄의 CLI 호출, 실제 업무 결과.", es:"Un comando CLI, salida de negocio real.", fr:"Une commande CLI, résultat métier réel.", de:"Ein CLI-Befehl, echte Geschäftsausgabe.", "pt-BR":"Um comando CLI, saída de negócio real."},

    // ===== UI tour ====================================================
    "uitour.kicker":             {en:"UI tour", ja:"UI ツアー", "zh-CN":"UI 演示", ko:"UI 투어", es:"Tour de UI", fr:"Visite de l'UI", de:"UI-Rundgang", "pt-BR":"Tour da UI"},
    "uitour.h2":                 {en:"The Streamlit dashboard at a glance.", ja:"Streamlit ダッシュボードの全体像。", "zh-CN":"Streamlit 仪表板一览。", ko:"Streamlit 대시보드 한눈에.", es:"El panel de Streamlit de un vistazo.", fr:"Le tableau de bord Streamlit en un coup d'œil.", de:"Das Streamlit-Dashboard auf einen Blick.", "pt-BR":"O painel Streamlit em um olhar."},

    // ===== Use cases section =========================================
    "uc.kicker":                 {en:"Use cases", ja:"ユースケース", "zh-CN":"使用案例", ko:"활용 사례", es:"Casos de uso", fr:"Cas d'usage", de:"Anwendungsfälle", "pt-BR":"Casos de uso"},
    "uc.h2":                     {en:"Concrete Before / After across six business functions.", ja:"6 業務領域での具体的 Before / After。", "zh-CN":"6 个业务职能的具体 Before / After。", ko:"6 가지 업무 영역의 구체적 Before / After.", es:"Before / After concreto en 6 funciones.", fr:"Before / After concret sur 6 fonctions métiers.", de:"Konkrete Before / After über 6 Geschäftsbereiche.", "pt-BR":"Before / After concreto em 6 funções de negócio."},

    // ===== Extending section =========================================
    "ext.kicker":                {en:"Extensibility", ja:"拡張性", "zh-CN":"可扩展性", ko:"확장성", es:"Extensibilidad", fr:"Extensibilité", de:"Erweiterbarkeit", "pt-BR":"Extensibilidade"},
    "ext.h2":                    {en:"Built to grow with your team.", ja:"チームと共に成長する設計。", "zh-CN":"为与您的团队共同成长而构建。", ko:"팀과 함께 성장하도록 설계.", es:"Diseñado para crecer con tu equipo.", fr:"Conçu pour grandir avec votre équipe.", de:"Gebaut, um mit Ihrem Team zu wachsen.", "pt-BR":"Construído para crescer com sua equipe."},

    // ===== ROI section ===============================================
    "roi.kicker":                {en:"ROI projection", ja:"ROI 試算", "zh-CN":"ROI 预测", ko:"ROI 추정", es:"Proyección de ROI", fr:"Projection ROI", de:"ROI-Prognose", "pt-BR":"Projeção de ROI"},
    "roi.h2":                    {en:"Cumulative effect compounds with the memory loop.", ja:"メモリ循環で累積効果が複利的に拡大。", "zh-CN":"累积效应随记忆循环复合增长。", ko:"누적 효과가 메모리 순환으로 복리 성장.", es:"El efecto acumulado crece exponencialmente con el bucle de memoria.", fr:"L'effet cumulatif croît avec la boucle de mémoire.", de:"Kumulative Wirkung wächst mit dem Memory-Loop.", "pt-BR":"O efeito acumulado cresce com o ciclo de memória."},

    // ----- Translation status notice (for non-English) -----
    "i18n.notice": {
      en: "",
      ja: "※ 主要部分のみ翻訳済 — 詳細な FAQ・コード例・カード本文は英語表示のままです。",
      "zh-CN": "※ 仅核心区域已翻译 — 详细 FAQ、代码示例和正文卡片仍为英文显示。",
      ko: "※ 핵심 영역만 번역됨 — 상세 FAQ, 코드 예제, 카드 본문은 영어로 표시됩니다.",
      es: "※ Solo se han traducido las áreas principales — FAQs detallados, ejemplos de código y cuerpo de tarjetas siguen en inglés.",
      fr: "※ Seules les zones principales sont traduites — les FAQ détaillées, exemples de code et corps des cartes restent en anglais.",
      de: "※ Nur die Kernbereiche sind übersetzt — detaillierte FAQs, Code-Beispiele und Kartenkörper bleiben auf Englisch.",
      "pt-BR": "※ Apenas as áreas principais foram traduzidas — FAQs detalhados, exemplos de código e corpo dos cards permanecem em inglês.",
    },
  };

  // ---- Detection ----------------------------------------------------------

  function pickLang() {
    // 1. Manual override (localStorage)
    const stored = localStorage.getItem("praxia-lang");
    if (stored && SUPPORTED.includes(stored)) return stored;
    // 2. URL param ?lang=ja
    const param = new URLSearchParams(location.search).get("lang");
    if (param && SUPPORTED.includes(param)) return param;
    // 3. Browser language
    const browserLangs = navigator.languages || [navigator.language || "en"];
    for (const raw of browserLangs) {
      // Try exact match
      if (SUPPORTED.includes(raw)) return raw;
      // Try prefix match (e.g. "zh-CN" matches "zh-CN" but "zh-TW" matches "zh-CN" too)
      const prefix = raw.split("-")[0].toLowerCase();
      const match = SUPPORTED.find(s => s.toLowerCase().startsWith(prefix));
      if (match) return match;
    }
    return "en";
  }

  // ---- Apply --------------------------------------------------------------

  let _currentLang = "en";

  function applyLang(lang) {
    _currentLang = lang;
    document.documentElement.lang = lang;
    document.documentElement.setAttribute("data-praxia-lang", lang);

    // Replace text-content elements
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      const dict = T[key];
      if (!dict) return;
      const value = dict[lang] || dict["en"];
      if (value !== undefined) el.innerHTML = value;
    });

    // Placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      const key = el.getAttribute("data-i18n-placeholder");
      const dict = T[key];
      if (dict) el.placeholder = dict[lang] || dict["en"];
    });

    // Titles / aria-labels
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
      const key = el.getAttribute("data-i18n-title");
      const dict = T[key];
      if (dict) el.title = dict[lang] || dict["en"];
    });

    // Show / hide translation-status notice
    const noticeEl = document.getElementById("i18n-notice");
    if (noticeEl) {
      const text = (T["i18n.notice"][lang] || "");
      if (text) {
        noticeEl.textContent = text;
        noticeEl.hidden = false;
      } else {
        noticeEl.hidden = true;
        noticeEl.textContent = "";
      }
    }

    // Update language switcher state
    document.querySelectorAll("[data-lang-option]").forEach(el => {
      el.classList.toggle(
        "lang-active",
        el.getAttribute("data-lang-option") === lang
      );
    });

    // Notify other modules (e.g. consent.js) so they can re-render
    document.dispatchEvent(
      new CustomEvent("praxia-lang-changed", {detail: {lang}})
    );
  }

  // Expose so other scripts can re-translate dynamically-injected nodes
  window.praxiaApplyI18n = function () { applyLang(_currentLang); };
  window.praxiaCurrentLang = function () { return _currentLang; };

  // ---- Switcher UI --------------------------------------------------------

  function buildSwitcher() {
    const container = document.getElementById("lang-switcher");
    if (!container) return;
    SUPPORTED.forEach(code => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lang-option";
      btn.setAttribute("data-lang-option", code);
      btn.textContent = LANG_DISPLAY[code];
      btn.addEventListener("click", () => {
        localStorage.setItem("praxia-lang", code);
        applyLang(code);
      });
      container.appendChild(btn);
    });
  }

  // ---- Init ---------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", () => {
    buildSwitcher();
    applyLang(pickLang());
  });
})();
