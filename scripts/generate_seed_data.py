"""
Generate realistic ATS seed data following ats_data_ingestion_plan.md.

Deliberate signals baked in for agents to detect:
  - technical_assessment avg ~72 hrs    → Pipeline Health Agent flags bottleneck
  - Alice Chen: 11 interviews/week      → Resource Optimization Agent flags overload
  - Indeed channel: 70% fail rate       → Sourcing Quality Agent flags weak channel
  - 12 rejections: technical_skills     → Improvement Action Agent dominant issue
  - 2 offer declines cite compensation  → Offer Insights Agent salary gap signal

Run:
    poetry run python scripts/generate_seed_data.py
"""

import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

BASE_DATE = datetime(2026, 5, 16, 9, 0, 0)


# ── Helpers ────────────────────────────────────────────────────────────────────

def uid() -> str:
    return str(uuid.uuid4())


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def days_ago(n: float) -> datetime:
    return BASE_DATE - timedelta(days=n)


# ── 1. INTERVIEWERS ────────────────────────────────────────────────────────────

INTERVIEWERS = [
    # Engineering (6)
    {"id": uid(), "name": "Alice Chen",      "email": "alice.chen@acme.com",      "department": "Engineering",   "role": "Staff Engineer",          "is_active": True},
    {"id": uid(), "name": "Bob Patel",       "email": "bob.patel@acme.com",       "department": "Engineering",   "role": "Staff Engineer",          "is_active": True},
    {"id": uid(), "name": "Carol Johnson",   "email": "carol.johnson@acme.com",   "department": "Engineering",   "role": "Senior Engineer",         "is_active": True},
    {"id": uid(), "name": "David Kim",       "email": "david.kim@acme.com",       "department": "Engineering",   "role": "Senior Engineer",         "is_active": True},
    {"id": uid(), "name": "Eve Martinez",    "email": "eve.martinez@acme.com",    "department": "Engineering",   "role": "Engineering Manager",     "is_active": True},
    {"id": uid(), "name": "Frank Thompson",  "email": "frank.thompson@acme.com",  "department": "Engineering",   "role": "VP Engineering",          "is_active": True},
    # Product (2)
    {"id": uid(), "name": "Grace Liu",       "email": "grace.liu@acme.com",       "department": "Product",       "role": "Director of Product",     "is_active": True},
    {"id": uid(), "name": "Henry Wilson",    "email": "henry.wilson@acme.com",    "department": "Product",       "role": "Senior Product Manager",  "is_active": True},
    # Data Science (2)
    {"id": uid(), "name": "Iris Chang",      "email": "iris.chang@acme.com",      "department": "Data Science",  "role": "Data Science Manager",    "is_active": True},
    {"id": uid(), "name": "James Brown",     "email": "james.brown@acme.com",     "department": "Data Science",  "role": "Senior Data Scientist",   "is_active": True},
    # DevOps (2)
    {"id": uid(), "name": "Karen Davis",     "email": "karen.davis@acme.com",     "department": "DevOps",        "role": "Platform Lead",           "is_active": True},
    {"id": uid(), "name": "Liam Murphy",     "email": "liam.murphy@acme.com",     "department": "DevOps",        "role": "Senior DevOps Engineer",  "is_active": True},
]

# Alice is index 0 — she will be overloaded
ALICE_ID = INTERVIEWERS[0]["id"]

# Interviewers by department for assignment
ENG_IDS   = [i["id"] for i in INTERVIEWERS if i["department"] == "Engineering"]
PM_IDS    = [i["id"] for i in INTERVIEWERS if i["department"] == "Product"]
DS_IDS    = [i["id"] for i in INTERVIEWERS if i["department"] == "Data Science"]
DEVOPS_IDS = [i["id"] for i in INTERVIEWERS if i["department"] == "DevOps"]

DEPT_MAP = {
    "Software Engineer":        ENG_IDS,
    "Senior Software Engineer": ENG_IDS,
    "Data Scientist":           DS_IDS,
    "Product Manager":          PM_IDS,
    "DevOps Engineer":          DEVOPS_IDS,
}


def pick_interviewer(position: str, alice_boost: bool = False) -> str:
    pool = DEPT_MAP.get(position, ENG_IDS)
    if alice_boost and ALICE_ID in pool:
        # Give Alice 3× weight to make her overloaded
        weighted = pool + [ALICE_ID, ALICE_ID]
        return random.choice(weighted)
    return random.choice(pool)


# ── 2. CANDIDATES ──────────────────────────────────────────────────────────────

POSITION_DIST = (
    ["Software Engineer"] * 40 +
    ["Senior Software Engineer"] * 30 +
    ["Data Scientist"] * 20 +
    ["Product Manager"] * 16 +
    ["DevOps Engineer"] * 14
)

