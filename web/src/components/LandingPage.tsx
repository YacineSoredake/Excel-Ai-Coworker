"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/*  Copy: EN / FR / AR                                                 */
/* ------------------------------------------------------------------ */

type Lang = "en" | "fr" | "ar";

const en = {
  nav: { how: "How it works", pricing: "Pricing", faq: "FAQ", signin: "Sign in", start: "Get started" },
  hero: {
    h1a: "Your spreadsheet, ", h1b: "finally explained.",
    sub: "Drop in an Excel file and get the KPIs, trends and surprises in seconds, calculated from your own data. No formulas to write.",
    cta1: "Analyze my workbook", cta2: "See how it works",
    ready: "Ready", sample: "Sample data", trend: "Revenue trend", insightTitle: "What stands out",
    askTitle: "Ask your data", askPh: "Ask about your data…",
    sets: [
      { tab: "Sales", file: "Q3_sales.xlsx", kpis: ["Revenue", "Growth", "Orders"], insight: "Revenue jumped 71% in September, led by Electronics.", q: "Why did September jump?", a: "Electronics drove most of it: +212% vs August.", chips: ["+71% in September", "14 duplicate rows found"] },
      { tab: "Inventory", file: "Warehouse_stock.xlsx", kpis: ["Low-stock items", "Overstocked", "Avg. days of cover"], insight: "38 products will run out within two weeks at the current pace.", q: "What should I reorder first?", a: "Five fast-selling products have under a week of stock.", chips: ["38 items running low", "12% overstocked"] },
      { tab: "Finance", file: "Monthly_P&L.xlsx", kpis: ["Net profit", "Margin", "Anomalies"], insight: "Marketing spend doubled in August with no matching revenue lift.", q: "Why did margin drop?", a: "Marketing spend doubled while revenue stayed flat.", chips: ["3 anomalies flagged", "Margin down 4 pts"] },
    ],
    strip: [".xlsx native", "Deterministic math", "Private by design", "Delete anytime"],
  },
  problem: {
    label: "The problem", title: "Spreadsheets hold the truth. Finding it is the hard part.",
    pains: [
      { big: "47 tabs", text: "Pivot tables, VLOOKUPs and final_v7_REAL.xlsx, before you see a single chart." },
      { big: "2 hrs", text: "Prepping numbers for a meeting that only needs three of them." },
      { big: "1 doubt", text: "“Is this figure right?” And no quick way to check." },
    ],
  },
  steps: {
    label: "How it works", title: "Three steps. One coffee.",
    items: [
      { title: "Drop in your workbook", text: "Upload an .xlsx. Tables, dates, measures and formulas are detected automatically." },
      { title: "Read the story", text: "KPIs, trends, comparisons and data-quality flags in one clean view." },
      { title: "Ask, then share", text: "Question your data in plain language, then export a client-ready PDF." },
    ],
  },
  chat: {
    label: "Ask your spreadsheet", title: "Questions in. Checked answers out.",
    body: "Ask like you'd ask a colleague. Every answer is calculated from your data and verified before it is shown.",
    cta: "Try it with your workbook", foot: "✓ Calculated from your data · checked before shown",
    items: [
      { q: "Which region grew fastest?", a: "North Africa grew fastest at +42%, ahead of the Gulf (+31%) and Europe (+12%).", bars: ["North Africa", "Gulf", "Europe"] },
      { q: "Why did margin drop in August?", a: "Marketing spend doubled while revenue stayed flat, pulling margin down about 4 points.", bars: ["Marketing", "Logistics", "Payroll"] },
      { q: "What should I reorder first?", a: "Five fast-selling products have under a week of stock. Reorder those first.", bars: ["Product A", "Product B", "Product C"] },
    ],
  },
  features: {
    label: "Capabilities", title: "Not another chart generator.",
    items: [
      { title: "Automatic KPIs & trends", text: "The numbers that matter, picked for you." },
      { title: "Grounded insights", text: "Every statement is backed by a calculation." },
      { title: "Data-quality signals", text: "Duplicates, gaps and outliers flagged early." },
      { title: "Plain-language questions", text: "No formulas. Just ask." },
      { title: "Guided investigation", text: "Follow a number back to its source rows." },
      { title: "Client-ready PDF reports", text: "Turn the analysis into something you can send today." },
    ],
  },
  trust: {
    label: "Trust", title: "Your workbook stays yours.",
    body: "Files are private to your account. The analysis uses deterministic calculations, and AI assistance is optional.",
    items: [
      { title: "Private storage", text: "Protected by account-level access controls." },
      { title: "Traceable numbers", text: "Figures are recomputed and linked to their source rows." },
      { title: "You decide", text: "Review, export or delete whenever you want." },
    ],
  },
  pricing: {
    label: "Pricing", title: "Start free. Upgrade when it pays for itself.",
    badge: "Most popular", per: "/ month",
    plans: [
      { name: "Free", price: "0 DA", note: "to try it", perks: ["A few workbooks", "KPIs, trends and insights", "Plain-language questions"], cta: "Start free" },
      { name: "Pro", price: "2 900 DA", note: "", perks: ["Unlimited workbooks", "Client-ready PDF reports", "Guided investigation", "Priority processing"], cta: "Go Pro" },
      { name: "Team", price: "7 900 DA", note: "", perks: ["Everything in Pro", "Shared workspace", "Team-wide reports"], cta: "Start with a team" },
    ],
  },
  faq: {
    label: "FAQ", title: "Straight answers.",
    items: [
      { q: "Is my data private?", a: "Yes. Files are private to your account and protected by account-level access controls. Review, export or delete them whenever you want." },
      { q: "Do I need to write formulas?", a: "No. Excel Copilot reads your workbook's structure and does the calculating. You look, or you ask." },
      { q: "Can I trust the numbers?", a: "Figures come from deterministic calculations on your own data and link back to their source rows. AI assistance is optional." },
      { q: "Which files work?", a: "Excel Copilot is built for .xlsx workbooks." },
      { q: "Can I share the results?", a: "Yes. Export a client-ready PDF straight from your analysis." },
    ],
  },
  final: { title: "Bring the spreadsheet. Leave with clarity.", sub: "Upload one workbook and see what your data has been trying to tell you.", cta: "Get started free" },
  footer: { tag: "Upload your Excel. Understand your data." },
};

