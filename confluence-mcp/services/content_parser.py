# Content parsing logic to convert markdown to confluence storage format (e.g XHTML)
import re
from typing import Union, Dict
from pathlib import Path
from fastmcp import Context

async def markdown_to_confluence_xhtml(markdown_path: str, ctx: Context = None) -> Union[str, Dict]:
    """
    Converts a Markdown performance report to Confluence storage-format XHTML.
    
    Args:
        markdown_path: File path to the markdown report.
        ctx: FastMCP context for logging.
    
    Returns:
        str: Confluence-compatible XHTML markup, or error dict if conversion fails.
    """
    # Check if file exists
    file_path = Path(markdown_path)
    if not file_path.exists():
        error_msg = f"Markdown file not found: {markdown_path}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Read markdown content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
    except Exception as e:
        error_msg = f"Failed to read markdown file: {e}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Convert markdown to XHTML
    try:
        xhtml = _markdown_to_confluence_storage_format(markdown_content)
        if ctx:
            await ctx.info(f"Successfully converted {file_path.name} to Confluence XHTML ({len(xhtml)} chars)")
        return xhtml
    except Exception as e:
        error_msg = f"Markdown conversion failed: {e}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}


def _markdown_to_confluence_storage_format(markdown: str) -> str:
    """
    Internal function to convert markdown to Confluence storage XHTML.
    Handles headings, tables, bold, italic, lists, code blocks, and chart placeholders.
    """
    lines = markdown.split('\n')
    xhtml_lines = []
    in_table = False
    in_code_block = False
    code_block_content = []
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_block_content = []
                continue
            else:
                # End code block
                in_code_block = False
                xhtml_lines.append('<ac:structured-macro ac:name="code">')
                xhtml_lines.append('<ac:plain-text-body><![CDATA[')
                xhtml_lines.append('\n'.join(code_block_content))
                xhtml_lines.append(']]></ac:plain-text-body>')
                xhtml_lines.append('</ac:structured-macro>')
                continue
        
        if in_code_block:
            code_block_content.append(line)
            continue
        
        # Handle headings
        if line.startswith('# '):
            xhtml_lines.append(f'<h1>{_escape_html(line[2:].strip())}</h1>')
            continue
        elif line.startswith('## '):
            xhtml_lines.append(f'<h2>{_escape_html(line[3:].strip())}</h2>')
            continue
        elif line.startswith('### '):
            xhtml_lines.append(f'<h3>{_escape_html(line[4:].strip())}</h3>')
            continue
        elif line.startswith('#### '):
            xhtml_lines.append(f'<h4>{_escape_html(line[5:].strip())}</h4>')
            continue
        
        # Handle tables
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                in_table = True
                xhtml_lines.append('<table>')
                xhtml_lines.append('<tbody>')
            
            # Skip separator lines (e.g., |---|---|)
            if re.match(r'^\|[\s\-:]+\|', line):
                continue
            
            # Parse table row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Skip first/last empty
            row_html = '<tr>'
            for cell in cells:
                cell_content = _apply_inline_formatting(cell)
                row_html += f'<td>{cell_content}</td>'
            row_html += '</tr>'
            xhtml_lines.append(row_html)
            continue
        else:
            if in_table:
                in_table = False
                xhtml_lines.append('</tbody>')
                xhtml_lines.append('</table>')
        
        # Handle horizontal rules
        if line.strip() == '---':
            xhtml_lines.append('<hr />')
            continue
        
        # Handle unordered lists
        if line.strip().startswith('- '):
            content = _apply_inline_formatting(line.strip()[2:])
            xhtml_lines.append(f'<ul><li>{content}</li></ul>')
            continue
        
        # Handle chart placeholders
        if '[CHART_PLACEHOLDER:' in line:
            chart_name = re.search(r'$$CHART_PLACEHOLDER:\s*([^$$]+)$$', line)
            if chart_name:
                xhtml_lines.append(f'<p><em>[Chart: {chart_name.group(1)}]</em></p>')
            continue
        
        # Handle blockquotes
        if line.strip().startswith('>'):
            content = _apply_inline_formatting(line.strip()[1:].strip())
            xhtml_lines.append(f'<blockquote><p>{content}</p></blockquote>')
            continue
        
        # Handle regular paragraphs
        if line.strip():
            content = _apply_inline_formatting(line.strip())
            xhtml_lines.append(f'<p>{content}</p>')
        else:
            # Preserve empty lines as line breaks
            xhtml_lines.append('<p></p>')
    
    # Close any open table
    if in_table:
        xhtml_lines.append('</tbody>')
        xhtml_lines.append('</table>')
    
    return '\n'.join(xhtml_lines)


def _apply_inline_formatting(text: str) -> str:
    """
    Applies inline markdown formatting (bold, italic, code, links) to text.
    """
    # Escape HTML first
    text = _escape_html(text)
    
    # Bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    
    # Italic (*text* or _text_)
    text = re.sub(r'\*([^\*]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_]+?)_', r'<em>\1</em>', text)
    
    # Inline code (`code`)
    text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
    
    # Links [text](url)
    text = re.sub(r'$$([^$$]+)$$$$([^$$]+)$$', r'<a href="\2">\1</a>', text)
    
    return text


def _escape_html(text: str) -> str:
    """
    Escapes HTML special characters to prevent injection.
    """
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

