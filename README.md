# pygame-ce-agent

A documentation agent that knows which pygame you are actually using.

`pygame` and `pygame-ce` are two separate distributions that install under
the same `pygame` namespace and cannot coexist in one environment. They share
most of their API, maintain two separate documentation sites, and have
drifted apart: each has functions, classes and modules the other does not.

A tutorial, a Stack Overflow answer or an AI-generated snippet rarely says
which one it was written for. When the call fails, the error message is a
bare `AttributeError` that gives no hint that the distribution is the
problem.

This agent answers questions about both at once. It never blends them: every
claim names the distribution it belongs to, with the version the feature
was added in, and the entry it came from.

## How it works

The knowledge base is built with [Sanity Context](https://www.sanity.io/),
which crawls both documentation sites and writes short, cited entries an
agent can navigate. Two sources feed it:

| Source | Pages indexed |
| --- | --- |
| `https://www.pygame.org/docs/ref/` | 42 |
| `https://pyga.me/docs/ref` | 42 |

Only the API reference is indexed. The tutorials are largely inherited from
the fork and near-identical in both, so indexing them would spend the
document budget on duplicates while adding no points of disagreement.

Context serves the result over an MCP endpoint. The Anthropic API talks to
that endpoint directly, so the model decides which entries to read instead
of this repository guessing in advance. There is no retrieval code here:
the agent is a system prompt, an endpoint and a scorer.

The endpoint carries its own instructions, which is what keeps the two
distributions apart at the source rather than only in the client.

## Example

```
$ python src/agent.py "Is Surface.premul_alpha_ip() available in upstream pygame?"

`Surface.premul_alpha_ip()` is documented explicitly as a **pygame-ce only** method. It performs the premultiplied-alpha multiplication in-place and returns `None`. It is not present in upstream pygame (v2.6.0), which only has `premul_alpha()`, which returns a new copy of the surface.

VERDICT: premul_alpha_ip = pygame:no, pygame-ce:yes

[knowledge base calls: initial_context, knowledge_base_read]
```

The `VERDICT:` lines are not decoration. They are what the evaluation
reads, and the reason it can score an answer without guessing at prose.
## Evaluation

The agent was never the hard part. Measuring it was.

The evaluation set holds seven questions whose answers were checked against
the upstream documentation, the pygame-ce documentation and the pygame-ce
release notes before being written down. Each question runs three times,
because the same question was observed to produce different claims on
different runs. A case counts as reliable only if all three runs pass, and
an answer that reached no knowledge base tool fails regardless of content.

### First scorer: substring matching

The first version declared, per case, phrases a correct answer must contain
and phrases that signal a wrong claim. It scored 4/7.

Reading the seven failures showed that all seven answers were correct and
the scorer was wrong, for two reasons:

- **Negation.** The pattern `available in pygame` matched the answer
  "premul_alpha_ip is **not** available in pygame" — the correct answer.
- **Scope.** The pattern `pygame-ce only` matched an answer about
  `premul_alpha` because it ended with a true aside about
  `premul_alpha_ip` being pygame-ce only. Substring matching cannot tell
  which claim a phrase belongs to.

### Second scorer: verdict lines

Prose is not scoreable, so the agent stopped being scored on prose. It now
ends every answer with machine-readable lines:

VERDICT: premul_alpha = pygame:yes, pygame-ce:yes
VERDICT: premul_alpha_ip = pygame:no, pygame-ce:yes


Scoring compares those lines and ignores everything above them. Negation
disappears, because there is nothing to negate. Scope disappears, because
each claim carries its own name.

This scored 3/7 — worse. Reading the failures again: the model wrote
`Surface.premul_alpha` where the case expected `premul_alpha`, and the
parser only stripped a `pygame.` prefix. Every failing verdict was correct
on the facts.

Stripping any dotted prefix, and telling the model to answer about a module
rather than each class inside it, took the same saved answers to 6/7 without
a single new API call. A fresh run then scored 7/7, stable.

### What the numbers actually say

| Run | Score | What it measured |
| --- | --- | --- |
| v1, substring | 4/7 | the scorer's handling of negation and scope |
| v2, verdict lines | 3/7 | the parser's handling of dotted prefixes |
| v2, parser fixed | 7/7 | the agent |

Twenty of the twenty-one answers in the second run were right before any
scorer was fixed. The one miss answered about `geometry.Circle` and
`geometry.Line` when the question was about the `geometry` module — the
right facts at the wrong granularity.

Both earlier runs are kept in `outputs/` rather than deleted. An evaluation
that is never itself validated produces a number that looks precise and
measures the wrong thing.

### Honest limits

Seven cases is a small set, and the cases were chosen by someone who already
knew the answers. 7/7 means the agent did not fail what it was tested on. It
does not mean it is reliable on questions nobody thought to ask. Verdict
lines also only capture presence and absence — a signature that differs
between the distributions has no verdict shape yet.

## Setup

```bash
git clone https://github.com/anaalkmim/pygame-ce-agent.git
cd pygame-ce-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with three values:

| Variable | Where it comes from |
| --- | --- |
| `SANITY_MCP_URL` | the MCP endpoint in the Sanity Context dashboard |
| `SANITY_API_TOKEN` | an organization token with Context Viewer permission |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

The Sanity token must be an **organization** token. A project token will not
reach Context.

Confirm the endpoint answers before spending anything on the model:

```bash
python scripts/check_connection.py
```

Then ask a question, or start a session with no argument:

```bash
python src/agent.py "Can I open two windows at once?"
python src/agent.py
```

## Tests and evaluation

The unit tests are offline. They need no key, no network and cost nothing:

```bash
pytest
```

The evaluation makes real API calls and costs real money — seven cases,
three runs each:

```bash
python scripts/run_eval.py        # 3 runs per case
python scripts/run_eval.py 5      # more runs, more confidence, more cost
```

Answers are written to `outputs/eval_results.json` in full, so a score can
always be traced back to the text that produced it.

## Layout

data/eval_cases.json questions and their verified verdicts
src/agent.py system prompt and the API call
src/scoring.py verdict parsing and scoring, no network
scripts/check_connection.py endpoint diagnostic
scripts/run_eval.py the live evaluation
tests/ offline unit tests
outputs/ evaluation runs, kept for comparison


## Sanity project

Project ID: `pdm0xx31` · Knowledge base: `kbJl4b52PrF6`
