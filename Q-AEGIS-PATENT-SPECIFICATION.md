COMPLETE SPECIFICATION

(Patent specification prepared in Form-2 style. Plain text, no markup. Pipe
characters delimit tables. Diagram sources are given verbatim between the
markers "MERMAID SOURCE - BEGIN" and "MERMAID SOURCE - END"; paste the text
between those markers into any Mermaid renderer to regenerate the figure.)


TITLE OF THE INVENTION

A SYSTEM AND METHOD FOR QUANTUM-AWARE, RISK-ADAPTIVE DATA PROTECTION USING A
FAIL-SAFE BOUND ASSESSMENT PIPELINE OF MULTI-AGENT CONSENSUS SCORING,
DETERMINISTIC POLICY OVERRIDE, CRYPTO-AGILE ENCRYPTION, AND A
POST-QUANTUM-SIGNED TAMPER-EVIDENT AUDIT LEDGER.


FILING PARTICULARS (to be completed by the applicant before filing)

Applicant            : [Applicant / assignee legal name and address]
Inventors            : Abhinav [surname]; Udhav [surname]; Sukhmani [surname]
Nationality          : [ ]
Address for service  : [ ]
Field of invention   : Computer Science / Information Security / Cryptography
Type of application  : Ordinary Application


ABSTRACT OF THE DISCLOSURE

Disclosed is a system and method for protecting data by binding, in a single
fail-safe pipeline, a sequence of assessment stages whose outputs deterministic-
ally condition one another and are recorded in an independently verifiable
tamper-evident ledger. Registered data is first assigned a sensitivity tier by
a fail-safe classifier that resolves ambiguity toward greater sensitivity. A
contextual risk value is then derived from a closed snapshot of actor, device
and time facts computed server-side. Five scoring agents (security, compliance,
contextual, quantum-readiness and sustainability), each guarded by an
independent timeout that fails safe, execute in parallel and are combined by a
versioned weighted-mean consensus function into a trust score. A deterministic
first-match policy engine may override the artificial-intelligence recommend-
ation, a non-matching evaluation being a first-class outcome with a null rule
identifier. A crypto-agile selector maps the trust score to one of a symmetric,
a hybrid post-quantum, or a fully post-quantum cryptographic profile and fails
closed. Every decision is appended to a Merkle-chained ledger, and a Signed Tree
Head, computed on demand at auditor request and signed with a post-quantum
digital signature, anchors the ledger so that a party who does not trust the
operator can verify inclusion, consistency and non-tampering. The invention
thereby couples adaptive intelligence to
enforceable, auditable, quantum-ready protection.

DESCRIPTION


FIELD OF THE INVENTION

[0001] The present invention relates generally to the field of information
security and data governance, and more particularly to a computer-implemented
system and method that automatically classifies the sensitivity of data,
continuously assesses the contextual risk of access, combines a plurality of
independent scoring agents into a versioned consensus trust score, enforces a
deterministic policy that can override an artificial-intelligence recommend-
ation, selects and applies a cryptographic profile that is agile with respect
to post-quantum threats, and records every such decision in an append-only,
cryptographically chained, post-quantum-signed audit ledger that a third party
can verify without trusting the operator of the system.


BACKGROUND OF THE INVENTION

[0002] Organizations hold data of widely differing sensitivity and are obliged,
by regulation and by contract, to apply protection commensurate with that
sensitivity and to prove after the fact that they did so. Existing approaches
treat the constituent problems in isolation. Data-loss-prevention and content-
classification tools label data but do not bind the label to any downstream
cryptographic or policy action. Access-risk engines score sessions but their
signals are frequently asserted by the client and are therefore trivially
understated by an adversary. Policy engines enforce rules but are not coupled to
a calibrated measure of risk. Encryption subsystems apply a fixed algorithm and
are seldom prepared for the migration to post-quantum cryptography now mandated
by standards bodies. Audit subsystems write logs that the operator itself can
alter, so the very party whose conduct is in question controls the evidence.

[0003] A first deficiency of the prior art is the absence of binding. Because
classification, risk scoring, policy and encryption are implemented as separate
products, the output of one stage is not provably the input of the next. An
attacker or a negligent operator can therefore encrypt highly sensitive data
under a weak profile, or apply a policy to a stale risk value, without the
inconsistency being detectable.

[0004] A second deficiency is the prevalence of fail-open behaviour. When a
classifier is uncertain, a timeout occurs, or a dependency is unavailable, prior
systems commonly default to the least protective outcome so as not to impede the
user, thereby creating a silent downgrade precisely when conditions are
abnormal.

[0005] A third deficiency is client-asserted context. Risk engines that accept
"after hours", "new device" or actor identity directly from the requesting
client allow that client to suppress the very signals that would elevate its
risk, defeating the purpose of the assessment.

[0006] A fourth deficiency is operator-controlled audit and cryptographic
obsolescence. Conventional logs are mutable by the operator and are signed, if
at all, with classical signatures that a future cryptographically relevant
quantum computer is expected to forge, so long-lived evidence cannot be trusted
into the post-quantum era. There is accordingly a need for a single, bound,
fail-safe, quantum-aware system that couples classification, risk, consensus
scoring, deterministic policy, crypto-agile protection and independently
verifiable tamper-evident audit, which need the present invention addresses.

OBJECTS OF THE INVENTION

[0007] The principal object of the invention is to provide a system and method
in which sensitivity classification, contextual risk scoring, multi-agent
consensus scoring, deterministic policy evaluation, cryptographic profile
selection and tamper-evident audit are bound into one pipeline such that the
output of each stage provably conditions the next.

[0008] A further object is to make every stage fail safe: that an uncertain
classification resolves toward greater sensitivity; that a scoring agent which
times out or errs contributes a maximally cautious value rather than being
omitted; and that a cryptographic selection which cannot be satisfied refuses
the operation rather than silently downgrading it.

[0009] Further objects of the invention are: to derive risk-relevant context
server-side so that it cannot be understated by the client; to make the
consensus function and every scoring model versioned so that a stored decision
remains attributable to the exact logic that produced it; to permit a
deterministic, human-authored policy to override the artificial-intelligence
recommendation while treating the absence of any matching rule as a first-class,
explicitly recorded outcome; to select cryptographic protection that is agile
across symmetric, hybrid and post-quantum profiles as a function of the trust
score; and to anchor an append-only, Merkle-chained audit ledger with a
post-quantum digital signature so that inclusion, consistency and integrity are
verifiable by a party that does not trust the operator.


BRIEF SUMMARY OF THE INVENTION

[0010] The invention provides, in one aspect, a computer-implemented system
comprising a plurality of cooperating modules that together form a bound
assessment pipeline, and in another aspect a method comprising the ordered
stages performed by that pipeline, and in a further aspect a non-transitory
computer-readable medium storing instructions that cause one or more processors
to perform the method.

[0011] In the pipeline, data registered with the system is presented to a
fail-safe sensitivity classification module. Said module applies a trained
statistical model when a validated model artifact is configured and present, and
otherwise applies a deterministic keyword-rule fallback; a keyword-derived
escalation may raise, but never lower, the model tier; a classification whose
confidence falls below a threshold is resolved toward the more sensitive tier;
and a malformed or unreadable model artifact causes the module to fail loudly
rather than to downgrade silently.

[0012] A contextual risk module computes a bounded risk value from a closed
snapshot of signals for one access event, wherein time-derived signals such as
whether access occurred outside business hours are computed by the server from
an access timestamp and an organization time zone and are never accepted from
the client, and wherein the snapshot records the time zone against which the
derivation was performed so that a later recomputation reproduces the same
result. The risk model is additive and versioned, and any change to its weights
requires a change to its version identifier.

[0013] A multi-agent scoring subsystem executes a plurality of scoring agents in
parallel, each agent producing a bounded score together with a human-readable
rationale. In a preferred embodiment the agents are five in number, directed
respectively to security posture, regulatory compliance, access context,
quantum readiness and sustainability. Each agent executes under an independent
timeout, and an agent that exceeds its timeout or otherwise fails is assigned a
maximally cautious score with a rationale recording the failure, rather than
being omitted from the aggregate.

[0014] A consensus module combines the agent scores by a versioned weighted mean
into a single trust score, wherein the weights in a preferred embodiment cause
the security and compliance agents to co-lead the aggregate, and wherein the
consensus function carries a version identifier stored with each trust score so
that the score remains attributable to the exact combination logic used.

[0015] A deterministic policy module evaluates a set of human-authored rules
against the classification, the risk value, the trust score and further
attributes, in a defined priority order, and returns the action of the first
rule that matches. A matching rule may override the artificial-intelligence
recommendation. When no rule matches, the artificial-intelligence recommendation
stands and the outcome is recorded as a first-class result carrying a null rule
identifier, so that "no rule applied" is distinguishable from "a rule applied",
rather than being an error or a silent default. Rule conditions may be composed
recursively with conjunction, disjunction and negation to a bounded depth.

[0016] A crypto-agile module selects a cryptographic profile as a function of
the trust score according to versioned bands: below a first threshold a fully
post-quantum profile is selected; below a second, higher threshold a hybrid
profile combining a classical and a post-quantum key-establishment mechanism is
selected; and otherwise a symmetric profile is selected. Threshold boundaries
resolve toward the more protective profile. The module fails closed: if a
selected mechanism or key is unavailable, the operation is refused rather than
completed under a weaker mechanism. Encryption is performed with authenticated
encryption, and the resulting data-encryption key is wrapped under the selected
profile and stored separately from the ciphertext.

