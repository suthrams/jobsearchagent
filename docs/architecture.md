# Architecture Diagrams

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render automatically on GitHub.

---

## 1. System Architecture — Component Overview

High-level block diagram showing the four layers and how components relate.

```mermaid
graph TB
    subgraph ENTRY["Entry Points"]
        CLI["main.py\nCLI"]
        DASH["dashboard.py\nStreamlit UI"]
    end

    subgraph AGENTS["Agent Layer"]
        PA["ProfileAgent\nResume → Profile"]
        SA["ScoringAgent\nBatch Scorer"]
        TA["TailoringAgent\nResume Tailoring"]
    end

    subgraph CLAUDE["Claude Layer"]
        CC["ClaudeClient\nAnthropic SDK"]
        PL["PromptLoader\nTemplate Engine"]
        RP["ResponseParser\nJSON Validator"]
    end

    subgraph DATA["Data Layer"]
        direction LR
        LI["LinkedIn\nScraper"]
        AZ["Adzuna\nScraper"]
        LA["Ladders\nScraper"]
        DB[("SQLite\nDatabase")]
        CACHE["Profile Cache\ndata/profile.json"]
    end

    subgraph EXTERNAL["External Services"]
        ANTHROPIC["Anthropic API\nclaude-sonnet-4-6"]
        ADZUNA_API["Adzuna REST API"]
    end

    CLI --> PA
    CLI --> SA
    CLI --> TA
    DASH --> DB

    PA --> CC
    PA --> CACHE
    SA --> CC
    TA --> CC

    CC --> PL
    CC --> RP
    CC --> ANTHROPIC

    LI --> DB
    AZ --> DB
    LA --> DB
    AZ --> ADZUNA_API

    SA --> DB
    TA --> DB
    PA --> DB
```

---

## 2. Main Run — Control Flow

End-to-end flow for `python main.py` (the default scrape + score command).

```mermaid
flowchart TD
    START([python main.py]) --> CONFIG[Load & validate\nconfig.yaml]
    CONFIG --> BOOT[Bootstrap\nDB · ClaudeClient · Agents]
    BOOT --> SCRAPE

    subgraph SCRAPE["Scrape Phase"]
        S1["LinkedInScraper\ninbox/linkedin.txt"]
        S2["AdzunaScraper\nAdzuna REST API"]
        S3["LaddersScraper\nHTML scraping"]
        S1 & S2 & S3 --> MERGE["Merge results\nN jobs"]
    end

    MERGE --> DEDUP["Deduplicate\nby URL + title+company"]
    DEDUP --> INSERT["Insert new jobs\nstatus = NEW"]
    INSERT --> UNSCORED["Query: get_by_status(NEW)"]

    UNSCORED --> ESTIMATE["Estimate API cost\nShow to user"]
    ESTIMATE --> CONFIRM{User confirms\ny/N?}
    CONFIRM -- N --> CANCEL([Cancelled])
    CONFIRM -- Y --> PROFILE

    subgraph SCORE["Score Phase"]
        PROFILE["ProfileAgent.load()\nresume.pdf → Profile"]
        PROFILE --> FILTER["Filter jobs\nstale · no desc · excluded title · non-tech"]
        FILTER --> BATCH["Chunk into\nbatches of 5"]
        BATCH --> CLAUDE["Claude API call\n5 jobs → 3-track scores"]
        CLAUDE --> SAVE["db.update_job()\nstatus = SCORED"]
        SAVE --> BATCH
    end

    SAVE --> DISPLAY["print_scored_jobs()\nRich table + results.txt"]
    DISPLAY --> END([Done])
```

---

## 3. Agentic Pattern: Cache-Aside (ProfileAgent)

Shows how the ProfileAgent avoids redundant Claude calls using a file-based cache.

```mermaid
sequenceDiagram
    participant M as main.py
    participant PA as ProfileAgent
    participant FS as File System
    participant PL as PromptLoader
    participant CC as ClaudeClient
    participant API as Anthropic API

    M->>PA: load("resume.pdf")
    PA->>FS: stat(data/profile.json)

    alt Cache is fresh (profile.json newer than resume.pdf)
        FS-->>PA: cache mtime > resume mtime
        PA->>FS: read data/profile.json
        FS-->>PA: JSON string
        PA-->>M: Profile (no API call)
    else Cache is stale or missing
        FS-->>PA: cache missing or resume newer
        PA->>FS: pdfplumber.open(resume.pdf)
        FS-->>PA: extracted text
        PA->>PL: load("parse_resume", resume_text=...)
        PL-->>PA: rendered system prompt
        PA->>CC: call(system, user, "resume_parsing")
        CC->>API: messages.create(model, tokens, prompt)
        API-->>CC: raw JSON text
        CC-->>PA: response string
        PA->>PA: ResponseParser.parse(raw, Profile)
        PA->>FS: write data/profile.json
        PA-->>M: Profile
    end
```

