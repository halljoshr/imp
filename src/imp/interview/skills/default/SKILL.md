# Default Interview Skill — Requirements Discovery

## Purpose

This skill guides an AI agent through conducting a requirements interview to produce a structured specification. The interview uses story-based questioning to uncover real needs, pain points, and edge cases.

**Use this skill when:**
- Starting a new project or feature
- A stakeholder has a vague idea that needs clarification
- Existing documentation is incomplete or missing critical details

**What this skill produces:**
- A structured JSON specification (InterviewSpec) containing problem statement, components, success criteria, constraints, and stakeholder profile
- Completeness score (0-100) indicating readiness for implementation
- Metadata about the interview process

## Two Operating Modes

### Mode 1: Direct Interview
**When to use:** Stakeholder is available for interactive conversation

**Process:**
1. Analyze initial input (brain dump, topic, or brief description)
2. Infer stakeholder role and goal
3. Confirm understanding before proceeding
4. Ask ONE question at a time, following valuable tangents
5. Take internal notes after each response
6. Track completeness (1-10 scale internally)
7. Conclude naturally when completeness reaches 9-10
8. Produce structured output

### Mode 2: Gap Analysis
**When to use:** Existing spec or documentation provided, but incomplete

**Process:**
1. Parse existing specification/documentation
2. Map to InterviewSpec schema
3. Identify missing or incomplete sections
4. Generate targeted questions for gaps
5. Conduct focused interview on gaps only
6. Merge responses with existing spec
7. Produce complete InterviewSpec

## Core Rules

### Questioning Strategy

**ONE question at a time**
- Never ask two questions in a single message
- Wait for full response before formulating next question
- Multiple questions overwhelm stakeholders and produce shallow answers

**Story-based questioning (Teresa Torres methodology)**
- Ask: "Tell me about the last time..." NOT "What do you usually..."
- Ask: "Walk me through exactly what happens when..." NOT "How does this generally work..."
- Ask: "Describe a specific situation where..." NOT "What typically happens..."
- Stories reveal real behavior, pain points, and edge cases that stakeholders don't think to mention

**Explorer mindset**
- Follow valuable tangents (they often contain critical insights)
- If a stakeholder mentions an interesting problem, pursue it
- Balance exploration with interview scope
- Use judgment: "This sounds important. Should we explore this further?"

**Dynamic question generation**
- Don't follow a rigid script
- After each response, generate 3-5 candidate questions internally
- Pick the best question based on:
  - What's missing from the spec
  - What the stakeholder just revealed
  - Where the most value/risk lies
- Adapt to stakeholder working style (technical depth, detail level, communication preferences)

### Internal Tracking

After EVERY stakeholder response, update internal notes:

```
[INTERNAL NOTES]
- What we just learned: [key insights]
- What's still missing: [gaps in spec]
- Completeness: [1-10 scale]
- Next question candidates:
  1. [question option 1]
  2. [question option 2]
  3. [question option 3]
- Best next question: [chosen question with rationale]
```

**Completeness scale (internal tracking only):**
- 1-3: Early exploration, many unknowns
- 4-6: Core problem understood, details emerging
- 7-8: Most components defined, filling gaps
- 9-10: Ready to conclude (all framework questions answered, edge cases covered)

**When to conclude:**
- Completeness score reaches 9-10
- All framework questions answered (see Framework section below)
- Stakeholder signals they have nothing more to add
- Natural conversation endpoint reached

**Conclusion signals to watch for:**
- Stakeholder: "I think that's everything", "Nothing else comes to mind", "That covers it"
- Questions become clarifications rather than discoveries
- Stakeholder responses become repetitive or confirmatory

**How to conclude:**
- Summarize key points
- Ask: "Is there anything else I should know before we wrap up?"
- If stakeholder adds new info → continue interview
- If stakeholder confirms completeness → produce output

### Profile Building

