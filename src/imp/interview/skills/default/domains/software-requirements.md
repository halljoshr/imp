# Software Requirements Domain Library

## Purpose

This domain library provides question patterns specifically for software engineering requirements discovery. Use these patterns when interviewing for:
- Web applications
- APIs and microservices
- CLI tools and scripts
- System integrations
- Developer tooling
- Infrastructure automation

## How to Use This Library

1. **Don't treat this as a checklist** — These are question patterns, not a rigid script
2. **Adapt to context** — Modify questions based on stakeholder responses
3. **Follow value** — If a stakeholder reveals something interesting, pursue it (even if not in this library)
4. **Use story-based format** — All questions should start with "Tell me about..." or "Walk me through..."

## Architecture & System Design

### High-Level Structure
```
"Walk me through the last time you explained this system to someone new. What components did you describe?"

"Tell me about how the different parts of this system communicate today."

"Describe a time when you had to debug an issue that crossed multiple components. What did you learn about how they connect?"
```

### Scalability & Performance
```
"Tell me about the last time the system was slower than expected. What caused it?"

"Walk me through a time when traffic/load was higher than normal. What happened?"

"Describe the current system's limits. How did you discover them?"

"Tell me about the largest dataset you've processed. What challenges did you encounter?"
```

### Technology Stack
```
"Walk me through the current technology stack. Why was each piece chosen?"

"Tell me about a time when the current stack wasn't the right fit. What problem did it create?"

"Describe the last time you had to integrate with an external technology. What made it easy or difficult?"
```

## Data & State Management

### Data Sources
```
"Tell me about where this data comes from today. Walk me through the full journey."

"Describe a time when data from [source] was incorrect or missing. What happened?"

"Walk me through the last time you had to reconcile data from multiple sources. What challenges came up?"
```

### Data Transformations
```
"Tell me about the last time you processed this data. What transformations were needed?"

"Describe a time when data was in an unexpected format. How did you handle it?"

"Walk me through a specific example of this data before and after processing. What changed?"
```

### State & Persistence
```
"Tell me about what state needs to be remembered across [sessions/requests/runs]."

"Walk me through a time when state got out of sync. What was the impact?"

"Describe how you currently handle [data persistence]. What works well? What doesn't?"

"Tell me about the last time you lost data. What protections exist today?"
```

### Data Volume & Growth
```
"Tell me about the largest dataset you've worked with in this domain. How much data are we talking about?"

"Walk me through how data volume has changed over time. Any surprises?"

"Describe a time when data growth caused problems. What was the tipping point?"
```

## APIs & Integrations

### API Design
```
"Tell me about the last time you (or someone else) used this API. What was the experience like?"

"Walk me through a real request/response example from the last time you tested this."

"Describe a time when the API didn't behave as expected. What was confusing?"

"Tell me about the most common use case for this API. What does that workflow look like?"
```

### Authentication & Authorization
```
"Walk me through how authentication works today. What's the full flow?"

"Tell me about a time when someone couldn't access something they should have (or could access something they shouldn't). What happened?"

"Describe how you currently manage API keys/tokens/credentials. What's manual vs automated?"
```

### Rate Limiting & Quotas
```
"Tell me about a time when you hit a rate limit (yours or an external API's). What was the impact?"

"Walk me through how you currently handle API quotas. Any surprises or issues?"

"Describe the busiest period for this API. What does traffic look like?"
```

### Error Handling
```
"Tell me about the last time this API returned an error. What did the error message look like?"

"Walk me through what happens when [external service] is unavailable. How does the system behave?"

"Describe a time when an error message didn't help you diagnose the problem. What was missing?"
```

### Versioning
```
"Tell me about the last time you had to update this API. How did you handle backward compatibility?"

"Describe a time when a breaking change caused problems. What happened?"

"Walk me through how you communicate API changes to consumers today."
```

## User Interface & Experience

### User Workflows
```
"Tell me about the last time you (or a user) performed [task]. Walk me through every step, don't skip the tedious parts."

"Describe a time when the UI got in the way. What were you trying to do?"

"Walk me through the most common workflow. What do users do most frequently?"
```

### Input & Output
```
"Tell me about the last time you entered data into this system. What format was it in? What happened to it?"

"Describe an example of the output users care about most. What does it look like?"

"Walk me through a time when the output wasn't useful. What was wrong with it?"
```

