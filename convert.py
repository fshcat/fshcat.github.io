#!/usr/bin/env python3

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import yaml
import markdown
try:
    import obsidian_callouts  # Python-Markdown plugin for Obsidian callouts
    _HAS_OBSIDIAN_CALLOUTS = True
except Exception:  # ImportError or any runtime issue
    _HAS_OBSIDIAN_CALLOUTS = False

from markdown.extensions import toc
import html
import json

class MarkdownConverter:
    def __init__(self, template_path='templates/base.html'):
        self.template_path = Path(template_path)
        
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        
        self.callout_types = {
            'note': '[!]',
            'abstract': '[*]',
            'summary': '[*]',
            'tldr': '[*]',
            'info': '[i]',
            'todo': '[ ]',
            'tip': '[T]',
            'hint': '[T]',
            'important': '[!]',
            'success': '[+]',
            'check': '[+]',
            'done': '[+]',
            'question': '[?]',
            'help': '[?]',
            'faq': '[?]',
            'warning': '[W]',
            'caution': '[W]',
            'attention': '[W]',
            'failure': '[-]',
            'fail': '[-]',
            'missing': '[-]',
            'danger': '[!]',
            'error': '[!]',
            'bug': '[B]',
            'example': '[E]',
            'quote': '[Q]',
            'cite': '[Q]'
        }
    
    def parse_markdown_file(self, filepath):
        """Parse markdown file with YAML frontmatter."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML frontmatter
        yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
        
        if not yaml_match:
            raise ValueError(f"No YAML frontmatter found in {filepath}")
        
        frontmatter = yaml.safe_load(yaml_match.group(1))
        markdown_content = yaml_match.group(2)
        
        # Validate required fields
        required_fields = ['title', 'url_name', 'tags', 'date']
        for field in required_fields:
            if field not in frontmatter:
                raise ValueError(f"Missing required field '{field}' in frontmatter of {filepath}")
        
        return frontmatter, markdown_content
    
    def process_custom_images(self, content, assets_dir, output_dir):
        """Convert ![[filename]] or ![[filename|width]] syntax to HTML img tags and copy images."""
        def replace_image(match):
            # Parse filename and optional width
            parts = match.group(1).split('|')
            filename = parts[0].strip()
            width = parts[1].strip() if len(parts) > 1 else None
            
            src_path = Path(assets_dir) / filename
            if src_path.exists():
                dest_dir = output_dir / 'assets'
                dest_dir.mkdir(exist_ok=True)
                dest_path = dest_dir / filename
                shutil.copy2(src_path, dest_path)
                
                # Generate HTML with inline style for specific sizing
                if width:
                    # Use inline style for explicit width - ensures it's respected
                    return f'<img src="assets/{filename}" alt="{filename}" style="width: {width}px; max-width: 100%; height: auto;">'
                else:
                    # Use standard markdown for default sizing
                    return f'![{filename}](assets/{filename})'
            else:
                print(f"  ⚠ Warning: Image not found: {src_path}")
                if width:
                    return f'<img src="assets/{filename}" alt="{filename}" style="width: {width}px; max-width: 100%; height: auto;">'
                else:
                    return f'![{filename}](assets/{filename})'
        
        # Updated regex to capture optional width parameter
        content = re.sub(r'!\[\[(.+?)\]\]', replace_image, content)
        return content
    
    def slugify_header(self, text, separator='-'):
        """Convert header text to a slug for use as an ID."""
        # Convert to lowercase and replace spaces with separator
        slug = text.lower().replace(' ', separator).replace('/', separator)
        # Remove any characters that aren't alphanumeric or hyphens
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        return slug
    
    def process_internal_links(self, content):
        """Convert [[#Section Name]] to proper anchor links."""
        def replace_link(match):
            section_name = match.group(1).strip()
            # Use the same slugify logic as TOC generation
            slug = self.slugify_header(section_name)
            return f'[{section_name}](#{slug})'
        
        # Match [[#Section Name]] pattern
        content = re.sub(r'\[\[#(.+?)\]\]', replace_link, content)
        return content
    
    def process_callouts(self, content):
        """Convert Obsidian-style callouts to HTML."""
        lines = content.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this line starts a callout
            # Match > [!type] or > [!type]- with optional title
            callout_pattern = r'^>\s*\[!(\w+)\](-?)(?:\s+(.+))?$'
            callout_match = re.match(callout_pattern, line)
            
            if callout_match:
                callout_type = callout_match.group(1).lower()
                is_collapsible = callout_match.group(2) == '-'
                title = callout_match.group(3) or callout_type.title()
                
                # Get icon for callout type
                icon = self.callout_types.get(callout_type, '📌')
                
                # Collect all subsequent lines that start with >
                content_lines = []
                i += 1
                while i < len(lines) and lines[i].startswith('>'):
                    # Remove the > prefix (and optional space)
                    content_line = lines[i][1:]
                    if content_line.startswith(' '):
                        content_line = content_line[1:]
                    content_lines.append(content_line)
                    i += 1
                
                # Join the content and convert from markdown to HTML
                callout_content = '\n'.join(content_lines)
                # Process the callout content as markdown
                md = markdown.Markdown(extensions=['fenced_code', 'nl2br', 'smarty'])
                callout_html = md.convert(callout_content)
                
                # Build HTML based on whether it's collapsible
                if is_collapsible:
                    html_output = f'<details class="callout callout-{callout_type}">'
                    html_output += f'\n<summary class="callout-header">'
                    html_output += f'\n<span class="callout-icon">{icon}</span>'
                    html_output += f'\n<span class="callout-title">{html.escape(title)}</span>'
                    html_output += f'\n<span class="callout-fold">▶</span>'
                    html_output += f'\n</summary>'
                    html_output += f'\n<div class="callout-content">'
                    html_output += f'\n{callout_html}'
                    html_output += f'\n</div>'
                    html_output += f'\n</details>'
                else:
                    html_output = f'<div class="callout callout-{callout_type}">'
                    html_output += f'\n<div class="callout-header">'
                    html_output += f'\n<span class="callout-icon">{icon}</span>'
                    html_output += f'\n<span class="callout-title">{html.escape(title)}</span>'
                    html_output += f'\n</div>'
                    html_output += f'\n<div class="callout-content">'
                    html_output += f'\n{callout_html}'
                    html_output += f'\n</div>'
                    html_output += f'\n</div>'
                
                result.append(html_output)
                # i is already incremented past the callout
            else:
                result.append(line)
                i += 1
        
        return '\n'.join(result)
    
    def generate_toc(self, html_content, title="Table of Contents"):
        """Extract headers and generate a table of contents."""
        # Find all headers (h1-h3) in the HTML
        header_pattern = r'<h([1-3])[^>]*(?:\s+id="([^"]+)")?[^>]*>(.*?)</h[1-3]>'
        headers = re.findall(header_pattern, html_content)

        if not headers:
            return ''  # Return empty string instead of None for cleaner template handling

        toc_html = f'<nav class="toc">\n<h2 class="toc-title"><a href="#top">{html.escape(title)}</a></h2>\n<ul class="toc-list">\n'
        
        current_level = 0
        for level, header_id, header_text in headers:
            level = int(level)
            # Clean up header text (remove any HTML tags)
            clean_text = re.sub(r'<[^>]+>', '', header_text)
            
            # Generate ID if not present (though TOC extension should have added them)
            if not header_id:
                header_id = self.slugify_header(clean_text)
            
            # Adjust nesting
            if level > current_level:
                toc_html += '<ul>\n' * (level - current_level)
            elif level < current_level:
                toc_html += '</ul>\n' * (current_level - level)
            
            current_level = level
            
            # Add list item
            toc_html += f'<li><a href="#{header_id}">{clean_text}</a></li>\n'
        
        # Close any remaining open lists
        toc_html += '</ul>\n' * current_level
        toc_html += '</ul>\n</nav>\n'
        
        return toc_html
    
    def convert_markdown_to_html(self, markdown_content):
        """Convert markdown to HTML with extensions."""
        # Configure markdown with TOC extension
        extensions = [
            'fenced_code',
            'codehilite',
            'tables',
            'toc',
            'nl2br',
            'sane_lists',
            'smarty',
            'attr_list',
            'def_list',
            'footnotes',
        ]
        if _HAS_OBSIDIAN_CALLOUTS:
            extensions.append('obsidian_callouts')
        md = markdown.Markdown(extensions=extensions, extension_configs={
            'toc': {
                'permalink': False,  # Don't add permalink markers
                'slugify': self.slugify_header
            }
        })
        html_content = md.convert(markdown_content)
        return html_content
        return html_content
    
    def render_template(self, template_content, metadata, html_content):
        """Simple template rendering with variable substitution."""
        try:
            date_obj = datetime.strptime(metadata['date'], '%Y-%m-%d')
            formatted_date = date_obj.strftime('%B %d, %Y')
        except:
            formatted_date = metadata['date']
        
        tags_html = '\n'.join([f'<span class="tag">{tag}</span>' for tag in metadata['tags']])
        tags_string = ', '.join(metadata['tags'])
        
        # Generate table of contents
        toc_html = self.generate_toc(html_content, metadata.get('title', 'Untitled'))
        
        replacements = {
            '{{ title }}': metadata.get('title', 'Untitled'),
            '{{ description }}': metadata.get('description', ''),
            '{{ tags_string }}': tags_string,
            '{{ tags_html }}': tags_html,
            '{{ formatted_date }}': formatted_date,
            '{{ toc }}': toc_html,  # Empty string if no headers
            '{{ content }}': html_content
        }
        
        result = template_content
        for key, value in replacements.items():
            result = result.replace(key, str(value))
        
        return result
    
    def convert_file(self, markdown_path, assets_dir=None):
        """Convert a single markdown file to HTML in its own directory."""
        markdown_path = Path(markdown_path)
        assets_dir = Path(assets_dir) if assets_dir else markdown_path.parent
        
        print(f"Processing: {markdown_path}")
        
        # Parse markdown file
        metadata, markdown_content = self.parse_markdown_file(markdown_path)
        
        # Create output directory based on url_name
        output_dir = Path(metadata['url_name'])
        output_dir.mkdir(exist_ok=True)
        
        # Save metadata for the index updater
        metadata_path = output_dir / '.metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump({
                'title': metadata.get('title'),
                'tags': metadata.get('tags', []),
                'date': metadata.get('date'),
                'description': metadata.get('description', '')
            }, f, indent=2)
        
        # Process custom syntax in order
        markdown_content = self.process_custom_images(markdown_content, assets_dir, output_dir)
        markdown_content = self.process_internal_links(markdown_content)
        if not _HAS_OBSIDIAN_CALLOUTS:
            markdown_content = self.process_callouts(markdown_content)
        
        # Convert markdown to HTML
        html_content = self.convert_markdown_to_html(markdown_content)
        
        # Read template and render
        with open(self.template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        final_html = self.render_template(template_content, metadata, html_content)
        
        # Save as index.html
        output_path = output_dir / 'index.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        print(f"Created: {output_path}")
        if (output_dir / 'assets').exists():
            image_count = len(list((output_dir / 'assets').glob('*')))
            if image_count > 0:
                print(f"Copied {image_count} image(s) to {output_dir}/assets/")
        
        return metadata['url_name']

def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown to HTML for portfolio site',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Convert a single file:
    python convert.py markdown_sources/ecommerce.md --assets-dir markdown_sources/images

  Convert all markdown files in a directory:
    python convert.py markdown_sources/ --batch --assets-dir markdown_sources/images

Features:
  • Obsidian-style callouts: > [!note] Title
  • Collapsible callouts: > [!warning]- Collapsible Title
  • Internal links: [[#Section Name]]
  • Custom images: ![[image.png]] or ![[image.png|500]]
  • Automatic table of contents generation

After converting, run update_index.py to update the main page.
        """
    )
    
    parser.add_argument('markdown_file', 
                        help='Path to markdown file or directory (with --batch)')
    parser.add_argument('--assets-dir', 
                        help='Path to directory containing image assets')
    parser.add_argument('--batch', 
                        action='store_true', 
                        help='Process all .md files in a directory')
    parser.add_argument('--template', 
                        default='templates/base.html',
                        help='Path to HTML template')
    
    args = parser.parse_args()
    
    try:
        converter = MarkdownConverter(template_path=args.template)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    converted_projects = []
    
    if args.batch:
        md_dir = Path(args.markdown_file)
        if not md_dir.is_dir():
            print(f"Error: {md_dir} is not a directory")
            sys.exit(1)
        
        md_files = list(md_dir.glob('*.md'))
        if not md_files:
            print(f"No .md files found in {md_dir}")
            sys.exit(1)
        
        print(f"Found {len(md_files)} markdown file(s) to process")
        
        for md_file in md_files:
            try:
                url_name = converter.convert_file(md_file, args.assets_dir or md_dir)
                converted_projects.append(url_name)
            except Exception as e:
                print(f"Error processing {md_file}: {e}")
    else:
        try:
            url_name = converter.convert_file(args.markdown_file, args.assets_dir)
            converted_projects.append(url_name)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    if converted_projects:
        print(f"Successfully converted {len(converted_projects)} project(s)")
        print("Run 'python update_index.py' to update the main page")

if __name__ == '__main__':
    main()
