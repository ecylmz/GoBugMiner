# Installation

```bash
git clone https://github.com/ecylmz/GoBugMiner
cd GoBugMiner
uv sync --all-groups
uv run gobugminer version
```

Python 3.11+, Git, and `uv` are required. Live operation additionally requires
the GitHub CLI and `gh auth login`. Linux and macOS are supported. Windows is
not claimed because it has not been tested.
