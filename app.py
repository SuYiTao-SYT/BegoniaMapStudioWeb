from flask import Flask, render_template, request, jsonify
import os
import shutil
# 导入核心模块
from core import svg_processor, renderer
from core.data_manager import DataManager

app = Flask(__name__)

# 配置文件夹
UPLOAD_FOLDER = 'static/uploads'
WORKSPACE_FOLDER = 'static/data_workspace' # 数据库存放位置

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['WORKSPACE_FOLDER'] = WORKSPACE_FOLDER

# 初始化目录
for folder in [UPLOAD_FOLDER, WORKSPACE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

# 初始化数据管理器
data_mgr = DataManager(WORKSPACE_FOLDER)
# 确保工作区文件存在（即便为空）
data_mgr.init_workspace()

@app.route('/')
def index():
    return render_template('index.html')

# === 核心处理接口：上传文件并初始化 ===
@app.route('/api/process', methods=['POST'])
def process_map():
    try:
        # 1. 获取上传的文件 (如果有的话)
        # 注意：v3.0支持只上传SVG，数据复用之前工作区的
        svg_file = request.files.get('svg_file')
        csv_file = request.files.get('csv_file') # 这是旧版格式的CSV
        
        map_title = request.form.get('map_title', '选情地图')
        stroke_width = request.form.get('stroke_width', '1.0')

        # 2. 处理 SVG
        # 如果用户传了新SVG，就清洗并覆盖；没传就用旧的 cleaned.svg
        cleaned_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cleaned.svg')
        
        if svg_file:
            raw_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'raw.svg')
            svg_file.save(raw_svg_path)
            # 清洗
            success_clean, _ = svg_processor.clean_and_extract_ids(raw_svg_path, cleaned_svg_path)
            if not success_clean:
                return jsonify({'error': 'SVG清洗失败'}), 500
        elif not os.path.exists(cleaned_svg_path):
            return jsonify({'error': '请先上传 SVG 文件'}), 400

        # 3. 处理数据 (导入逻辑)
        if csv_file:
            # 如果用户传了CSV，说明要导入新数据（覆盖数据库）
            temp_csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'import_temp.csv')
            csv_file.save(temp_csv_path)
            # 调用 DataManager 拆解并导入
            success_import, msg = data_mgr.import_from_legacy_v2(temp_csv_path)
            if not success_import:
                return jsonify({'error': f'数据导入失败: {msg}'}), 500

        # 4. 获取渲染所需数据 (从数据库读取)
        # 无论是否刚上传了CSV，现在都统一从 DataManager 获取标准化数据
        district_data, party_colors, party_seats = data_mgr.get_joined_data()

        # 5. 渲染
        final_svg_path = os.path.join(app.config['UPLOAD_FOLDER'], 'final_result.svg')
        
        success_render, msg = renderer.render_map_from_data(
            cleaned_svg_path, 
            final_svg_path, 
            district_data, 
            party_colors, 
            party_seats,
            map_title, 
            stroke_width
        )

        if success_render:
            with open(final_svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            return jsonify({
                'status': 'success',
                'svg_content': svg_content, 
                'download_url': f'/static/uploads/final_result.svg'
            })
        else:
            return jsonify({'error': f'渲染失败: {msg}'}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# === 选区编辑接口 ===
@app.route('/api/district/<did>', methods=['GET'])
def get_district_api(did):
    data = data_mgr.get_district_detail(did)
    if data:
        return jsonify({'status': 'success', 'data': data})
    else:
        # 如果选区ID存在于SVG但不在数据库中（可能是新加的），返回空模板
        return jsonify({'status': 'empty', 'data': {'info': {'District_ID': did, 'Seats': 1}, 'votes': {}}})

@app.route('/api/district/update', methods=['POST'])
def update_district_api():
    try:
        req = request.json
        did = req.get('district_id')
        votes = req.get('votes') 
        
        data_mgr.update_district_votes(did, votes)
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)