/* ================================================================
   Choko Knowledge Base v2 — Nexus-UGC Complete App Guide
   Covers: all pages, features, workflows, how-tos, and architecture.
   ================================================================ */

const CHOKO_KNOWLEDGE = {
  app: {
    name: "Nexus-UGC",
    tagline: "AI-Powered Viral Video Engine",
    description: "Turn long-form videos into viral short clips automatically. Upload once, get AI-transcribed, scored, reframed, and captioned clips in 16 languages — all running 100% locally.",
    architecture: "7 agents: Perception (Whisper.cpp transcription), Strategist (Ollama Qwen for hook selection), Scoring (heuristic ranking), Caption Style (AI style selection), Editing (FFmpeg rendering), Publishing (multi-platform posting), Orchestrator (lifecycle + progress + cancellation).",
    tech: { stack: ["Python (FastAPI)", "Whisper.cpp", "Ollama / Qwen", "FFmpeg", "HTML/CSS/JS Vanilla"], privacy: "100% local. No cloud dependency. No data leaves your machine." },
    urls: { pipeline: "/#app", brainrot: "/brainrot.html", queue: "/queue.html", accounts: "/accounts.html", billing: "/billing.html", calendar: "/calendar.html", personas: "/personas.html", campaigns: "/campaigns.html", admin: "/admin.html", login: "/login.html" },
  },

  pages: {
    dashboard: { title: "Dashboard (Home)", url: "/", description: "Landing page with hero, feature cards, upload pipeline, processing status, results with clips, pricing plans, and footer." },
    brainrot: { title: "Brain Rot Shorts Generator", url: "/brainrot.html", description: "One-click viral short generator. Pick a niche (drama/gaming/fake life stories/motivation/money/facts), caption style (brain rot/hype/clean), and platform (YouTube/TikTok). AI generates script, renders 30s video with captions, and creates a pending post." },
    queue: { title: "Post Queue", url: "/queue.html", description: "Review, approve, schedule, or cancel posts before they go live. Status tabs: Pending, Approved, Scheduled, Failed, Drafts. Approve for immediate publishing, schedule for later, retry failed posts. Auto-refreshes every 30s." },
    accounts: { title: "Social Accounts", url: "/accounts.html", description: "Connect and manage social platform accounts. Supports YouTube, TikTok, Instagram, X/Twitter, Facebook, LinkedIn. Add via manual token entry or OAuth. Account Groups for batch publishing. Token health indicators show connection status." },
    billing: { title: "Billing & Licensing", url: "/billing.html", description: "Current plan display, pricing cards (Free/Pro/Enterprise), Whop license key claim form, monthly usage progress bar." },
    calendar: { title: "Content Calendar", url: "/calendar.html", description: "Monthly grid view of scheduled posts. Color-coded by status. Click a day to compose a new post. Click a post to approve/schedule/cancel/delete. Filter by persona or platform." },
    personas: { title: "Personas", url: "/personas.html", description: "Create brand identities with name, avatar, bio, voice, target audience, tone, and content pillars. Auto-approve option for automated publishing. Repurpose content into platform-specific posts." },
    campaigns: { title: "Campaigns", url: "/campaigns.html", description: "Organize content around themes or events. Assign personas, select platforms, set date ranges. Activate/pause campaigns. Track publishing progress." },
    admin: { title: "Admin Panel", url: "/admin.html", description: "6 views: Overview (stats), System Health (database + worker probes), Publishing (per-platform analytics), Users, Accounts (all connected accounts), Licenses (Whop license management). Enterprise tier or admin@nexusugc.com access." },
  },

  features: {
    pipeline: {
      name: "Video Upload Pipeline",
      steps: ["Upload a video file (MP4/MOV/AVI/MKV/WebM, up to 2GB) or paste a Google Drive link", "Choose caption language (16 languages available)", "Select output aspect ratio (9:16 vertical, 1:1 square, 4:5 portrait, 16:9 landscape, or original)", "Add optional end screen image and CTA text", "Click Start Analysis — AI processes locally", "Review clips with virality scores (1-100)", "Download or publish directly to social platforms"],
      languages: 16,
      aspectRatios: ["9:16 (TikTok/Reels)", "1:1 (Instagram)", "4:5 (Facebook)", "16:9 (YouTube)", "Original (no reframe)"],
    },
    brainrot: {
      name: "Brain Rot Shorts Generator",
      niches: ["Drama", "Gaming", "Fake Life Stories", "Motivation", "Money/Hustle", "Mind-Blowing Facts"],
      captionStyles: ["Brain Rot (Impact) — bold center, cyan gradient, high energy", "Hype (Yellow/Red) — aggressive call-to-action style", "Clean (Minimal) — white text, subtle, professional"],
      buttons: ["Generate Script — AI writes hook + script + caption cues via Ollama", "Render & Publish — creates 30s video with animated captions", "One-Click Publish — generates + renders + creates post in one step"],
      flow: "Select niche → Pick caption style → Choose platform → Click Generate → Review script → Click Render → Preview video → Click Publish → Post appears in Queue as 'pending' → Approve in Queue → Auto-publishes on next worker cycle",
    },
    queue: {
      name: "Post Queue & Auto-Publishing",
      statuses: { pending: "Awaiting review. Approve, schedule, or cancel.", approved: "Will be published on next worker cycle (every 60s). Can still be scheduled or cancelled.", scheduled: "Set for future publishing at the scheduled time.", failed: "Publishing failed. Check error message and retry after fixing the issue.", posted: "Successfully published. Check the platform to view.", cancelled: "Manually cancelled. Won't be published.", draft: "Not yet submitted for review." },
      autoPublish: "A background worker runs every 60 seconds. It picks up approved posts and publishes them immediately. Scheduled posts publish when their scheduled_at time arrives. No manual action needed after approval.",
    },
    accounts: {
      name: "Social Account Management",
      platforms: ["YouTube (refresh token + channel ID)", "TikTok (access token + refresh token + open ID)", "Instagram (access token + user ID)", "X/Twitter (access token + user ID)", "Facebook (access token + page ID)", "LinkedIn (access token + user ID)"],
      systemAccounts: "If SYSTEM_ACCOUNTS_ENABLED=true in .env, the app auto-creates system-level accounts on startup from configured credentials. You don't need to manually add accounts — just set tokens in .env and restart.",
      groups: "Account Groups let you batch-publish to multiple platforms at once. Create a group, add accounts, and publish to the group.",
    },
    publishing: {
      platforms: ["YouTube", "TikTok", "Instagram", "Facebook", "LinkedIn", "X (Twitter)"],
      howToPublish: ["Go to Queue page", "Find your pending post", "Click Approve (publishes immediately) or Schedule (set future time)", "The auto-publish worker will handle the rest", "Check status after worker cycle (60s max wait)"],
      autoPublishFlow: "Brain Rot → creates post as 'pending' → User approves in Queue → Worker picks up 'approved' posts → Publishes to selected platform → Sets status to 'posted' or 'failed'",
    },
    calendar: {
      name: "Content Calendar",
      useCases: ["View monthly schedule of all posts", "Color-coded by status (green=posted, red=failed, amber=pending, etc.)", "Click any day to create a new post", "Click any post to approve/schedule/cancel", "Filter by persona or platform"],
    },
    personas: {
      name: "Personas",
      fields: ["Name", "Bio", "Voice description", "Target audience", "Content pillars (topics/themes)", "Tone (professional, casual, etc.)", "Auto-approve toggle (auto-publish generated content)"],
      useCases: ["Create brand-specific content voices", "Define target audience and tone per brand", "Generate consistent posting schedules", "Auto-publish approved content without manual review"],
    },
    campaigns: {
      name: "Campaigns",
      features: ["Organize content around themes (product launch, event, seasonal)", "Assign persona and select platforms", "Set start/end dates", "Track publishing progress per campaign", "Activate or pause campaigns"],
    },
    security: {
      name: "Security Features",
      features: ["JWT authentication with 24h expiry (configurable)", "Per-user password salting (PBKDF2-HMAC-SHA256, 600k iterations)", "Rate limiting: 60 req/min general, 10 req/min auth endpoints", "Security headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy", "CSRF protection (for cookie-based auth future)", "CORS with restricted methods/headers", "Stripe webhook signature verification", "Input sanitization (HTML/JS stripping)", "Audit logging of sensitive operations", "Token encryption at rest (AES-256-CBC via Fernet)"],
    },
    multitenant: {
      name: "Multi-Tenant (Future)",
      features: ["Tenant model with slug, domain, user limits", "tenant_id on User model for data isolation", "Tenant-aware JWT payload", "Tenant middleware for scoped API access"],
    },
  },

  workflows: {
    howToBrainRot: {
      title: "How to create a Brain Rot Short",
      steps: ["Go to the Brain Rot page (/brainrot.html)", "Select a niche (Drama, Gaming, Fake Life Stories, Motivation, Money, Facts)", "Pick a caption style (Brain Rot, Hype, Clean)", "Choose target platform (YouTube Shorts or TikTok)", "Optionally enter a video idea or custom title", "Click 'Generate Script' — wait for AI to write the script", "Review the hook, full script, and caption cues", "Click 'Render & Publish' to create the video", "Click 'One-Click Publish' to create the post", "Go to Queue page to approve or schedule the post", "Worker auto-publishes on next cycle after approval"],
    },
    howToPublish: {
      title: "How to publish to social media",
      steps: ["Make sure you have accounts connected (Accounts page)", "Generate content via Brain Rot or Pipeline upload", "Post appears in Queue as 'pending'", "Go to Queue page", "Click Approve (publishes immediately) or Schedule (pick date/time)", "Worker publishes within 60 seconds", "Check status refreshes automatically every 30s"],
      note: "If SYSTEM_ACCOUNTS_ENABLED=true in .env, the app has built-in accounts and you don't need to add them manually.",
    },
    howToConnectAccounts: {
      title: "How to connect social accounts",
      methods: [
        { name: "Manual (recommended for testing)", steps: ["Go to Accounts page", "Click 'Add Account'", "Select platform", "Enter account name", "Paste tokens from platform developer portal", "Enter platform-specific ID (channel ID, user ID, etc.)", "Click Save"] },
        { name: "System Accounts (auto)", steps: ["Set SYSTEM_ACCOUNTS_ENABLED=true in .env", "Fill in platform token variables (SYSTEM_YOUTUBE_REFRESH_TOKEN, etc.)", "Restart the server", "Accounts are auto-provisioned on startup"] },
      ],
    },
    howToUsePipeline: {
      title: "How to process a video through the pipeline",
      steps: ["Go to the Dashboard page", "Upload a video file (or paste Google Drive link)", "Select caption language and output aspect ratio", "Optionally add an end screen image and CTA text", "Click 'Start Analysis'", "Wait for AI to process (Whisper + Ollama + FFmpeg)", "Review the transcript and virality scores", "View generated clips with preview player", "Download clips or publish directly"],
    },
    howToCreatePersona: {
      title: "How to create a Persona",
      steps: ["Go to Personas page", "Click '+ New Persona'", "Enter name, bio, and voice description", "Define target audience", "Add content pillars (themes for posts)", "Select tone (professional, casual, etc.)", "Toggle auto-approve if desired", "Click Save"],
    },
    howToSchedule: {
      title: "How to schedule a post",
      steps: ["Go to Queue page", "Find the post you want to schedule", "Click 'Schedule' button", "Pick date and time in the modal", "Click Confirm", "Post will publish automatically at the scheduled time"],
    },
    howToUseCalendar: {
      title: "How to use the Content Calendar",
      steps: ["Go to Calendar page", "View monthly grid with post indicators", "Click a day to create a new post", "Select persona, platform, and set time", "Enter title and body", "Click Schedule", "Click existing posts to approve/schedule/cancel"],
    },
    howToCampaigns: {
      title: "How to use Campaigns",
      steps: ["Go to Campaigns page", "Click '+ New Campaign'", "Enter name, description", "Select persona and platforms", "Set start and end dates", "Click Save", "Use Activate/Pause to control campaign"],
    },
  },

  troubleshooting: {
    noYoutubeAccount: "Error 'No YouTube account connected' means the platform credentials aren't configured. Either: 1) Add a YouTube account manually in Accounts page, or 2) Set SYSTEM_ACCOUNTS_ENABLED=true and SYSTEM_YOUTUBE_REFRESH_TOKEN in .env",
    noTikTokAccount: "Same as above but for TikTok. Configure SYSTEM_TIKTOK_ACCESS_TOKEN in .env or add manually.",
    brainRotFails: "Brain Rot generation requires Ollama running on port 11434 with a model installed (phi3:latest is recommended for 2GB VRAM). Check that Ollama is running and the model is pulled.",
    videoRenderFails: "Video rendering requires FFmpeg with proper codec support. Check that FFmpeg is installed and the output directory has write permissions.",
    authFailed: "Login requires a registered user. Register a new account to get started. Rate limiting may block repeated attempts — wait 60s between retries.",
  },
};