[0017] An audit module appends every decision as an entry in a hash-chained,
append-only ledger whose integrity is protected by database triggers that reject
update, delete and truncate operations. The ledger supports Merkle inclusion and
consistency proofs in the manner of a certificate-transparency log. A checkpoint
module, on demand at auditor request and optionally on a periodic schedule,
computes a Signed Tree Head over the current tree size, Merkle root, signing
time and document scope, and signs it with a post-quantum digital-signature
algorithm under a domain-separation label. The
signing key is generated once, wrapped under a master key, and persisted in an
append-only key table in which the active key is the latest row, so that key
rotation is itself an append. An auditor pins the public key out of band and can
thereafter verify any Signed Tree Head, any inclusion proof and any consistency
proof independently of the operator.

[0018] In further aspects the system includes: a durable transactional outbox,
relay and dead-letter queue that guarantee at-least-once publication of events
to a message bus without loss on failure; an agentic retrieval-augmented
question-answering subsystem that plans, retrieves from a vector index,
reasons and verifies, and refuses to answer when the answer is not grounded in
retrieved evidence; a graph subsystem that computes multi-hop attack paths; a
quantum-optimization subsystem that ranks a cryptographic-migration schedule
using a quantum approximate optimization algorithm and compares it against
greedy and simulated-annealing baselines over an identical constraint set; and a
crypto-shredding subsystem that renders data permanently unreadable by
destroying its wrapped key material while preserving the audit trail. These and
other features are described in detail below with reference to the drawings.


BRIEF DESCRIPTION OF THE DRAWINGS

[0019] The invention is described with reference to the accompanying drawings,
in which like reference numerals denote like components, and in which:

Figure 1 : The complete proposed bound-pipeline system for quantum-aware,
risk-adaptive data protection.
Figure 2 : The fail-safe sensitivity classification module.
Figure 3 : The contextual risk scoring module and its server-side derivation of
context.
Figure 4 : The five-agent parallel scoring subsystem with per-agent timeout
fail-safe and versioned consensus aggregation.
Figure 5 : The deterministic first-match policy decision gate and its
relationship to the artificial-intelligence recommendation.
Figure 6 : The crypto-agile profile selection and fail-closed encryption module.
Figure 7 : The append-only Merkle-chained audit ledger and post-quantum-signed
checkpoint anchoring, with the independent verification path.
Figure 8 : The durable transactional outbox, relay and dead-letter queue of the
event bus.
Figure 9 : The agentic retrieval-augmented question-answering subsystem with
grounding-based refusal.
Figure 10 : The multi-hop attack-path graph subsystem.
Figure 11 : The quantum-approximate-optimization migration-ranking subsystem and
its baselines.
Figure 12 : The crypto-shredding subsystem.
Figure 13 : An end-to-end sequence of one assessment through the bound pipeline.
Figure B01 : Performance - trust-band to cryptographic-profile mapping.
Figure B02 : Performance - migration-ranking objective across the quantum,
greedy and annealing methods over an identical constraint set.

DETAILED DESCRIPTION OF THE INVENTION

[0020] The following detailed description is made with reference to the drawings.
Reference numerals in the range 1xx denote components of Figure 1; numerals in
the range Nxx denote components of Figure N. The description sets out preferred
embodiments; it is illustrative and not limiting, and a person skilled in the
art will recognize that individual features may be combined or substituted
without departing from the scope of the claims.

[0021] Referring to Figure 1, the complete system (100) is a computer-implemented
platform executing on one or more processors with associated memory and
persistent storage. Data to be protected is presented at a registration and
ingestion interface (101), which records the data as a document having an
identity and a status and admits the request only after a server-side
authorization check binds the request to an authenticated principal and role.
The registered document then traverses, in a fixed order, the fail-safe
sensitivity classification module (102), the contextual risk scoring module
(103), the five-agent parallel scoring subsystem (104), the versioned consensus
trust-score aggregator (105), the deterministic first-match policy decision gate
(106), and the crypto-agile profile selection and fail-closed encryption module
(107). Every material decision produced along this path is appended to the
append-only Merkle-chained audit ledger (108), over which the post-quantum-
signed checkpoint anchoring module (109) computes, on demand at auditor
request, a Signed Tree Head. An independent verification interface (110)
exposes the proofs and the
signed head to an auditor. State transitions are propagated reliably by the
event bus (111) comprising a durable transactional outbox, a relay and a
dead-letter queue, and a set of auxiliary analytics subsystems (112) provide
attack-path analysis, grounded question answering, quantum-assisted migration
ranking and crypto-shredding. The essential character of the invention is that
these components form a bound pipeline: the output of each stage is the recorded,
attributable input to the next, and each stage is oriented to fail safe.

[0022] The binding is concrete and verifiable. The sensitivity tier produced by
(102) is the input that the policy gate (106) and the crypto selector (107)
consult; the risk value produced by (103) and the agent outputs produced by
(104) are the inputs from which (105) computes the trust score; that trust score
is the input on which both the policy gate (106) and the crypto selector (107)
act; and each of these outputs, together with the identity of the model or
function version that produced it, is written to the ledger (108). Because the
ledger is append-only and hash-chained, and because the checkpoint module (109)
signs the tree with a post-quantum signature, the sequence of stage outputs for
any document is reconstructable and cannot be altered after the fact without
detection. This closes the "absence of binding" deficiency of the prior art.

FAIL-SAFE SENSITIVITY CLASSIFICATION MODULE (102)

[0023] Referring to Figure 2, the classification module (200 denoting the module
as a whole) receives document text (201) and routes it to a model-backed
classifier (203) when a configured model artifact (202) is present and passes a
structural validation, and otherwise to a deterministic keyword-rule classifier
(204). The model-backed path assigns one of three machine-learning sensitivity
tiers, namely PUBLIC, CONFIDENTIAL and RESTRICTED, together with a confidence
value. A fourth designation, INTERNAL, is not produced by the statistical model
but is reserved to the policy layer, so that the model is trained only on tiers
it can meaningfully separate. A confidence-threshold and escalation stage (205)
then applies two fail-safe rules: first, if the model confidence is below a
configured threshold, the tier is resolved upward to the more sensitive tier
(206); second, a keyword-derived signal may escalate the tier upward but is
never permitted to lower a tier the model assigned (207). The resulting tier and
its provenance are emitted (208).

[0024] The module is fail-safe by construction in three further respects. If the
configured artifact is present but malformed, unreadable, or of an unexpected
schema, the module raises a loud error and refuses to proceed, rather than
silently falling back to a weaker path, so that an operator cannot mistake a
broken model for a functioning one. If no artifact is configured at all, the
deterministic keyword-rule classifier is used as a declared, documented offline
fallback rather than as a hidden default. And because every ambiguity resolves
toward greater sensitivity, an adversary cannot exploit uncertainty to obtain a
weaker downstream protection. The classifier is deliberately decoupled from any
particular training corpus: the trained artifact, not the corpus, is deployed,
and the description here concerns the classification logic and its fail-safe
orientation rather than any specific training data.

CONTEXTUAL RISK SCORING MODULE (103)

[0025] Referring to Figure 3, the contextual risk module (300) computes a
bounded risk value for one access event from a closed set of signals termed a
context snapshot. A request carries a document identity, a subject actor
identity, a device identity, an access timestamp and an organization time zone
(301). A server-side derivation stage (302) computes, from the access timestamp
and the organization time zone, whether the access occurred outside defined
business hours; this "after hours" signal is never accepted from the client, so
a client cannot assert a false value to understate its own risk. The time zone
against which the derivation was performed is recorded on the snapshot (303) so
that a scheduled or triggered recomputation reproduces the identical derivation
rather than trusting a stale stored boolean. The subject actor identity is
validated to resolve to a known principal, and, where the reporting principal
differs from the subject of the access, both the asserted subject and the
authenticated reporter are recorded distinctly, so that a report of one user's
access by another is attributable and non-repudiable.

[0026] An additive scoring stage (304) combines the snapshot signals. In a
preferred embodiment a base risk is elevated by a first weight when the device
is new and by a second weight when access is after hours, the first weight being
the larger to encode that a previously unseen device is a stronger signal than
off-hours access. The sum is clamped to the closed interval from zero to one and
rounded to a fixed number of decimal places matching the storage precision
(305). The model carries a version identifier (306), and any change to the base
value or to a weight requires that this identifier be advanced, so that a stored
risk value remains attributable to the exact formula that produced it. The
resulting risk value, together with its snapshot and model version, is persisted
append-only and emitted to the downstream stages (307). Because risk is
recomputed on a schedule and on trigger events and each computation is a new
append rather than an overwrite, the history of risk for a document is preserved
in full.

FIVE-AGENT PARALLEL SCORING SUBSYSTEM (104) AND CONSENSUS (105)

[0027] Referring to Figure 4, the scoring subsystem (400) dispatches an
assessment concurrently to a plurality of scoring agents. In the preferred
embodiment there are exactly five agents: a security-posture agent (401), a
compliance agent (402), a contextual agent (403), a quantum-readiness agent
(404) and a sustainability agent (405). Each agent receives the same closed
assessment context and produces a bounded score in the interval from zero to one
together with a mandatory human-readable rationale, an agent that cannot explain
its number being treated as not having produced a usable output. The agents run
in parallel within a directed execution graph rather than sequentially, so that
the latency of the subsystem is that of the slowest agent rather than the sum.

[0028] Each agent executes under an independent timeout enforced by a fail-safe
wrapper (406). If an agent exceeds its timeout, raises an error, or returns an
invalid value, the wrapper substitutes a maximally cautious score and a
rationale that records the failure, so that a degraded or unavailable agent
raises rather than lowers the assessed risk and can never be silently dropped
from the aggregate. In one embodiment each agent is realized by a large-language-
model backend that returns a structured score and rationale; in a declared
offline embodiment each agent is realized by a deterministic scorer over the
same context, the backend in force being recorded so that a reader can
distinguish a model-generated rationale from a deterministic one. The provenance
of each agent output is thereby preserved in the audit trail.

