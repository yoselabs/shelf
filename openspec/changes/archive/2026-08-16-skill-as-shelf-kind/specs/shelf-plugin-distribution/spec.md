## Purpose

Defines the shelf repo as its own `claude plugin` marketplace and plugin source, so skill members are
installable by any consumer without a second repo, and defines how updates reach a consumer in a way
consistent with the loop's existing pull-at-checkpoint posture.

## ADDED Requirements

### Requirement: The shelf repo is both a marketplace and a plugin source
The shelf repo SHALL carry `.claude-plugin/marketplace.json` at its root, listing a plugin whose
`source` is a relative in-repo path to `skills/`, so no second repo is required to distribute skill
members.

#### Scenario: A consumer adds the shelf as a marketplace
- **WHEN** a consumer runs `claude plugin marketplace add https://github.com/yoselabs/shelf`
- **THEN** the shelf's own `marketplace.json` is discovered and its listed plugin(s) become
  installable, with no separate distribution repo involved

### Requirement: Skill updates are pull-at-checkpoint, never mid-session
A consumer's skill pin SHALL only advance via an explicit `claude plugin marketplace update` +
`claude plugin update <name>` pair, run at a `WORKFLOW: SESSION-RESOLVE` checkpoint — never
automatically mid-session. This mirrors the existing staleness-bound pull behavior already defined
for the shelf's package/doc content.

#### Scenario: A newer skill tag exists mid-session
- **WHEN** a consumer's installed skill has a newer tag available and the consumer is mid-session
- **THEN** the running session keeps the currently-loaded skill version; the update is deferred to
  the next `SESSION-RESOLVE` checkpoint, consistent with "restart required to apply"

### Requirement: A consumer upgrading a skill pin follows RECEIVE
Upgrading an installed skill to a newer tag SHALL follow `WORKFLOW: RECEIVE` — reading the skill's
`CHANGELOG.md` before its `SKILL.md` body, same as a package pin upgrade reads `CHANGELOG.md` before
source.

#### Scenario: A consumer decides to upgrade a skill pin
- **WHEN** an agent at a `SESSION-RESOLVE` checkpoint sees a newer tag for an installed skill and
  decides to upgrade
- **THEN** it reads `skills/<name>/CHANGELOG.md` first, exactly as `WORKFLOW: RECEIVE` already
  requires for a package pin
