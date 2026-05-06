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