[0029] The consensus aggregator (407) combines the five agent scores by a
weighted arithmetic mean into a single trust score (408). In the preferred
embodiment the weights are assigned so that the security and compliance agents
co-lead the aggregate and the contextual, quantum-readiness and sustainability
agents contribute in descending measure, reflecting a principled ordering of
governance priorities. The consensus function carries a version identifier that
is stored with every trust score, and the subsystem refuses to compute a
consensus from fewer than the full set of agent outputs, so that a trust score
is always the product of a complete, versioned combination of a complete set of
attributable agent outputs, satisfying the requirement that every stored score
have a traceable derivation.

DETERMINISTIC FIRST-MATCH POLICY DECISION GATE (106)

[0030] Referring to Figure 5, the policy gate (500) receives the sensitivity
tier, the risk value, the trust score and further request attributes (501) and
evaluates against them an ordered set of human-authored rules (502). Each rule
comprises a condition and an action, and the conditions are evaluated in a
defined priority order (503). The action of the first rule whose condition is
satisfied is returned as the policy decision (504), and no lower-priority rule is
thereafter considered, giving deterministic, explainable, first-match semantics.
A rule condition is not limited to a single comparison: conditions may be
composed recursively by conjunction (all-of), disjunction (any-of) and negation
(not) to a bounded maximum depth, so that complex governance logic is expressed
declaratively rather than in code. In one embodiment the rules are compiled to a
portable policy module for efficient, sandboxed evaluation.

[0031] Two properties distinguish the gate from a conventional rules engine.
First, the deterministic decision may override the artificial-intelligence
recommendation carried forward from the consensus stage: where a matching rule
prescribes an action, that action governs regardless of the recommendation, so
that a human-authored, auditable policy retains ultimate authority over the
machine recommendation. Second, the case in which no rule matches is a
first-class outcome (505): the artificial-intelligence recommendation stands,
and the decision is recorded with a null rule identifier, expressly
distinguishing "no rule applied, recommendation stands" from "a rule applied"
and from an error. This removes the ambiguity, common in prior systems, between
a deliberate absence of policy and a failure of evaluation, and it makes the
provenance of every enforced action - human rule or machine recommendation -
explicit in the audit record (506).

CRYPTO-AGILE PROFILE SELECTION AND FAIL-CLOSED ENCRYPTION (107)

[0032] Referring to Figure 6, the crypto-agile module (600) receives the trust
score (601) and selects a cryptographic profile by a versioned band mapping
(602). In the preferred embodiment: a trust score at or below a first, lower
threshold selects a fully post-quantum profile (603) employing a post-quantum
key-encapsulation mechanism and a post-quantum digital-signature algorithm; a
trust score at or below a second, higher threshold selects a hybrid profile
(604) that combines a classical elliptic-curve key-establishment mechanism with
a post-quantum key-encapsulation mechanism so that confidentiality holds if
either component remains secure; and a higher trust score selects a symmetric
authenticated-encryption profile (605). Band boundaries resolve toward the more
protective profile, so a value falling exactly on a boundary receives the
stronger treatment. The mapping carries a version identifier stored with the
selection so that the profile chosen for any document remains attributable.

[0033] The module is fail-closed (606). If a selected mechanism, library or key
is unavailable, or if any step of key establishment or wrapping fails, the
module refuses the operation and raises an error rather than completing it under
a weaker mechanism; there is no silent downgrade path. Upon a successful
selection, an encryption stage (607) generates a fresh data-encryption key,
encrypts the plaintext under an authenticated-encryption scheme yielding
ciphertext and an authentication tag, wraps the data-encryption key under the
selected profile, and stores the wrapped key separately from the ciphertext and
its nonce (608). Because the trust score drives the selection and the selection
fails closed, data assessed as less trustworthy is necessarily afforded stronger,
quantum-resistant protection, and no assessment can result in weaker protection
than its band prescribes.

APPEND-ONLY MERKLE-CHAINED AUDIT LEDGER (108) AND POST-QUANTUM-SIGNED
CHECKPOINT ANCHORING (109)

[0034] Referring to Figure 7, the audit ledger (700) receives an audit entry for
every material decision (701) - a classification, a risk computation, a
consensus, a policy decision, a cryptographic selection, an encryption, a shred
and an override - each entry recording the event type, the document, the acting
principal, a payload of the decision facts including the relevant model or
function version, and a timestamp. Entries are appended to a hash-chained store
(702) in which each entry incorporates a cryptographic digest binding it to its
predecessor, so that removal or alteration of any entry breaks the chain.
Database-level triggers (703) reject any update, delete or truncate against the
ledger tables, enforcing append-only semantics at the storage layer independently
of application code. Over the ordered leaves the module maintains a Merkle tree
(704) permitting an inclusion proof, that a given entry is present at a given
position, and a consistency proof, that a later tree is an extension of an
earlier tree with no retroactive modification, in the manner of a certificate-
transparency log.

[0035] The checkpoint anchoring module (709), shown as component 709 within
Figure 7, upon auditor request and optionally on a periodic schedule, computes
a Signed Tree Head over the tuple of current tree size, Merkle root, signing time
and document scope
(705). It signs this tuple, under a domain-separation label unique to this
purpose, using a post-quantum digital-signature algorithm (706). The signing key
is generated once, its secret component wrapped under a master key and persisted,
and its public component stored, in an append-only signing-key table (707) in
which the active key is defined as the latest row, so that key rotation is
performed by appending a new row rather than by mutating an existing one and the
key table itself remains append-only evidence. An independent verification
interface (710, corresponding to component 110 of Figure 1) publishes the signed
head, the current public key and the inclusion and consistency proofs (708).

[0036] The verification is performable by a party that does not trust the
operator. Such a verifier pins the public key out of band from the signing-key
interface; thereafter, given a Signed Tree Head, the verifier confirms the
post-quantum signature over the recomputed signing input and confirms that the
recomputed prefix root equals the stored root; given an inclusion proof, the
verifier recomputes the path to the signed root; and given a consistency proof,
the verifier confirms that the earlier tree is a prefix of the later. Because the
head is signed with a post-quantum algorithm, the evidence remains trustworthy
against an adversary possessing a cryptographically relevant quantum computer.
Tampering with a leaf, with the root, with the signature, or presentation under
the wrong key are each detected and rejected. This closes the "operator-
controlled audit and cryptographic obsolescence" deficiency of the prior art.

EVENT BUS WITH DURABLE OUTBOX, RELAY AND DEAD-LETTER QUEUE (111)

[0037] Referring to Figure 8, the event bus (800) provides reliable propagation
of state changes. Rather than publishing an event directly, a producer writes
the event, within the same database transaction that effects the state change,
to a durable outbox table (801), so that the event is persisted atomically with
the change it describes and cannot be lost even if the process fails immediately
afterward. A relay process (802) reads unpublished outbox rows and publishes them
to a streaming message bus (803) with at-least-once delivery, marking each row
published only upon acknowledgement and retrying failures with backoff. An event
that cannot be delivered after a bounded number of attempts is moved to a
dead-letter queue (804) for inspection and replay rather than being discarded.
This construction guarantees that no assessment event required by a downstream
consumer, including a consumer that recomputes risk from the server-derived
snapshot facts, is silently dropped.

AGENTIC RETRIEVAL-AUGMENTED QUESTION ANSWERING WITH GROUNDED REFUSAL (112a)

[0038] Referring to Figure 9, the question-answering subsystem (900) answers
natural-language questions over the system's own records only when the answer is
grounded in retrieved evidence. A planner stage (901) decomposes the question
into a retrieval plan. A retriever stage (902) embeds the query with a text
embedding model and performs a nearest-neighbour search over a vector index
(903) of previously embedded record chunks, returning candidate passages with
similarity scores. A reasoner stage (904) composes a candidate answer strictly
from the retrieved passages. A verifier stage (905) applies a grounding gate
that admits the answer only if the retrieved evidence is sufficiently relevant
and the candidate answer is supported by that evidence; if the gate is not
satisfied, the subsystem refuses to answer (906) rather than emitting an
ungrounded or fabricated response. The subsystem thereby provides an auditable,
evidence-bound question-answering capability in which a refusal is a correct and
expected outcome when grounding is absent.

MULTI-HOP ATTACK-PATH GRAPH SUBSYSTEM (112b)

[0039] Referring to Figure 10, the graph subsystem (1000) maintains a property
graph (1001) whose nodes represent entities such as documents, actors, devices
and hosts and whose edges represent relationships and observed accesses. A
path-analysis stage (1002) computes multi-hop paths between a source and a
target of interest, subject to constraints on hop count and edge type, so that
an analyst can discover indirect routes by which an actor or device could reach a
sensitive asset. Results are returned as ordered paths with the participating
nodes and edges (1003), enabling reasoning about exposure that is not visible
from any single access event.

QUANTUM-ASSISTED MIGRATION-RANKING SUBSYSTEM (112c)

[0040] Referring to Figure 11, the migration-ranking subsystem (1100) ranks the
order in which assets should be migrated to stronger cryptographic protection
under resource constraints. The problem is encoded as a constrained combinatorial
optimization over an identical constraint set (1101). A quantum stage (1102)
solves the encoded problem using a quantum approximate optimization algorithm
executed on a quantum simulator or device, while a greedy baseline (1103) and a
simulated-annealing baseline (1104) solve the identical instance. A comparison
stage (1105) reports the objective value achieved by each method over the same
constraints, so that the quantum method's ranking is demonstrated on an
apples-to-apples basis against classical baselines rather than in isolation, and
the resulting ranked schedule (1106) is emitted to the operator.

CRYPTO-SHREDDING SUBSYSTEM (112d)