CHANNEL_DIST = (
    ["LinkedIn"] * 44 +
    ["Referral"] * 24 +
    ["Indeed"] * 20 +
    ["Company Website"] * 16 +
    ["GitHub"] * 12 +
    ["University"] * 4
)

SKILLS_BY_POSITION = {
    "Software Engineer": [
        "Python, Java, REST APIs, SQL, Git, Docker",
        "JavaScript, React, Node.js, PostgreSQL, AWS",
        "Python, FastAPI, Kubernetes, CI/CD, Terraform",
        "Java, Spring Boot, Microservices, Kafka, Redis",
        "Go, gRPC, Distributed Systems, PostgreSQL, GCP",
    ],
    "Senior Software Engineer": [
        "Python, System Design, Distributed Systems, PostgreSQL, Kafka",
        "Java, Microservices, AWS, Docker, Kubernetes, Team Leadership",
        "TypeScript, React, Node.js, GraphQL, MongoDB, Architecture",
        "Go, gRPC, Kubernetes, Terraform, CI/CD, Code Review",
        "Python, ML Pipelines, FastAPI, Redis, PostgreSQL, Mentoring",
    ],
    "Data Scientist": [
        "Python, PyTorch, Scikit-learn, SQL, Pandas, A/B Testing",
        "Python, TensorFlow, NLP, Spark, Databricks, Statistics",
        "R, Python, Machine Learning, SQL, Tableau, Hypothesis Testing",
        "Python, XGBoost, Feature Engineering, MLflow, Airflow, SQL",
    ],
    "Product Manager": [
        "Product Roadmapping, Agile, SQL, Figma, Stakeholder Management",
        "User Research, A/B Testing, JIRA, Data Analysis, GTM Strategy",
        "OKRs, Product Analytics, Roadmapping, Cross-functional Leadership",
    ],
    "DevOps Engineer": [
        "Kubernetes, Terraform, AWS, CI/CD, Prometheus, Grafana",
        "Docker, Jenkins, Ansible, Azure, Linux, Bash, Python",
        "GCP, Helm, ArgoCD, Datadog, Incident Response, SRE",
    ],
}

BACKGROUND_BY_POSITION = {
    "Software Engineer": [
        "3 years at a mid-size startup building REST APIs and backend services.",
        "Recent bootcamp graduate with strong portfolio in web development projects.",
        "2 years in fintech building payment processing systems.",
        "Former QA engineer transitioning to full-stack development role.",
    ],
    "Senior Software Engineer": [
        "6 years at FAANG, led a team of 4 engineers on core infrastructure.",
        "8 years in enterprise software, architected 3 production microservices.",
        "7 years in startups, scaled platforms from 0 to 1M users.",
        "5 years in consulting, delivered projects across finance and healthcare.",
    ],
    "Data Scientist": [
        "PhD in Statistics, 3 years applying ML to customer churn prediction.",
        "4 years in e-commerce building recommendation and pricing models.",
        "2 years in healthcare analytics, HIPAA-compliant data pipelines.",
        "3 years in fintech, built fraud detection models at scale.",
    ],
    "Product Manager": [
        "5 years in B2B SaaS, launched 3 major product lines from 0 to $5M ARR.",
        "4 years in consumer apps, managed teams of 8 engineers and 2 designers.",
        "3 years in marketplace products, strong data-driven decision-making track record.",
    ],
    "DevOps Engineer": [
        "4 years managing Kubernetes clusters at scale for a Series C startup.",
        "5 years in cloud infrastructure, reduced infra costs by 35%.",
        "3 years in SRE, achieved 99.99% uptime for critical payment services.",
    ],
}

EXPERIENCE_BY_POSITION = {
    "Software Engineer":        (1.0, 5.0),
    "Senior Software Engineer": (5.0, 12.0),
    "Data Scientist":           (2.0, 8.0),
    "Product Manager":          (3.0, 10.0),
    "DevOps Engineer":          (2.0, 8.0),
}

random.shuffle(POSITION_DIST)
random.shuffle(CHANNEL_DIST)

CANDIDATES = []
for i in range(120):
    position = POSITION_DIST[i]
    channel  = CHANNEL_DIST[i]
    exp_min, exp_max = EXPERIENCE_BY_POSITION[position]
    exp = round(random.uniform(exp_min, exp_max), 1)
    created = days_ago(random.uniform(7, 180))
    CANDIDATES.append({
        "id":               uid(),
        "name":             fake.name(),
        "source_channel":   channel,
        "position":         position,
        "experience_years": exp,
        "skills":           random.choice(SKILLS_BY_POSITION[position]),
        "background":       random.choice(BACKGROUND_BY_POSITION[position]),
        "created_at":       created,
        # current_stage and overall_status filled after stage generation
        "current_stage":    "application_review",
        "overall_status":   "active",
    })


# ── 3. STAGE PROGRESSION ───────────────────────────────────────────────────────