---

## 4. Agentic Pattern: Batched Fan-Out (ScoringAgent)

Shows how 5 jobs are packed into one Claude call, scored simultaneously across all tracks, and mapped back by index.

```mermaid
sequenceDiagram
    participant SA as ScoringAgent
    participant PL as PromptLoader
    participant CC as ClaudeClient
    participant API as Anthropic API
    participant RP as ResponseParser
    participant DB as SQLite

    Note over SA: 50 jobs → 10 batches of 5

    loop Each batch of 5 jobs
        SA->>SA: Filter: stale? no desc?\nexcluded title? non-tech?

        Note over SA: Build XML jobs block
        SA->>SA: &lt;job index="0"&gt;...&lt;/job&gt;<br/>&lt;job index="1"&gt;...&lt;/job&gt;<br/>...&lt;job index="4"&gt;...&lt;/job&gt;

        SA->>PL: load("score_job", profile, jobs, tracks, salary_min)
        PL-->>SA: rendered system prompt

        SA->>CC: call(system, "Score these 5 jobs", "job_scoring")
        CC->>API: messages.create(claude-sonnet-4-6)
        API-->>CC: JSON array [0..4]
        CC-->>SA: raw response string

        SA->>RP: parse_list(raw, BatchJobScore)
        RP->>RP: strip_code_fences()<br/>extract_json()<br/>json.loads()<br/>model_validate() ×5
        RP-->>SA: list[BatchJobScore]

        Note over SA: Map scores back by job_index
        SA->>SA: score_map = {item.job_index: item}

        loop Each job in batch
            SA->>SA: job.scores = TrackScores(ic, architect, management)
            SA->>SA: job.status = SCORED
            SA->>DB: update_job(job)
        end
    end
```

---

## 5. Agentic Pattern: Structured Output Pipeline

How raw Claude text becomes a validated, typed Python object at every agent boundary.

```mermaid
flowchart LR
    A["Claude\nraw text"] --> B["_strip_code_fences()\nremove ```json``` wrapping"]
    B --> C["_extract_json()\nfind first { or [\nwalk to matching close"]
    C --> D["json.loads()\nPython dict / list"]
    D --> E["Model.model_validate()\nPydantic type check\nconstraint enforcement"]
    E --> F["Typed Python object\nProfile / TrackScores\n/ BatchJobScore"]

    style A fill:#ffeeba,stroke:#e0a800
    style F fill:#d4edda,stroke:#28a745

    B --> ERR1["ResponseParseError\nif no JSON found"]
    D --> ERR2["ResponseParseError\nif invalid JSON"]
    E --> ERR3["ResponseParseError\nif schema mismatch"]

    style ERR1 fill:#f8d7da,stroke:#dc3545
    style ERR2 fill:#f8d7da,stroke:#dc3545
    style ERR3 fill:#f8d7da,stroke:#dc3545
```

---

## 6. Job Lifecycle — Pipeline State Machine

Every job moves through a defined set of states. Status transitions are explicit and stored in the database.

```mermaid
stateDiagram-v2
    [*] --> NEW : Scraper creates job

    NEW --> SCORED : ScoringAgent\nClaude evaluates job

    NEW --> NEW : Scraper re-runs\n(deduplication skips it)

    SCORED --> APPLIED : User runs --tailor\nand confirms application

    SCORED --> REJECTED : User decides\nnot to apply

    APPLIED --> REJECTED : Company rejects\nor user withdraws

    APPLIED --> OFFER : Company extends offer

    OFFER --> [*]
    REJECTED --> [*]

    note right of NEW
        status = "new"
        Queried by get_by_status(NEW)
        to find jobs needing scoring
    end note

    note right of SCORED
        status = "scored"
        TrackScores populated
        Shown in dashboard + terminal
    end note
```

---

## 7. Resume Tailoring — Sequence Diagram

Flow for `python main.py --tailor 42`.