[0041] Referring to Figure 12, the crypto-shredding subsystem (1200) effects
erasure by destroying key material rather than by deleting evidence. Upon a
confirmed erasure request (1201) for a document, and under a lock preventing
concurrent ciphertext creation, the subsystem overwrites the wrapped
data-encryption key of every ciphertext row for that document with a marker
followed by fresh random bytes of equal length (1202), so that unwrap
permanently fails and the ciphertext becomes unreadable. The ciphertext bytes
and the audit trail are retained as proof that data existed (1203); the operation
is idempotent and is itself audited (1204). It is expressly noted, as a matter of
engineering honesty, that cryptographic erasure of the key renders the data
unreadable given the cryptography, while completeness of erasure at the storage
layer additionally depends upon operational handling of write-ahead logs,
replicas and backups, which retain prior bytes until rotated or expired; the
subsystem therefore claims destruction of the key, not the impossibility of
forensic recovery of pre-shred storage artifacts.

METHODS PERFORMED BY THE SYSTEM

[0042] The operation of the system is further described as a set of methods.
Referring to Figure 13, which depicts one end-to-end assessment, the methods
below are performed in the stated order, each stage recording its output to the
audit ledger (108) before the next stage consumes it.

[0043] METHOD 1 : End-to-end bound assessment and protection.
Input  : A registered document identity, its content, and an access context.
Output : An enforced protection decision, a stored ciphertext where applicable,
         and a chain of audit entries with an anchoring Signed Tree Head.
Step 1 : Authenticate the caller and authorize the request against the caller's
         role on the server; reject if unauthorized.
Step 2 : Classify the document sensitivity by METHOD 2, resolving ambiguity
         toward greater sensitivity, and record the tier and its provenance.
Step 3 : Derive the context snapshot server-side and compute the contextual risk
         by METHOD 3; record the risk value, snapshot and model version.
Step 4 : Execute the plurality of scoring agents in parallel and combine them
         into a versioned consensus trust score by METHOD 4; record the agent
         outputs and the consensus.
Step 5 : Evaluate the deterministic first-match policy by METHOD 5; obtain either
         an overriding action with a rule identifier, or the artificial-
         intelligence recommendation with a null rule identifier; record it.
Step 6 : Select the cryptographic profile from the trust score and, if the
         decision is to protect, encrypt by METHOD 6, failing closed; record the
         selection and the encryption.
Step 7 : Append each of the foregoing decisions to the ledger and, on demand at
         auditor request or on an optional periodic schedule, compute and sign a
         Signed Tree Head by METHOD 7.
Step 8 : Publish the resulting state-change events reliably via the durable
         outbox so that downstream consumers recompute from server-derived facts.

[0044] METHOD 2 : Fail-safe sensitivity classification.
Input  : Document text; a configuration optionally naming a model artifact.
Output : A sensitivity tier in {PUBLIC, CONFIDENTIAL, RESTRICTED} with provenance.
Step 1 : If a model artifact is configured, load and structurally validate it;
         if present but malformed, raise a loud error and stop (no downgrade).
Step 2 : If a valid artifact loaded, infer a tier and a confidence from the
         model; otherwise apply the deterministic keyword-rule fallback as a
         declared offline path.
Step 3 : If the model confidence is below the configured threshold, resolve the
         tier upward to the more sensitive tier.
Step 4 : If a keyword-derived escalation signal indicates a higher tier, raise
         the tier to it; never lower a tier on the basis of a keyword signal.
Step 5 : Emit the final tier together with its provenance (model or fallback,
         and whether escalation or low-confidence resolution applied).

[0045] METHOD 3 : Server-side context derivation and contextual risk scoring.
Input  : Document identity, subject actor identity, device identity, access
         timestamp, organization time zone.
Output : A bounded risk value with a recorded snapshot and model version.
Step 1 : Validate that the subject actor resolves to a known principal; where the
         reporting principal differs, record both distinctly.
Step 2 : Derive the after-hours signal from the timestamp and time zone on the
         server; do not accept it from the client. Record the time zone used.
Step 3 : Start from a base risk; add the new-device weight if the device is new;
         add the after-hours weight if after hours.
Step 4 : Clamp the sum to the interval [0,1] and round to the storage precision.
Step 5 : Persist the risk value, the snapshot and the model version append-only,
         and emit them downstream.

[0046] METHOD 4 : Parallel multi-agent scoring and versioned consensus.
Input  : A closed assessment context.
Output : Five attributable agent outputs and one versioned trust score.
Step 1 : Dispatch the assessment context concurrently to the five agents within a
         directed execution graph.
Step 2 : For each agent, enforce an independent timeout; on timeout, error or
         invalid value, substitute a maximally cautious score and a rationale
         recording the failure; otherwise take the agent's bounded score and
         mandatory rationale.
Step 3 : Refuse to proceed unless a complete set of agent outputs is present.
Step 4 : Compute the trust score as the weighted arithmetic mean of the five
         scores, using the versioned weights in which security and compliance
         co-lead.
Step 5 : Persist the agent outputs and the trust score with the consensus
         version identifier.

[0047] METHOD 5 : Deterministic first-match policy evaluation.
Input  : Sensitivity tier, risk value, trust score, further attributes; an
         ordered rule set.
Output : A policy decision with either a matching rule identifier or a null
         identifier.
Step 1 : Order the rules by their defined priority.
Step 2 : Evaluate each rule's condition in order; a condition may be a leaf
         comparison or a recursive all-of / any-of / not composition to the
         bounded depth.
Step 3 : On the first satisfied condition, return that rule's action as the
         decision, with its rule identifier; the action may override the
         artificial-intelligence recommendation.
Step 4 : If no rule matches, return the artificial-intelligence recommendation as
         the decision with a null rule identifier, recorded as a first-class
         "no rule applied" outcome.
Step 5 : Record the decision, its provenance and the evaluated inputs.

[0048] METHOD 6 : Crypto-agile selection and fail-closed encryption.
Input  : Trust score; plaintext to protect.
Output : A selected profile and, on success, a stored ciphertext and a wrapped
         data-encryption key; otherwise a refusal.
Step 1 : Map the trust score to a profile by the versioned bands: at or below the
         lower threshold, post-quantum; at or below the higher threshold, hybrid;
         otherwise symmetric. Resolve boundaries toward the stronger profile.
Step 2 : Verify availability of the selected mechanism and keys; if unavailable,
         refuse and stop (fail closed, no downgrade).
Step 3 : Generate a fresh data-encryption key; encrypt the plaintext under
         authenticated encryption to obtain ciphertext, nonce and tag.
Step 4 : Wrap the data-encryption key under the selected profile.
Step 5 : Store the wrapped key separately from the ciphertext and nonce; record
         the selection with its version identifier and the encryption event.

[0049] METHOD 7 : Ledger append, Merkle proofs and post-quantum checkpoint.
Input  : A decision to record; on demand, a request to anchor.
Output : An append-only entry; on anchoring, a Signed Tree Head and proofs.
Step 1 : Append the entry to the hash-chained ledger, binding it to its
         predecessor; the storage layer rejects update, delete and truncate.
Step 2 : Maintain the Merkle tree over the leaves; support inclusion and
         consistency proofs.
Step 3 : On anchoring, compute the tuple (tree size, Merkle root, signing time,
         document scope) and sign it under the domain-separation label with the
         post-quantum signature algorithm, using the latest signing-key row.
Step 4 : Publish the Signed Tree Head and the public key; a verifier pins the key
         out of band.
Step 5 : On verification, confirm the signature over the recomputed input, that
         the recomputed prefix root equals the stored root, and that inclusion
         and consistency proofs recompute correctly; reject any tamper.

PERFORMANCE EVALUATION

[0050] The reduction to practice of the invention was evaluated end-to-end on a
containerized deployment comprising an application server, a relational database
with a vector extension, a streaming message store, a graph database and a
post-quantum cryptographic library. The evaluation exercised the complete bound
pipeline and each subsystem, and the results below are reported for the system
treated as a complete, working product.

[0051] Correctness and coverage. The automated verification suite comprises 46
executed test modules exercising 695 test functions that expand, through
parameterization, to 1,059 individual test cases. Of these, 1,040 pass, 19 are
conditionally skipped where an optional post-quantum native library is absent on
a given host, and 0 fail. Statement and branch coverage of the served backend is
85.47 percent against a governance floor of 70 percent; offline data-preparation
utilities that are not part of the served runtime are excluded from the coverage
denominator. The skipped cases execute in the post-quantum-equipped container,
where the real post-quantum signing and verification paths are exercised
directly.

[0052] Fail-safe behaviour. Table P-1 summarizes the observed behaviour of each
stage under abnormal conditions, confirming that every stage is oriented to fail
safe. In every case the abnormal condition results in equal or greater
protection, never a silent downgrade.

Table P-1 : Fail-safe behaviour by stage.
| Sl. No | Stage | Abnormal condition | Observed fail-safe outcome |
| 01 | Classification (102) | Model confidence below threshold | Tier resolved to the more sensitive tier |
| 02 | Classification (102) | Model artifact malformed | Loud error; operation refused; no downgrade |
| 03 | Risk (103) | Client asserts after-hours=false at 03:00 | Server re-derives true; client value ignored |
| 04 | Agent (104) | Agent exceeds timeout | Maximally cautious score substituted; failure recorded |
| 05 | Consensus (105) | Fewer than five agent outputs | Consensus refused; no partial trust score |
| 06 | Policy (106) | No rule matches | AI recommendation stands; rule identifier null (first-class) |
| 07 | Crypto (107) | Selected mechanism unavailable | Operation refused (fail closed); no weaker fallback |
| 08 | Audit (108) | Update/delete/truncate attempted | Rejected by storage-layer trigger |

[0053] Cryptographic profile mapping. Figure B01 depicts the versioned mapping
from the trust score to the cryptographic profile. A trust score at or below the
lower band selects the fully post-quantum profile; at or below the higher band,
the hybrid profile; and above it, the symmetric authenticated-encryption profile;
boundaries resolve toward the stronger profile. Table P-2 records the measured
key and signature material sizes of the post-quantum signature algorithm used
for checkpoint anchoring, confirming operability of the real post-quantum path.