# Pass rates per stage per channel
CHANNEL_TECH_PASS = {
    "LinkedIn":        0.50,
    "Referral":        0.82,   # deliberate strong channel (was 0.75)
    "Indeed":          0.18,   # deliberate weak channel  (was 0.30)
    "Company Website": 0.62,
    "GitHub":          0.88,   # deliberate strongest     (was 0.80)
    "University":      0.35,   # weak — graduates under-skilled (was 0.40)
}

STAGE_ORDER = [
    "application_review",
    "phone_screen",
    "technical_assessment",
    "panel_interview",
    "final_interview",
    "offer",
]

STAGE_PASS_RATE = {
    "application_review":  0.75,
    "phone_screen":        0.60,
    "technical_assessment": None,  # channel-dependent, set per candidate
    "panel_interview":     0.55,
    "final_interview":     0.70,
    "offer":               0.70,   # accept rate
}

# Duration ranges in hours
STAGE_DURATION = {
    "application_review":  (24, 72),
    "phone_screen":        (0.75, 1.5),
    "technical_assessment": (48, 96),  # deliberate bottleneck
    "panel_interview":     (1.5, 2.5),
    "final_interview":     (1.0, 2.0),
    "offer":               (48, 120),
}

# Gap between stages in hours
STAGE_GAP = {
    "phone_screen":        (24, 72),
    "technical_assessment": (24, 72),
    "panel_interview":     (24, 48),
    "final_interview":     (48, 120),
    "offer":               (24, 72),
}

FEEDBACK_TEMPLATES = {
    "application_review": {
        "passed": [
            "Profile meets minimum requirements. Strong background for the role.",
            "Good match on experience level and technical stack. Moving forward.",
            "Resume shows relevant experience. Referred by team member, high priority.",
            "GitHub profile impressive. Strong open source contributions.",
        ],
        "failed": [
            "Experience level below threshold for this role.",
            "Skills do not match position requirements.",
            "Position already filled, archiving application.",
            "Overqualified — would likely leave quickly.",
        ],
    },
    "phone_screen": {
        "passed": [
            "Strong communicator. Clear on motivations and career goals. Technical fundamentals solid.",
            "Enthusiastic about the role. Asked good questions about team structure and tech stack.",
            "Good culture add. Experience directly relevant. Recommending for technical assessment.",
            "Referral candidate — very well prepared. Moved quickly through screen.",
        ],
        "failed": [
            "Unclear on basic technical concepts for the role. Not ready at this level.",
            "Salary expectations significantly above our band. Discussed and candidate declined to proceed.",
            "Communication skills need development. Struggled to articulate past projects.",
            "Candidate withdrew — accepted another offer.",
        ],
    },
    "technical_assessment": {
        "passed": [
            "Strong solution. Clean code, good test coverage, explained trade-offs well.",
            "Completed within time. Algorithm choice was optimal. Good documentation.",
            "Solid performance. Some minor issues with edge cases but overall strong.",
            "Exceptional submission. Exceeded expectations for the level.",
        ],
        "failed": [
            "Assessment instructions were unclear — candidate said they were confused about scope. Failed to complete in time.",
            "Waited 4 days with no feedback after submission. Candidate disengaged. Code quality was average.",
            "Technical gaps in system design. Not at the level required for this role.",
            "Candidate did not complete assessment. Instructions said 3 hours but test platform timed out at 1 hour — bug in our system.",
            "Code submitted but no tests written. Output was partially correct. Below bar.",
            "Unclear time limits caused candidate to rush. Solution incomplete. Need to fix assessment rubric.",
            "Candidate flagged that assessment had a broken test case. Investigation needed. Failed on other sections.",
            "Performance was below our bar. Assessment too hard for this level — may need calibration.",
        ],
    },
    "panel_interview": {
        "passed": [
            "All three panelists aligned — strong hire. Great problem-solving approach and team fit.",
            "Excellent system design discussion. Collaborative and thoughtful. Recommended.",
            "Strong on technical depth. Good culture add. Minor concern on seniority but resolved.",
        ],
        "failed": [
            "Culture fit concerns raised by two panelists. Communication style mismatch with team.",
            "Technical depth insufficient for senior role. Panel not aligned on hire decision.",
            "Candidate seemed disengaged. Did not ask questions. Panel voted no hire.",
            "Panelists gave conflicting feedback — no clear rubric being used. Need calibration session.",
        ],
    },
    "final_interview": {
        "passed": [
            "Exec interview went well. Candidate aligned on company vision and growth trajectory.",
            "Hiring manager enthusiastic. Strong close — candidate excited about offer.",
            "Final check passed. Reference calls positive. Extending offer.",
        ],
        "failed": [
            "Compensation expectations too high for current band. Cannot accommodate.",
            "Candidate concerns about company growth stage — decided to decline to proceed.",
            "Final round revealed gaps in leadership experience. Not ready for this level.",
        ],
    },
    "offer": {
        "passed": [
            "Offer accepted. Start date confirmed.",
            "Candidate accepted. Background check in progress.",
        ],
        "failed": [
            "Offer declined — candidate accepted a competing offer with higher compensation.",
            "Offer declined — salary below candidate expectation. Gap too large to bridge.",
            "Offer expired — candidate unresponsive for 2 weeks.",
            "Candidate withdrew — personal reasons.",
        ],
    },
}

