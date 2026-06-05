#!/usr/bin/env python3
"""
Populate SPRINT-INDEX.md with story counts and basic sprint information.

This script scans all sprint folders and updates the Sprint Overview table
in knowledge/sprints/SPRINT-INDEX.md with actual story counts.
"""

from pathlib import Path
from datetime import datetime

def main():
    print("Populating Sprint Index...")
    
    # Base paths
    base_path = Path("knowledge/sprints")
    index_path = base_path / "SPRINT-INDEX.md"
    
    if not base_path.exists():
        print(f"Error: {base_path} not found")
        return
    
    # Find all sprint directories
    sprint_dirs = sorted([d for d in base_path.iterdir() if d.is_dir() and "Sprint" in d.name])
    
    # Count stories in each sprint
    sprint_data = []
    total_stories = 0
    
    for sprint_dir in sprint_dirs:
        sprint_name = sprint_dir.name
        stories_dir = sprint_dir / "stories"
        
        if stories_dir.exists():
            story_files = list(stories_dir.glob("*.md"))
            story_count = len(story_files)
            total_stories += story_count
            
            # Find HTML file
            html_files = list(sprint_dir.glob("*.html"))
            html_name = html_files[0].name if html_files else "Missing"
            
            sprint_data.append({
                "name": sprint_name,
                "html": html_name,
                "count": story_count
            })
            
            print(f"  {sprint_name}: {story_count} stories")
        else:
            print(f"  {sprint_name}: No stories directory")
    
    # Generate the Sprint Overview table
    today = datetime.now().strftime("%b %d, %Y")
    
    table_lines = [
        "| Sprint | File | Stories | Status Last Updated |",
        "|--------|------|---------|-------------------|"
    ]
    
    for sprint in sprint_data:
        table_lines.append(
            f"| {sprint['name']} | {sprint['html']} | {sprint['count']} | {today} |"
        )
    
    # Read existing index
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and replace the Sprint Overview section
        start_marker = "## 📊 Sprint Overview"
        end_marker = "---"
        
        start_idx = content.find(start_marker)
        if start_idx == -1:
            print("Error: Could not find Sprint Overview section")
            return
        
        # Find the end of the table (next --- after the table)
        table_start = content.find("|-----", start_idx)
        if table_start == -1:
            print("Error: Could not find table in Sprint Overview")
            return
        
        # Find the next section marker after the table
        end_idx = content.find("
---
", table_start)
        if end_idx == -1:
            print("Error: Could not find end of Sprint Overview section")
            return
        
        # Replace the table
        new_content = (
            content[:start_idx] +
            start_marker + "

" +
            "
".join(table_lines) + "

" +
            content[end_idx:]
        )
        
        # Write back
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"
✅ Sprint Index updated: {index_path}")
        print(f"   Total sprints: {len(sprint_data)}")
        print(f"   Total stories: {total_stories}")
    else:
        print(f"Error: Index file not found: {index_path}")

if __name__ == "__main__":
    main()