type Dict = typeof en;

const fr: Dict = {
  nav: { how: "Comment ça marche", pricing: "Tarifs", faq: "FAQ", signin: "Connexion", start: "Commencer" },
  hero: {
    h1a: "Votre tableur, ", h1b: "enfin expliqué.",
    sub: "Déposez un fichier Excel et obtenez KPI, tendances et surprises en quelques secondes, calculés à partir de vos propres données. Zéro formule.",
    cta1: "Analyser mon classeur", cta2: "Voir comment ça marche",
    ready: "Prêt", sample: "Données d'exemple", trend: "Évolution du chiffre d'affaires", insightTitle: "Ce qui ressort",
    askTitle: "Interrogez vos données", askPh: "Posez une question sur vos données…",
    sets: [
      { tab: "Ventes", file: "Q3_ventes.xlsx", kpis: ["Chiffre d'affaires", "Croissance", "Commandes"], insight: "Le chiffre d'affaires bondit de 71 % en septembre, porté par l'électronique.", q: "Pourquoi septembre a-t-il bondi ?", a: "L'électronique explique l'essentiel : +212 % par rapport à août.", chips: ["+71 % en septembre", "14 doublons détectés"] },
      { tab: "Stocks", file: "Stock_entrepot.xlsx", kpis: ["Articles en stock bas", "Surstock", "Jours de couverture moy."], insight: "38 produits seront en rupture d'ici deux semaines au rythme actuel.", q: "Que dois-je recommander en premier ?", a: "Cinq produits qui se vendent vite ont moins d'une semaine de stock.", chips: ["38 articles en stock bas", "12 % en surstock"] },
      { tab: "Finance", file: "Resultat_mensuel.xlsx", kpis: ["Bénéfice net", "Marge", "Anomalies"], insight: "Les dépenses marketing ont doublé en août sans hausse de revenus correspondante.", q: "Pourquoi la marge a-t-elle baissé ?", a: "Les dépenses marketing ont doublé alors que le chiffre d'affaires stagnait.", chips: ["3 anomalies signalées", "Marge en baisse de 4 pts"] },
    ],
    strip: [".xlsx natif", "Calculs déterministes", "Privé par conception", "Suppression à tout moment"],
  },
  problem: {
    label: "Le problème", title: "Les tableurs contiennent la vérité. La trouver, c'est le plus dur.",
    pains: [
      { big: "47 onglets", text: "Tableaux croisés, RECHERCHEV et final_v7_VRAI.xlsx, avant même de voir un graphique." },
      { big: "2 h", text: "À préparer des chiffres dont la réunion n'a besoin que de trois." },
      { big: "1 doute", text: "« Ce chiffre est-il juste ? » Et aucun moyen simple de vérifier." },
    ],
  },
  steps: {
    label: "Comment ça marche", title: "Trois étapes. Un café.",
    items: [
      { title: "Déposez votre classeur", text: "Importez un .xlsx. Tables, dates, mesures et formules sont détectées automatiquement." },
      { title: "Lisez l'histoire", text: "KPI, tendances, comparaisons et alertes qualité dans une seule vue claire." },
      { title: "Demandez, puis partagez", text: "Interrogez vos données en langage naturel, puis exportez un PDF prêt pour le client." },
    ],
  },
  chat: {
    label: "Interrogez votre tableur", title: "Vos questions. Des réponses vérifiées.",
    body: "Posez la question comme à un collègue. Chaque réponse est calculée à partir de vos données et vérifiée avant d'être affichée.",
    cta: "Essayer avec votre classeur", foot: "✓ Calculé à partir de vos données · vérifié avant affichage",
    items: [
      { q: "Quelle région croît le plus vite ?", a: "L'Afrique du Nord croît le plus vite à +42 %, devant le Golfe (+31 %) et l'Europe (+12 %).", bars: ["Afrique du Nord", "Golfe", "Europe"] },
      { q: "Pourquoi la marge a-t-elle baissé en août ?", a: "Les dépenses marketing ont doublé alors que le chiffre d'affaires stagnait, ce qui a réduit la marge d'environ 4 points.", bars: ["Marketing", "Logistique", "Salaires"] },
      { q: "Que dois-je recommander en premier ?", a: "Cinq produits qui se vendent vite ont moins d'une semaine de stock. Recommandez-les en premier.", bars: ["Produit A", "Produit B", "Produit C"] },
    ],
  },
  features: {
    label: "Fonctionnalités", title: "Pas un énième générateur de graphiques.",
    items: [
      { title: "KPI et tendances automatiques", text: "Les chiffres qui comptent, choisis pour vous." },
      { title: "Analyses fondées", text: "Chaque affirmation repose sur un calcul." },
      { title: "Signaux de qualité des données", text: "Doublons, trous et valeurs aberrantes signalés tôt." },
      { title: "Questions en langage naturel", text: "Zéro formule. Posez la question." },
      { title: "Investigation guidée", text: "Remontez d'un chiffre jusqu'à ses lignes sources." },
      { title: "Rapports PDF prêts pour le client", text: "Transformez l'analyse en document à envoyer dès aujourd'hui." },
    ],
  },
  trust: {
    label: "Confiance", title: "Votre classeur reste le vôtre.",
    body: "Les fichiers sont privés pour votre compte. L'analyse repose sur des calculs déterministes, et l'assistance IA est facultative.",
    items: [
      { title: "Stockage privé", text: "Protégé par des contrôles d'accès au niveau du compte." },
      { title: "Chiffres traçables", text: "Les chiffres sont recalculés et reliés à leurs lignes sources." },
      { title: "Vous décidez", text: "Consultez, exportez ou supprimez quand vous voulez." },
    ],
  },
  pricing: {
    label: "Tarifs", title: "Commencez gratuitement. Passez au payant quand ça devient rentable.",
    badge: "Le plus choisi", per: "/ mois",
    plans: [
      { name: "Gratuit", price: "0 DA", note: "pour essayer", perks: ["Quelques classeurs", "KPI, tendances et analyses", "Questions en langage naturel"], cta: "Commencer gratuitement" },
      { name: "Pro", price: "2 900 DA", note: "", perks: ["Classeurs illimités", "Rapports PDF prêts pour le client", "Investigation guidée", "Traitement prioritaire"], cta: "Passer en Pro" },
      { name: "Équipe", price: "7 900 DA", note: "", perks: ["Tout ce qu'inclut Pro", "Espace partagé", "Rapports d'équipe"], cta: "Démarrer en équipe" },
    ],
  },
  faq: {
    label: "FAQ", title: "Des réponses claires.",
    items: [
      { q: "Mes données sont-elles privées ?", a: "Oui. Les fichiers sont privés pour votre compte et protégés par des contrôles d'accès. Consultez, exportez ou supprimez-les quand vous voulez." },
      { q: "Dois-je écrire des formules ?", a: "Non. Excel Copilot lit la structure de votre classeur et fait les calculs. Vous regardez, ou vous demandez." },
      { q: "Puis-je me fier aux chiffres ?", a: "Les chiffres viennent de calculs déterministes sur vos propres données et renvoient à leurs lignes sources. L'assistance IA est facultative." },
      { q: "Quels fichiers sont pris en charge ?", a: "Excel Copilot est conçu pour les classeurs .xlsx." },
      { q: "Puis-je partager les résultats ?", a: "Oui. Exportez un PDF prêt pour le client directement depuis votre analyse." },
    ],
  },
  final: { title: "Apportez le tableur. Repartez avec de la clarté.", sub: "Importez un classeur et découvrez ce que vos données essaient de vous dire.", cta: "Commencer gratuitement" },
  footer: { tag: "Importez votre Excel. Comprenez vos données." },
};