const normalize = (value) =>
  value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9+#.\s-]/g, " ").replace(/\s+/g, " ").trim();

const includesAny = (text, words) => words.some((word) => text.includes(word));
const includesAll = (text, words) => words.every((word) => text.includes(word));

function detectCurrentPage() {
  const path = window.location.pathname;
  if (path === "/" || path === "/index.html") return "dashboard";
  if (path.includes("brainrot")) return "brainrot";
  if (path.includes("queue")) return "queue";
  if (path.includes("accounts")) return "accounts";
  if (path.includes("billing")) return "billing";
  if (path.includes("calendar")) return "calendar";
  if (path.includes("personas")) return "personas";
  if (path.includes("campaigns")) return "campaigns";
  if (path.includes("admin")) return "admin";
  if (path.includes("login")) return "login";
  return "unknown";
}

function generatePageSuggestions() {
  const page = detectCurrentPage();
  const all = [
    "What is Nexus-UGC?",
    "How does the pipeline work?",
    "What features are available?",
    "How do I publish to social media?",
    "What are the pricing plans?",
  ];
  const pageSpecific = {
    dashboard: ["How do I upload a video?", "What aspect ratios are available?", "What languages are supported?", "How does virality scoring work?"],
    brainrot: ["How do I create a Brain Rot short?", "What niches are available?", "What caption styles exist?", "How does auto-publishing work?"],
    queue: ["How do I approve a post?", "How do I schedule a post?", "Why did my post fail?", "How does the auto-publish worker work?"],
    accounts: ["How do I connect an account?", "What platforms are supported?", "What are system accounts?", "How do account groups work?"],
    billing: ["What are the pricing plans?", "How do I claim a Whop license?", "What is the free tier limit?"],
    calendar: ["How do I use the calendar?", "How do I create a post from the calendar?"],
    personas: ["How do I create a Persona?", "What is auto-approve?"],
    campaigns: ["How do I create a campaign?", "How do I activate a campaign?"],
    admin: ["How do I view system health?", "How do I manage users?"],
    login: ["How do I register?", "What is the admin password?"],
  };
  return [...(pageSpecific[page] || []), ...all].slice(0, 8);
}