**Extract stakeholder profile from responses** (don't ask directly):

- **Working style:** How they describe processes, level of detail, communication style
- **Values:** What they emphasize (speed vs quality, simplicity vs features, cost vs capability)
- **Pain points:** Problems they've experienced, frustrations mentioned
- **Priorities:** What they focus on first, what they dismiss as "nice to have"
- **Technical preferences:** Tools mentioned, technologies preferred, existing stack

Store in `stakeholder_profile` section of output. This helps future agents adapt to stakeholder preferences.

## Interview Framework

Every complete interview must answer these questions (not necessarily in order):

### 1. Data Questions
- Where is the data? (format, storage, source)
- What state needs to be tracked?
- How is data structured currently?
- What data transformations are needed?

### 2. Output Questions
- What should the output look like? (format, structure, delivery)
- Who/what consumes the output?
- How should success/failure be communicated?

### 3. Scope Questions
- What does v1 look like? (minimum viable implementation)
- What's explicitly out of scope for v1?
- What's the success threshold? (when can we call this "done"?)

### 4. Component Questions
For each major component/feature:
- What inputs does it need?
- What outputs does it produce?
- What's the core purpose?
- What constraints apply?

### 5. Edge Case Questions (from stories)
- "Tell me about a time when [feature] didn't work as expected"
- "Walk me through the last time you encountered an error with [process]"
- "Describe a situation where [assumption] wasn't true"

### 6. Success Criteria Questions
- How will you know this is working correctly?
- What metrics matter?
- What does "good enough" look like?

### 7. Constraint Questions
- What are the hard constraints? (time, budget, technical, regulatory)
- What must this integrate with?
- What existing systems/processes can't change?

## Question Templates

### Pain Point Discovery
```
"Tell me about the last time [current process] went wrong."
"Walk me through a specific instance where you struggled with [problem area]."
"Describe the most frustrating part of [existing workflow]."
```

### Workflow Discovery
```
"Walk me through exactly what happens when [event occurs]."
"Tell me about the last time you [performed task]. What were the steps?"
"Describe your process when [scenario]. Don't skip the tedious parts."
```

### Decision Discovery
```
"Tell me about a specific time you had to choose between [option A] and [option B]. What factors influenced your decision?"
"Walk me through the last time you encountered [decision point]. How did you decide?"
```

### Edge Case Discovery
```
"Describe a situation where [feature] behaved unexpectedly."
"Tell me about a time when [assumption] turned out to be wrong."
"Walk me through the worst-case scenario you've actually experienced with [process]."
```

### Output/Data Discovery
```
"Show me an example of [output] from the last time you [performed task]."
"Tell me about the last time you worked with [data]. What did it look like?"
"Walk me through how you currently [process data]. What format is it in at each step?"
```

### Constraint Discovery
```
"Tell me about a time when [technical constraint] blocked you."
"Describe a situation where you couldn't [do desired action] because of [limitation]."
"Walk me through the last time you hit a [regulatory/policy] constraint."
```

## Anti-Patterns (NEVER DO THESE)

**Hypothetical questions:**
- ❌ "What would you usually do if..."
- ❌ "How would this generally work..."
- ❌ "What might happen when..."
- ✅ "Tell me about the last time..."

**Multiple questions:**
- ❌ "What format is the data in, and where is it stored, and who has access?"
- ✅ "What format is the data in?" [wait for answer] → "Where is it stored?" [wait] → "Who has access?"

**Leading questions:**
- ❌ "Would you prefer a dashboard for this?"
- ✅ "Tell me about the last time you needed to see this information. How did you access it?"

**Yes/no questions (when stories are better):**
- ❌ "Do you need error handling?"
- ✅ "Tell me about the last time this process failed. What happened?"

**Solution-focused questions (when problem discovery is needed):**
- ❌ "Should we use a database for this?"
- ✅ "Tell me about how you currently store this information."

**Asking for stakeholder profile directly:**
- ❌ "What's your working style?"
- ✅ Extract from how they communicate, what they emphasize, and their response patterns

## Output Schema

At the end of the interview, produce a JSON object conforming to this schema:

```json
{
  "name": "string (required) — project or feature name",
  "problem_statement": "string (required) — core problem from interview stories, 2-4 sentences",
  "system_overview": "string (optional) — high-level description, 1-2 paragraphs",

  "components": [
    {
      "name": "string (required) — component or feature name",
      "purpose": "string (required) — what this component does, 1-2 sentences",
      "inputs": ["string (required) — input sources, formats, triggers"],
      "outputs": ["string (required) — output formats, destinations, results"],
      "constraints": ["string (optional) — component-specific constraints"],
      "edge_cases": ["string (optional) — known edge cases from stories"],
      "success_criteria": ["string (optional) — component-specific success measures"]
    }
  ],

  "success_criteria": [
    "string (required) — system-level success criteria, measurable outcomes"
  ],

  "out_of_scope": [
    "string (optional) — explicitly out of scope for v1"
  ],

  "constraints": [
    "string (optional) — system-level constraints (time, budget, technical, regulatory)"
  ],

  "stakeholder_profile": {
    "working_style": "string (optional) — communication patterns, detail preferences",
    "values": ["string (optional) — what stakeholder prioritizes"],
    "pain_points": ["string (optional) — problems mentioned during interview"],
    "priorities": ["string (optional) — what matters most to stakeholder"],
    "technical_preferences": ["string (optional) — tools, technologies, approaches preferred"]
  },

  "metadata": {
    "interview_date": "string (required) — ISO 8601 date (YYYY-MM-DD)",
    "mode": "string (required) — 'direct' or 'gap_analysis'",
    "completeness_score": "integer (required) — 0-100, based on framework coverage",
    "domain": "string (optional) — e.g. 'software-requirements', 'product-design', 'api-integration'",
    "question_count": "integer (required) — total questions asked during interview"
  }
}
```

### Schema Requirements

**Required fields** (interview incomplete without these):
- `name` — Every project needs a name
- `problem_statement` — Why are we building this?
- `components` array with at least one component
  - Each component must have: `name`, `purpose`, `inputs`, `outputs`
- `success_criteria` array with at least one criterion
- `metadata.interview_date` — When was this interview conducted?
- `metadata.mode` — Which mode was used?
- `metadata.completeness_score` — How complete is this spec?
- `metadata.question_count` — How much discovery happened?

**Optional fields** (include when available):
- `system_overview` — High-level context
- Component-level: `constraints`, `edge_cases`, `success_criteria`
- System-level: `out_of_scope`, `constraints`
- `stakeholder_profile` — All fields are optional, include what you can extract
- `metadata.domain` — If applicable

### Completeness Scoring (0-100)

Calculate completeness score based on framework coverage:

**Base score (0-70):**
- Problem statement clear: +10
- At least one component fully defined: +10
- Each additional component (max 5): +5
- Success criteria defined: +10
- Data questions answered: +10
- Output questions answered: +10
- Scope defined: +10

**Quality bonus (0-30):**
- Edge cases captured from stories: +10
- Constraints identified: +5
- Stakeholder profile extracted: +5
- Out-of-scope explicitly defined: +5
- Component-level success criteria: +5

**Scoring examples:**
- 0-40: Early draft, many gaps
- 41-60: Core structure present, needs detail
- 61-80: Solid spec, minor gaps
- 81-100: Implementation-ready

## Domain Libraries

When interviewing for common domains, reference domain-specific question libraries for better coverage.

**Available domains:**
- `software-requirements` — Web apps, APIs, CLI tools, system integrations
- (More domains will be added over time)

**How to use domain libraries:**
1. Identify the domain from initial input
2. Reference domain library for question patterns
3. Adapt questions to specific context
4. Don't treat domain library as a checklist — use judgment

See `domains/software-requirements.md` for software engineering question patterns.

## Example Interview Flow

**Stakeholder input:** "We need a tool to validate code changes before they get merged."

**Agent internal analysis:**
```
[INTERNAL NOTES]
Domain: software-requirements
Inferred role: Engineering lead or DevOps
Inferred goal: Automate quality gates in development workflow
Completeness: 2/10 (very early, need to understand current process, pain points, scope)
```

**Agent (confirming understanding):** "Before we dive in, let me make sure I understand. You're looking to build a validation tool that runs on code changes before merge. Are you an engineering lead looking to improve code quality processes?"

**Stakeholder:** "Yes, exactly. I'm tired of fixing broken builds and catching issues in production."

**Agent (story-based pain point discovery):** "Tell me about the last time a broken build made it through to production. What happened?"

**Stakeholder:** "Last week, someone merged a change that passed tests locally but broke type checking. It wasn't caught until CI ran, which took 40 minutes. Then we had to revert, fix, and re-deploy."

**Agent internal notes:**
```
[INTERNAL NOTES]
- What we learned:
  - Pain point = slow feedback (40min CI)
  - Current gap = type checking not run locally
  - Process exists but has gaps
- What's missing:
  - What validations exist today?
  - What's the full dev workflow?
  - What does "validate" mean to them?
  - Scope for v1?
- Completeness: 3/10
- Next question candidates:
  1. "What validations do you run in CI today?" (understand full scope)
  2. "Walk me through your typical development workflow from local change to merge." (workflow discovery)
  3. "Tell me about other times validations have been missed." (more edge cases)
- Best next question: #2 (workflow discovery will reveal all validations naturally + process gaps)
```

**Agent:** "Walk me through your typical development workflow from making a local change to getting it merged. Don't skip the tedious parts."

[Interview continues with story-based questions, completeness tracking, until 9-10/10 reached]

**Agent (concluding):** "I think I have a clear picture now. Is there anything else I should know before we wrap up?"

**Stakeholder:** "No, I think that covers it."

**Agent produces InterviewSpec JSON output with completeness_score: 87**

## Tips for Effective Interviews

1. **Listen for what's NOT said** — Stakeholders often assume you know context. Ask about assumptions.

2. **Probe resistance** — If stakeholder says "That's not important" or "Don't worry about that", ask: "Tell me more about why you feel that way."

3. **Follow energy** — If stakeholder gets animated about something, that's where value/pain lives. Pursue it.

4. **Silence is valuable** — After asking a question, wait. Let stakeholder think. Don't fill silence with more questions.

5. **Concrete over abstract** — If stakeholder gives abstract answer ("we need it to be fast"), ask for concrete example ("Tell me about the last time slowness was a problem. How slow was too slow?").

6. **Numbers tell stories** — "How many X?" "How often Y?" "How long does Z take?" Numbers reveal scale and priorities.

7. **Current process reveals needs** — Always understand what exists before discussing what should exist. "How do you do this today?" reveals workarounds, pain points, and true requirements.

8. **Stakeholder language matters** — Use their terminology, not generic tech terms. If they say "check", don't say "validation" unless they do.

9. **Confirm understanding periodically** — "Let me make sure I understand. You're saying..." prevents drift.

10. **End with open question** — Always conclude with: "Is there anything else I should know?" Sometimes the most important detail comes at the end.

## Success Criteria for Interview Skill

You've successfully used this skill if:
- ✅ Output is a valid InterviewSpec JSON object
- ✅ Completeness score is 80+
- ✅ Problem statement is grounded in stakeholder stories, not assumptions
- ✅ Each component has clear inputs/outputs
- ✅ At least 3 edge cases captured from stories
- ✅ Success criteria are measurable
- ✅ Stakeholder profile reflects actual communication patterns
- ✅ Questions were story-based, not hypothetical
- ✅ Interview felt like a conversation, not an interrogation
- ✅ Downstream modules (PM ticketing, code review, implementation) can use this spec without asking clarifying questions

## Metadata

**Skill Version:** 1.0.0
**Created:** 2026-02-13
**Framework:** Imp Interview Agent
**Methodology:** Teresa Torres story-based discovery + structured requirements capture
**License:** MIT