const ar: Dict = {
  nav: { how: "كيف يعمل", pricing: "الأسعار", faq: "الأسئلة", signin: "دخول", start: "ابدأ" },
  hero: {
    h1a: "جدول بياناتك، ", h1b: "أخيرًا مفهوم.",
    sub: "ارفع ملف إكسل واحصل خلال ثوانٍ على المؤشرات والاتجاهات والمفاجآت، محسوبة من بياناتك أنت. بدون معادلات.",
    cta1: "حلّل ملفي", cta2: "شاهد كيف يعمل",
    ready: "جاهز", sample: "بيانات تجريبية", trend: "اتجاه الإيرادات", insightTitle: "أبرز ما لفت الانتباه",
    askTitle: "اسأل بياناتك", askPh: "اسأل عن بياناتك…",
    sets: [
      { tab: "المبيعات", file: "مبيعات_Q3.xlsx", kpis: ["الإيرادات", "النمو", "الطلبات"], insight: "قفزت الإيرادات 71٪ في سبتمبر بقيادة الإلكترونيات.", q: "لماذا قفز سبتمبر؟", a: "الإلكترونيات سبب معظم القفزة: +212٪ مقارنة بأغسطس.", chips: ["+71٪ في سبتمبر", "اكتشاف 14 صفًا مكررًا"] },
      { tab: "المخزون", file: "مخزون_المستودع.xlsx", kpis: ["أصناف منخفضة المخزون", "فائض المخزون", "متوسط أيام التغطية"], insight: "سينفد 38 منتجًا خلال أسبوعين بالوتيرة الحالية.", q: "ماذا أعيد طلبه أولًا؟", a: "خمسة منتجات سريعة البيع لديها مخزون أقل من أسبوع.", chips: ["38 صنفًا منخفض المخزون", "12٪ فائض مخزون"] },
      { tab: "المالية", file: "الأرباح_والخسائر.xlsx", kpis: ["صافي الربح", "الهامش", "حالات شاذة"], insight: "تضاعف الإنفاق التسويقي في أغسطس دون زيادة مقابلة في الإيرادات.", q: "لماذا انخفض الهامش؟", a: "تضاعف الإنفاق التسويقي بينما ظلت الإيرادات ثابتة.", chips: ["رصد 3 حالات شاذة", "انخفاض الهامش 4 نقاط"] },
    ],
    strip: ["يدعم .xlsx", "حسابات حتمية دقيقة", "خصوصية افتراضية", "احذف متى شئت"],
  },
  problem: {
    label: "المشكلة", title: "جداول البيانات تحمل الحقيقة، لكن الوصول إليها هو الصعب.",
    pains: [
      { big: "47 ورقة", text: "جداول محورية ودوال بحث وملف final_v7_REAL.xlsx قبل أن ترى أي رسم." },
      { big: "ساعتان", text: "لتحضير أرقام لا يحتاج الاجتماع منها إلا ثلاثة." },
      { big: "شك واحد", text: "«هل هذا الرقم صحيح؟» ولا طريقة سريعة للتحقق." },
    ],
  },
  steps: {
    label: "كيف يعمل", title: "ثلاث خطوات. فنجان قهوة.",
    items: [
      { title: "ارفع ملفك", text: "ارفع ملف .xlsx وسيتم اكتشاف الجداول والتواريخ والمقاييس والمعادلات تلقائيًا." },
      { title: "اقرأ القصة", text: "مؤشرات واتجاهات ومقارنات وتنبيهات جودة البيانات في عرض واحد واضح." },
      { title: "اسأل ثم شارك", text: "اسأل بياناتك بلغة بسيطة ثم صدّر تقرير PDF جاهزًا للعميل." },
    ],
  },
  chat: {
    label: "اسأل جدولك", title: "أسئلتك. إجابات موثّقة.",
    body: "اسأل كما تسأل زميلًا. كل إجابة تُحسب من بياناتك وتُراجع قبل عرضها.",
    cta: "جرّبه بملفك", foot: "✓ محسوب من بياناتك · تمت مراجعته قبل العرض",
    items: [
      { q: "أي منطقة نمت أسرع؟", a: "نمت شمال أفريقيا الأسرع بنسبة 42٪ متقدمة على الخليج (31٪) وأوروبا (12٪).", bars: ["شمال أفريقيا", "الخليج", "أوروبا"] },
      { q: "لماذا انخفض الهامش في أغسطس؟", a: "تضاعف الإنفاق التسويقي بينما ظلت الإيرادات ثابتة، فانخفض الهامش نحو 4 نقاط.", bars: ["التسويق", "اللوجستيات", "الرواتب"] },
      { q: "ماذا يجب أن أعيد طلبه أولًا؟", a: "خمسة منتجات سريعة البيع لديها مخزون أقل من أسبوع. أعد طلبها أولًا.", bars: ["منتج أ", "منتج ب", "منتج ج"] },
    ],
  },
  features: {
    label: "الإمكانيات", title: "ليس مجرد مولّد رسوم بيانية.",
    items: [
      { title: "مؤشرات واتجاهات تلقائية", text: "الأرقام المهمة، مختارة لك." },
      { title: "رؤى موثّقة", text: "كل جملة تدعمها عملية حسابية." },
      { title: "إشارات جودة البيانات", text: "التكرارات والفجوات والقيم الشاذة تُكتشف مبكرًا." },
      { title: "أسئلة بلغة بسيطة", text: "بدون معادلات. اسأل فقط." },
      { title: "تحقيق موجَّه", text: "تتبّع الرقم وصولًا إلى صفوفه المصدرية." },
      { title: "تقارير PDF جاهزة للعميل", text: "حوّل التحليل إلى ملف يمكنك إرساله اليوم." },
    ],
  },
  trust: {
    label: "الثقة", title: "ملفك يبقى ملكك.",
    body: "الملفات خاصة بحسابك. يعتمد التحليل على حسابات حتمية، والاستعانة بالذكاء الاصطناعي اختيارية.",
    items: [
      { title: "تخزين خاص", text: "محمي بضوابط وصول على مستوى الحساب." },
      { title: "أرقام يمكن تتبعها", text: "تُعاد حسابات الأرقام وترتبط بصفوفها المصدرية." },
      { title: "القرار لك", text: "راجع أو صدّر أو احذف متى شئت." },
    ],
  },
  pricing: {
    label: "الأسعار", title: "ابدأ مجانًا. ارتقِ عندما يؤتي ثماره.",
    badge: "الأكثر اختيارًا", per: "/ شهريًا",
    plans: [
      { name: "مجاني", price: "0 دج", note: "للتجربة", perks: ["بضعة ملفات", "مؤشرات واتجاهات ورؤى", "أسئلة بلغة بسيطة"], cta: "ابدأ مجانًا" },
      { name: "احترافي", price: "2 900 دج", note: "", perks: ["ملفات غير محدودة", "تقارير PDF جاهزة للعميل", "تحقيق موجَّه", "معالجة ذات أولوية"], cta: "اشترك الآن" },
      { name: "فريق", price: "7 900 دج", note: "", perks: ["كل ما في الاحترافي", "مساحة عمل مشتركة", "تقارير للفريق كله"], cta: "ابدأ مع فريقك" },
    ],
  },
  faq: {
    label: "الأسئلة", title: "إجابات مباشرة.",
    items: [
      { q: "هل بياناتي خاصة؟", a: "نعم. الملفات خاصة بحسابك ومحمية بضوابط وصول على مستوى الحساب. راجعها أو صدّرها أو احذفها متى شئت." },
      { q: "هل أحتاج إلى كتابة معادلات؟", a: "لا. يقرأ Excel Copilot بنية ملفك ويقوم بالحساب. أنت تنظر أو تسأل." },
      { q: "هل يمكنني الوثوق بالأرقام؟", a: "تأتي الأرقام من حسابات حتمية على بياناتك وترتبط بصفوفها المصدرية. الاستعانة بالذكاء الاصطناعي اختيارية." },
      { q: "ما الملفات المدعومة؟", a: "صُمّم Excel Copilot لملفات .xlsx." },
      { q: "هل يمكنني مشاركة النتائج؟", a: "نعم. صدّر تقرير PDF جاهزًا للعميل مباشرة من تحليلك." },
    ],
  },
  final: { title: "أحضر الجدول. وارحل بالوضوح.", sub: "ارفع ملفًا واحدًا واكتشف ما تحاول بياناتك قوله لك.", cta: "ابدأ مجانًا" },
  footer: { tag: "ارفع ملف إكسل. افهم بياناتك." },
};