STAGES = []
OFFERS = []
REJECTIONS_LIST = []

# Track rejection reason targets (scaled to 120 candidates)
rejection_targets = {
    "technical_skills": 24,
    "experience_level": 14,
    "culture_fit":       8,
    "compensation":      6,
    "withdrew":          4,
}
rejection_counts = {k: 0 for k in rejection_targets}

# Track offer decline targets (scaled to 120 candidates)
offer_decline_targets = {"compensation": 4, "accepted_elsewhere": 2, "role_mismatch": 2}
offer_decline_counts = {k: 0 for k in offer_decline_targets}

# Alice interview count tracker (for overloading)
alice_weekly_count = {}


def get_week(dt: datetime) -> str:
    return dt.strftime("%Y-W%W")


def assign_interviewer_overloaded(position: str, entered_at: datetime) -> str:
    """Assign Alice with heavy bias to create overload signal."""
    week = get_week(entered_at)
    alice_weekly_count[week] = alice_weekly_count.get(week, 0)
    pool = DEPT_MAP.get(position, ENG_IDS)
    if ALICE_ID in pool and alice_weekly_count[week] < 11:
        alice_weekly_count[week] += 1
        return ALICE_ID
    return random.choice(pool)


for candidate in CANDIDATES:
    cid       = candidate["id"]
    channel   = candidate["source_channel"]
    position  = candidate["position"]
    created   = candidate["created_at"]

    tech_pass_rate = CHANNEL_TECH_PASS[channel]

    current_dt = created
    final_stage = "application_review"
    final_outcome = "pending"
    candidate_rejected = False
    candidate_hired = False
    candidate_withdrew = False

    for stage_name in STAGE_ORDER:
        stage_id = uid()
        entered_at = current_dt

        if stage_name == "application_review":
            duration = random.uniform(*STAGE_DURATION[stage_name])
            pass_rate = STAGE_PASS_RATE[stage_name]
        else:
            gap = random.uniform(*STAGE_GAP[stage_name])
            entered_at = current_dt + timedelta(hours=gap)
            duration = random.uniform(*STAGE_DURATION[stage_name])
            if stage_name == "technical_assessment":
                pass_rate = tech_pass_rate
            else:
                pass_rate = STAGE_PASS_RATE[stage_name]

        passed = random.random() < pass_rate

        # For offer stage, determine accept/decline
        if stage_name == "offer":
            if passed:
                outcome = "accepted"
                feedback = random.choice(FEEDBACK_TEMPLATES["offer"]["passed"])
                exited_at = entered_at + timedelta(hours=duration)
            else:
                outcome = "declined"
                # Pick decline reason based on targets
                if offer_decline_counts["compensation"] < offer_decline_targets["compensation"]:
                    decline_reason = "compensation"
                    offer_decline_counts["compensation"] += 1
                    feedback = "Offer declined — salary below candidate expectation. Gap too large to bridge."
                elif offer_decline_counts["accepted_elsewhere"] < offer_decline_targets["accepted_elsewhere"]:
                    decline_reason = "accepted_elsewhere"
                    offer_decline_counts["accepted_elsewhere"] += 1
                    feedback = "Offer declined — candidate accepted a competing offer with higher compensation."
                else:
                    decline_reason = "role_mismatch"
                    offer_decline_counts["role_mismatch"] += 1
                    feedback = "Candidate withdrew — personal reasons."
                exited_at = entered_at + timedelta(hours=duration)

            salary_map = {
                "Software Engineer":        random.uniform(90000, 120000),
                "Senior Software Engineer": random.uniform(130000, 160000),
                "Data Scientist":           random.uniform(110000, 140000),
                "Product Manager":          random.uniform(120000, 150000),
                "DevOps Engineer":          random.uniform(100000, 130000),
            }
            OFFERS.append({
                "id":              stage_id,
                "candidate_id":    cid,
                "position":        position,
                "salary_offered":  round(salary_map[position], 2),
                "currency":        "USD",
                "offered_at":      ts(entered_at),
                "responded_at":    ts(exited_at) if outcome != "pending" else "",
                "status":          outcome,
                "rejection_reason": decline_reason if outcome == "declined" else "",
            })

            interviewer_id = ""
            STAGES.append({
                "id":             stage_id,
                "candidate_id":   cid,
                "stage_name":     stage_name,
                "entered_at":     ts(entered_at),
                "exited_at":      ts(exited_at),
                "outcome":        outcome,
                "interviewer_id": interviewer_id,
                "duration_hours": round(duration, 2),
                "feedback":       feedback,
            })

            if outcome == "accepted":
                candidate_hired = True
            current_dt = exited_at
            final_stage = stage_name
            break

        # Non-offer stages
        interviewer_id = ""
        if stage_name not in ("application_review",):
            interviewer_id = assign_interviewer_overloaded(position, entered_at)

        if passed:
            exited_at = entered_at + timedelta(hours=duration)
            feedback = random.choice(FEEDBACK_TEMPLATES[stage_name]["passed"])
            outcome = "passed"
        else:
            # withdrew chance 10% at any non-offer stage
            if random.random() < 0.10 and not candidate_withdrew:
                outcome = "withdrew"
                feedback = "Candidate withdrew from the process."
                candidate_withdrew = True
            else:
                outcome = "failed"
                feedback = random.choice(FEEDBACK_TEMPLATES[stage_name]["failed"])
                candidate_rejected = True

            exited_at = entered_at + timedelta(hours=duration * 0.6)

        STAGES.append({
            "id":             stage_id,
            "candidate_id":   cid,
            "stage_name":     stage_name,
            "entered_at":     ts(entered_at),
            "exited_at":      ts(exited_at),
            "outcome":        outcome,
            "interviewer_id": interviewer_id,
            "duration_hours": round(duration, 2),
            "feedback":       feedback,
        })

        current_dt = exited_at
        final_stage = stage_name

        if outcome in ("failed", "withdrew"):
            # Generate rejection record
            if outcome == "failed":
                # Assign reason category based on stage and targets
                if stage_name == "technical_assessment" and rejection_counts["technical_skills"] < rejection_targets["technical_skills"]:
                    reason_cat = "technical_skills"
                    reason_detail = "Failed technical assessment — code quality below threshold or incomplete submission."
                elif stage_name == "phone_screen" and rejection_counts["experience_level"] < rejection_targets["experience_level"]:
                    reason_cat = "experience_level"
                    reason_detail = "Experience level does not match the role requirements."
                elif stage_name == "panel_interview" and rejection_counts["culture_fit"] < rejection_targets["culture_fit"]:
                    reason_cat = "culture_fit"
                    reason_detail = "Culture and communication style mismatch identified by panel."
                elif stage_name == "final_interview" and rejection_counts["compensation"] < rejection_targets["compensation"]:
                    reason_cat = "compensation"
                    reason_detail = "Salary expectations significantly above our approved band."
                elif rejection_counts["experience_level"] < rejection_targets["experience_level"]:
                    reason_cat = "experience_level"
                    reason_detail = "Skill set does not align with current team needs."
                elif rejection_counts["technical_skills"] < rejection_targets["technical_skills"]:
                    reason_cat = "technical_skills"
                    reason_detail = "Technical gaps identified during assessment stage."
                else:
                    reason_cat = "experience_level"
                    reason_detail = "Profile does not meet current requirements."
                rejection_counts[reason_cat] += 1
            else:
                reason_cat = "withdrew"
                reason_detail = "Candidate self-removed from the process."
                rejection_counts["withdrew"] = rejection_counts.get("withdrew", 0) + 1

            REJECTIONS_LIST.append({
                "id":                          uid(),
                "candidate_id":                cid,
                "stage_name":                  stage_name,
                "rejected_at":                 ts(exited_at),
                "reason_category":             reason_cat,
                "reason_detail":               reason_detail,
                "rejected_by_interviewer_id":  interviewer_id,
            })
            break

    # Update candidate overall_status and current_stage
    if candidate_hired:
        candidate["overall_status"] = "hired"
    elif candidate_withdrew:
        candidate["overall_status"] = "withdrew"
    elif candidate_rejected:
        candidate["overall_status"] = "rejected"
    else:
        candidate["overall_status"] = "active"
    candidate["current_stage"] = final_stage