### Error States & Validation
```
"Tell me about the last time you saw an error message. Was it helpful?"

"Describe a time when you entered invalid input. How did the system respond?"

"Walk me through what happens when [operation] fails. What does the user see?"
```

## Infrastructure & Deployment

### Deployment Process
```
"Walk me through the last deployment you did. What were the steps?"

"Tell me about a time when a deployment went wrong. What happened?"

"Describe the current deployment process. What's manual? What's automated?"

"Tell me about how long deployments typically take. What's the fastest? The slowest?"
```

### Environment Management
```
"Walk me through the different environments (local, staging, prod). How do they differ?"

"Tell me about a time when something worked in one environment but not another. What was different?"

"Describe how you manage configuration across environments today."
```

### Monitoring & Observability
```
"Tell me about the last time you investigated a production issue. What information did you look at first?"

"Walk me through the current monitoring setup. What alerts exist?"

"Describe a time when you didn't know something was broken until [too late/a user reported it]. What monitoring was missing?"

"Tell me about the logs. What format are they in? Where do they go? How do you search them?"
```

### Reliability & Uptime
```
"Tell me about the last outage. What caused it? How long did it last?"

"Describe the current backup and recovery process. Have you ever had to use it?"

"Walk me through what happens when [critical dependency] goes down."
```

## Security & Compliance

### Security Practices
```
"Tell me about the last security review or audit. What issues came up?"

"Walk me through how you currently handle [sensitive data]. Who has access?"

"Describe a time when you discovered a security vulnerability. How was it found? How was it fixed?"

"Tell me about the current authentication and authorization model. Any gaps or concerns?"
```

### Data Privacy
```
"Walk me through what personal data this system collects. How is it used?"

"Tell me about any data retention policies. How long do you keep data?"

"Describe how users can access/delete their data today."
```

### Compliance Requirements
```
"Tell me about any regulatory requirements that apply (GDPR, HIPAA, SOC2, etc.). How do you ensure compliance?"

"Walk me through the last audit. What did auditors ask about?"

"Describe any compliance gaps or concerns."
```

## Testing & Quality

### Testing Strategy
```
"Tell me about the current testing setup. What types of tests exist?"

"Walk me through the last time a bug made it to production. Why didn't tests catch it?"

"Describe a time when tests gave a false positive or false negative. What happened?"

"Tell me about test coverage. What's tested well? What's not?"
```

### Test Data
```
"Walk me through how you create test data. Is it realistic?"

"Tell me about a time when test data didn't match production data. What broke?"

"Describe the process for setting up test environments. What's hard about it?"
```

### Quality Gates
```
"Tell me about what checks run before code can be merged. What's automated vs manual?"

"Walk me through the last time a quality gate blocked a merge. Was it the right call?"

"Describe a time when code got merged that shouldn't have. What gate was missing?"
```

## Performance & Optimization

### Performance Characteristics
```
"Tell me about the last time you measured performance. What did you measure? What were the results?"

"Walk me through what 'fast enough' means for this system. Any specific targets?"

"Describe a time when performance degraded. What was the cause?"
```

### Bottlenecks
```
"Tell me about the slowest part of the current system. How do you know it's the bottleneck?"

"Walk me through a time when you optimized something. What was the before/after?"

"Describe the process for identifying performance issues today. What tools do you use?"
```

### Caching
```
"Tell me about what gets cached today. How did you decide what to cache?"

"Walk me through a time when cached data caused problems (stale data, invalidation issues, etc.)."

"Describe the cache eviction strategy. How do you know it's working?"
```

## Developer Experience

### Development Workflow
```
"Walk me through a typical day of development. What's your workflow?"

"Tell me about the last time you set up this project from scratch (fresh clone). How long did it take? What was confusing?"

"Describe the most tedious part of the development process. What slows you down?"
```

### Debugging & Troubleshooting
```
"Tell me about the last bug you debugged. How did you figure out what was wrong?"

"Walk me through the debugging tools available. What's missing?"

"Describe a time when debugging was harder than it should have been. What made it difficult?"
```

### Documentation
```
"Tell me about the last time you needed to look something up in the docs. Did you find what you needed?"

"Walk me through the current documentation. What's documented well? What's missing?"

"Describe a time when lack of documentation cost you time. What would have helped?"
```

### Dependency Management
```
"Tell me about the dependencies this project has. Any problematic ones?"

"Walk me through the last time you updated a dependency. Any issues?"

"Describe a time when a dependency broke something. What happened?"
```

## Edge Cases & Error Scenarios

