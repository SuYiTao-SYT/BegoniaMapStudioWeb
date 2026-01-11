from flask import Flask, render_template, request, jsonify
import os
import shutil
# 导入核心模块
from core import svg_processor, renderer

app = Flask(__name__)

# 配置上传文件夹
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保目录存在
if os.path.exists(UPLOAD_FOLDER):
    shutil.rmtree(UPLOAD_FOLDER) # 每次重启清空临时文件
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_map():
    try:
        # 1. 获取上传的文件
        svg_file = request.files.get('svg_file')
        csv_file = request.files.get('csv_file')
        
        # 2. 获取参数
        map_title = request.form.get('map_title', '选情地图')
        stroke_width = request.form.get('stroke_width', '1.0')

        if not svg_file or not csv_file:
            return jsonify({'error': '请上传 SVG 和 CSV 文件'}), 400

        # 3. 保存临时文件
        raw_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_raw.svg')
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_data.csv')
        cleaned_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_cleaned.svg')
        final_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'final_result.svg')
        
        svg_file.save(raw_svg_path)
        csv_file.save(csv_path)

        # 4. 调用 Core 模块：清洗
        # 注意：这里我们简化流程，直接在渲染前清洗
        success_clean, _ = svg_processor.clean_and_extract_ids(raw_svg_path, cleaned_svg_path)
        if not success_clean:
            return jsonify({'error': 'SVG清洗失败'}), 500

        # 5. 调用 Core 模块：渲染
        # 我们需要在 renderer.py 里加一个读取 CSV 的逻辑，或者像之前一样处理
        # 这里为了复用 renderer.py 的 render_map_to_file，我们直接调用它
        
        # 注意：你需要确保 renderer.render_map_to_file 已经像上一步那样去掉了 self 并可以独立运行
        success_render, msg = renderer.render_map_to_file(
            cleaned_svg_path, 
            csv_path, 
            final_svg_path, 
            map_title, 
            stroke_width
        )

        if success_render:
            # 读取生成的 SVG 内容返回给前端 (以便直接嵌入 HTML 实现交互)
            with open(final_svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            return jsonify({
                'status': 'success',
                'svg_content': svg_content, # 直接返回代码用于交互
                'download_url': f'/{final_svg_path}' # 用于下载
            })
        else:
            return jsonify({'error': f'渲染失败: {msg}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)