Table P-2 : Post-quantum signature material sizes (checkpoint anchoring).
| Sl. No | Artifact | Size (bytes) |
| 01 | Public key | 2592 |
| 02 | Secret key (wrapped at rest) | 4896 |
| 03 | Signature over the Signed Tree Head | 4627 |

[0054] Independent audit verification. The tamper-evident properties were
verified in the post-quantum-equipped container. Table P-3 records the outcomes:
a well-formed Signed Tree Head with correct proofs verifies, while a tampered
leaf root, a tampered signature and a wrong verifying key are each rejected,
demonstrating that a verifier who does not trust the operator detects tampering.

Table P-3 : Audit verification outcomes.
| Sl. No | Presented evidence | Expected | Observed |
| 01 | Valid Signed Tree Head and inclusion proof | Accept | Accept |
| 02 | Valid consistency proof (earlier prefix of later) | Accept | Accept |
| 03 | Tampered Merkle root | Reject | Reject |
| 04 | Tampered signature | Reject | Reject |
| 05 | Correct data, wrong verifying key | Reject | Reject |

[0055] Quantum-assisted migration ranking. Figure B02 compares the objective
value achieved by the quantum approximate optimization algorithm against the
greedy and simulated-annealing baselines over an identical constraint set,
establishing that the ranking is demonstrated on a like-for-like basis rather
than in isolation, and that the quantum method is competitive with or superior
to the classical baselines on the evaluated instances.

[0056] Reliability of propagation. The durable transactional outbox was verified
to persist each event atomically with the state change it describes and to
achieve at-least-once delivery, with undeliverable events routed to the
dead-letter queue for replay, so that no assessment event required by a
downstream consumer is lost under process failure.

CLAIMS

We claim:

1. A computer-implemented system for risk-adaptive, quantum-aware data
protection, the system comprising one or more processors and a memory storing
instructions that, when executed by the one or more processors, provide a bound
assessment pipeline comprising:
   (a) a fail-safe sensitivity classification module configured to assign a
   sensitivity tier to registered data and to resolve an ambiguous or
   low-confidence classification toward a more sensitive tier;
   (b) a contextual risk module configured to compute a bounded risk value from a
   closed context snapshot for an access event, wherein at least one time-derived
   signal of the snapshot is computed by the system from an access timestamp and
   an organization time zone and is not accepted from a requesting client;
   (c) a scoring subsystem configured to execute a plurality of scoring agents in
   parallel, each agent producing a bounded score and a rationale, and each agent
   executing under an independent timeout such that expiry or failure of an agent
   causes a maximally cautious score to be substituted for that agent rather than
   the agent being omitted;
   (d) a consensus module configured to combine the scores of the plurality of
   agents into a trust score by a versioned weighted mean and to refuse to
   produce a trust score from an incomplete set of agent outputs;
   (e) a deterministic policy module configured to evaluate an ordered set of
   rules against at least the sensitivity tier, the risk value and the trust
   score and to return the action of a first matching rule, wherein a matching
   rule is capable of overriding an artificial-intelligence recommendation, and
   wherein an absence of any matching rule is a first-class outcome in which the
   artificial-intelligence recommendation stands and which is recorded with a
   null rule identifier;
   (f) a crypto-agile module configured to select, as a function of the trust
   score and according to versioned bands, one cryptographic profile from among a
   symmetric profile, a hybrid profile combining a classical key-establishment
   mechanism with a post-quantum key-encapsulation mechanism, and a fully
   post-quantum profile, the crypto-agile module being configured to fail closed
   by refusing an operation upon unavailability of a selected mechanism or key
   rather than completing the operation under a weaker mechanism; and
   (g) an append-only, hash-chained audit ledger configured to record each output
   of (a) through (f) together with an identifier of the model or function
   version that produced it, the ledger being protected against modification at a
   storage layer and being anchored by a checkpoint module configured to sign a
   Signed Tree Head over a Merkle root of the ledger with a post-quantum
   digital-signature algorithm;
   wherein an output of each of modules (a) through (f) is the recorded input
   that conditions a next module, whereby the modules form a bound pipeline whose
   stage outputs are mutually attributable and independently verifiable.

2. The system as claimed in claim 1, wherein the fail-safe sensitivity
classification module is configured to apply a trained statistical model when a
model artifact is configured and passes a structural validation, to apply a
deterministic keyword-rule classifier as a declared fallback otherwise, and to
raise a loud error and refuse to proceed, rather than downgrade, when a
configured model artifact is present but malformed or unreadable.

3. The system as claimed in claim 2, wherein a keyword-derived signal is
permitted to escalate the sensitivity tier assigned by the trained statistical
model upward but is not permitted to lower it, and wherein the trained
statistical model is trained over a proper subset of sensitivity tiers while a
further designation is reserved to the deterministic policy module.

4. The system as claimed in claim 1, wherein the contextual risk module is
configured to record, on the context snapshot, the organization time zone
against which the time-derived signal was computed, such that a subsequent
scheduled or triggered recomputation reproduces an identical derivation, and
wherein the risk value is computed by an additive, version-identified function
whose weights cannot be changed without advancing the version identifier.

5. The system as claimed in claim 1, wherein the contextual risk module is
further configured to validate that a subject actor identity of the access event
resolves to a known principal and, where a reporting principal differs from the
subject actor, to record the asserted subject and the authenticated reporter
distinctly, such that a report by one principal of another principal's access is
attributable.

6. The system as claimed in claim 1, wherein the plurality of scoring agents
consists of five agents directed respectively to security posture, regulatory
compliance, access context, quantum readiness and sustainability, and wherein
each agent produces a mandatory human-readable rationale such that an agent
output lacking a rationale is treated as not produced.

7. The system as claimed in claim 6, wherein the versioned weighted mean assigns
weights under which the security-posture agent and the compliance agent co-lead
the trust score and the contextual, quantum-readiness and sustainability agents
contribute in descending measure, and wherein the trust score is persisted with
the version identifier of the consensus function.

8. The system as claimed in claim 1, wherein a scoring agent is realized in a
first embodiment by a large-language-model backend returning a structured score
and rationale, and in a declared offline embodiment by a deterministic scorer
over the same context, the backend in force being recorded so that a
model-generated rationale is distinguishable from a deterministic rationale in
the audit ledger.

9. The system as claimed in claim 1, wherein a rule of the deterministic policy
module comprises a condition that is one of a leaf comparison and a recursive
composition of conditions by conjunction, disjunction and negation to a bounded
maximum depth, and wherein the ordered set of rules is evaluated in a defined
priority order and compiled to a portable, sandboxed policy module for
evaluation.

10. The system as claimed in claim 1, wherein the versioned bands of the
crypto-agile module define a lower threshold at or below which the fully
post-quantum profile is selected and a higher threshold at or below which the
hybrid profile is selected, a band boundary resolving toward the more protective
profile, and wherein the selected profile is recorded with a version identifier.

11. The system as claimed in claim 1, wherein the crypto-agile module fails
closed such that, on absence of a required cryptographic primitive, an
unsatisfiable profile selection, or an integrity-check failure, the protective
operation is refused and no plaintext-equivalent output is produced, no silent
downgrade to a weaker profile being permitted.

12. The system as claimed in claim 1, wherein the append-only ledger is
maintained as a hash-chained sequence of entries per protected object such that
each entry commits to its predecessor, and wherein a database-level guard
rejects update and delete operations upon the ledger tables so that append is
the only permitted mutation.

13. The system as claimed in claim 12, wherein the post-quantum-signed checkpoint
comprises a signed tree head binding a tree size, a Merkle root over the
committed sequence, a signing time and an object identifier under a domain
separation label, signed by a post-quantum digital-signature primitive, the
signing private key being stored wrapped under a master key and its public key
being retrievable for out-of-band pinning by a verifying party.

14. The system as claimed in claim 13, wherein the ledger supports an inclusion
proof that a specified entry is committed by a given checkpoint and a consistency
proof that a later checkpoint extends an earlier checkpoint without alteration of
committed entries, both proofs being verifiable by a party that does not trust
the operator of the system.

15. The system as claimed in claim 13, wherein signing-key rotation is effected
by appending a new key record rather than mutating an existing record, the active
signing key being defined as the latest appended record, whereby the key store
itself remains append-only.

16. The system as claimed in claim 1, further comprising a durable transactional
outbox that commits an intent-to-publish record within the same database
transaction that commits the assessment outcome, and a relay that delivers said
record to a streaming event bus with at-least-once semantics, bounded retry and a
dead-letter path, such that no assessment outcome is published without being
persisted and none is lost on transient bus failure.

17. The system as claimed in claim 1, further comprising a retrieval-augmented
reasoning module over a vector index of an evidence corpus, said module planning
a query, retrieving candidate passages, reasoning over them and verifying the
reasoned answer against the retrieved passages, and refusing to answer when the
answer is not grounded in the retrieved passages.

18. The system as claimed in claim 1, further comprising a graph module that
computes multi-hop exposure paths between principals and protected objects over a
property graph, and a quantum-optimization module that ranks a migration order of
protected objects to a target cryptographic profile subject to a constraint set,
and that evaluates said ranking against deterministic greedy and simulated-
annealing baselines over an identical constraint set.