# Pad offers to 20 total (pending ones)
while len(OFFERS) < 20:
    cand = random.choice([c for c in CANDIDATES if c["overall_status"] == "hired"])
    OFFERS.append({
        "id":              uid(),
        "candidate_id":    cand["id"],
        "position":        cand["position"],
        "salary_offered":  round(random.uniform(100000, 150000), 2),
        "currency":        "USD",
        "offered_at":      ts(days_ago(random.uniform(1, 5))),
        "responded_at":    "",
        "status":          "pending",
        "rejection_reason": "",
    })


# ── 4. INTERVENTIONS (ChromaDB) ────────────────────────────────────────────────

INTERVENTIONS = [
    # slow_technical_assessment (4)
    {
        "intervention_id":       "INT-001",
        "issue_type":            "slow_technical_assessment",
        "role":                  "Software Engineer",
        "observed_impact_pct":   35.0,
        "implementation_weeks":  3,
        "issue_text":            "Technical assessment stage taking 72+ hours causing candidate drop-off. Instructions unclear, time limits not communicated, no automated feedback loop.",
        "outcome_text":          "Switched from async take-home to structured live coding with rubric. Added automated confirmation email on submission. Reduced assessment duration from 72h to 3h.",
        "steps":                 ["Define clear time limit (90 min) in assessment instructions", "Add automated submission confirmation email", "Create scoring rubric shared with all interviewers", "Schedule live debrief within 24h of submission", "Track completion rate weekly"],
    },
    {
        "intervention_id":       "INT-002",
        "issue_type":            "slow_technical_assessment",
        "role":                  "Senior Software Engineer",
        "observed_impact_pct":   28.0,
        "implementation_weeks":  2,
        "issue_text":            "Senior engineer candidates abandoning process at take-home assessment. 48h response window too long for passive candidates already employed.",
        "outcome_text":          "Replaced 48h take-home with 2h live system design + coding session. Candidate satisfaction score increased from 3.1 to 4.4/5.",
        "steps":                 ["Replace take-home with 2h live session via CoderPad", "Send calendar invite within 24h of phone screen pass", "Use standardised system design prompt reviewed by EM", "Score with rubric immediately after session", "Share decision within 48h"],
    },
    {
        "intervention_id":       "INT-003",
        "issue_type":            "slow_technical_assessment",
        "role":                  "Data Scientist",
        "observed_impact_pct":   22.0,
        "implementation_weeks":  4,
        "issue_text":            "Data science assessment had broken test cases and no clear evaluation criteria. 60% of submissions were incomplete due to environment setup issues.",
        "outcome_text":          "Rewrote assessment on hosted Jupyter environment. Added pre-flight check script. Completion rate improved from 40% to 91%.",
        "steps":                 ["Host assessment on pre-configured Jupyter environment", "Add environment validation script run before timer starts", "Write clear rubric covering: EDA, modeling, interpretation", "Assign DS manager to review all submissions within 48h", "Add candidate feedback survey after assessment"],
    },
    {
        "intervention_id":       "INT-004",
        "issue_type":            "slow_technical_assessment",
        "role":                  "DevOps Engineer",
        "observed_impact_pct":   40.0,
        "implementation_weeks":  2,
        "issue_text":            "DevOps take-home assessment required local Docker setup causing 30% failure rate on environment issues alone before any actual evaluation.",
        "outcome_text":          "Moved to cloud sandbox (Katacoda / Killercoda). Environment issues dropped to 0%. Pass rate based purely on skills improved clarity.",
        "steps":                 ["Provision cloud sandbox environment per candidate", "Pre-install all required tools and dependencies", "Send access link with assessment instructions 1h before start", "Set 90-minute timer from first command execution", "Auto-capture session logs for reviewer"],
    },
    # high_rejection_technical_skills (3)
    {
        "intervention_id":       "INT-005",
        "issue_type":            "high_rejection_technical_skills",
        "role":                  "Software Engineer",
        "observed_impact_pct":   30.0,
        "implementation_weeks":  6,
        "issue_text":            "42% of candidates failing technical assessment. Root cause: assessment testing senior-level system design for entry-level role. Misalignment between JD and assessment difficulty.",
        "outcome_text":          "Redesigned assessment to match JD level. Added pre-screen coding questions. Pass rate improved from 42% to 68% without lowering the bar.",
        "steps":                 ["Audit assessment difficulty vs JD requirements", "Add 2 pre-screen LeetCode easy questions before main assessment", "Remove system design section for junior roles", "Calibrate with 3 current engineers on appropriate difficulty", "Review pass rate monthly"],
    },
    {
        "intervention_id":       "INT-006",
        "issue_type":            "high_rejection_technical_skills",
        "role":                  "Senior Software Engineer",
        "observed_impact_pct":   25.0,
        "implementation_weeks":  4,
        "issue_text":            "High failure rate at technical assessment despite strong phone screen scores. Phone screen not predictive of assessment outcome — wrong questions being asked.",
        "outcome_text":          "Added technical depth questions to phone screen (algorithm complexity, system design basics). Assessment-to-pass correlation improved from 0.2 to 0.7.",
        "steps":                 ["Add 2-3 technical depth questions to phone screen script", "Test: big-O complexity, one design question, debugging scenario", "Train recruiters on technical question delivery and scoring", "Track screen-to-assessment pass rate correlation monthly", "Iterate question bank quarterly"],
    },
    {
        "intervention_id":       "INT-007",
        "issue_type":            "high_rejection_technical_skills",
        "role":                  "Data Scientist",
        "observed_impact_pct":   20.0,
        "implementation_weeks":  5,
        "issue_text":            "Data science candidates failing on statistics and probability questions despite strong ML project portfolios. Assessment overweights theory vs applied skills.",
        "outcome_text":          "Rebalanced assessment: 40% applied ML problem, 30% data wrangling, 30% communication. Hire rate from assessment improved by 20%.",
        "steps":                 ["Map assessment sections to actual job tasks", "Add take-home case study using realistic dataset", "Reduce pure theory questions to max 20% of score", "Include stakeholder presentation component", "Review assessment with DS team quarterly"],
    },
    # poor_sourcing_channel (3)
    {
        "intervention_id":       "INT-008",
        "issue_type":            "poor_sourcing_channel",
        "role":                  "Software Engineer",
        "observed_impact_pct":   45.0,
        "implementation_weeks":  8,
        "issue_text":            "Indeed sourcing producing 70% rejection rate at technical assessment. Candidates lack depth in required stack. Job description on Indeed too generic.",
        "outcome_text":          "Rewrote Indeed JD with specific technical requirements. Added skills screening questions. Quality score improved from 2.1 to 3.8/5.",
        "steps":                 ["Rewrite job description with specific tech stack requirements", "Add 3 required screening questions on application", "Set minimum experience threshold in job board filters", "A/B test different JD formats over 30 days", "Redirect budget from Indeed to GitHub Jobs and referrals"],
    },
    {
        "intervention_id":       "INT-009",
        "issue_type":            "poor_sourcing_channel",
        "role":                  "Senior Software Engineer",
        "observed_impact_pct":   50.0,
        "implementation_weeks":  4,
        "issue_text":            "University hiring producing candidates 2-3 levels below target seniority. Channel allocation consuming 15% of sourcing budget with 0 hires.",
        "outcome_text":          "Reallocated budget to GitHub outreach and referral bonuses. Referral hire rate: 68%. Cost-per-hire from referrals 40% lower than job boards.",
        "steps":                 ["Calculate cost-per-qualified-candidate per channel", "Pause underperforming channels (< 15% advancement rate)", "Double referral bonus for senior roles", "Create GitHub outreach template for active contributors", "Measure channel ROI quarterly"],
    },
    {
        "intervention_id":       "INT-010",
        "issue_type":            "poor_sourcing_channel",
        "role":                  "Product Manager",
        "observed_impact_pct":   35.0,
        "implementation_weeks":  6,
        "issue_text":            "LinkedIn sourcing for PM roles attracting candidates with no B2B or technical PM experience. 80% rejection at first interview stage.",
        "outcome_text":          "Switched to targeted LinkedIn outreach with custom message by Director of Product. Response rate 3×, qualification rate 2× vs passive posting.",
        "steps":                 ["Identify 20 target companies with similar product culture", "Build Boolean search string for relevant PM experience", "Personalize outreach messages — reference specific projects", "Have Director of Product sign outreach emails", "Track outreach-to-interview conversion rate weekly"],
    },
    # offer_decline_compensation (2)
    {
        "intervention_id":       "INT-011",
        "issue_type":            "offer_decline_compensation",
        "role":                  "Senior Software Engineer",
        "observed_impact_pct":   60.0,
        "implementation_weeks":  3,
        "issue_text":            "30% of Senior SWE offers declined citing compensation. Salary bands 15-20% below market. Losing candidates to FAANG and well-funded startups.",
        "outcome_text":          "Updated salary bands using Levels.fyi and Radford data. Added equity refresh component. Offer acceptance rate improved from 65% to 88%.",
        "steps":                 ["Benchmark against Levels.fyi, Radford, Glassdoor for P50 and P75", "Present compensation analysis to leadership with data", "Propose 15% band increase for senior roles", "Add RSU refresh grant (1-year cliff) to offer package", "Discuss comp range in phone screen to avoid late-stage surprises"],
    },
    {
        "intervention_id":       "INT-012",
        "issue_type":            "offer_decline_compensation",
        "role":                  "Data Scientist",
        "observed_impact_pct":   45.0,
        "implementation_weeks":  4,
        "issue_text":            "DS offer declines increasing — candidates citing competing AI startup offers 20-30% higher. Current bands set 2 years ago pre-AI boom.",
        "outcome_text":          "Emergency band refresh for DS roles. Added signing bonus option. Decline rate dropped from 35% to 12% within 2 months.",
        "steps":                 ["Pull current DS market data from multiple sources", "Calculate gap between current band and P50 market rate", "Propose signing bonus as bridge while permanent band reviewed", "Add ML compute credits and conference budget to offer", "Set quarterly band review cadence going forward"],
    },
    # interviewer_overload (2)
    {
        "intervention_id":       "INT-013",
        "issue_type":            "interviewer_overload",
        "role":                  "Software Engineer",
        "observed_impact_pct":   25.0,
        "implementation_weeks":  2,
        "issue_text":            "Two senior engineers conducting 80% of technical interviews. Overloaded interviewers providing rushed feedback. Quality scores declining. Interviewer burnout risk.",
        "outcome_text":          "Trained 4 additional engineers as interviewers. Distributed load evenly. Feedback quality score improved from 2.8 to 4.1/5.",
        "steps":                 ["Identify all engineers eligible and willing to interview", "Run interviewer training workshop (3h) covering rubric and bias", "Shadow program: new interviewer observes 2 sessions before solo", "Cap interviews at 4 per week per interviewer", "Rotate panel assignments monthly"],
    },
    {
        "intervention_id":       "INT-014",
        "issue_type":            "interviewer_overload",
        "role":                  "Senior Software Engineer",
        "observed_impact_pct":   30.0,
        "implementation_weeks":  3,
        "issue_text":            "Staff engineers spending 20% of work hours on interviews without recognition in performance reviews. Causing resentment and declining interview quality.",
        "outcome_text":          "Added interview contribution to performance review rubric. Interviewing excellence recognized in quarterly reviews. Volunteer rate doubled.",
        "steps":                 ["Add interviewing metrics to performance review template", "Set public goal: each senior IC conducts 2-4 interviews/month", "Create interviewer recognition program (shoutouts, swag)", "Track and report interview load by person monthly to EM", "Ensure EM reviews before adding more than 4/week to anyone"],
    },
    # panel_calibration (1)
    {
        "intervention_id":       "INT-015",
        "issue_type":            "panel_calibration",
        "role":                  "Software Engineer",
        "observed_impact_pct":   20.0,
        "implementation_weeks":  4,
        "issue_text":            "Panel interviewers giving inconsistent signals. Culture fit rejection rate 30% — unclear what culture fit means. No shared rubric for panel evaluation.",
        "outcome_text":          "Defined culture fit criteria with concrete behavioral examples. Shared rubric across all panelists. Consistency score (inter-rater reliability) improved from 0.4 to 0.8.",
        "steps":                 ["Workshop: define culture fit with specific, observable behaviors", "Document: list 5 must-have and 5 nice-to-have behavioral traits", "Create structured scorecard for each panelist to complete independently", "Debrief meeting: share scores before group discussion to avoid anchoring", "Audit rejection reasons monthly for illegal or biased patterns"],
    },
]