const dict: Record<Lang, Dict> = { en, fr, ar };
const chatVals = [[92, 68, 26], [88, 34, 30], [95, 82, 64]];
const tints = Array(6).fill("bg-white shadow-sm ring-1 ring-black/5");
const spans = ["lg:col-span-2", "", "", "lg:col-span-2", "", "lg:col-span-2"];
const painTints = Array(3).fill("bg-white shadow-sm ring-1 ring-black/5");

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={`transition duration-700 ease-out ${shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"} ${className}`}>
      {children}
    </div>
  );
}

function useTypewriter(text: string, run: boolean, speed = 16, startDelay = 0) {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!run) { setOut(""); return; }
    setOut("");
    let i = 0;
    let id: ReturnType<typeof setInterval> | undefined;
    const t = setTimeout(() => {
      id = setInterval(() => {
        i += 1;
        setOut(text.slice(0, i));
        if (i >= text.length && id) clearInterval(id);
      }, speed);
    }, startDelay);
    return () => { clearTimeout(t); if (id) clearInterval(id); };
  }, [text, run, speed, startDelay]);
  return out;
}

function useCountUp(to: number, dec: number, ms = 1400) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      setV(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, ms]);
  return v.toFixed(dec);
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-green-100/80 px-3 py-1 text-xs font-medium text-green-800">
      <span className="h-1.5 w-1.5 rounded-full bg-green-600" aria-hidden />{children}
    </span>
  );
}

