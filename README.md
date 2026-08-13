# Pathway

**AI-powered treatment observability and clinical-trial access for patients with serious or rare conditions.**

Pathway helps patients, caregivers, and clinicians move from **“What treatment options are left?”** to **“These trials may be relevant, here is why, and here is how to pursue them.”**

Built with **AWS Strands Agents SDK**, **Claude on Amazon Bedrock**, **ClinicalTrials.gov API v2** and **BrightData**


## Table of Contents
1. [Collaborators](#collaborators)
2. [The Problem](#the-problem)
3. [Key Features](#key-features)
4. [Differentiation](#differentiation)
5. [System Architecture](#system-architecture)
6. [Technology Stack](#technology-stack)
7. [Getting Started](#getting-started)
8. [Future Developments](#future-developments)

## Collaborators

Built for NTU's CAmpcOde Hackathon 2025 - Code with AI, The SUPERCELLS project is made possible by the contributions of the following individuals:

| Name | GitHub | LinkedIn |
|------|--------|----------|
| Nicole Ang | [![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nicoleang18) | [![LinkedIn](https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/nicoleang18/) |
| Teow Choon Ray | [![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)](https://github.com/TeowChoonRay) | [![LinkedIn](https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/choonray/) |

## The Problem

### Treatment options exist. Patients often cannot see, understand, or act on them.

For patients with serious or rare conditions, clinical trials may represent one of the few remaining treatment paths. ClinicalTrials.gov can show what studies exist, but it does not solve the harder patient problem: **Which options may actually be relevant to me, and what do I need to do next?**

Patients still have to:

* interpret complex inclusion and exclusion criteria
* understand which parts of their medical history matter
* determine whether a study is realistically reachable
* find the correct recruiting hospital or study contact
* identify missing records or clinical information
* navigate referral and screening steps

A trial can be scientifically relevant and still be practically inaccessible.

**Pathway turns clinical-trial discovery into a guided path toward access.**

## Key Features

1. **Understand the patient** — converts a free-text narrative into a structured clinical profile and exposes assumptions for review.
2. **Find relevant trials** — searches live recruiting studies through ClinicalTrials.gov.
3. **Structure eligibility** — converts free-text study criteria into checkable rules.
4. **Evaluate transparently** — classifies criteria as **PASS / FAIL / UNKNOWN** with deterministic Python logic.
5. **Show the evidence** — every verdict points back to the exact trial text that supports it.
6. **Ask targeted follow-ups** — UNKNOWN criteria become focused questions instead of a long generic intake form.
7. **Model practical access** — considers eligibility, recruitment freshness, geography, and contactability.
8. **Help the patient act** — surfaces recruiting sites, contacts, needed documents, next steps, and draft outreach material.
9. **Enrich site access** — Bright Data looks up public links, such as a site's trials page or a sponsor's contact page, for a selected trial.

## Differentiation

### Evidence-first eligibility

Every checkable criterion is tied to the **verbatim source text** from the study record. If the evidence is unclear, Pathway returns **UNKNOWN** rather than confidently excluding a patient.

### LLM parses; Python judges

Models handle language understanding. Eligibility verdicts, recomputation, geography, and access scoring are deterministic and reproducible.

### Adaptive screening

Pathway asks for the information that matters to the remaining study options instead of forcing every patient through the same questionnaire.

### Access, not just matching

Pathway does not stop at *“here are some trials.”* It asks:

> **What stands between this patient and actually reaching screening?**

## System Architecture

```text
                  Patient / Caregiver / Clinician
                               │
                               ▼
                       ┌───────────────┐
                       │ React / Vite  │
                       │    Pathway    │
                       └───────┬───────┘
                               │ HTTP + SSE
                               ▼
                       ┌───────────────┐
                       │    FastAPI    │
                       └───────┬───────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      Patient profile    ClinicalTrials.gov   Eligibility engine
      Bedrock + Strands       API v2            Python
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                     Evidence-backed matches
                               │
                               ▼
                         Access Outlook
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
      ClinicalTrials.gov                Bright Data
       source of truth                access enrichment
                │                             │
      eligibility / status /          site page /
      site / official contact         sponsor contact
                └──────────────┬──────────────┘
                               ▼
                       Patient next steps
                               │
                missing info / doctor note /
                 outreach / site screening
```

## Technology Stack

| Source / tool                 | Role                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------- |
| **ClinicalTrials.gov**        | Official trial data, eligibility, recruiting status, locations, and contacts |
| **Amazon Bedrock + Strands**  | Patient-profile extraction and eligibility-criteria parsing                  |
| **Python eligibility engine** | Deterministic PASS / FAIL / UNKNOWN evaluation and access scoring            |
| **Bright Data**               | Public link lookup (site's trials page, sponsor's contact page) for a selected trial |
| **React + FastAPI**           | Patient-facing experience and backend orchestration                          |

Pathway avoids fake probability scores. Each study receives a transparent **High / Moderate / Low / Blocked / Unclear** outlook based on:
* **Eligibility fit**
* **Recruitment momentum**
* **Geographic access**
* **Contactability**

A confirmed hard eligibility failure forces **Blocked**. Missing information stays visible as **UNKNOWN**.

## Getting Started

### Backend

```bash
pip install -r backend/requirements.txt
cp .env.example .env
# Configure BEDROCK_REGION and BEDROCK_MODEL_ID
python -m uvicorn backend.main:app --reload --port 8123
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Future Developments

**Patient access**

* direct hospital/referral handoff where supported

**Treatment observability**

* emerging therapies and drug-development context through sources such as Convoke
* visibility beyond currently recruiting trials into the broader treatment pipeline

**Clinical-trial intelligence**

* aggregate access-barrier analytics
* recruitment and site-placement intelligence
* protocol-access and eligibility design insights

---

### Pathway Thesis

**Treatment observability should not stop at showing patients what trials exist. It should help them understand which options may be relevant, what is still unknown, and how to take the next step toward access.**
