from flask import Flask, render_template, request, jsonify, send_file
import os
from core import svg_processor, renderer
# 以后CSV读取逻辑也可以封装，暂时先简单写

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_svg', methods=['POST'])
def upload_svg():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
        
    # 保存原始SVG
    raw_path = os.path.join(app.config['UPLOAD_FOLDER'], 'raw.svg')
    cleaned_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cleaned.svg')
    file.save(raw_path)
    
    # 调用 Core 模块进行清洗
    success, ids = svg_processor.clean_and_extract_ids(raw_path, cleaned_path)
    
    if success:
        # 返回清洗后的SVG路径（供前端显示）和提取出的ID列表
        return jsonify({
            'status': 'success',
            'svg_url': '/static/uploads/cleaned.svg',
            'districts': ids
        })
    else:
        return jsonify({'error': 'SVG处理失败'}), 500

if __name__ == '__main__':
    app.run(debug=True)