### Boundary Conditions
```
"Tell me about what happens when [input] is empty/zero/null/negative/very large."

"Walk me through a time when you encountered an unexpected edge case. What was it?"

"Describe the limits of the system. What breaks first?"
```

### Failure Modes
```
"Tell me about what happens when [external service] is down."

"Walk me through what happens when [operation] times out."

"Describe a time when the system failed gracefully. What made that possible?"

"Tell me about a time when failure cascaded. How did one failure cause others?"
```

### Concurrent Access
```
"Tell me about what happens when two users/processes try to [modify the same thing] at the same time."

"Walk me through a time when race conditions or concurrency issues caused problems."

"Describe how the system handles parallel requests today."
```

### Data Corruption
```
"Tell me about a time when data got corrupted or into a bad state. How did you recover?"

"Walk me through the data validation that exists today. What's checked? What's not?"

"Describe a time when invalid data made it into the system. What happened?"
```

## Migration & Legacy Systems

### Current System
```
"Walk me through the current system that this will replace (or integrate with). How does it work?"

"Tell me about what works well in the current system. What should we preserve?"

"Describe the biggest pain points with the current system. What must change?"
```

### Migration Strategy
```
"Tell me about how you envision transitioning from the old to the new. What's the plan?"

"Walk me through what happens to existing data. How does it get migrated?"

"Describe a time when a migration went wrong. What lessons were learned?"
```

### Backward Compatibility
```
"Tell me about what depends on the current system. What breaks if we change things?"

"Walk me through any backward compatibility requirements."

"Describe a time when breaking changes caused problems. What happened?"
```

## Success Metrics

### Business Metrics
```
"Tell me about what business metrics this impacts. What moves the needle?"

"Walk me through how success will be measured. What metrics matter?"

"Describe the last time you looked at these metrics. What did you learn?"
```

### Technical Metrics
```
"Tell me about what technical metrics you track today (latency, error rate, throughput, etc.)."

"Walk me through what 'good' looks like for these metrics. Any specific targets?"

"Describe a time when metrics revealed a problem you didn't know existed."
```

### User Satisfaction
```
"Tell me about how you measure user satisfaction today. What do users complain about?"

"Walk me through the last time you got user feedback. What did you learn?"

"Describe what would make users happy with this change. What would delight them?"
```

## Example Question Progression

Here's an example of how to use these patterns in a real interview:

**Context:** Building a CLI tool for code validation

**Discovery sequence:**

1. **Pain point** → "Tell me about the last time a broken build made it to production."
2. **Current workflow** → "Walk me through your typical development workflow from local change to merge."
3. **Validation types** → "You mentioned type checking failed. What other validations run in CI today?"
4. **Performance** → "Tell me about how long these validations take. When has slowness been a problem?"
5. **Edge cases** → "Describe a time when CI passed but something was still broken."
6. **Developer experience** → "Walk me through the last time you had to fix a validation failure. What was the experience like?"
7. **Success criteria** → "Tell me what 'fast enough' means for validation. What's your target?"

Each question builds on the previous answer, following value and uncovering real needs.

## Tips for Software Interviews

1. **Code is a solved problem** — Focus on requirements, not implementation. Stakeholders often jump to "we should use [technology]" before defining the problem.

2. **Ask about the last time, not the future** — "Tell me about the last deployment" reveals real process. "How will deployments work?" produces speculation.

3. **Numbers ground conversations** — "How many users?", "How much data?", "How long does it take?" turn vague into concrete.

4. **Errors reveal requirements** — "Tell me about the last error" often uncovers edge cases, missing validations, and true complexity.

5. **Current process is your friend** — Always understand what exists before designing what should exist. Workarounds reveal pain. Manual steps reveal automation opportunities.

6. **Integration questions prevent surprises** — Software rarely exists in isolation. "What does this connect to?" prevents late-stage integration headaches.

7. **Observability is non-negotiable** — If you can't see it, you can't fix it. Always ask about logs, metrics, and debugging.

8. **Security and compliance are not afterthoughts** — Ask early. Retrofitting security is expensive and risky.

9. **Performance without numbers is meaningless** — "It should be fast" is not a requirement. "Sub-second response time" is.

10. **Documentation gaps reveal knowledge gaps** — If it's not documented, it might not be fully understood.

## Metadata

**Domain:** software-requirements
**Version:** 1.0.0
**Created:** 2026-02-13
**Scope:** Web apps, APIs, CLI tools, system integrations, developer tooling, infrastructure automation
