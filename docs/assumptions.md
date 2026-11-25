# Assumptions

Open assumptions behind the retrospective ADRs in `docs/adr/` (inferred 2026-11-25 at c41074a674fd5876fbdc0c6387bb980dac251cd6).

| ID | Assumption | Why needed | Evidence / source file | How to verify | Confidence | Status |
|----|------------|-----------|------------------------|---------------|------------|--------|
| A-001 | The move from in-process MLX models to a remote OMLX server was motivated by keeping the client light and OS-agnostic. | ADR 0001 context | Commit ab32516 title; README/CLAUDE.md wording (earlier code not read in diff form) | Read `git show ab32516` and ask Nic | medium | open |
| A-002 | langchain-core was kept only for message types, probably a leftover from an earlier LangChain-based design. | ADR 0002 | core/agent.py imports; requirements.txt | Check history before ab32516; ask Nic | low | open |
| A-003 | The code in tts/engine.py (`instructions` via extra_body plus `voice`) is authoritative; docstrings in tts/engine.py, config/settings.py and README saying description goes in `voice` only are stale. | ADR 0003 | tts/engine.py lines 97-112 vs module/TTSConfig docstrings | Test against the oMLX version in use | high | open |
| A-004 | The trust knob not having a directive tier is unintentional or deliberately only cosmetic. | ADR 0005 | config/settings.py to_prompt_block loops humor/honesty/discretion; prompts.yaml has no trust scale | Ask Nic; check behaviour with trust 0 vs 100 | medium | open |
| A-005 | TARS prompt lives in YAML while crew prompts live in code for historical/editing-convenience reasons. | ADR 0006 | prompts.yaml header vs core/characters.py | Ask Nic | low | open |
| A-006 | Sending `chat_template_kwargs.enable_thinking` to non-Qwen models (default MiniMax) is harmless on OMLX. | ADR 0015 | core/agent.py OMLXLLM.generate | Run default model with OMLX and inspect request handling | medium | open |
| A-007 | K=20, 256 guest tokens, and 20-char silence buffer are tuned heuristics chosen by experience, not derived values. | ADRs 0007, 0008, 0010 | config/settings.py; core/orchestrator.py | Ask Nic or review tuning notes | low | open |
| A-008 | The default LLM differs between code (MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX) and setup_and_run.sh (Qwen3.6-27B-bf16); code default is the intended one. | ADR 0016 | main.py, config/settings.py, setup_and_run.sh OMLX_MODEL default | Ask Nic which default is intended | medium | open |
| A-009 | Exact version pins in requirements.txt (e.g. openai==3.45.0, numpy==2.5.4, pytest==9.2.0) resolve on PyPI and match what runs on Nic's machine. | ADR 0017 | requirements.txt; commit b167b83 message says pinned to running versions | Run `pip install -r requirements.txt` in a clean env and the test suite | medium | open |
| A-010 | Wordmark "MLX Native" and argparse description "MLX Native" are leftover text, not a claim that inference is local in-process. | ADR 0018 | ui.py _WORDMARK; main.py parse_args | Ask Nic | medium | open |
| A-011 | The README claim of 59 unit tests is current. | ADR 0019 | README.md Tests section | Run `pytest --collect-only -q` | medium | open |
| A-012 | The default API key `test` and plain-http URLs are acceptable because OMLX runs on a trusted local network. | ADR 0016 | config/settings.py OMLXConfig; README | Confirm OMLX auth setup | medium | open |
| A-013 | README line "TTS model downloads on first launch" is stale since nothing downloads to the client. | ADR 0001 | README.md Quick Start step 3 vs CLAUDE.md/README intro | Edit README after confirming | high | open |
| A-014 | Mixed path bases (conversations/ repo-relative, audio_output relative to cwd) are accidental rather than a design choice. | ADRs 0013, 0014 | core/persistence.py CONVERSATIONS_DIR; config/settings.py audio_output_dir | Run from another cwd and observe | medium | open |
| A-015 | CLAUDE.md is kept as repo guidance for Claude Code and is the project's agent-context file. | not an ADR; repo hygiene | CLAUDE.md; user memory says Claude is being decommissioned | Ask Pedro whether to keep, rename (e.g. AGENTS.md) or remove | low | open |
| A-016 | images/1.png (176760 bytes) is only the README hero image; its content was not inspected. | documentation | README.md `<img src="images/1.png">` | Open the image | high | open |
