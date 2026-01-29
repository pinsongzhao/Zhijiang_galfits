# 用于批量替换超大 HTML 文件中的图片 src 赋值为 base64 变量
import re

input_html = 'galaxy_classification_embedded.html'
output_html = 'galaxy_classification_embedded_fixed.html'

with open(input_html, 'r', encoding='utf-8') as f:
    html = f.read()

# 替换 singleImg.src 和 rgbImg.src
html = re.sub(r'singleImg\.src\s*=\s*`Images/Single_band/\$\{g.name}_grz.png`;',
              'singleImg.src = singleBandBase64[g.name];', html)
html = re.sub(r'rgbImg\.src\s*=\s*`Images/RGB/\$\{g.name}_riz.png`;',
              'rgbImg.src = rgbBase64[g.name];', html)

with open(output_html, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'已生成: {output_html}')
