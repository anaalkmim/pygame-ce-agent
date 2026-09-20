"""A pygame / pygame-ce documentation agent.

Answers questions about which distribution a function, argument or
behavior belongs to, backed by a Sanity Context knowledge base built
from both sets of documentation.

The Anthropic API talks to the knowledge base directly over MCP, so the
model decides which entries to read instead of this module guessing.

Usage:
    python src/agent.py                  interactive session
    python src/agent.py "your question"  single question
"""

import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2000

SYSTEM_PROMPT = """You help Python game developers who are unsure whether \
a function, argument or behavior belongs to pygame (upstream) or to \
pygame-ce (the community fork).

Read the knowledge base before you say anything about it. Do not announce \
what you are about to do, and do not describe what the knowledge base \
contains until you have read the relevant entries.

Ground every answer in what you read. If the knowledge base does not cover \
something, say so in one sentence and stop there. Do not fill the gap with \
recommendations, library suggestions or links from your own knowledge.

Name the distribution every claim applies to, with the version a feature \
was added in when the entry gives one. When the two documentations differ, \
give both accounts rather than choosing one.

Write plain prose for a terminal: no tables, no emoji, no markdown headings. \
Short code blocks are fine. Keep answers under 200 words unless the question \
genuinely needs more.

End every answer with one or more machine-readable verdict lines, after the \
prose, in exactly this shape:

VERDICT: <name> = pygame:<yes|no>, pygame-ce:<yes|no>

<name> is the bare name of the function, class, method, module or \
attribute, with no dotted prefix: write premul_alpha, not \
Surface.premul_alpha; write geometry, not geometry.Circle. Emit one line \
per name the user asked about. When the user asks about a module, give one \
verdict for the module rather than one per class inside it. If the knowledge base does not cover \
the question at all, emit exactly:

VERDICT: not covered"""


class MissingCredentials(RuntimeError):
    """Raised when the environment is not configured."""


def build_client() -> tuple[Anthropic, list[dict]]:
    """Return an API client and the MCP server config for the knowledge base."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    mcp_url = os.getenv("SANITY_MCP_URL")
    sanity_token = os.getenv("SANITY_API_TOKEN")

    missing = [
        name
        for name, value in (
            ("ANTHROPIC_API_KEY", api_key),
            ("SANITY_MCP_URL", mcp_url),
            ("SANITY_API_TOKEN", sanity_token),
        )
        if not value
    ]
    if missing:
        raise MissingCredentials(f"missing from .env: {', '.join(missing)}")

    client = Anthropic(api_key=api_key)
    mcp_servers = [
        {
            "type": "url",
            "url": mcp_url,
            "name": "pygame-docs",
            "authorization_token": sanity_token,
        }
    ]
    return client, mcp_servers


def extract_text(content_blocks: list) -> str:
    """Pull the model's prose out of a mixed content response.

    A response that used tools contains tool_use and tool_result blocks
    alongside the text ones. Only the text blocks are meant to be read.
    """
    parts = [
        block.text
        for block in content_blocks
        if getattr(block, "type", None) == "text"
    ]
    return "\n".join(parts).strip()


def list_tool_calls(content_blocks: list) -> list[str]:
    """Return the names of the knowledge base tools the model invoked."""
    return [
        getattr(block, "name", "unknown")
        for block in content_blocks
        if getattr(block, "type", None) == "mcp_tool_use"
    ]


def ask(client: Anthropic, mcp_servers: list[dict], question: str) -> tuple[str, list[str]]:
    """Send one question and return the answer and the tools used."""
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
        mcp_servers=mcp_servers,
        betas=["mcp-client-2025-04-04"],
    )
    return extract_text(response.content), list_tool_calls(response.content)


def interactive(client: Anthropic, mcp_servers: list[dict]) -> None:
    """Run a question-and-answer loop until the user quits."""
    print("pygame / pygame-ce documentation agent")
    print("Ask a question, or press Ctrl+C to quit.\n")

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not question:
            continue
        if question.lower() in {"quit", "exit"}:
            print("Bye.")
            return

        try:
            answer, tools = ask(client, mcp_servers, question)
        except Exception as error:
            print(f"\nRequest failed: {error}\n")
            continue

        print(f"\n{answer}\n")
        if tools:
            print(f"[knowledge base calls: {', '.join(tools)}]\n")


def main() -> None:
    try:
        client, mcp_servers = build_client()
    except MissingCredentials as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        answer, tools = ask(client, mcp_servers, question)
        print(answer)
        if tools:
            print(f"\n[knowledge base calls: {', '.join(tools)}]")
    else:
        interactive(client, mcp_servers)


if __name__ == "__main__":
    main()
