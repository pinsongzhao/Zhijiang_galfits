
import os
import re
import base64
from io import BytesIO
try:
    from PIL import Image
except ImportError:
    raise ImportError('请先运行 pip install pillow')

# 输入和输出文件名
template_html = 'galaxy_classification.html'
output_html = 'galaxy_classification_embedded.html'

# 读取原始 HTML
with open(template_html, 'r', encoding='utf-8') as f:
    html = f.read()


# 1. 收集所有 galaxy.name
import json
import re
galaxy_names = set()
for m in re.finditer(r'\{\s*name:\s*"([A-Za-z0-9\-\+]+)"', html):
    galaxy_names.add(m.group(1))

# 2. 构建 base64 映射
sb_map = {}  # Single_band
rgb_map = {} # RGB
for name in galaxy_names:
    sb_path = f'Images/Single/{name}_grz.png'
    rgb_path = f'Images/RGB/{name}_grz.jpg'
    # Single: 保留原始清晰度（不缩放不压缩，仅如有必要才转为JPEG）
    abs_path = os.path.join(os.path.dirname(template_html), sb_path)
    if os.path.exists(abs_path):
        try:
            img = Image.open(abs_path)
            img = img.convert('RGB')
            buf = BytesIO()
            ext = os.path.splitext(sb_path)[1].lower()
            if ext == '.jpg' or ext == '.jpeg':
                img.save(buf, format='JPEG', quality=100, optimize=True)
                mime = 'image/jpeg'
            elif ext == '.png':
                img.save(buf, format='PNG', optimize=True)
                mime = 'image/png'
            else:
                img.save(buf, format='JPEG', quality=100, optimize=True)
                mime = 'image/jpeg'
            img_bytes = buf.getvalue()
        except Exception as e:
            print(f'压缩图片失败 {sb_path}: {e}, 使用原图')
            with open(abs_path, 'rb') as imgf:
                img_bytes = imgf.read()
            ext = os.path.splitext(sb_path)[1].lower()
            if ext == '.jpg' or ext == '.jpeg':
                mime = 'image/jpeg'
            elif ext == '.png':
                mime = 'image/png'
            elif ext == '.gif':
                mime = 'image/gif'
            else:
                mime = 'application/octet-stream'
        except Exception as e:
            print(f'压缩图片失败 {sb_path}: {e}, 使用原图')
            with open(abs_path, 'rb') as imgf:
                img_bytes = imgf.read()
            ext = os.path.splitext(sb_path)[1].lower()
            if ext == '.jpg' or ext == '.jpeg':
                mime = 'image/jpeg'
            elif ext == '.png':
                mime = 'image/png'
            elif ext == '.gif':
                mime = 'image/gif'
            else:
                mime = 'application/octet-stream'
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        sb_map[name] = f'data:{mime};base64,{b64}'
    else:
        print(f'Warning: {sb_path} not found, skip.')

    # RGB: 压缩
    abs_path = os.path.join(os.path.dirname(template_html), rgb_path)
    if os.path.exists(abs_path):
        try:
            img = Image.open(abs_path)
            img = img.convert('RGB')
            max_size = 400
            w, h = img.size
            scale = min(max_size / w, max_size / h, 1.0)
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=70, optimize=True)
            img_bytes = buf.getvalue()
            mime = 'image/jpeg'
        except Exception as e:
            print(f'压缩图片失败 {rgb_path}: {e}, 使用原图')
            with open(abs_path, 'rb') as imgf:
                img_bytes = imgf.read()
            ext = os.path.splitext(rgb_path)[1].lower()
            if ext == '.jpg' or ext == '.jpeg':
                mime = 'image/jpeg'
            elif ext == '.png':
                mime = 'image/png'
            elif ext == '.gif':
                mime = 'image/gif'
            else:
                mime = 'application/octet-stream'
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        rgb_map[name] = f'data:{mime};base64,{b64}'
    else:
        print(f'Warning: {rgb_path} not found, skip.')

# 3. 注入 JS 变量到 HTML <script> 前


# 直接在 </head> 前插入 base64 变量
inject = f"""
<script>
// base64 image maps injected by embed_images_to_html.py
const singleBandBase64 = {json.dumps(sb_map, ensure_ascii=False)};
const rgbBase64 = {json.dumps(rgb_map, ensure_ascii=False)};
</script>
"""
html = re.sub(r'</head>', inject + '\n</head>', html, count=1)

# 4. 替换 JS 赋值图片 src 的代码
html = re.sub(r"document.getElementById\('single-band-img'\)\.src = `\./Images/Single_band/\$\{galaxy.name}_grz.png`;",
              "document.getElementById('single-band-img').src = singleBandBase64[galaxy.name];",
              html)
html = re.sub(r"document.getElementById\('rgb-img'\)\.src = `\./Images/RGB/\$\{galaxy.name}_riz.png`;",
              "document.getElementById('rgb-img').src = rgbBase64[galaxy.name];",
              html)

# 5. 保存新 HTML
with open(output_html, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'生成完成: {output_html} (所有图片已嵌入，JS 赋值已改为 base64)')