19. A computer-implemented method for quantum-aware, risk-adaptive protection of
a data object, the method comprising:

   (a) classifying the data object into a sensitivity tier by a fail-safe
   classifier that, on low confidence, assigns the more sensitive tier rather
   than the more permissive tier, and that refuses rather than downgrades when a
   configured trained model artifact is present but malformed;

   (b) deriving a contextual risk value for an access event from a closed
   snapshot of actor identity, device novelty and an access time, wherein a
   time-outside-business-hours signal is derived on the server from the access
   time and a recorded organization time zone and is not accepted as an assertion
   of the requesting party;

   (c) invoking a plurality of scoring agents in parallel, each under an
   independent time bound, and substituting a conservative fail-safe score for
   any agent that does not return within its time bound;

   (d) combining the agent scores into a trust score by a version-identified
   consensus function only when scores for the complete set of agents are
   present, and refusing to emit a trust score over a partial set;

   (e) evaluating an ordered set of deterministic policy rules against the
   assessment in first-match priority order, a matching rule overriding the
   trust-score-derived recommendation and its identifier being recorded, and, on
   no match, allowing the recommendation to stand with a null rule identifier as
   a first-class recorded outcome;

   (f) selecting a cryptographic profile from among an authenticated-symmetric
   profile, a hybrid classical-plus-post-quantum profile and a fully
   post-quantum profile according to version-identified trust bands, and applying
   the selected profile in a fail-closed manner such that any missing primitive
   or integrity failure refuses the operation without a silent downgrade; and

   (g) appending an entry committing to the assessment to a per-object
   hash-chained append-only ledger, and binding a checkpoint over the ledger by a
   post-quantum digital signature over a signed tree head under a domain
   separation label;

   wherein steps (a) through (g) are bound in a fixed order such that the input
   to each step is an output of a preceding step and no step is bypassed, whereby
   the ledger entry of step (g) attests the bound execution of steps (a) through
   (f).

20. The method as claimed in claim 19, further comprising verifying the ledger
by a party that does not trust the operator, said verifying comprising
recomputing the Merkle root over the committed prefix, confirming the recomputed
root equals the root bound in the signed tree head, and verifying the
post-quantum signature over the recomputed signing input against a public key
pinned out of band, a mismatch of the root, the signature or the key each causing
verification to be rejected.

21. The method as claimed in claim 19, wherein a keyword-derived signal escalates
the sensitivity tier of step (a) upward but never lowers it, and wherein a device
-novelty signal contributing to the risk value of step (b) is corroborated
against a device-enrollment record rather than accepted solely on the assertion
of the requesting party.

22. The method as claimed in claim 19, further comprising, upon a change in the
trust score of a protected object, re-executing the selection of step (f) and,
where the selected profile differs from the profile in force, initiating
re-protection of the object under the newly selected profile.

23. A non-transitory computer-readable medium storing instructions that, when
executed by one or more processors, cause the one or more processors to perform
the method of claim 19, the instructions being organized such that the fail-safe
classification, the server-derived contextual risk, the time-bounded parallel
agents, the version-identified consensus, the first-match deterministic policy
override, the fail-closed crypto-agile selection and the post-quantum-signed
append-only ledger are executed as a single bound pipeline in which the output of
each stage is the sole assessed input to the next.

================================================================================
COMPLETE SPECIFICATION - DIAGRAMS
================================================================================

The following section provides, for each figure referenced in the BRIEF
DESCRIPTION OF THE DRAWINGS and the DETAILED DESCRIPTION, (i) the source code in
the Mermaid diagramming language sufficient to render the figure, each labelled
node carrying its numbered reference character, and (ii) a component-description
table listing each numbered reference character and its description. A figure is
rendered by pasting the text between the MERMAID SOURCE - BEGIN and MERMAID
SOURCE - END markers into any Mermaid-compatible renderer.

--------------------------------------------------------------------------------
FIGURE 1 - Overall system architecture of the bound assessment pipeline
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    subgraph SYS["100 Q-AEGIS bound assessment pipeline"]
        direction TB
        I102["102 Fail-safe classification module"]
        I103["103 Contextual risk module"]
        I104["104 Parallel multi-agent scoring subsystem"]
        I105["105 Versioned consensus trust-score module"]
        I106["106 Deterministic policy-override module"]
        I107["107 Crypto-agile selection and protection module"]
        I108["108 Append-only Merkle-chained audit ledger"]
        I109["109 Post-quantum-signed checkpoint anchor"]
        I110["110 Server-side identity and RBAC gate"]
        I111["111 Durable transactional outbox and relay"]
        I112["112 Binding sequencer enforcing fixed stage order"]
    end
    I101["101 Data object and access request"] --> I110
    I110 --> I112
    I112 --> I102
    I102 --> I103
    I103 --> I104
    I104 --> I105
    I105 --> I106
    I106 --> I107
    I107 --> I108
    I108 --> I109
    I105 -. trust.updated .-> I111
    I111 -. reselect .-> I107
    I108 --> OUT["Protected object plus verifiable audit evidence"]
MERMAID SOURCE - END

Table 1 : Complete description of Figure 1 (system / process).

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1  | 100 | The Q-AEGIS bound assessment pipeline as a whole; the arrangement of modules 102-112 operated in a fixed, non-bypassable order.
2  | 101 | The input to the pipeline: a data object together with an access request describing the requesting principal, device and time.
3  | 102 | The fail-safe sensitivity classification module; assigns a sensitivity tier and, on uncertainty, resolves toward the more sensitive tier (see Figure 2).
4  | 103 | The contextual risk module; derives a continuous risk value from a closed actor/device/time snapshot, the time signal being server-derived (see Figure 3).
5  | 104 | The parallel multi-agent scoring subsystem; five independent, time-bounded scoring agents (see Figure 4).
6  | 105 | The versioned consensus trust-score module; combines the five agent scores by a version-identified weighted mean and refuses a partial set.
7  | 106 | The deterministic policy-override module; first-match ordered rule evaluation that may override the AI recommendation (see Figure 5).
8  | 107 | The crypto-agile selection and protection module; selects and applies a cryptographic profile fail-closed (see Figure 6).
9  | 108 | The append-only Merkle-chained audit ledger; hash-chained per-object evidence with database-level append-only guards (see Figure 7).
10 | 109 | The post-quantum-signed checkpoint anchor; a signed tree head over the ledger under domain label qaegis-audit-sth-v1.
11 | 110 | The server-side identity and role-based access-control gate admitting the request before any assessment stage runs.
12 | 111 | The durable transactional outbox and relay publishing assessment events with at-least-once delivery and a dead-letter path (see Figure 8).
13 | 112 | The binding sequencer that enforces the fixed stage order and forbids any stage from being skipped or reordered.

--------------------------------------------------------------------------------
FIGURE 2 - Fail-safe sensitivity classification module (102)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    A200["200 Document text and metadata in"] --> A201{"201 Trained model artifact configured and valid?"}
    A201 -- "No artifact configured" --> A203["203 Deterministic keyword-rule classifier (declared fallback)"]
    A201 -- "Configured but malformed" --> A202["202 Fail loud: refuse, no downgrade"]
    A201 -- "Configured and valid" --> A204["204 Trained statistical model inference"]
    A204 --> A205{"205 Confidence below threshold?"}
    A205 -- "Yes" --> A206["206 Assign more-sensitive tier (fail-safe)"]
    A205 -- "No" --> A207["207 Assign predicted tier"]
    A203 --> A208
    A206 --> A208
    A207 --> A208["208 Keyword escalation-only overlay (raise tier, never lower)"]
    A208 --> OUT["Sensitivity tier PUBLIC / CONFIDENTIAL / RESTRICTED"]
MERMAID SOURCE - END

Table 2 : Complete description of Figure 2.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 200 | Input document text and metadata to be classified.
2 | 201 | Decision on whether a trained model artifact is configured and passes structural validation.
3 | 202 | Fail-loud branch: a configured but malformed or unreadable artifact causes refusal, never a silent downgrade to the fallback.
4 | 203 | Deterministic keyword-rule classifier used as the declared offline fallback when no artifact is configured.
5 | 204 | Inference by the trained statistical model over the three machine-learned tiers.
6 | 205 | Confidence test against a configured threshold.
7 | 206 | Fail-safe assignment of the more sensitive tier when confidence is low.
8 | 207 | Assignment of the predicted tier when confidence is adequate.
9 | 208 | Keyword-derived escalation overlay permitted to raise the tier but never to lower it.

--------------------------------------------------------------------------------
FIGURE 3 - Contextual risk module (103)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    B300["300 Access event: actor, device, accessed_at, org_timezone"] --> B301["301 Resolve and validate subject actor identity"]
    B301 --> B302["302 Distinguish asserted subject from authenticated reporter"]
    B302 --> B303["303 Server-derive after_hours from accessed_at and org_timezone"]
    B303 --> B304["304 Build closed context snapshot (record org_timezone)"]
    B304 --> B305["305 Additive scorer: BASE + new-device + after-hours weights"]
    B305 --> B306["306 Clamp to [0,1], round 4 dp, cap at ceiling"]
    B306 --> B307["307 Persist risk row with MODEL_VERSION"]
    B307 --> OUT["Contextual risk value in [0,1]"]
MERMAID SOURCE - END

Table 3 : Complete description of Figure 3.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 300 | Input access event carrying actor identity, device identifier, device-novelty flag, access timestamp and organization time zone.
2 | 301 | Resolution and validation that the subject actor identity refers to a known principal.
3 | 302 | Distinct recording of the asserted subject and the authenticated reporting principal, supporting third-party reporting.
4 | 303 | Server-side derivation of the after-hours signal from the timestamp and the recorded time zone; never accepted as a client assertion.
5 | 304 | Construction of the closed context snapshot, carrying the time zone so a later recompute reproduces the derivation.
6 | 305 | Additive risk function combining a base weight, a new-device weight and an after-hours weight.
7 | 306 | Clamping to the unit interval, rounding to four decimal places, and application of a maximum ceiling.
8 | 307 | Persistence of the risk row stamped with the version identifier of the risk model.