```mermaid
sequenceDiagram
    actor User
    participant M as main.py
    participant DB as SQLite
    participant PA as ProfileAgent
    participant TA as TailoringAgent
    participant PL as PromptLoader
    participant CC as ClaudeClient
    participant API as Anthropic API
    participant FS as File System

    User->>M: python main.py --tailor 42
    M->>DB: get_by_id(42)
    DB-->>M: Job object

    M->>User: "Which track? [1] IC  [2] Architect  [3] Management"
    User->>M: "2" (Architect)

    M->>PA: load("resume.pdf")
    PA-->>M: Profile (from cache)

    M->>TA: tailor(job, profile, CareerTrack.ARCHITECT)
    TA->>PL: load("tailor_resume", profile, job, track="architect")
    PL-->>TA: rendered system prompt

    TA->>CC: call(system, user, "resume_tailoring")
    CC->>API: messages.create(temperature=0.3)
    API-->>TA: JSON with tailored content

    TA->>TA: extract_json() → parse dict
    TA->>FS: write output/resumes/Acme_SrArchitect_architect.txt
    FS-->>TA: path confirmed

    TA-->>M: TailoredResume(summary, experience, keywords, gaps, path)

    M->>User: Show keywords + gaps
    M->>User: "Mark as APPLIED? (y/n)"
    User->>M: "y"
    M->>DB: update_job(status=APPLIED, applied_at=now)
```

---

## 8. Prompt-as-Template Pattern

How a prompt file flows from disk to the Claude API.

```mermaid
flowchart LR
    subgraph FILES["prompts/ directory"]
        F1["parse_resume.md\n{{resume_text}}"]
        F2["score_job.md\n{{profile}} {{jobs}}\n{{tracks}} {{salary_min}}"]
        F3["tailor_resume.md\n{{profile}} {{job}} {{track}}"]
    end

    subgraph LOADER["PromptLoader.load()"]
        L1["Read .md file"]
        L2["Replace {{placeholders}}\nwith runtime values"]
        L3["Check for unfilled\n{{placeholders}} — fail fast"]
    end

    subgraph AGENTS["Agents"]
        A1["ProfileAgent"]
        A2["ScoringAgent"]
        A3["TailoringAgent"]
    end

    F1 --> L1
    F2 --> L1
    F3 --> L1
    L1 --> L2 --> L3

    L3 --> CC["ClaudeClient.call(\n  system=rendered_prompt,\n  user=task_message,\n  operation=...\n)"]

    A1 --> |"resume_text=pdf_text"| L1
    A2 --> |"profile, jobs, tracks,\nsalary_min, num_jobs"| L1
    A3 --> |"profile, job, track"| L1
```

---

## 9. Pre-Filter Gate Pattern

Two-stage filtering that eliminates irrelevant jobs before Claude is called.

```mermaid
flowchart TD
    START(["N unscored jobs"]) --> G1

    G1{"posted > 30 days ago?\nis_stale = True"}
    G1 -- Yes --> SKIP1["Skip\nlog: stale"]
    G1 -- No --> G2

    G2{"description\nis None or empty?"}
    G2 -- Yes --> SKIP2["Skip\nlog: no description"]
    G2 -- No --> G3

    G3{"title contains\nexcluded keyword?\npresales · sales eng\njava developer\ncivil/mechanical eng..."}
    G3 -- Yes --> SKIP3["Skip\nlog: excluded title"]
    G3 -- No --> G4

    G4{"description contains\nat least one tech keyword?\nsoftware · cloud · api\nkubernetes · python\narchitecture · llm..."}
    G4 -- No --> SKIP4["Skip\nlog: non-tech description"]
    G4 -- Yes --> SCORE["Send to\nClaude for scoring\n💰 token cost incurred here"]

    style SCORE fill:#d4edda,stroke:#28a745
    style SKIP1 fill:#f8d7da,stroke:#dc3545
    style SKIP2 fill:#f8d7da,stroke:#dc3545
    style SKIP3 fill:#f8d7da,stroke:#dc3545
    style SKIP4 fill:#f8d7da,stroke:#dc3545
```

---

## 10. Agentic Patterns Summary

Where each pattern appears in the codebase.

```mermaid
mindmap
  root((Job Search\nAgent))
    Structured Output
      ResponseParser strips fences
      ResponseParser extracts JSON
      Pydantic validates schema
      Every Claude response typed
    Prompt as Template
      prompts/*.md files
      PromptLoader substitutes vars
      XML tags structure context
      Prompts editable without code
    Cache Aside
      ProfileAgent checks mtime
      data/profile.json warm cache
      Re-parse only when resume changes
      Saves 1 Claude call per run
    Batched Fan-Out
      5 jobs per Claude call
      XML index tags for mapping
      job_index remaps results
      10x fewer API calls
    Pre-Filter Gate
      Stale date check
      Excluded title keywords
      Tech description keywords
      Cheap before expensive
    Pipeline State Machine
      NEW → SCORED → APPLIED
      APPLIED → REJECTED or OFFER
      DB status column queryable
      get_by_status drives workflow
    Retry with Backoff
      tenacity on ClaudeClient
      tenacity on all scrapers
      2s → 4s → 8s exponential
      3 attempts max
    Multi-Track Scoring
      One call scores IC + Arch + Mgmt
      Active tracks from config
      Null for disabled tracks
      3x cost reduction vs per-track
```
