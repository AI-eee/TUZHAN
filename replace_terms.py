import os

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content
    
    # Replace "协作中心" -> "Agent协作中心"
    content = content.replace('TUZHAN Agent协作中心', 'TUZHAN Agent协作中心')
    
    # Replace "邮件" -> "邮件"
    content = content.replace('邮件', '邮件')
    content = content.replace('发送邮件', '发送邮件')
    
    # Fix some specific weird cases if any (like "发件" to "写邮件" in dashboard)
    content = content.replace('发件</div>', '写邮件</div>')
    
    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")

for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.html') or file.endswith('.py') or file.endswith('.md'):
            replace_in_file(os.path.join(root, file))