const ICONS = [
  "M5 20V11M12 20V5M19 20v-6",
  "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  "M5 21V4m0 0h11l-2 4 2 4H5",
  "M4 5h16v11H9l-5 4z",
  "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4-4",
  "M7 3h7l5 5v13H7zM14 3v5h5",
];

function Icon({ i, className = "h-5 w-5" }: { i: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={ICONS[i]} />
    </svg>
  );
}

const BTN_DARK = "inline-flex items-center justify-center gap-2 rounded-full bg-neutral-950 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-black/10 transition hover:-translate-y-0.5 hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 focus-visible:ring-offset-2";
const BTN_LIGHT = "inline-flex items-center justify-center gap-2 rounded-full border border-black/10 bg-white px-6 py-3.5 text-sm font-semibold text-neutral-900 transition hover:border-black/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600";

/* ------------------------------------------------------------------ */
/*  Hero product visual                                                */
/* ------------------------------------------------------------------ */

const SETS = [
  { series: [22, 30, 26, 41, 38, 52, 47, 64, 92], kpis: [{ to: 7.2, dec: 1, suffix: "M", prefix: "" }, { to: 71, dec: 0, prefix: "+", suffix: "%" }, { to: 339, dec: 0, prefix: "", suffix: "" }] },
  { series: [70, 66, 72, 61, 55, 49, 52, 38, 30], kpis: [{ to: 38, dec: 0, prefix: "", suffix: "" }, { to: 12, dec: 0, prefix: "", suffix: "%" }, { to: 9, dec: 0, prefix: "", suffix: "" }] },
  { series: [40, 44, 43, 50, 58, 55, 49, 46, 53], kpis: [{ to: 412, dec: 0, prefix: "", suffix: "K" }, { to: 18.4, dec: 1, prefix: "", suffix: "%" }, { to: 3, dec: 0, prefix: "", suffix: "" }] },
];

function Kpi({ label, to, dec, prefix, suffix }: { label: string; to: number; dec: number; prefix: string; suffix: string }) {
  const v = useCountUp(to, dec);
  return (
    <div className="rounded-xl bg-white p-3 ring-1 ring-black/5">
      <p className="truncate text-[11px] text-neutral-500">{label}</p>
      <p dir="ltr" className="mt-1 text-start text-xl font-semibold tabular-nums tracking-tight text-neutral-900 sm:text-2xl">{prefix}{v}{suffix}</p>
    </div>
  );
}