window.CHOKO_SUGGESTIONS = generatePageSuggestions();

const answerChokoQuestion = (rawQuestion) => {
  const question = normalize(rawQuestion);
  const { app, pages, features, workflows, troubleshooting } = CHOKO_KNOWLEDGE;

  if (!question) return "Ask me about Nexus-UGC features, how-tos, pages, or troubleshooting! Currently on: " + (pages[detectCurrentPage()]?.title || "unknown page");

  // Greetings
  if (includesAny(question, ["hi", "hello", "hey", "greetings", "what's up", "sup"])) {
    return "Hey there! I'm Choko, your Nexus-UGC guide. Ask me about any page, feature, or workflow. I can help with Brain Rot, publishing, accounts, pipelines, and more!";
  }

  // Page detection
  if (includesAny(question, ["what page", "where am i", "current page", "this page"])) {
    const page = detectCurrentPage();
    const info = pages[page];
    return info ? `You're on the **${info.title}** page. ${info.description}` : "I'm not sure which page this is!";
  }

  // What is Nexus-UGC
  if (includesAny(question, ["what is nexus", "what is nexus-ugc", "what does nexus", "about", "what is this"])) {
    return `${app.name}: ${app.description} Architecture: ${app.architecture} Key features: multi-language captions, virality scoring, auto reframe, smart transcription, animated captions, one-click publish, AI thumbnails, and more. All running locally with no cloud dependency.`;
  }

  // Tech stack / privacy
  if (includesAny(question, ["technical", "stack", "technology", "local", "privacy", "private", "offline", "how it works"])) {
    return `Stack: ${app.tech.stack.join(", ")}. ${app.tech.privacy}`;
  }

  // Pipeline / upload
  if (includesAny(question, ["pipeline", "upload", "process", "analyze", "how does it work", "whisper", "clip"])) {
    const p = features.pipeline;
    return `The video pipeline works in ${p.steps.length} steps: ${p.steps.map((s, i) => `${i + 1}) ${s}`).join(". ")}. Supports ${p.languages} languages and aspect ratios: ${p.aspectRatios.join(", ")}.`;
  }

  // Features overview
  if (includesAny(question, ["feature", "capabilities", "what can", "what all", "list"])) {
    return `Key features: ${Object.values(features).map((f) => f.name || f.title).join(", ")}. Each feature has its own page — ask me about any one!`;
  }

  // ---- PAGE-SPECIFIC ----

  // Brain Rot
  if (includesAny(question, ["brain rot", "brainrot", "shorts generator", "viral short", "short form"])) {
    const br = features.brainrot;
    return `${br.name}: ${br.niches.length} niches (${br.niches.join(", ")}), ${br.captionStyles.length} caption styles (${br.captionStyles.join("; ")}). Flow: ${br.flow}`;
  }
  if (includesAny(question, ["niche", "drama", "gaming", "motivation", "money", "facts", "life stories"])) {
    return `Available niches: ${features.brainrot.niches.join(", ")}. Pick one that fits your content theme!`;
  }
  if (includesAny(question, ["caption style", "brain rot style", "hype", "clean", "impact"])) {
    return `Caption styles: ${features.brainrot.captionStyles.join("; ")}. Brain Rot is bold and energetic, Hype is aggressive with yellow/red, Clean is minimal and professional.`;
  }

  // Queue
  if (includesAny(question, ["queue", "approve", "approval", "pending post", "post queue"])) {
    const q = features.queue;
    return `The Post Queue manages your content lifecycle. Statuses: ${Object.entries(q.statuses).map(([k, v]) => `${k}: ${v}`).join(". ")}. ${q.autoPublish}`;
  }
  if (includesAny(question, ["approve post", "how to approve"])) {
    return "To approve a post, go to the Queue page, find the pending post, and click the 'Approve' button. The auto-publish worker will pick it up within 60 seconds and publish it.";
  }
  if (includesAny(question, ["schedule post", "how to schedule", "post later"])) {
    return "To schedule a post: go to Queue, find your post, click 'Schedule', pick a date and time in the modal, and confirm. The worker will publish it automatically when the time arrives.";
  }
  if (includesAny(question, ["failed post", "post failed", "error", "retry"])) {
    return "If a post fails, check the error message shown in the Queue. Common issues: no account connected (connect one or use system accounts), invalid tokens (refresh them), or network errors (try again). Click 'Retry' to re-attempt publishing.";
  }
  if (includesAny(question, ["auto publish", "auto-post", "auto posting", "worker", "background"])) {
    return `${features.queue.autoPublish}`;
  }

  // Accounts
  if (includesAny(question, ["account", "connect", "social", "platform", "oauth", "token"])) {
    const a = features.accounts;
    return `Supported platforms: ${a.platforms.join(", ")}. ${a.systemAccounts}. Groups: ${a.groups}`;
  }
  if (includesAny(question, ["system account", "auto account", "env account", "built-in"])) {
    return features.accounts.systemAccounts;
  }
  if (includesAny(question, ["account group", "batch publish", "group"])) {
    return features.accounts.groups;
  }

  // Billing
  if (includesAny(question, ["pricing", "price", "cost", "plan", "free", "pro", "enterprise", "subscription", "billing", "whop", "license"])) {
    const p = [
      ["Free", "$0/mo", "5 credits, English only, standard ARs, virality score"],
      ["Pro", "$19/mo", "60 min video, all 16 languages, all ARs, AI analysis, end screen, priority processing"],
      ["Enterprise", "$99/mo", "Unlimited, all languages + custom, API/webhooks, team collab, priority support"],
    ];
    return `Plans: ${p.map(([n, pr, f]) => `${n} (${pr}) — ${f}`).join(". ")}. Purchase a license via Whop (go to Billing page and enter your license key).`;
  }

  // Calendar
  if (includesAny(question, ["calendar", "content calendar"])) {
    const c = features.calendar;
    return `${c.name}: ${c.useCases.join(". ")}.`;
  }

  // Personas
  if (includesAny(question, ["persona", "brand voice", "content profile", "voice"])) {
    const p = features.personas;
    return `${p.name}: Fields — ${p.fields.join(", ")}. Use cases: ${p.useCases.join("; ")}.`;
  }
  if (includesAny(question, ["auto approve persona"])) {
    return "The auto-approve toggle on a Persona automatically approves generated posts (sets them to 'approved' status) so they go straight to publishing without manual review. Use with caution!";
  }

  // Campaigns
  if (includesAny(question, ["campaign", "campaigns"])) {
    const c = features.campaigns;
    return `${c.name}: ${c.features.join(". ")}.`;
  }

  // Admin
  if (includesAny(question, ["admin", "admin panel", "manage users", "system health"])) {
    const a = pages.admin;
    return `${a.description}. Access requires enterprise tier or admin@nexusugc.com email.`;
  }

  // Security
  if (includesAny(question, ["security", "secure", "protected", "csrf", "rate limit", "password", "encrypt", "header"])) {
    return `Security features: ${features.security.features.join("; ")}.`;
  }

  // Multi-tenant
  if (includesAny(question, ["multi tenant", "tenant", "multi-user", "team", "organization"])) {
    return `Multi-tenant architecture: ${features.multitenant.features.join("; ")}. Ready for future client deployments.`;
  }

  // Pipeline steps
  if (includesAny(question, ["language", "translate", "16 lang", "caption lang"])) {
    return `Nexus-UGC supports 16 languages: English, Spanish, French, German, Italian, Portuguese, Russian, Japanese, Korean, Chinese, Arabic, Hindi, Dutch, Turkish, Vietnamese, and Thai.`;
  }
  if (includesAny(question, ["aspect ratio", "format", "9:16", "16:9", "1:1", "4:5"])) {
    return features.pipeline.aspectRatios.join(", ");
  }
  if (includesAny(question, ["virality", "score", "viral", "prediction"])) {
    return "Every clip gets a hybrid heuristic + AI virality prediction score from 1-100. Scores above 70 are high-potential viral clips. The scoring considers semantic keywords, speech density, scene boundaries, and duration diversity.";
  }
  if (includesAny(question, ["caption style", "animated", "subtitle", "style agent"])) {
    return "6 caption styles: neutral, impact, question, money, warning, hype. The Caption Style Agent (AI) selects the best style per cue automatically. You can also choose rule-based or hybrid mode.";
  }

  // ---- WORKFLOWS ----

  // How to Brain Rot
  if (includesAll(question, ["how", "brain", "rot"]) || (includesAny(question, ["create short", "make short", "generate short"]) && includesAny(question, ["brain", "rot"]))) {
    return workflows.howToBrainRot.steps.map((s, i) => `${i + 1}. ${s}`).join("\n");
  }
  if (includesAll(question, ["how", "publish"]) || (includesAny(question, ["post video", "upload video", "share video"]) && includesAny(question, ["social", "youtube", "tiktok", "instagram"]))) {
    return `To publish: ${features.publishing.howToPublish.join(" → ")}. The auto-publish flow: ${features.publishing.autoPublishFlow}.`;
  }
  if (includesAll(question, ["how", "connect"]) || includesAll(question, ["add", "account"])) {
    return `Two ways: 1) Manual: Go to Accounts page → Add Account → select platform → enter tokens. 2) System: Set SYSTEM_ACCOUNTS_ENABLED=true and platform tokens in .env → restart. The app creates accounts automatically.`;
  }
  if (includesAll(question, ["how", "schedul"]) || includesAny(question, ["schedule post", "post later", "delay publish"])) {
    return workflows.howToSchedule.steps.join(" ");
  }
  if (includesAll(question, ["how", "persona"]) || (includesAny(question, ["create persona", "new persona"]))) {
    return workflows.howToCreatePersona.steps.join(" ");
  }
  if (includesAll(question, ["how", "calendar"])) {
    return workflows.howToUseCalendar.steps.join(" ");
  }
  if (includesAll(question, ["how", "campaign"])) {
    return workflows.howToCampaigns.steps.join(" ");
  }
  if (includesAll(question, ["how", "upload"]) || includesAll(question, ["how", "process"]) || includesAny(question, ["start analysis", "upload video"])) {
    return workflows.howToUsePipeline.steps.join(" ");
  }

  // ---- TROUBLESHOOTING ----
  if (includesAny(question, ["troubleshoot", "issue", "problem", "broken", "not working", "error", "fail"])) {
    return Object.values(troubleshooting).join(" ");
  }
  if (includesAny(question, ["no account", "youtube account", "tiktok account", "account connected"])) {
    return troubleshooting.noYoutubeAccount;
  }
  if (includesAny(question, ["model", "ollama", "phi3", "qwen", "ai not", "brain rot fail"])) {
    return troubleshooting.brainRotFails;
  }
  if (includesAny(question, ["ffmpeg", "render", "video fail", "no video"])) {
    return troubleshooting.videoRenderFails;
  }
  if (includesAny(question, ["login", "auth", "can't log", "password wrong", "rate limit"])) {
    return troubleshooting.authFailed;
  }
  if (includesAny(question, ["navigation", "go to", "where is", "find the", "link to"])) {
    const targets = { "brain rot": "brainrot.html", "queue": "queue.html", "accounts": "accounts.html", "billing": "billing.html", "calendar": "calendar.html", "personas": "personas.html", "campaigns": "campaigns.html", "admin": "admin.html", "dashboard": "index.html", "login": "login.html" };
    const found = Object.entries(targets).find(([k]) => question.includes(k));
    return found ? `You can find the ${found[0]} page at /${found[1]}. Use the navbar or sidebar to navigate!` : "Pages: Dashboard, Brain Rot, Queue, Accounts, Billing, Calendar, Personas, Campaigns, Admin. Which one are you looking for?";
  }

  return `I can answer questions about: Nexus-UGC features (pipeline, Brain Rot, publishing), how-tos (uploading, connecting accounts, scheduling posts), pages (Dashboard, Brain Rot, Queue, Accounts, Billing, Calendar, Personas, Campaigns), troubleshooting, and security. Try asking something specific!`;
};