# ── 5. WRITE CSV FILES ─────────────────────────────────────────────────────────

def write_csv(filepath: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  OK {filepath.name}: {len(rows)} rows")


# Add timestamps to interviewers and write
now_str = ts(BASE_DATE)
for iv in INTERVIEWERS:
    iv["created_at"] = ts(days_ago(random.uniform(60, 365)))
    iv["updated_at"] = now_str

# Strip internal fields from candidates before writing
candidates_out = []
for c in CANDIDATES:
    candidates_out.append({
        "id":               c["id"],
        "name":             c["name"],
        "source_channel":   c["source_channel"],
        "position":         c["position"],
        "experience_years": c["experience_years"],
        "skills":           c["skills"],
        "background":       c["background"],
        "current_stage":    c["current_stage"],
        "overall_status":   c["overall_status"],
        "created_at":       ts(c["created_at"]),
        "updated_at":       now_str,
    })

print("\nWriting data files to data/ ...")
write_csv(DATA_DIR / "interviewers.csv", INTERVIEWERS)
write_csv(DATA_DIR / "candidates.csv",   candidates_out)
write_csv(DATA_DIR / "stages.csv",       STAGES)
write_csv(DATA_DIR / "offers.csv",       OFFERS)
write_csv(DATA_DIR / "rejections.csv",   REJECTIONS_LIST)

# Write interventions as JSON
interventions_path = DATA_DIR / "interventions.json"
with open(interventions_path, "w", encoding="utf-8") as f:
    json.dump(INTERVENTIONS, f, indent=2)
print(f"  OK interventions.json: {len(INTERVENTIONS)} documents")

# ── 6. SUMMARY ─────────────────────────────────────────────────────────────────

from collections import Counter

print("\n--- Summary ---")
print(f"  Interviewers:     {len(INTERVIEWERS)}")
print(f"  Candidates:       {len(CANDIDATES)}")
print(f"  Stages:           {len(STAGES)}")
print(f"  Offers:           {len(OFFERS)}")
print(f"  Rejections:       {len(REJECTIONS_LIST)}")
print(f"  Interventions:    {len(INTERVENTIONS)}")

print("\n--- Candidate Status ---")
status_counts = Counter(c["overall_status"] for c in CANDIDATES)
for status, count in sorted(status_counts.items()):
    print(f"  {status:<12} {count}")

print("\n--- Rejection Reasons ---")
for reason, count in sorted(rejection_counts.items()):
    print(f"  {reason:<25} {count}")

print("\n--- Source Channels ---")
channel_counts = Counter(c["source_channel"] for c in CANDIDATES)
for ch, count in sorted(channel_counts.items()):
    print(f"  {ch:<20} {count}")

print("\n--- Alice Interview Load (last 5 weeks) ---")
for week, count in sorted(alice_weekly_count.items())[-5:]:
    bar = "#" * count
    print(f"  {week}  {bar} ({count})")

print("\nDone. All files written to data/")