function HeroShowcase({ t }: { t: Dict["hero"] }) {
  const [set, setSet] = useState(0);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => setSet((s) => (s + 1) % 3), 8000);
    return () => clearInterval(id);
  }, [auto]);

  const d = t.sets[set];
  const data = SETS[set];
  const W = 360, H = 120;
  const pts = data.series.map((v, i) => [(i * W) / (data.series.length - 1), H - 6 - (v / 100) * (H - 18)] as const);
  let line = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1]; const [x1, y1] = pts[i]; const mx = (x0 + x1) / 2;
    line += ` C${mx} ${y0}, ${mx} ${y1}, ${x1} ${y1}`;
  }
  const area = `${line} L${W} ${H} L0 ${H} Z`;
  const last = pts[pts.length - 1];
  const answer = useTypewriter(d.a, true, 22, 1400);
  const pick = (i: number) => { setAuto(false); setSet(i); };

  return (
    <div className="relative mx-auto mt-14 max-w-5xl px-4 sm:px-6">
      {/* floating findings */}
      <div key={`c1-${set}`} className="absolute start-1 top-28 z-10 hidden animate-fade-up sm:block md:-start-4 lg:-start-10" style={{ animationDelay: "1.1s" }}>
        <div className="flex animate-float items-center gap-2 rounded-full bg-white px-3.5 py-2 text-xs font-medium shadow-[0_12px_30px_-10px_rgba(0,0,0,0.3)] ring-1 ring-black/5"><span className="h-2 w-2 rounded-full bg-green-500" />{d.chips[0]}</div>
      </div>
      <div key={`c2-${set}`} className="absolute end-1 top-64 z-10 hidden animate-fade-up sm:block md:-end-4 lg:-end-10" style={{ animationDelay: "1.8s" }}>
        <div className="flex animate-float items-center gap-2 rounded-full bg-white px-3.5 py-2 text-xs font-medium shadow-[0_12px_30px_-10px_rgba(0,0,0,0.3)] ring-1 ring-black/5" style={{ animationDelay: "-3s" }}><span className="h-2 w-2 rounded-full bg-amber-400" />{d.chips[1]}</div>
      </div>

      <div className="relative max-h-[34rem] overflow-hidden rounded-t-[1.75rem] bg-white shadow-[0_-10px_80px_-20px_rgba(21,80,45,0.3)] ring-1 ring-black/5">
        <div className="flex items-center gap-1.5 border-b border-black/5 px-4 py-3" dir="ltr">
          <span className="h-2.5 w-2.5 rounded-full bg-neutral-200" /><span className="h-2.5 w-2.5 rounded-full bg-neutral-200" /><span className="h-2.5 w-2.5 rounded-full bg-neutral-200" />
          <span className="mx-auto pe-10 text-[11px] text-neutral-400">Excel Copilot</span>
        </div>
        <div className="grid text-start md:grid-cols-[12rem_1fr] lg:grid-cols-[12rem_1fr_17rem]">
          {/* sidebar */}
          <div className="hidden border-e border-black/5 bg-[#faf9f6] p-3 md:block">
            <div className="space-y-1">
              {t.sets.map((x, i) => (
                <button key={x.tab} type="button" onClick={() => pick(i)} aria-pressed={set === i}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-start text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 ${set === i ? "bg-green-100 text-green-900" : "text-neutral-600 hover:bg-black/5"}`}>
                  <Icon i={5} className="h-4 w-4 shrink-0" />{x.tab}
                </button>
              ))}
            </div>
            <p className="mt-6 px-3 text-[11px] text-neutral-400">{t.sample}</p>
          </div>

          {/* main */}
          <div className="bg-[#f6f5f1] p-4 sm:p-5">
            <div className="mb-4 flex gap-2 md:hidden">
              {t.sets.map((x, i) => (
                <button key={x.tab} type="button" onClick={() => pick(i)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${set === i ? "bg-green-100 text-green-900" : "bg-white text-neutral-600"}`}>{x.tab}</button>
              ))}
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-lg bg-green-600 text-white"><Icon i={5} className="h-4 w-4" /></span>
                <p dir="ltr" className="text-sm font-semibold text-neutral-900">{d.file}</p>
              </div>
              <span className="rounded-full bg-green-100 px-2.5 py-1 text-[11px] font-medium text-green-800">{t.ready}</span>
            </div>

            <div key={`k-${set}`} className="mt-4 grid grid-cols-3 gap-2.5">
              {data.kpis.map((k, i) => <Kpi key={i} label={d.kpis[i]} to={k.to} dec={k.dec} prefix={k.prefix} suffix={k.suffix} />)}
            </div>

            <div className="mt-2.5 rounded-xl bg-white p-4 ring-1 ring-black/5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-neutral-900">{t.trend}</p>
                <p className="text-[10px] text-neutral-400">Jan – Sep</p>
              </div>
              <svg key={`s-${set}`} viewBox={`0 0 ${W} ${H}`} className="mt-3 h-32 w-full overflow-visible" style={{ direction: "ltr" }} role="img" aria-label={t.trend}>
                <defs><linearGradient id="hv-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#16a34a" stopOpacity="0.22" /><stop offset="100%" stopColor="#16a34a" stopOpacity="0" /></linearGradient></defs>
                {[0.25, 0.5, 0.75].map((g) => <line key={g} x1="0" x2={W} y1={H * g} y2={H * g} stroke="#ececec" strokeWidth="1" />)}
                <path d={area} fill="url(#hv-area)" className="animate-fade-up" style={{ animationDelay: "0.9s" }} />
                <path d={line} pathLength={1} fill="none" stroke="#16a34a" strokeWidth="3" strokeLinecap="round" className="draw-line" />
                <circle cx={last[0]} cy={last[1]} r="5" fill="#fff" stroke="#16a34a" strokeWidth="3" className="animate-fade-up" style={{ animationDelay: "1.5s" }} />
              </svg>
            </div>

            <div key={`i-${set}`} className="mt-2.5 flex animate-fade-up items-start gap-3 rounded-xl bg-green-50 p-3.5 ring-1 ring-green-100" style={{ animationDelay: "0.6s" }}>
              <span className="mt-0.5 text-green-700"><Icon i={1} className="h-4 w-4" /></span>
              <div>
                <p className="text-xs font-semibold text-green-900">{t.insightTitle}</p>
                <p className="mt-0.5 text-xs leading-5 text-green-900/80">{d.insight}</p>
              </div>
            </div>
          </div>

          {/* chat */}
          <div className="hidden flex-col border-s border-black/5 p-4 lg:flex">
            <p className="text-xs font-semibold text-neutral-900">{t.askTitle}</p>
            <div className="mt-4 space-y-2.5">
              <p key={`q-${set}`} className="ms-auto w-fit max-w-[90%] animate-fade-up rounded-xl rounded-ee-sm bg-neutral-950 px-3 py-2 text-xs text-white">{d.q}</p>
              <p className="min-h-[3.5rem] max-w-[95%] rounded-xl rounded-es-sm bg-[#f3f1ec] px-3 py-2 text-xs leading-5 text-neutral-700">{answer}</p>
            </div>
            <div className="mt-auto flex items-center justify-between rounded-full bg-[#f3f1ec] py-1.5 ps-3.5 pe-1.5 text-[11px] text-neutral-400">
              {t.askPh}
              <span className="grid h-6 w-6 place-items-center rounded-full bg-neutral-950 text-[10px] text-white" aria-hidden>↑</span>
            </div>
          </div>
        </div>
      </div>
      <div className="pointer-events-none absolute inset-x-4 bottom-0 h-40 bg-gradient-to-t from-[#fbfaf7] to-transparent sm:inset-x-6" aria-hidden />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chat demo                                                          */
/* ------------------------------------------------------------------ */

