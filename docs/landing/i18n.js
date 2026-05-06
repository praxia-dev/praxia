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
      en: "37+ advantages no other framework offers in one package.",
      ja: "1 パッケージに 37+ の独自優位性。他にないラインナップ。",
      "zh-CN": "37+ 项独特优势,无其他框架可比。",
      ko: "다른 프레임워크에는 없는 37+ 가지 강점.",
      es: "37+ ventajas que ningún otro framework ofrece en un solo paquete.",
      fr: "37+ avantages qu'aucun autre framework n'offre en un seul package.",
      de: "37+ Vorteile, die kein anderes Framework in einem Paket bietet.",
      "pt-BR": "37+ vantagens que nenhum outro framework oferece em um pacote.",
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

    // ===== Feature card titles (33 cards) ============================
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
    "feat.tests":                {en:"429 regression tests", ja:"429 件のリグレッションテスト", "zh-CN":"429 项回归测试", ko:"429 개 회귀 테스트", es:"429 tests de regresión", fr:"429 tests de régression", de:"429 Regressionstests", "pt-BR":"429 testes de regressão"},
    "feat.mcp_server":           {en:"MCP server (stdio + remote HTTP/SSE)", ja:"MCP サーバ (stdio + リモート HTTP/SSE)", "zh-CN":"MCP 服务器 (stdio + 远程 HTTP/SSE)", ko:"MCP 서버 (stdio + 원격 HTTP/SSE)", es:"Servidor MCP (stdio + HTTP/SSE remoto)", fr:"Serveur MCP (stdio + HTTP/SSE distant)", de:"MCP-Server (stdio + Remote HTTP/SSE)", "pt-BR":"Servidor MCP (stdio + HTTP/SSE remoto)"},
    "feat.responsive":           {en:"Mobile-responsive UI + landing", ja:"モバイル対応 UI + サイト", "zh-CN":"移动响应式 UI + 站点", ko:"모바일 반응형 UI + 사이트", es:"UI responsive móvil + sitio", fr:"UI responsive mobile + site", de:"Mobile-responsive UI + Site", "pt-BR":"UI responsiva móvel + site"},

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