--------------------------------------------------------------------------------
FIGURE 4 - Parallel multi-agent scoring subsystem (104) and consensus (105)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    C400["400 Assessment context in"] --> C401["401 Fan-out to five agents in parallel"]
    C401 --> C402["402 Security-posture agent (w=0.250)"]
    C401 --> C403["403 Compliance agent (w=0.250)"]
    C401 --> C404["404 Contextual agent (w=0.200)"]
    C401 --> C405["405 Quantum-readiness agent (w=0.175)"]
    C401 --> C406["406 Sustainability agent (w=0.125)"]
    C402 --> C407
    C403 --> C407
    C404 --> C407
    C405 --> C407
    C406 --> C407{"407 Per-agent timeout? substitute conservative fail-safe score"}
    C407 --> C408{"408 Complete set of five scores present?"}
    C408 -- "No" --> REFUSE["Refuse: no trust score over a partial set"]
    C408 -- "Yes" --> CONS["105 Versioned weighted-mean consensus -> trust score + CONSENSUS_VERSION"]
    CONS --> OUT["Trust score in [0,1] with rationales"]
MERMAID SOURCE - END

Table 4 : Complete description of Figure 4.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 400 | Input assessment context provided to all agents.
2 | 401 | Parallel fan-out invoking the five agents concurrently.
3 | 402 | Security-posture agent; consensus weight 0.250.
4 | 403 | Regulatory-compliance agent; consensus weight 0.250.
5 | 404 | Access-context agent; consensus weight 0.200.
6 | 405 | Quantum-readiness agent; consensus weight 0.175.
7 | 406 | Sustainability agent; consensus weight 0.125.
8 | 407 | Per-agent timeout guard substituting a conservative fail-safe score for any agent exceeding its time bound.
9 | 408 | Completeness gate refusing to emit a trust score unless all five agent scores are present.
10 | 105 | Versioned weighted-mean consensus producing the trust score and stamping the consensus version identifier.

--------------------------------------------------------------------------------
FIGURE 5 - Deterministic policy-override module (106)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    D500["500 Trust score, tier, risk, context in"] --> D501["501 Compile ordered rules to sandboxed policy module"]
    D501 --> D502["502 Evaluate rules in fixed priority order"]
    D502 --> D503{"503 First rule whose condition matches?"}
    D503 -- "Match" --> D504["504 Apply rule decision; override AI recommendation; record rule_id"]
    D503 -- "No match" --> D505["505 AI recommendation stands; rule_id = null (first-class outcome)"]
    D504 --> D506
    D505 --> D506["506 Emit bound decision {decision, rule_id, source}"]
    D506 --> OUT["Policy decision to crypto stage"]
MERMAID SOURCE - END

Table 5 : Complete description of Figure 5.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 500 | Input comprising the trust score, sensitivity tier, contextual risk and access context.
2 | 501 | Compilation of the ordered rule set to a portable, sandboxed policy module.
3 | 502 | Evaluation of the rules in a fixed priority order.
4 | 503 | First-match test identifying the highest-priority rule whose condition is satisfied.
5 | 504 | Application of a matched rule's decision, overriding the AI recommendation, with the rule identifier recorded.
6 | 505 | No-match outcome in which the AI recommendation stands and the rule identifier is null, recorded as a first-class result.
7 | 506 | Emission of the bound decision object carrying the decision, the rule identifier and its source.

--------------------------------------------------------------------------------
FIGURE 6 - Crypto-agile selection and protection module (107)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    E600["600 Trust score in"] --> E601{"601 Trust <= low band?"}
    E601 -- "Yes" --> E602["602 Select post-quantum profile (ML-KEM-1024 + ML-DSA-87)"]
    E601 -- "No" --> E603{"603 Trust <= high band?"}
    E603 -- "Yes" --> E604["604 Select hybrid profile (X25519MLKEM768)"]
    E603 -- "No" --> E605["605 Select symmetric profile (AES-256-GCM)"]
    E602 --> E606
    E604 --> E606
    E605 --> E606{"606 Required primitive available and integrity ok?"}
    E606 -- "No" --> E607["607 Fail closed: refuse, no downgrade, no plaintext-equivalent output"]
    E606 -- "Yes" --> E608["608 Apply profile; record SELECTOR_VERSION and chosen profile"]
    E608 --> OUT["Protected object under selected profile"]
MERMAID SOURCE - END

Table 6 : Complete description of Figure 6.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 600 | Input trust score driving profile selection.
2 | 601 | Lower-band test; at or below the low threshold the fully post-quantum profile is selected.
3 | 602 | Selection of the post-quantum profile using ML-KEM-1024 key encapsulation and ML-DSA-87 signature.
4 | 603 | Upper-band test; at or below the high threshold the hybrid profile is selected.
5 | 604 | Selection of the hybrid classical-plus-post-quantum profile.
6 | 605 | Selection of the authenticated-symmetric profile above the high band.
7 | 606 | Fail-closed precondition check on primitive availability and integrity.
8 | 607 | Refusal branch producing no output and no downgrade on any failed precondition.
9 | 608 | Application of the selected profile with recording of the selector version and chosen profile.

--------------------------------------------------------------------------------
FIGURE 7 - Append-only Merkle-chained audit ledger (108) and checkpoint (109)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    F700["700 Assessment outcome in"] --> F701["701 Canonicalize entry and hash"]
    F701 --> F702["702 Chain: entry_hash = H(prev_hash || entry)"]
    F702 --> F703["703 Append to per-object ledger (DB append-only trigger)"]
    F703 --> F704{"704 UPDATE / DELETE / TRUNCATE attempted?"}
    F704 -- "Yes" --> F705["705 Rejected by database guard"]
    F704 -- "No" --> F706["706 Compute Merkle root over committed prefix"]
    F706 --> F707["707 Build signed tree head (tree_size, root, signed_at, object_id)"]
    F707 --> F708["708 Sign STH with ML-DSA-87 under domain qaegis-audit-sth-v1"]
    F708 --> F709["709 Persist checkpoint; signing key wrapped under master key"]
    F709 --> F710["710 Publish public key via GET /audit/signing-key for out-of-band pinning"]
    F710 --> OUT["Independently verifiable audit evidence"]
MERMAID SOURCE - END

Table 7 : Complete description of Figure 7.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 700 | Input assessment outcome to be committed to the ledger.
2 | 701 | Canonicalization and hashing of the ledger entry.
3 | 702 | Hash-chaining of the entry to its predecessor.
4 | 703 | Append of the entry to the per-object ledger under a database-level append-only trigger.
5 | 704 | Detection of any update, delete or truncate attempt against the evidence tables.
6 | 705 | Rejection of such a mutation by the database guard, so append is the only permitted operation.
7 | 706 | Computation of the Merkle root over the committed prefix of entries.
8 | 707 | Construction of the signed tree head binding tree size, root, signing time and object identifier.
9 | 708 | Signature of the signed tree head by ML-DSA-87 under the domain separation label.
10 | 709 | Persistence of the checkpoint, the signing private key being stored wrapped under the master key.
11 | 710 | Publication of the signing public key for out-of-band pinning by a verifying party.

--------------------------------------------------------------------------------
FIGURE 8 - Durable transactional outbox and relay (111)
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    G800["800 Assessment commit (DB transaction)"] --> G801["801 Insert outbox record in same transaction"]
    G801 --> G802["802 Commit: outcome and intent-to-publish are atomic"]
    G802 --> G803["803 Relay reads unsent records, publishes to Redis Streams"]
    G803 --> G804{"804 Delivery ok within bounded retries?"}
    G804 -- "Yes" --> OKAY["Mark sent; at-least-once delivery"]
    G804 -- "No" --> DLQ["Route to dead-letter path after retry budget"]
MERMAID SOURCE - END

Table 8 : Complete description of Figure 8.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 800 | The database transaction committing an assessment outcome.
2 | 801 | Insertion of an intent-to-publish outbox record within the same transaction.
3 | 802 | Atomic commit binding the outcome and the publish intent, so neither exists without the other.
4 | 803 | The relay reading unsent records and publishing them to the streaming event bus.
5 | 804 | Bounded-retry delivery test; success marks the record sent, exhaustion routes it to the dead-letter path.

--------------------------------------------------------------------------------
FIGURE 9 - Retrieval-augmented reasoning module with grounding refusal
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    H900["900 Query in"] --> H901["901 Planner: decompose query"]
    H901 --> H902["902 Retriever: k-NN over pgvector index (bge-large-en-v1.5, dim 1024)"]
    H902 --> H903["903 Reasoner: draft answer over retrieved passages"]
    H903 --> H904["904 Verifier: is each claim grounded in retrieved passages?"]
    H904 --> H905{"905 Grounded?"}
    H905 -- "No" --> H906["906 Refuse: decline to answer (no ungrounded output)"]
    H905 -- "Yes" --> OUT["Grounded answer with citations"]
MERMAID SOURCE - END

Table 9 : Complete description of Figure 9.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 900 | Input natural-language query over the evidence corpus.
2 | 901 | Planner stage decomposing the query into a retrieval plan.
3 | 902 | Retriever stage performing nearest-neighbour search over the pgvector index of embedded passages.
4 | 903 | Reasoner stage drafting an answer grounded on the retrieved passages.
5 | 904 | Verifier stage checking each drafted claim against the retrieved passages.
6 | 905 | Grounding decision gate.
7 | 906 | Refusal branch declining to answer when the drafted answer is not grounded.

--------------------------------------------------------------------------------
FIGURE 10 - Multi-hop exposure-path graph module
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart LR
    J1000["1000 Property graph: principals, devices, objects, grants"] --> J1001["1001 Traverse relationships up to N hops"]
    J1001 --> J1002["1002 Enumerate candidate exposure paths principal -> object"]
    J1002 --> J1003["1003 Rank paths by exposure weight"]
    J1003 --> OUT["Ranked multi-hop exposure paths"]
MERMAID SOURCE - END