function ChatDemo({ t, lang }: { t: Dict["chat"]; lang: Lang }) {
  const [i, setI] = useState(0);
  const [thinking, setThinking] = useState(true);
  const c = t.items[i];
  useEffect(() => {
    setThinking(true);
    const id = setTimeout(() => setThinking(false), 800);
    return () => clearTimeout(id);
  }, [i, lang]);
  const typed = useTypewriter(c.a, !thinking, 14);
  const done = !thinking && typed.length === c.a.length;

  return (
    <div className="rounded-3xl bg-white p-5 shadow-[0_30px_70px_-30px_rgba(60,40,120,0.35)] ring-1 ring-black/5 sm:p-6">
      <div className="flex flex-wrap gap-2">
        {t.items.map((x, idx) => (
          <button key={x.q} type="button" onClick={() => setI(idx)} className={`rounded-full px-3.5 py-1.5 text-start text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 ${idx === i ? "bg-neutral-950 text-white" : "bg-[#f3f1ec] text-neutral-600 hover:bg-[#ebe8e1]"}`}>{x.q}</button>
        ))}
      </div>
      <div key={`${i}-${lang}`} className="mt-6 space-y-3">
        <div className="ms-auto w-fit max-w-[85%] animate-fade-up rounded-2xl rounded-ee-sm bg-neutral-950 px-4 py-2.5 text-sm text-white">{c.q}</div>
        <div className="max-w-[94%] rounded-2xl rounded-es-sm bg-[#f6f5f1] px-4 py-3.5 text-sm leading-6 text-neutral-800">
          {thinking ? <span className="inline-flex gap-1" aria-label="…">{[0, 1, 2].map((d) => <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400" style={{ animationDelay: `${d * 120}ms` }} />)}</span> : typed}
          <div className="mt-4 space-y-2.5">
            {c.bars.map((l, k) => (
              <div key={l} className="flex items-center gap-3 text-[11px] text-neutral-500">
                <span className="w-24 shrink-0">{l}</span>
                <span className="h-2 flex-1 overflow-hidden rounded-full bg-black/5"><span className="block h-full rounded-full bg-green-600 transition-all duration-1000" style={{ width: done ? `${chatVals[i][k]}%` : "0%" }} /></span>
              </div>
            ))}
          </div>
          {done && <p className="mt-4 text-[11px] font-medium text-green-700">{t.foot}</p>}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

function LangSwitch({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const opts: [Lang, string][] = [["en", "EN"], ["fr", "FR"], ["ar", "عربي"]];
  return (
    <div className="flex rounded-full bg-black/[0.05] p-0.5 text-[11px] font-medium" role="group" aria-label="Language">
      {opts.map(([k, label]) => (
        <button key={k} type="button" onClick={() => setLang(k)} aria-pressed={lang === k}
          className={`rounded-full px-3 py-1.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 ${lang === k ? "bg-white text-neutral-950 shadow-sm" : "text-neutral-500 hover:text-neutral-900"}`}>{label}</button>
      ))}
    </div>
  );
}

export default function LandingPage({ onGetStarted }: { onGetStarted: () => void }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    try {
      const s = localStorage.getItem("ec-lang");
      if (s === "en" || s === "fr" || s === "ar") { setLangState(s); return; }
      const n = navigator.language.slice(0, 2);
      if (n === "fr" || n === "ar") setLangState(n);
    } catch { /* storage unavailable */ }
  }, []);

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  const setLang = (l: Lang) => { setLangState(l); try { localStorage.setItem("ec-lang", l); } catch { /* ignore */ } };
  const t = dict[lang];
  const rtl = lang === "ar";
  const arrow = rtl ? "←" : "→";
  const h = rtl ? "leading-[1.3]" : "leading-[1.08] tracking-[-0.03em]";

  return (
    <main dir={rtl ? "rtl" : "ltr"} lang={lang} className="min-h-screen overflow-x-clip bg-[#fbfaf7] text-neutral-900 selection:bg-green-200">
      {/* nav */}
      <header className={`sticky top-0 z-50 transition ${scrolled ? "border-b border-black/5 bg-[#fbfaf7]/85 backdrop-blur-lg" : "border-b border-transparent"}`}>
        <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3.5">
          <a href="#" className="flex items-center gap-2.5" aria-label="Excel Copilot">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-green-600 text-white"><Icon i={5} className="h-4 w-4" /></span>
            <span className="text-[15px] font-semibold tracking-tight">Excel Copilot</span>
          </a>
          <div className="hidden items-center gap-8 text-sm text-neutral-600 md:flex">
            <a href="#how" className="transition hover:text-neutral-950">{t.nav.how}</a>
            <a href="#pricing" className="transition hover:text-neutral-950">{t.nav.pricing}</a>
            <a href="#faq" className="transition hover:text-neutral-950">{t.nav.faq}</a>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <LangSwitch lang={lang} setLang={setLang} />
            <button type="button" onClick={onGetStarted} className="hidden px-2 text-sm font-medium text-neutral-700 transition hover:text-neutral-950 sm:block">{t.nav.signin}</button>
            <button type="button" onClick={onGetStarted} className="rounded-full bg-neutral-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 focus-visible:ring-offset-2">{t.nav.start}</button>
          </div>
        </nav>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[38rem] bg-gradient-to-b from-green-50 to-transparent" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-6 pt-16 text-center sm:pt-20">
          <Pill>{t.hero.strip[0]} · {t.hero.strip[2]}</Pill>
          <h1 className={`mx-auto mt-6 max-w-4xl text-5xl font-semibold sm:text-6xl lg:text-7xl ${h}`}>
            {t.hero.h1a}
            <span className="bg-[linear-gradient(transparent_62%,#bbf7d0_62%)]">{t.hero.h1b}</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-neutral-600">{t.hero.sub}</p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={onGetStarted} className={BTN_DARK}>{t.hero.cta1} <span aria-hidden>{arrow}</span></button>
            <a href="#how" className={BTN_LIGHT}>{t.hero.cta2}</a>
          </div>
          <ul className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-neutral-500">
            {t.hero.strip.map((s) => <li key={s} className="flex items-center gap-1.5"><span className="text-green-600">✓</span>{s}</li>)}
          </ul>
        </div>
        <HeroShowcase t={t.hero} key={lang} />
      </section>

      {/* problem */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <Reveal className="max-w-3xl">
          <Pill>{t.problem.label}</Pill>
          <h2 className={`mt-5 text-3xl font-semibold sm:text-5xl ${h}`}>{t.problem.title}</h2>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {t.problem.pains.map((p, i) => (
            <Reveal key={p.big} delay={i * 90}>
              <article className={`h-full rounded-3xl p-8 ${painTints[i]}`}>
                <p className="text-4xl font-semibold tracking-tight text-neutral-900">{p.big}</p>
                <p className="mt-4 text-sm leading-6 text-neutral-700">{p.text}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* how */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-6 pb-24">
        <Reveal className="max-w-2xl">
          <Pill>{t.steps.label}</Pill>
          <h2 className={`mt-5 text-3xl font-semibold sm:text-5xl ${h}`}>{t.steps.title}</h2>
        </Reveal>
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {t.steps.items.map((s, i) => (
            <Reveal key={s.title} delay={i * 90}>
              <li className="h-full list-none rounded-3xl bg-white p-8 shadow-sm ring-1 ring-black/5 transition hover:-translate-y-1 hover:shadow-xl hover:shadow-black/5">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-green-100 text-sm font-semibold text-green-800">{i + 1}</span>
                <h3 className="mt-10 text-xl font-semibold tracking-tight">{s.title}</h3>
                <p className="mt-3 text-sm leading-6 text-neutral-600">{s.text}</p>
              </li>
            </Reveal>
          ))}
        </ol>
      </section>

      {/* chat */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid items-center gap-12 rounded-[2rem] bg-[#f1efe9] p-8 sm:p-12 lg:grid-cols-[0.85fr_1.15fr]">
          <Reveal>
            <Pill>{t.chat.label}</Pill>
            <h2 className={`mt-5 text-3xl font-semibold sm:text-4xl ${h}`}>{t.chat.title}</h2>
            <p className="mt-5 max-w-md text-sm leading-7 text-neutral-700">{t.chat.body}</p>
            <button type="button" onClick={onGetStarted} className={`${BTN_DARK} mt-8`}>{t.chat.cta} <span aria-hidden>{arrow}</span></button>
          </Reveal>
          <Reveal delay={100}><ChatDemo t={t.chat} lang={lang} /></Reveal>
        </div>
      </section>

      {/* features */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <Reveal className="max-w-2xl">
          <Pill>{t.features.label}</Pill>
          <h2 className={`mt-5 text-3xl font-semibold sm:text-5xl ${h}`}>{t.features.title}</h2>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {t.features.items.map((f, i) => (
            <Reveal key={f.title} delay={(i % 3) * 70} className={spans[i]}>
              <article className={`h-full rounded-3xl p-8 transition hover:-translate-y-1 ${tints[i]}`}>
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-green-50 text-green-700"><Icon i={i} /></span>
                <h3 className="mt-10 text-lg font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 max-w-sm text-sm leading-6 text-neutral-700">{f.text}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* trust */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <Reveal>
          <div className="rounded-[2rem] bg-[#f1efe9] p-8 sm:p-12">
            <div className="max-w-2xl">
              <Pill>{t.trust.label}</Pill>
              <h2 className={`mt-5 text-3xl font-semibold sm:text-4xl ${h}`}>{t.trust.title}</h2>
              <p className="mt-4 text-sm leading-7 text-neutral-700">{t.trust.body}</p>
            </div>
            <div className="mt-10 grid gap-3 sm:grid-cols-3">
              {t.trust.items.map((x) => (
                <div key={x.title} className="rounded-2xl bg-white p-6 shadow-sm">
                  <p className="text-sm font-semibold"><span className="me-2 text-green-600">●</span>{x.title}</p>
                  <p className="mt-2 text-xs leading-5 text-neutral-600">{x.text}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* pricing (placeholder prices: edit in the dictionaries above) */}
      <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-6 pb-24">
        <Reveal className="mx-auto max-w-2xl text-center">
          <Pill>{t.pricing.label}</Pill>
          <h2 className={`mt-5 text-3xl font-semibold sm:text-5xl ${h}`}>{t.pricing.title}</h2>
        </Reveal>
        <div className="mx-auto mt-12 grid max-w-5xl gap-4 md:grid-cols-3">
          {t.pricing.plans.map((p, i) => {
            const featured = i === 1;
            return (
              <Reveal key={p.name} delay={i * 90}>
                <article className={`relative flex h-full flex-col rounded-3xl p-8 ${featured ? "bg-neutral-950 text-white shadow-2xl shadow-black/20" : "bg-white shadow-sm ring-1 ring-black/5"}`}>
                  {featured && <span className="absolute -top-3 start-8 rounded-full bg-green-400 px-3 py-1 text-[11px] font-semibold text-neutral-950">{t.pricing.badge}</span>}
                  <h3 className="text-sm font-semibold">{p.name}</h3>
                  <p className="mt-5 flex flex-wrap items-baseline gap-2">
                    <span className="text-4xl font-semibold tabular-nums tracking-tight">{p.price}</span>
                    <span className={`text-xs ${featured ? "text-neutral-400" : "text-neutral-500"}`}>{i === 0 ? p.note : t.pricing.per}</span>
                  </p>
                  <ul className="mt-8 flex-1 space-y-3 text-sm">
                    {p.perks.map((perk) => <li key={perk} className={`flex gap-2.5 ${featured ? "text-neutral-300" : "text-neutral-600"}`}><span className="text-green-500" aria-hidden>✓</span>{perk}</li>)}
                  </ul>
                  <button type="button" onClick={onGetStarted} className={`mt-10 rounded-full px-5 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 ${featured ? "bg-white text-neutral-950 hover:bg-green-100" : "bg-neutral-950 text-white hover:bg-neutral-800"}`}>{p.cta}</button>
                </article>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* faq */}
      <section id="faq" className="mx-auto grid max-w-6xl scroll-mt-20 gap-12 px-6 pb-24 lg:grid-cols-[0.7fr_1.3fr]">
        <Reveal>
          <Pill>{t.faq.label}</Pill>
          <h2 className={`mt-5 text-3xl font-semibold sm:text-5xl ${h}`}>{t.faq.title}</h2>
        </Reveal>
        <div className="space-y-3">
          {t.faq.items.map((f) => (
            <details key={f.q} className="group rounded-2xl bg-white p-5 shadow-sm ring-1 ring-black/5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600">
                {f.q}<span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-green-100 text-lg text-green-800 transition group-open:rotate-45" aria-hidden>+</span>
              </summary>
              <p className="mt-3 max-w-xl text-sm leading-6 text-neutral-600">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* final CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <Reveal>
          <div className="rounded-[2rem] bg-[#f1efe9] px-6 py-20 text-center sm:px-12">
            <h2 className={`mx-auto max-w-3xl text-4xl font-semibold sm:text-6xl ${h}`}>{t.final.title}</h2>
            <p className="mx-auto mt-6 max-w-md text-sm leading-6 text-neutral-700">{t.final.sub}</p>
            <button type="button" onClick={onGetStarted} className={`${BTN_DARK} mt-9`}>{t.final.cta} <span aria-hidden>{arrow}</span></button>
          </div>
        </Reveal>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 pb-10 text-xs text-neutral-500">
        <span className="font-semibold text-neutral-800">Excel Copilot</span>
        <span>{t.footer.tag}</span>
        <LangSwitch lang={lang} setLang={setLang} />
        <span>© 2026 Excel Copilot</span>
      </footer>
    </main>
  );
}