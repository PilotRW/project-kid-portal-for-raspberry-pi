import json
import sys
from pathlib import Path


FILTER_FIELDS = [
    "allowed_keywords",
    "approval_keywords",
    "blocked_channels",
    "blocked_categories",
    "blocked_keywords",
]

REMOVED_DEFAULT_SITE_DOMAINS = {
    "wikipedia.org",
    "khanacademy.org",
}

MANAGED_DEFAULT_SITE_DOMAINS = {
    "kids.orf.at",
    "on.orf.at",
}

APPROVAL_NOT_BLOCKED = {
    "minecraft",
    "roblox",
    "among us",
    "fortnite",
}


def append_unique(target: list[str], values: list[str]) -> None:
    seen = {str(item).casefold() for item in target}
    for value in values:
        key = str(value).casefold()
        if key not in seen:
            target.append(value)
            seen.add(key)


def merge_allowed_sites(default_config: dict, target_config: dict) -> None:
    default_sites = {
        site.get("domain"): site
        for site in default_config.get("allowed_sites", [])
        if site.get("domain") in MANAGED_DEFAULT_SITE_DOMAINS
    }
    target_sites = [
        site for site in target_config.get("allowed_sites", [])
        if site.get("domain") not in REMOVED_DEFAULT_SITE_DOMAINS
    ]
    existing = {site.get("domain") for site in target_sites}
    target_sites.extend(site for domain, site in default_sites.items() if domain not in existing)
    target_config["allowed_sites"] = target_sites


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: merge_filter_rules.py DEFAULT_CONFIG TARGET_CONFIG", file=sys.stderr)
        return 2

    default_config = json.loads(Path(sys.argv[1]).read_text())
    target_path = Path(sys.argv[2])
    target_config = json.loads(target_path.read_text())

    merge_allowed_sites(default_config, target_config)

    defaults = default_config.get("filtering", {})
    target = target_config.setdefault("filtering", {})

    for field in FILTER_FIELDS:
        target.setdefault(field, [])
        append_unique(target[field], defaults.get(field, []))

    target["blocked_keywords"] = [
        value for value in target.get("blocked_keywords", [])
        if str(value).casefold() not in APPROVAL_NOT_BLOCKED
    ]
    append_unique(target.setdefault("approval_keywords", []), sorted(APPROVAL_NOT_BLOCKED))

    target_path.write_text(json.dumps(target_config, ensure_ascii=False, indent=2) + "\n")
    print(
        "merged",
        "blocked_keywords",
        len(target.get("blocked_keywords", [])),
        "approval_keywords",
        len(target.get("approval_keywords", [])),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
