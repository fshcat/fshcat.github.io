#!/usr/bin/env python3

import shutil
import json
import re
from pathlib import Path
from datetime import datetime

class IndexUpdater:
    def __init__(self, index_path='index.html'):
        self.index_path = Path(index_path)
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")
        
        # Directories to exclude from scanning
        self.exclude_dirs = {
            'styles', 'templates', 'scripts', 'markdown_sources', 
            'node_modules', '.git', 'pages', 'assets'
        }
    
    def scan_projects(self):
        """Scan directories for project metadata files."""
        projects = []
        
        # Find all directories in the current directory
        for item in Path('.').iterdir():
            if item.is_dir() and item.name not in self.exclude_dirs:
                metadata_file = item / '.metadata.json'
                
                # Check if this is a project directory (has metadata)
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        # Add URL based on directory name
                        projects.append({
                            'title': metadata['title'],
                            'url': f"{item.name}/",
                            'tags': metadata['tags'],
                            'date': metadata['date'],
                            'description': metadata.get('description', '')
                        })
                        
                        print(f"Found project: {item.name}")
                    except Exception as e:
                        print(f"Error reading {metadata_file}: {e}")
        
        # Sort by date (newest first)
        projects.sort(key=lambda x: x['date'], reverse=True)
        
        return projects
    
    def generate_projects_js(self, projects):
        """Generate the JavaScript array for projects."""
        js_lines = []
        
        for project in projects:
            js_lines.append("            {")
            js_lines.append(f'                title: "{project["title"]}",')
            js_lines.append(f'                url: "{project["url"]}",')
            js_lines.append(f'                tags: {json.dumps(project["tags"])},')
            js_lines.append(f'                date: "{project["date"]}"')
            js_lines.append("            },")
        
        # Remove trailing comma from last project
        if js_lines:
            js_lines[-1] = js_lines[-1].rstrip(',')
        
        return '\n'.join(js_lines)
    
    def update_index_html(self, projects):
        """Update the PROJECTS array in index.html."""
        with open(self.index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the PROJECTS array in the script
        # Match from "const PROJECTS = [" to "];"
        pattern = r'(const\s+PROJECTS\s*=\s*\[)(.*?)(\s*\];)'
        
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            print("Could not find PROJECTS array in index.html")
            print("Make sure your index.html contains: const PROJECTS = [ ... ];")
            return False
        
        # Generate new projects array content
        projects_js = self.generate_projects_js(projects)
        
        # Replace the old projects array with the new one
        if projects_js:
            new_projects_section = f"{match.group(1)}\n{projects_js}\n        {match.group(3)}"
        else:
            new_projects_section = f"{match.group(1)}\n            // No projects found\n        {match.group(3)}"
        
        # Replace in content
        new_content = content[:match.start()] + new_projects_section + content[match.end():]
        
        # Write updated content
        with open(self.index_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    
    def update_links(self):
        """Update any hardcoded project links to use new URL structure."""
        with open(self.index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update common link patterns
        replacements = [
            (r'href="pages/contact\.html"', 'href="contact/"'),
            (r'href="pages/(\w+)\.html"', r'href="\1/"'),
            (r'url:\s*"pages/(\w+)\.html"', r'url: "\1/"'),
        ]
        
        updated = False
        for pattern, replacement in replacements:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                updated = True
        
        if updated:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("Updated link URLs to new structure")
        
        return updated

def main():
    import argparse
    import shutil
    
    parser = argparse.ArgumentParser(
        description='Automatically update the main index.html with project data'
    )
    parser.add_argument('--index', default='index.html', 
                        help='Path to index.html (default: index.html)')
    
    args = parser.parse_args()
    
    print("Scanning for projects...")
    
    try:
        updater = IndexUpdater(index_path=args.index)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    # Scan for projects
    projects = updater.scan_projects()
    
    if not projects:
        print("No projects found!")
        print("Make sure to run convert.py first to generate project directories")
        return 1
    
    print(f"Found {len(projects)} project(s)")
    
    # Update index.html
    print("Updating index.html...")
    
    if updater.update_index_html(projects):
        print("Updated PROJECTS array")
    else:
        return 1
    
    # Update any old-style links
    updater.update_links()
    
    print(f"Successfully updated index.html with {len(projects)} project(s)")

    print("Projects in index:")
    for project in projects:
        tags = ', '.join(project['tags'])
        print(f"  {project['title']} ({project['url']}) - {tags}")

if __name__ == '__main__':
    import sys
    sys.exit(main())
