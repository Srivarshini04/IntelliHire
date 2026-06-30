# Canonical Entity-Reference Convention

**Status:** Authoritative · **Applies to:** entire backend intelligence pipeline
(RoleDNA → Evidence → Graph → Claims → Gap Analysis → Reasoning → Decision → Ranking)

Every entity in the system — a skill, repository, organization, project, domain — is
identified by **one** canonical string. Two references point at the same entity **iff
their canonical ids are byte-for-byte equal**. Reasoning, gap analysis, and confidence
fusion all compare entity references by equality, so a single divergent producer breaks
the whole chain (see [Background](#background)).

---

## 1. The format

```
<type>:<slug>
```

- `type` — the entity namespace (lowercase, see §3).
- `slug` — the canonical name, lowercased, with every run of non-alphanumeric
  characters collapsed to a single `-` (`react.js` → `react-js`).

Examples (these are the **real** outputs of the resolver):

| Raw input | Evidence type | Canonical id |
|---|---|---|
| `python` | skill | `skill:python` |
| `JavaScript` | skill | `skill:javascript` |
| `react.js` | skill | `skill:react-js` |
| `postgres` | skill | `skill:postgresql` |
| `Docker` | tool | `skill:docker` |
| `ClinicBot` | repository | `repository:clinicbot` |
| `Google` | experience | `org:google` |
| `AWS Certified` | certification | `certification:aws-certified` |

---

## 2. The single authority

> **Every producer MUST mint entity references through
> `EntityResolver.resolve(raw, evidence_type).node_id`.
> Never construct an identifier by hand (no `f"skill:{name}"`, no `name.lower()`,
> no string concatenation).**

```python
from app.intelligence.candidate_graph.entity_resolver import EntityResolver
from app.shared.enums import EvidenceType

_RESOLVER = EntityResolver()
node_id = _RESOLVER.resolve("postgres", EvidenceType.SKILL).node_id   # -> "skill:postgresql"
```

The resolver is the **only** place normalization lives. It applies, in order: a
technology-alias table, the skill ontology, fuzzy matching against known canonical
names, and finally a slug fallback. Hand-building `f"skill:{name}"` would produce
`skill:postgres`, which is **not equal** to the graph's `skill:postgresql` — exactly the
class of bug this convention exists to prevent.

Because everyone funnels through one resolver, **future ontology improvements
(new aliases, better fuzzy matching) automatically benefit every producer** with no
code changes elsewhere.

---

## 3. Namespaces

Node types: `candidate`, `skill`, `project`, `repository`, `organization`, `role`,
`education`, `certification`, `achievement`, `publication`, `domain`, `contribution`,
`technology`.

**Unified skill namespace (important).** Skills, programming languages, frameworks,
libraries, tools, and databases **all collapse into the single `skill:` namespace**.
For a candidate, "uses the technology PostgreSQL" and "has the skill PostgreSQL" are the
same entity, so they resolve to one node (`skill:postgresql`) regardless of whether they
arrived typed as `SKILL`, `TOOL`, or `TECHNOLOGY`. Do **not** invent `language:`,
`framework:`, or `database:` prefixes — they would fragment a single competency across
multiple nodes and silently reintroduce the mismatch.

Other entity kinds keep their own namespace: `repository:<slug>`, `project:<slug>`,
`org:<slug>` (organizations), `certification:<slug>`, `domain:<slug>`, etc. The
`candidate:<id>` node embeds the raw candidate id (an identifier, not a slugged entity).

---

## 4. Consumer contract

Consumers (gap analyzer, claim synthesizer, uncertainty detector, confidence engine)
compare references by **equality only**. They MUST NOT strip, re-prefix, or fuzzy-match
references themselves — if two refs should match, the fix belongs in the **producer**,
not in scattered consumer-side conversions.

```python
# correct — equality against canonical ids
if entity_ref in role.must_have_skills: ...

# WRONG — consumer-side normalization (creates drift, duplicates logic)
if entity_ref.replace("skill:", "") in {s.replace("skill:", "") for s in role.must_have_skills}: ...
```

---

## 5. Background

This convention was established after a production incident: `RoleDNAProvider` emitted
**bare** skill names (`python`) while the graph emitted **prefixed** ids (`skill:python`).
The gap analyzer's `entity_ref in role.must_have_skills` never matched, scoring every
must-have skill `strength = 0.0` → false critical gaps → **every candidate rejected**.
The fix routed RoleDNA's skills through `EntityResolver.resolve()` — the producer, not
the consumers — restoring correct behavior with no scoring or threshold changes.

## 6. Known gaps (backlog)

- **Domain references** are still built inline as `f"domain:{role.domain}"` in the
  reasoning modules, where `role.domain` is a raw label, while the graph emits
  `domain:<slug>`. This is the same bug class, currently **dormant** (only active when
  `role.domain` is set against an inferred domain node). Route `role.domain` through the
  resolver / slug when this path is activated.

---

**Rule of thumb for every new intelligence engine:** if you are about to write a colon
into an entity id string, stop — call `EntityResolver.resolve()` instead.
