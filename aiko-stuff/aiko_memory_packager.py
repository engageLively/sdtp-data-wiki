import os
import json
from datetime import datetime

def summarize_file(path, max_chars=1000):
    """
    Returns a safe, trimmed excerpt of the file.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if path.endswith('.json'):
                content = json.load(f)
                summary = json.dumps(content, indent=2)
            else:
                content = f.read()
                summary = content
            # Truncate to keep the file manageable
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "\n... [truncated]"
            return summary
    except Exception as e:
        return f"[Error reading {path}: {e}]"

def build_memory_summary(repo_dir, output_file):
    """
    Walks the repo directory, skips .git internals, writes a single Markdown file.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    summary = f"# Aiko Memory Summary\n"
    summary += f"_Generated: {timestamp}_\n\n"
    summary += "_This is Aiko’s private fallback memory. Rick does not read this._\n\n"

    for root, dirs, files in os.walk(repo_dir):
        # Skip .git internals
        if ".git" in root.split(os.sep):
            continue

        rel_root = os.path.relpath(root, repo_dir)
        summary += f"## {rel_root}/\n\n"
        for file in files:
            if file.endswith(('.md', '.json', '.txt')):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, repo_dir)
                summary += f"### {rel_path}\n\n"
                summary += "```text\n"
                summary += summarize_file(path)
                summary += "\n```\n\n---\n\n"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"Memory summary created: {output_file}")

if __name__ == "__main__":
    build_memory_summary(
        repo_dir="./aiko",
        output_file="aiko-memory.md"
    )