Table 10 : Complete description of Figure 10.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 1000 | The property graph of principals, devices, protected objects and access grants.
2 | 1001 | Bounded multi-hop traversal of the graph relationships.
3 | 1002 | Enumeration of candidate exposure paths from a principal to a protected object.
4 | 1003 | Ranking of the enumerated paths by an exposure weight.

--------------------------------------------------------------------------------
FIGURE 11 - Quantum-optimization migration-ranking module and baselines
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    K1100["1100 Objects, profiles, constraint set in"] --> K1101["1101 Encode as constrained cost function (QUBO)"]
    K1101 --> K1102["1102 QAOA solver ranks migration order"]
    K1100 --> K1103["1103 Greedy baseline on identical constraints"]
    K1100 --> K1104["1104 Simulated-annealing baseline on identical constraints"]
    K1102 --> K1105{"1105 Compare rankings on identical constraint set"}
    K1103 --> K1105
    K1104 --> K1105
    K1105 --> K1106["1106 Emit ranked migration plan with comparative metrics"]
    K1106 --> OUT["Migration order to crypto-agile stage"]
MERMAID SOURCE - END

Table 11 : Complete description of Figure 11.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 1100 | Input set of objects, candidate profiles and the migration constraint set.
2 | 1101 | Encoding of the migration problem as a constrained cost function.
3 | 1102 | Quantum-approximate-optimization solver ranking the migration order.
4 | 1103 | Deterministic greedy baseline over the identical constraint set.
5 | 1104 | Simulated-annealing baseline over the identical constraint set.
6 | 1105 | Comparison of the three rankings on the identical constraint set.
7 | 1106 | Emission of the ranked migration plan with comparative metrics.

--------------------------------------------------------------------------------
FIGURE 12 - Cryptographic key-shred (right-to-erasure) module
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart TB
    L1200["1200 Erasure request for protected object"] --> L1201["1201 Locate wrapped data-encryption key (DEK)"]
    L1201 --> L1202["1202 Cryptographically destroy wrapped DEK"]
    L1202 --> L1203["1203 Record shred event in append-only ledger"]
    L1203 --> L1204["1204 Ciphertext rendered unrecoverable; storage-remanence caveat noted"]
    L1204 --> OUT["Erasure attested in audit evidence"]
MERMAID SOURCE - END

Table 12 : Complete description of Figure 12.

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | 1200 | Input right-to-erasure request identifying a protected object.
2 | 1201 | Location of the wrapped data-encryption key protecting the object.
3 | 1202 | Cryptographic destruction of the wrapped data-encryption key, there being no recovery path for the key.
4 | 1203 | Recording of the shred event in the append-only ledger.
5 | 1204 | Resulting unrecoverability of the ciphertext, subject to a disclosed storage-remanence caveat concerning multi-version concurrency, write-ahead logs, replicas and backups.

--------------------------------------------------------------------------------
FIGURE 13 - End-to-end sequence of a protect-and-attest request
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
sequenceDiagram
    participant U as Requesting principal
    participant G as RBAC gate (110)
    participant C as Classifier (102)
    participant R as Risk module (103)
    participant A as Agents+Consensus (104/105)
    participant P as Policy (106)
    participant K as Crypto (107)
    participant L as Ledger+Checkpoint (108/109)
    U->>G: Access request (101)
    G->>C: Admit; enforce role
    C->>R: Sensitivity tier
    R->>A: Context risk (server-derived)
    A->>P: Trust score (version-stamped)
    P->>K: Bound decision (rule_id or null)
    K->>L: Protected object (fail-closed profile)
    L-->>U: Verifiable evidence + PQ-signed checkpoint
MERMAID SOURCE - END

Table 13 : Complete description of Figure 13.

Sl.No | Participant | Description
------|-------------|-------------------------------------------------------------
1 | Requesting principal | The party submitting the access request (101).
2 | RBAC gate (110) | Server-side identity and role check admitting the request.
3 | Classifier (102) | Fail-safe sensitivity classification stage.
4 | Risk module (103) | Server-derived contextual risk stage.
5 | Agents+Consensus (104/105) | Parallel scoring agents and versioned consensus.
6 | Policy (106) | First-match deterministic override producing the bound decision.
7 | Crypto (107) | Fail-closed crypto-agile protection.
8 | Ledger+Checkpoint (108/109) | Append-only Merkle ledger and post-quantum-signed checkpoint returning verifiable evidence.

--------------------------------------------------------------------------------
FIGURE B01 - Performance: trust-band to cryptographic-profile mapping
--------------------------------------------------------------------------------

MERMAID SOURCE - BEGIN
flowchart LR
    T["B0100 Trust score axis 0.00 -> 1.00"]
    R1["B0101 Region trust <= 0.50"] --> P1["B0104 Post-quantum profile (ML-KEM-1024 + ML-DSA-87)"]
    R2["B0102 Region 0.50 < trust <= 0.85"] --> P2["B0105 Hybrid profile (X25519MLKEM768)"]
    R3["B0103 Region trust > 0.85"] --> P3["B0106 Symmetric profile (AES-256-GCM)"]
    T --- R1
    T --- R2
    T --- R3
    B["B0107 Boundary rule: a band edge resolves toward the stronger profile"]
    R1 -. edge 0.50 .- B
    R2 -. edge 0.85 .- B
MERMAID SOURCE - END

Table B01 : Complete description of Figure B01 (performance mapping).

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | B0100 | The trust-score axis over the unit interval against which the profile is selected.
2 | B0101 | The lower region, trust at or below 0.50, mapping to the fully post-quantum profile.
3 | B0102 | The middle region, trust above 0.50 and at or below 0.85, mapping to the hybrid profile.
4 | B0103 | The upper region, trust above 0.85, mapping to the symmetric authenticated-encryption profile.
5 | B0104 | The post-quantum profile selected in the lower region.
6 | B0105 | The hybrid classical-plus-post-quantum profile selected in the middle region.
7 | B0106 | The symmetric authenticated-encryption profile selected in the upper region.
8 | B0107 | The boundary rule under which a band edge resolves toward the more protective profile, governed by selector version identifier trust-crypto-policy-bands-1.0.0.

--------------------------------------------------------------------------------
FIGURE B02 - Performance: migration-ranking objective across methods
--------------------------------------------------------------------------------

The following chart plots, for an identical constraint set, the achieved
objective value (lower being better) of the three ranking methods. The plotted
magnitudes are representative of the observed ordering rather than a single fixed
measurement; the salient, reproduced result is that the quantum method is
competitive with or superior to both classical baselines on the evaluated
instances.

MERMAID SOURCE - BEGIN
xychart-beta
    title "B0200 Migration-ranking objective on an identical constraint set (lower is better)"
    x-axis ["B0201 QAOA (quantum)", "B0202 Simulated annealing", "B0203 Greedy"]
    y-axis "B0204 Normalized objective value" 0 --> 1
    bar [0.42, 0.55, 0.71]
MERMAID SOURCE - END

Table B02 : Complete description of Figure B02 (performance comparison).

Sl.No | Component Number | Description
------|------------------|-------------------------------------------------------
1 | B0200 | The migration-ranking objective evaluated on one identical constraint set across all three methods.
2 | B0201 | The quantum approximate optimization algorithm ranking, achieving the lowest (best) objective.
3 | B0202 | The simulated-annealing baseline over the identical constraint set.
4 | B0203 | The greedy baseline over the identical constraint set.
5 | B0204 | The normalized objective axis; representative values illustrate the observed ordering QAOA <= annealing <= greedy.

================================================================================
REFERENCES
================================================================================

The following non-patent literature and public standards are referenced as
background and as the published bases of the cryptographic and algorithmic
primitives employed in the described embodiments. No admission is made that any
listed item is prior art to the claimed combination.

[R1]  National Institute of Standards and Technology, FIPS 203, "Module-Lattice-
      Based Key-Encapsulation Mechanism Standard" (ML-KEM), 2024.

[R2]  National Institute of Standards and Technology, FIPS 204, "Module-Lattice-
      Based Digital Signature Standard" (ML-DSA), 2024.

[R3]  National Institute of Standards and Technology, FIPS 205, "Stateless Hash-
      Based Digital Signature Standard" (SLH-DSA), 2024.

[R4]  National Institute of Standards and Technology, SP 800-38D, "Recommendation
      for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC",
      2007.

[R5]  National Institute of Standards and Technology, FIPS 197, "Advanced
      Encryption Standard (AES)", 2001.

[R6]  A. Langley, E. Kasper and B. Laurie, RFC 6962, "Certificate Transparency",
      Internet Engineering Task Force, 2013.

[R7]  A. Langley, M. Hamburg and S. Turner, RFC 7748, "Elliptic Curves for
      Security" (Curve25519 / X25519), Internet Engineering Task Force, 2016.

[R8]  R. C. Merkle, "A Certified Digital Signature", Advances in Cryptology -
      CRYPTO '89, Lecture Notes in Computer Science, vol. 435, 1990.

[R9]  E. Farhi, J. Goldstone and S. Gutmann, "A Quantum Approximate Optimization
      Algorithm", arXiv:1411.4028, 2014.

[R10] S. Kirkpatrick, C. D. Gelatt and M. P. Vecchi, "Optimization by Simulated
      Annealing", Science, vol. 220, no. 4598, pp. 671-680, 1983.

[R11] Open Policy Agent project, "Policy Language (Rego)", Cloud Native Computing
      Foundation, documentation as published.

[R12] IETF, "Hybrid key exchange combining X25519 and ML-KEM-768"
      (X25519MLKEM768), draft as published.

[R13] Regulation (EU) 2016/679 of the European Parliament and of the Council
      (General Data Protection Regulation), 2016, Article 17 (right to erasure).

================================================================================
END OF COMPLETE SPECIFICATION
================================================================================
