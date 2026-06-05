#!/usr/bin/env python3
"""
Rebuild All — Single-command regeneration of the entire RAG index layer.

Usage:
    python3 scripts/rebuild-all.py                    # Rebuild everything
    python3 scripts/rebuild-all.py --sprint "Sprint 14"  # Single sprint + indexes
    python3 scripts/rebuild-all.py --indexes-only      # Skip per-story, rebuild indexes only
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Script execution order (dependencies matter)
SCRIPTS = [
    {
        "name": "Split Sprint Stories",
        "script": "split-sprint-stories.py",
        "description": "Generate per-story markdown files from HTML",
        "required_for": "indexes",
        "estimated_time": "2-3 seconds"
    },
    {
        "name": "AC Index",
        "script": "create-ac-index.py",
        "description": "Generate Acceptance Criteria index",
        "estimated_time": "1-2 seconds"
    },
    {
        "name": "Solution Index",
        "script": "create-solution-index.py",
        "description": "Generate Solution index",
        "estimated_time": "1-2 seconds"
    },
    {
        "name": "Component Map",
        "script": "create-component-story-map.py",
        "description": "Generate component-to-story mappings",
        "estimated_time": "1-2 seconds"
    },
    {
        "name": "Feature Map",
        "script": "create-feature-epic-map.py",
        "description": "Generate feature/epic-to-story mappings",
        "estimated_time": "1-2 seconds"
    },
    {
        "name": "Dependency Graph",
        "script": "create-dependency-graph.py",
        "description": "Generate story dependency graph",
        "estimated_time": "<1 second"
    },
    {
        "name": "Traceability Index",
        "script": "create-traceability-index.py",
        "description": "Generate Copado traceability index",
        "estimated_time": "<1 second"
    },
    {
        "name": "Sprint Index",
        "script": "populate-sprint-index.py",
        "description": "Populate sprint overview quick-reference",
        "estimated_time": "<1 second"
    }
]

def run_script(script_info, sprint=None, force=False):
    """Run a single script and return success/failure."""
    script_path = Path("scripts") / script_info["script"]
    
    if not script_path.exists():
        print(f"  ⚠️  Warning: {script_path} not found, skipping")
        return True  # Don't fail the whole rebuild
    
    print(f"\n{'='*60}")
    print(f"Running: {script_info['name']}")
    print(f"Description: {script_info['description']}")
    print(f"Estimated time: {script_info['estimated_time']}")
    print(f"{'='*60}\n")
    
    cmd = [sys.executable, str(script_path)]
    
    # Add sprint-specific args for split-sprint-stories.py
    if script_info["script"] == "split-sprint-stories.py":
        if sprint:
            cmd.extend(["--sprint", sprint])
        if force:
            cmd.append("--force")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"\n✅ {script_info['name']} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {script_info['name']} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ {script_info['name']} failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Rebuild all RAG indexes with a single command"
    )
    parser.add_argument(
        "--sprint",
        help='Regenerate specific sprint only (e.g., "Sprint 14")'
    )
    parser.add_argument(
        "--indexes-only",
        action="store_true",
        help="Skip per-story generation, rebuild indexes only"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing per-story files"
    )
    
    args = parser.parse_args()
    
    print(f"\n{'#'*60}")
    print("# RAG Index Rebuild Tool")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")
    
    if args.sprint:
        print(f"Mode: Single sprint rebuild ({args.sprint})")
    elif args.indexes_only:
        print("Mode: Indexes only (skip per-story generation)")
    else:
        print("Mode: Full rebuild (all sprints + all indexes)")
    
    print()
    
    # Determine which scripts to run
    if args.indexes_only:
        scripts_to_run = [s for s in SCRIPTS if s["script"] != "split-sprint-stories.py"]
        print("Skipping per-story generation as requested.\n")
    else:
        scripts_to_run = SCRIPTS
    
    # Run scripts in order
    success_count = 0
    failure_count = 0
    
    for script in scripts_to_run:
        success = run_script(script, sprint=args.sprint, force=args.force)
        if success:
            success_count += 1
        else:
            failure_count += 1
            print(f"\n⚠️  Continuing despite failure in {script['name']}...\n")
    
    # Summary
    print(f"\n{'='*60}")
    print("REBUILD SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successful: {success_count}/{len(scripts_to_run)}")
    print(f"❌ Failed: {failure_count}/{len(scripts_to_run)}")
    
    if failure_count == 0:
        print("\n🎉 All scripts completed successfully!")
        print("\nRAG index layer is now up to date.")
        return 0
    else:
        print(f"\n⚠️  {failure_count} script(s) failed. Review output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
